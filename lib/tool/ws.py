from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

from mando.core import Program

import os
import sys

from .. import config
from .. import tech

from ..pkg.workspace import Workspace
from ..pkg import archive
from ..pkg import layouts
from ..pkg import metakey

from .. import VERSION

main = Program('ws', VERSION)
arg = main.arg
command = main.command

Path = tech.fs.Path
timestamp = tech.timestamp.timestamp
uuid_translator = tech.uuid_translator.uuid_translator

ERROR_EXIT = 1

FIXME_PERSONAL_UUID = 'FIXME: personal-uuid'


def die(msg):
    sys.stderr.write('ERROR: ')
    sys.stderr.write(msg)
    sys.stderr.write('\n')
    sys.exit(ERROR_EXIT)


def assert_valid_workspace(workspace):
    if not workspace.is_valid:
        die('{} is not a valid workspace'.format(workspace.directory))


def assert_may_be_valid_name(name):
    valid_syntax = (
        name
        and os.path.sep not in name
        and '/' not in name
        and '\\' not in name
        and ':' not in name
    )
    if not valid_syntax:
        die('Invalid name "{}"'.format(name))

    packages_db_file_name = config.get_path(config.PACKAGES_DB_FILE_NAME)
    with uuid_translator(packages_db_file_name) as t:
        if t.has_name(scope=FIXME_PERSONAL_UUID, name=name):
            die('"{}" is already used, rename it if you insist'.format(name))


@command
def new(name):
    '''
    Create new package directory layout.
    '''
    config.ensure_config_dir()
    assert_may_be_valid_name(name)

    package_uuid = tech.identifier.uuid()
    packages_db_file_name = config.get_path(config.PACKAGES_DB_FILE_NAME)
    ws = Workspace(name)
    ws.create(package_uuid)
    with uuid_translator(packages_db_file_name) as t:
        t.add(scope=FIXME_PERSONAL_UUID, name=name, uuid=package_uuid)

    print('Created {}'.format(name))


@command
def develop(name, package_file_name, mount=False):
    '''
    Unpack a package as a source tree.

    Package directory layout is created, but only the source files are
    extracted.
    '''
    dir = Path(name)
    workspace = Workspace(dir)

    with archive.Archive(package_file_name) as pkg:
        pkg.extract_dir(layouts.Archive.CODE, dir)
        workspace.create_directories()

        # extracted PKGMETA needs a rewrite
        # as it contains different things in the development and archive format
        archive_meta = pkg.meta
        development_meta = {
            metakey.PACKAGE: archive_meta[metakey.PACKAGE],
            metakey.INPUTS: {
                input_nick: {
                    metakey.INPUT_MOUNTED: False,
                    metakey.INPUT_PACKAGE: spec[metakey.INPUT_PACKAGE],
                    metakey.INPUT_VERSION: spec[metakey.INPUT_VERSION],
                }
                for input_nick, spec in archive_meta[metakey.INPUTS].items()
            },
        }
        workspace.meta = development_meta
        # this flat repo can be used to mount packages for demo purposes
        # that is, until we have a proper repo
        workspace.flat_repo = os.path.abspath(
            os.path.dirname(package_file_name)
        )

    assert workspace.is_valid

    if mount:
        mount_all(workspace)

    print('Extracted source into {}'.format(dir))
    print_mounts(directory=dir)


@command
def pack():
    '''Create a new archive from the workspace'''
    workspace = Workspace()
    ts = timestamp()
    zipfilename = (
        Path('.') / layouts.Workspace.TEMP / (
            '{package}_{timestamp}.zip'
            .format(
                package=workspace.package_name,
                timestamp=ts,
            )
        )
    )
    workspace.pack(zipfilename, timestamp=ts)

    print('Package created at {}'.format(zipfilename))


def find_package(repo_dir, package_uuid, package_version):
    for name in os.listdir(repo_dir):
        candidate = repo_dir / name
        try:
            package = archive.Archive(candidate)
            if package.uuid == package_uuid:
                if package.version == package_version:
                    return candidate
        except:
            pass


def mount_input_nick(workspace, input_nick):
    assert workspace.has_input(input_nick)
    if not workspace.is_mounted(input_nick):
        spec = workspace.inputspecs[input_nick]
        package_file_name = find_package(
            Path(workspace.flat_repo),
            spec[metakey.INPUT_PACKAGE],
            spec[metakey.INPUT_VERSION],
        )
        if package_file_name is None:
            print(
                'Could not find archive for {} - not mounted!'
                .format(input_nick)
            )
            return
        workspace.mount(input_nick, archive.Archive(package_file_name))
        print('Mounted {}.'.format(input_nick))


@command('mount-all')
def mount_all(workspace):
    for input_nick in workspace.inputs:
        mount_input_nick(workspace, input_nick)


def mount_archive(workspace, input_nick, package_file_name):
    assert not workspace.has_input(input_nick)
    workspace.mount(input_nick, archive.Archive(package_file_name))
    print('{} mounted on {}.'.format(package_file_name, input_nick))


@command
@arg(
    'package', nargs='?', metavar='PACKAGE',
    help='package to mount data from'
)
@arg(
    'input_nick', metavar='NAME',
    help='data will be mounted under "input/%(metavar)s"'
)
def mount(package, input_nick):
    '''
    Add data from another package to the input directory.
    '''
    workspace = Workspace()
    if package is None:
        mount_input_nick(workspace, input_nick)
    else:
        package_file_name = package
        mount_archive(workspace, input_nick, package_file_name)


def print_mounts(directory):
    workspace = Workspace(directory)
    assert_valid_workspace(workspace)
    inputs = workspace.inputs
    if not inputs:
        print('Package has no defined inputs, yet')
    else:
        print('Package inputs:')
        MOUNTED = 'mounted'
        NOT_MOUNTED = 'not mounted'
        for input_nick in sorted(inputs):
            print(
                '  {}: {}'
                .format(
                    input_nick,
                    MOUNTED
                    if workspace.is_mounted(input_nick)
                    else NOT_MOUNTED
                )
            )


@command('mounts')
def mounts():
    '''Show mount names and their status'''
    print_mounts('.')


@command('delete-input')
def delete_input(input_nick):
    '''Forget input'''
    Workspace().delete_input(input_nick)
    print('Input {} is deleted.'.format(input_nick))


@command
@arg('package_file_name', nargs='?')
def update(input_nick, package_file_name):
    '''TODO: replace input with a newer version
    '''
    pass


@command
@arg(
    'directory', nargs='?', default='.',
    help='workspace directory (default: %(default)s)'
)
def nuke(directory):
    '''Delete the workspace, inluding data, code and documentation'''
    workspace = Workspace(directory)
    assert_valid_workspace(workspace)
    tech.fs.rmtree(os.path.abspath(directory))
