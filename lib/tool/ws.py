from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

import appdirs
from argh import ArghParser
from argh.decorators import arg, named

import os
import sys

from .. import tech

from ..pkg.workspace import Workspace
from ..pkg.archive import Archive
from ..pkg import layouts
from ..pkg import metakey
from .. import db

from .. import PACKAGE, VERSION
from ..translations import Peer, add_translation


Path = tech.fs.Path
timestamp = tech.timestamp.timestamp

ERROR_EXIT = 1


def opt_workspace(func):
    '''
    define `workspace` as option, defaulting to current directory
    '''
    decorate = arg(
        '--workspace', dest='workspace_directory', metavar='DIRECTORY',
        default='.',
        help='workspace directory')
    return decorate(func)


def arg_workspace(func):
    '''
    define `workspace` argument, defaulting to current directory
    '''
    decorate = arg(
        'workspace_directory', nargs='?', metavar='WORKSPACE',
        default='.',
        help='workspace directory')
    return decorate(func)


def arg_new_workspace(func):
    '''
    define mandatory `workspace` argument (without default)
    '''
    decorate = arg(
        'workspace', type=Workspace,
        help='workspace directory')
    return decorate(func)


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

    if Peer.self().knows_about(name):
        die('"{}" is already used, rename it if you insist'.format(name))


# @command
@arg_new_workspace
def new(workspace):
    '''
    Create new package directory layout.
    '''
    uuid = tech.identifier.uuid()

    assert_may_be_valid_name(workspace.package_name)
    add_translation(workspace.package_name, uuid)

    workspace.create(uuid)
    print('Created {}'.format(workspace.package_name))


class Repository(object):

    def find_package(self, uuid, version=None):
        # -> [Package]
        pass

    def find_newest(self, uuid):
        # -> Package
        pass

    def store(self, workspace, timestamp):
        # -> Package
        pass


class UserManagedDirectory(Repository):

    # TODO: user maintained directory hierarchy

    def __init__(self, directory):
        self.directory = Path(directory)

    def find_package(self, uuid, version=None):
        # -> [Package]
        for name in os.listdir(self.directory):
            candidate = self.directory / name
            try:
                package = Archive(candidate)
                if package.uuid == uuid:
                    if version in (None, package.version):
                        return package
            except:
                pass


# @command
@arg_new_workspace
def develop(workspace, package_file_name, mount=False):
    '''
    Unpack a package as a source tree.

    Package directory layout is created, but only the source files are
    extracted.
    '''
    # TODO: #10 names for packages
    dir = workspace.directory

    package = Archive(package_file_name)
    package.unpack_to(workspace)

    # FIXME: flat repo can be used to mount packages for demo purposes
    # that is, until we have a proper repo
    workspace.flat_repo = os.path.abspath(
        os.path.dirname(package_file_name)
    )

    assert workspace.is_valid

    if mount:
        mount_all(workspace)

    print('Extracted source into {}'.format(dir))
    print_mounts(directory=dir)


# @command
@opt_workspace
def pack(workspace_directory='.'):
    '''Create a new archive from the workspace'''
    # TODO: #9 personal config: directory to store newly created packages in
    # repo = get_store_repo()
    # repo.store_workspace(Workspace(), timestamp())
    workspace = Workspace(workspace_directory)
    ts = timestamp()
    zipfilename = (
        workspace.directory / layouts.Workspace.TEMP / (
            '{package}_{timestamp}.zip'
            .format(
                package=workspace.package_name,
                timestamp=ts,
            )
        )
    )
    workspace.pack(zipfilename, timestamp=ts)

    print('Package created at {}'.format(zipfilename))


def mount_input_nick(workspace, input_nick):
    assert workspace.has_input(input_nick)
    if not workspace.is_mounted(input_nick):
        spec = workspace.inputspecs[input_nick]
        # TODO: #14 personal config: list of local directories having packages
        flat_repo = UserManagedDirectory(workspace.flat_repo)
        package = flat_repo.find_package(
            spec[metakey.INPUT_PACKAGE],
            spec[metakey.INPUT_VERSION],
        )
        if package is None:
            print(
                'Could not find archive for {} - not mounted!'
                .format(input_nick)
            )
            return
        workspace.mount(input_nick, package)
        print('Mounted {}.'.format(input_nick))


