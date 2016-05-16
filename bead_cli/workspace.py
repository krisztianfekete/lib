from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

import os

from bead import tech
from bead.workspace import Workspace, CurrentDirWorkspace
from bead import layouts

from .cmdparse import Command
from .common import die, warning
from .common import DefaultArgSentinel
from .common import OPTIONAL_WORKSPACE, OPTIONAL_ENV
from .common import bead_spec_kwargs, get_bead_ref
from . import arg_metavar
from . import arg_help


timestamp = tech.timestamp.timestamp
time_from_timestamp = tech.timestamp.time_from_timestamp


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


class CmdNew(Command):
    '''
    Create and initialize new workspace directory with a new bead.
    '''

    def declare(self, arg):
        arg('workspace', type=Workspace, metavar=arg_metavar.WORKSPACE,
            help='bead and directory to create')

    def run(self, args):
        workspace = args.workspace
        assert_may_be_valid_name(workspace.bead_name)
        # FIXME: die with message when directory already exists

        bead_uuid = tech.identifier.uuid()
        workspace.create(bead_uuid)
        print('Created {}'.format(workspace.bead_name))


CURRENT_DIRECTORY = CurrentDirWorkspace()


def workspace_defaulting_to(default_workspace):
    def opt_workspace(parser):
        parser.arg(
            'workspace', nargs='?', type=Workspace,
            default=default_workspace,
            metavar=arg_metavar.WORKSPACE, help=arg_help.WORKSPACE)
    return opt_workspace


USE_THE_ONLY_REPO = DefaultArgSentinel(
    'if there is exactly one repository,' +
    ' store there, otherwise it MUST be specified')


class CmdSave(Command):
    '''
    Save workspace in a repository.
    '''

    def declare(self, arg):
        arg('repo_name', nargs='?', default=USE_THE_ONLY_REPO, type=str,
            metavar='REPOSITORY', help='Name of repository to store bead')
        arg(OPTIONAL_WORKSPACE)
        arg(OPTIONAL_ENV)

    def run(self, args):
        repo_name = args.repo_name
        workspace = args.workspace
        env = args.get_env()
        assert_valid_workspace(workspace)
        if repo_name is USE_THE_ONLY_REPO:
            repositories = list(env.get_repos())
            if not repositories:
                die('No repositories defined, please define one!')
            if len(repositories) > 1:
                die(
                    'REPOSITORY parameter is not optional!\n' +
                    '(more than one repositories exists)')
            repo = repositories[0]
        else:
            repo = env.get_repo(repo_name)
            if repo is None:
                die('Unknown repository: {}'.format(repo_name))
        repo.store(workspace, timestamp())
        print('Successfully stored bead.')


DERIVE_FROM_BEAD_NAME = DefaultArgSentinel('derive one from bead name')


class CmdDevelop(Command):
    '''
    Unpack a bead as a source tree.

    Bead directory layout is created, but only the source files are
    extracted by default.
    '''

    def declare(self, arg):
        arg('bead_name', metavar='bead-name')
        arg(bead_spec_kwargs)
        # TODO: delete arg_metavar.BEAD_REF
        arg(workspace_defaulting_to(DERIVE_FROM_BEAD_NAME))
        arg('-x', '--extract-output', dest='extract_output',
            default=False, action='store_true',
            help='Extract output data as well (normally it is not needed!).')
        arg(OPTIONAL_ENV)

    def run(self, args):
        extract_output = args.extract_output
        env = args.get_env()
        bead_ref = get_bead_ref(env, args.bead_name, args.bead_query)
        try:
            bead = bead_ref.bead
        except LookupError:
            die('Bead not found!')
        if not bead.is_valid:
            die('Bead is found but damaged')
        if args.workspace is DERIVE_FROM_BEAD_NAME:
            workspace = bead_ref.default_workspace
        else:
            workspace = args.workspace

        bead.unpack_to(workspace)
        assert workspace.is_valid

        if extract_output:
            output_directory = workspace.directory / layouts.Workspace.OUTPUT
            bead.unpack_data_to(output_directory)

        print('Extracted source into {}'.format(workspace.directory))
        # XXX: try to load smaller inputs?
        if workspace.inputs:
            print('Input data not loaded, update if needed and load manually')


def assert_valid_workspace(workspace):
    if not workspace.is_valid:
        die('{} is not a valid workspace'.format(workspace.directory))


def print_inputs(env, workspace, verbose):
    assert_valid_workspace(workspace)
    inputs = sorted(workspace.inputs)

    if inputs:
        repositories = env.get_repos()

        print('Inputs:')
        for input in inputs:
            print('input/' + input.name)
            print('\tName[s]:')
            has_name = False
            for repo in repositories:
                timestamp = time_from_timestamp(input.timestamp)
                (
                    exact_match, best_guess, best_guess_timestamp, names
                ) = repo.find_names(input.bead_uuid, input.content_hash, timestamp)
                #
                has_name = has_name or exact_match or best_guess or names
                if exact_match:
                    print('\t * -r {} {}'.format(repo.name, exact_match))
                    names.remove(exact_match)
                elif best_guess:
                    print('\t ? -r {} {}'.format(repo.name, best_guess))
                    names.remove(best_guess)
                for name in sorted(names):
                    print('\t [-r {} {}]'.format(repo.name, name))
            if verbose or not has_name:
                print('\tBead UUID:', input.bead_uuid)
                print('\tContent hash:', input.content_hash)
                print('\tFreeze time:', input.timestamp)

        print('')
        unloaded = [
            input.name
            for input in inputs
            if not workspace.is_loaded(input.name)]
        if unloaded:
            print('These inputs are not loaded:')
            unloaded_list = '\t- ' + '\n\t- '.join(unloaded)
            print(unloaded_list.expandtabs(2))
            print('You can "load" or "update" them manually.')
    else:
        print('No inputs defined')


class CmdStatus(Command):
    '''
    Show workspace status - name of bead, inputs and their unpack status.
    '''

    def declare(self, arg):
        arg(OPTIONAL_WORKSPACE)
        arg('-v', '--verbose', default=False, action='store_true',
            help='show more detailed information')
        arg(OPTIONAL_ENV)

    def run(self, args):
        workspace = args.workspace
        verbose = args.verbose
        env = args.get_env()
        # TODO: use a template and render it with passing in all data
        uuid_needed = verbose
        if workspace.is_valid:
            print('Bead Name: {}'.format(workspace.bead_name))
            if uuid_needed:
                print('Bead UUID: {}'.format(workspace.bead_uuid))
            print()
            print_inputs(env, workspace, verbose)
        else:
            warning('Invalid workspace ({})'.format(workspace.directory))


class CmdNuke(Command):
    '''
    Delete the workspace, inluding data, code and documentation.
    '''

    def declare(self, arg):
        arg(workspace_defaulting_to(CURRENT_DIRECTORY))

    def run(self, args):
        workspace = args.workspace
        assert_valid_workspace(workspace)
        directory = workspace.directory
        tech.fs.rmtree(directory)
        print('Deleted workspace {}'.format(directory))