# @command('mount-all')
@named('mount-all')
def mount_all(workspace):
    for input_nick in workspace.inputs:
        mount_input_nick(workspace, input_nick)


def mount_archive(workspace, input_nick, package_file_name):
    assert not workspace.has_input(input_nick)
    workspace.mount(input_nick, Archive(package_file_name))
    print('{} mounted on {}.'.format(package_file_name, input_nick))


# @command
@arg(
    'package', nargs='?', metavar='PACKAGE',
    help='package to mount data from'
)
@arg(
    'input_nick', metavar='NAME',
    help='data will be mounted under "input/%(metavar)s"'
)
@opt_workspace
def mount(package, input_nick, workspace_directory='.'):
    '''
    Add data from another package to the input directory.
    '''
    workspace = Workspace(workspace_directory)
    # TODO: #10 names for packages
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
        msg_mounted = 'mounted'
        msg_not_mounted = 'not mounted'
        for input_nick in sorted(inputs):
            print(
                '  {}: {}'
                .format(
                    input_nick,
                    msg_mounted
                    if workspace.is_mounted(input_nick)
                    else msg_not_mounted
                )
            )


# @command
def status():
    '''Show workspace status - name of package, mount names and their status'''
    # TODO: print Package UUID
    print_mounts('.')


# @command('delete-input')
@named('delete-input')
@opt_workspace
def delete_input(input_nick, workspace_directory='.'):
    '''Forget input'''
    workspace = Workspace(workspace_directory)
    workspace.delete_input(input_nick)
    print('Input {} is deleted.'.format(input_nick))


# @command
@arg('package_file_name', nargs='?')
def update(input_nick, package_file_name):
    '''Replace input with a newer version or different package.
    '''
    # TODO: #16 implement update command
    pass


# @command
@arg_workspace
def nuke(workspace_directory):
    '''Delete the workspace, inluding data, code and documentation'''
    workspace = Workspace(workspace_directory)
    assert_valid_workspace(workspace)
    tech.fs.rmtree(workspace.directory)


# TODO: rename commands
# input add <name> (<package>|<file>)
# input load <name>
# input load --all
# input delete <name>

# TODO: names/translations management commands
# - import peer filename
# - rename-peer old-name new-name
# - delete-peer name
#
# - export [--peer name] filename
# - rename-package old-name new-name
# - delete-package package-name
# - lift peer:name [local-name]
#
# TODO: parse package-name
# format: [[peer]:]name[@version]
# already implemented:
# https://gist.github.com/krisztianfekete/25f972c70d1cdbd19b9d#file-new-py

# TODO: repository management
# - list-repos
# - add-repo repo
# - delete-repo repo-ref
# - set-output-repo repo-ref
# where repo-ref is either an id or its path


def initialize_env(config_dir):
    try:
        os.makedirs(config_dir)
    except OSError:
        assert os.path.isdir(config_dir)
    db_path = os.path.join(config_dir, 'config.sqlite')
    db.connect(db_path)


def make_argument_parser():
    parser = ArghParser(prog=__name__)
    parser.add_argument('--version', action='version', version=VERSION)
    parser.add_commands(
        [
            new,
            develop,
            pack,
            mount_all,
            mount,
            status,
            delete_input,
            update,
            nuke
        ])
    return parser


def cli(config_dir, argv):
    initialize_env(config_dir)
    parser = make_argument_parser()
    parser.dispatch(argv)
    # TODO verify exit status


def main():
    config_dir = appdirs.user_config_dir(
        PACKAGE + '-6a4d9d98-8e64-4a2a-b6c2-8a753ea61daf')
    cli(config_dir, sys.argv[1:])


if __name__ == '__main__':
    main()
