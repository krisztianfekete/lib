from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

from .test import TestCase, TempDir, CaptureStdout, CaptureStderr
# from ..test import xfail
from testtools.content import text_content
from testtools.matchers import FileContains, Not, Contains, FileExists

import os
from .pkg.workspace import Workspace
from . import commands
from . import db
from . import pkg
from . import tech
from .tech.timestamp import timestamp
from .translations import add_translation, Peer
from .test_fixture_robot import Robot
from . import repos


class Test_new(TestCase):  # noqa

    def test_first_workspace(self):
        self.given_an_empty_uuid_name_map()
        self.when_new_is_called_with_nonexisting_name()
        self.then_uuid_map_is_created_with_the_uuid_name_stored_in_it()

    def test_new_package_name(self):
        self.given_a_non_empty_uuid_name_map()
        self.when_new_is_called_with_nonexisting_name()
        self.then_workspace_is_created()

    def test_existing_package_name(self):
        self.given_a_non_empty_uuid_name_map()
        self.when_new_is_called_with_already_existing_name()
        self.then_error_is_raised()

    def test_created_workspace_has_same_uuid_as_registered_for_name(self):
        self.given_a_non_empty_uuid_name_map()
        self.when_new_is_called_with_nonexisting_name()
        self.then_workspace_uuid_is_the_uuid_registered_for_name()

    # implementation

    __stderr = None
    __error_raised = False
    home = None
    current_dir = None

    def setUp(self):  # noqa
        super(Test_new, self).setUp()
        # protect user's home directory
        self.home = self.new_temp_home_dir()
        # protect current directory
        self.current_dir = self.new_temp_dir()
        orig_wd = os.getcwd()
        os.chdir(self.current_dir)
        self.addCleanup(os.chdir, orig_wd)

    def given_an_empty_uuid_name_map(self):
        db.connect(db.MEMORY)

    def given_a_non_empty_uuid_name_map(self):
        self.given_an_empty_uuid_name_map()
        add_translation('existing', 'test-uuid')
        self.assertTrue(Peer.self().knows_about('existing'))

    def when_new_is_called_with_nonexisting_name(self):
        with CaptureStdout():
            commands.workspace.new(Workspace('new'))

    def when_new_is_called_with_already_existing_name(self):
        self.assertTrue(Peer.self().knows_about('existing'))
        with CaptureStderr() as stderr:
            try:
                commands.workspace.new(Workspace('existing'))
            except SystemExit:
                self.__error_raised = True
            finally:
                self.__stderr = stderr.text

    def then_error_is_raised(self):
        self.assertTrue(self.__error_raised)
        self.assertIn('ERROR: ', self.__stderr)

    def then_workspace_is_created(self):
        self.assertTrue(Workspace('new').is_valid)

    def then_uuid_map_is_created_with_the_uuid_name_stored_in_it(self):
        self.assertTrue(Peer.self().knows_about('new'))

    def then_workspace_uuid_is_the_uuid_registered_for_name(self):
        self.assertEqual(
            Workspace('new').meta[pkg.meta.PACKAGE],
            Peer.self().get_translation('new').package_uuid)


class Test_basic_command_line(TestCase):

    # fixtures
    def robot(self):
        return self.useFixture(Robot())

    def cli(self, robot):
        return robot.cli

    def cd(self, robot):
        return robot.cd

    def ls(self, robot):
        return robot.ls

    def repo_dir(self):
        return self.new_temp_dir()

    # tests
    def test(self, robot, cli, cd, ls, repo_dir):
        self.addDetail('home', text_content(robot.home))

        cli('new', 'something')
        self.assertIn('something', robot.stdout)

        cd('something')
        cli('status')
        self.assertNotIn('Inputs', robot.stdout)

        cli('repo', 'add', 'default', repo_dir)
        cli('pack')

        cd('..')
        cli('develop', 'something', 'something-develop')
        self.assertIn(robot.cwd / 'something-develop', ls())

        cd('something-develop')
        cli('input', 'add', 'older-self', 'something')
        cli('status')
        self.assertIn('Inputs', robot.stdout)
        self.assertIn('older-self', robot.stdout)

        cli('nuke', robot.cwd.parent / 'something')
        cli('nuke')

        cd('..')
        self.assertEqual([], ls(robot.home))


class Test_shared_repo(TestCase):

    # fixtures
    def repo(self):
        return self.new_temp_dir()

    def timestamp(self):
        return timestamp()

    def package(self, timestamp):
        tmp = self.new_temp_dir()
        ws = Workspace(tmp / 'ws')
        ws.create('pkg-uuid')
        package_archive = tmp / 'package.zip'
        ws.pack(package_archive, timestamp)
        return package_archive

    def alice(self, repo):
        robot = self.useFixture(Robot())
        robot.cli('repo', 'add', 'bobrepo', repo)
        return robot

    def bob(self, repo):
        robot = self.useFixture(Robot())
        robot.cli('repo', 'add', 'alicerepo', repo)
        return robot

    # tests
    def test_update(self, alice, bob, package):
        bob.cli('new', 'bobpkg')
        bob.cd('bobpkg')
        bob.cli('input', 'add', 'alicepkg1', package)
        bob.cli('input', 'add', 'alicepkg2', package)

        alice.cli('develop', package, 'alicepkg')
        alice.cd('alicepkg')
        alice.write_file('output/datafile', '''Alice's new data''')
        alice.cli('pack')

        # update only one input
        bob.cli('input', 'update', 'alicepkg1')

        self.assertThat(
            bob.cwd / 'input/alicepkg1/datafile',
            FileContains('''Alice's new data'''))

        # second input directory not changed
        self.assertThat(
            bob.cwd / 'input/alicepkg2/datafile',
            Not(FileExists()))

        # update all inputs
        bob.cli('input', 'update')

        self.assertThat(
            bob.cwd / 'input/alicepkg2/datafile',
            FileContains('''Alice's new data'''))


class Test_repo_commands(TestCase):

    # fixtures
    def robot(self):
        return self.useFixture(Robot())

    def dir1(self, robot):
        os.makedirs(robot.cwd / 'dir1')
        return 'dir1'

    def dir2(self, robot):
        os.makedirs(robot.cwd / 'dir2')
        return 'dir2'

    # tests
    def test_list_when_there_are_no_repos(self, robot):
        robot.cli('repo', 'list')
        self.assertThat(
            robot.stdout, Contains('There are no defined repositories'))

    def test_add_non_existing_directory_fails(self, robot):
        robot.cli('repo', 'add', 'notadded', 'non-existing')
        self.assertThat(robot.stdout, Contains('ERROR'))
        self.assertThat(robot.stdout, Not(Contains('notadded')))

    def test_add_multiple(self, robot, dir1, dir2):
        robot.cli('repo', 'add', 'name1', 'dir1')
        robot.cli('repo', 'add', 'name2', 'dir2')
        self.assertThat(robot.stdout, Not(Contains('ERROR')))

        robot.cli('repo', 'list')
        self.assertThat(robot.stdout, Contains('name1'))
        self.assertThat(robot.stdout, Contains('name2'))
        self.assertThat(robot.stdout, Contains('dir1'))
        self.assertThat(robot.stdout, Contains('dir2'))

    def test_add_with_same_name_fails(self, robot, dir1, dir2):
        robot.cli('repo', 'add', 'name', 'dir1')
        self.assertThat(robot.stdout, Not(Contains('ERROR')))

        robot.cli('repo', 'add', 'name', 'dir2')
        self.assertThat(robot.stdout, Contains('ERROR'))

    def test_add_same_directory_twice_fails(self, robot, dir1):
        robot.cli('repo', 'add', 'name1', dir1)
        self.assertThat(robot.stdout, Not(Contains('ERROR')))

        robot.cli('repo', 'add', 'name2', dir1)
        self.assertThat(robot.stdout, Contains('ERROR'))

    def test_forget_repo(self, robot, dir1, dir2):
        robot.cli('repo', 'add', 'repo-to-delete', dir1)
        robot.cli('repo', 'add', 'another-repo', dir2)

        robot.cli('repo', 'forget', 'repo-to-delete')
        self.assertThat(robot.stdout, Contains('forgotten'))

        robot.cli('repo', 'list')
        self.assertThat(robot.stdout, Not(Contains('repo-to-delete')))
        self.assertThat(robot.stdout, Contains('another-repo'))

    def test_forget_nonexisting_repo(self, robot):
        robot.cli('repo', 'forget', 'non-existing')
        self.assertThat(robot.stdout, Contains('WARNING'))


# timestamps
TS1 = '20150901_151015_1'
TS2 = '20150901_151016_2'


class PackageFixtures(object):

    # fixtures
    def robot(self):
        '''
        I am a robot user with a repo
        '''
        robot = self.useFixture(Robot())
        repo_dir = robot.cwd / 'repo'
        os.makedirs(repo_dir)
        robot.cli('repo', 'add', 'repo', repo_dir)
        return robot

    def repo(self, robot):
        with robot.environment:
            return repos.get('repo')

    def packages(self):
        return {}

    def _new_package(self, robot, packages, package_name, inputs=None):
        robot.cli('new', package_name)
        robot.cd(package_name)
        robot.write_file('README', package_name)
        robot.write_file('output/README', package_name)
        self._add_inputs(robot, inputs)
        repo = self.repo(robot)
        with robot.environment:
            packages[package_name] = repo.store(Workspace('.'), TS1)
        robot.cd('..')
        robot.cli('nuke', package_name)
        return package_name

    def _add_inputs(self, robot, inputs):
        inputs = inputs or {}
        for name in inputs:
            robot.cli('input', 'add', name, inputs[name])

    def pkg_a(self, robot, packages):
        return self._new_package(robot, packages, 'pkg_a')

    def pkg_b(self, robot, packages):
        return self._new_package(robot, packages, 'pkg_b')

    def _pkg_with_history(self, robot, repo, package_name, uuid):
        def make_package(timestamp):
            with TempDir() as tempdir_obj:
                workspace_dir = os.path.join(tempdir_obj.path, package_name)
                ws = Workspace(workspace_dir)
                ws.create(uuid)
                sentinel_file = ws.directory / 'sentinel-{}'.format(timestamp)
                tech.fs.write_file(sentinel_file, timestamp)
                repo.store(ws, timestamp)
                tech.fs.rmtree(workspace_dir)

        with robot.environment:
            add_translation(package_name, uuid)
            make_package(TS1)
            make_package(TS2)
        return package_name

    def pkg_with_history(self, robot, repo):
        return self._pkg_with_history(
            robot, repo, 'pkg_with_history', 'UUID:pkg_with_history')

    def pkg_with_inputs(self, robot, packages, pkg_a, pkg_b):
        inputs = dict(input_a=pkg_a, input_b=pkg_b)
        return self._new_package(robot, packages, 'pkg_with_inputs', inputs)


class Test_package_with_history(TestCase, PackageFixtures):

    # tests
    def test_develop_by_name(self, robot, pkg_a):
        robot.cli('develop', pkg_a)

        self.assertTrue(Workspace(robot.cwd / pkg_a).is_valid)
        self.assertThat(robot.cwd / pkg_a / 'README', FileContains(pkg_a))

    def test_develop_missing_package(self, robot, pkg_a):
        robot.cli('repo', 'forget', 'repo')
        try:
            robot.cli('develop', pkg_a)
        except SystemExit:
            self.assertThat(robot.stderr, Contains('Package'))
            self.assertThat(robot.stderr, Contains('not found'))
        else:
            self.fail('develop should have exited on missing package')

    def assert_develop_version(self, robot, pkg_spec, timestamp):
        assert pkg_spec.startswith('pkg_with_history')
        robot.cli('develop', pkg_spec)
        self.assertThat(
            robot.cwd / 'pkg_with_history' / 'sentinel-' + timestamp,
            FileExists())

    def test_develop_without_version(self, robot, pkg_with_history):
        self.assert_develop_version(robot, 'pkg_with_history', TS2)

    def test_develop_without_offset(self, robot, pkg_with_history):
        self.assert_develop_version(robot, 'pkg_with_history@', TS2)

    def test_develop_with_offset(self, robot, pkg_with_history):
        self.assert_develop_version(robot, 'pkg_with_history@-1', TS1)

    def test_develop_w_version_wo_offset(self, robot, pkg_with_history):
        self.assert_develop_version(robot, 'pkg_with_history@' + TS1, TS1)

    def test_develop_available_matches_to_version_are_less_than_offset(
            self, robot, pkg_with_history):
        self.assert_develop_version(
            robot, 'pkg_with_history@{}-1'.format(TS2), TS2)


class Test_input_commands(TestCase, PackageFixtures):

    def assert_mounted(self, robot, input_name, package_name):
        self.assertThat(
            robot.cwd / 'input' / input_name / 'README',
            FileContains(package_name))

    # tests

    def test_input_commands(self, robot, pkg_with_history):
        # nextpkg with input1 as datapkg1
        robot.cli('new', 'nextpkg')
        robot.cd('nextpkg')
        robot.cli('input', 'add', 'input1', 'pkg_with_history@' + TS1)
        robot.cli('pack')
        robot.cd('..')
        robot.cli('nuke', 'nextpkg')

        robot.cli('develop', 'nextpkg')
        robot.cd('nextpkg')
        assert not os.path.exists(robot.cwd / 'input/input1')

        robot.cli('input', 'load')
        assert os.path.exists(robot.cwd / 'input/input1')

        robot.cli('input', 'add', 'input2', 'pkg_with_history')
        assert os.path.exists(robot.cwd / 'input/input2')

        robot.cli('input', 'delete', 'input1')
        assert not os.path.exists(robot.cwd / 'input/input1')

        # no-op load do not crash
        robot.cli('input', 'load')

        robot.cli('status')

    def test_update_unmounted_input_with_explicit_package(
            self, robot, pkg_with_inputs, pkg_a, pkg_b):
        robot.cli('develop', pkg_with_inputs)
        robot.cd(pkg_with_inputs)

        assert not Workspace(robot.cwd).is_mounted('input_b')

        robot.cli('input', 'update', 'input_b', pkg_a)
        self.assert_mounted(robot, 'input_b', pkg_a)

        robot.cli('status')
        self.assertThat(robot.stdout, Not(Contains(pkg_b)))


class Test_status(TestCase, PackageFixtures):

    # tests

    def test(self, robot, packages, pkg_with_inputs, pkg_a):
        robot.cli('develop', pkg_with_inputs)
        robot.cd(pkg_with_inputs)
        robot.cli('status')

        self.assertThat(robot.stdout, Contains(pkg_with_inputs))
        self.assertThat(robot.stdout, Contains(pkg_a))

        pkg_a = packages[pkg_a]
        pkg_with_inputs = packages[pkg_with_inputs]
        self.assertThat(robot.stdout, Not(Contains(pkg_with_inputs.uuid)))
        self.assertThat(robot.stdout, Not(Contains(pkg_a.uuid)))
        self.assertThat(robot.stdout, Contains(pkg_a.timestamp_str))
        self.assertThat(robot.stdout, Not(Contains(pkg_a.version)))

    def test_verbose(self, robot, packages, pkg_with_inputs, pkg_a):
        robot.cli('develop', pkg_with_inputs)
        robot.cd(pkg_with_inputs)
        robot.cli('status', '-v')

        self.assertThat(robot.stdout, Contains(pkg_with_inputs))
        self.assertThat(robot.stdout, Contains(pkg_a))

        pkg_a = packages[pkg_a]
        pkg_with_inputs = packages[pkg_with_inputs]
        self.assertThat(robot.stdout, Contains(pkg_with_inputs.uuid))
        self.assertThat(robot.stdout, Contains(pkg_a.uuid))
        self.assertThat(robot.stdout, Contains(pkg_a.timestamp_str))
        self.assertThat(robot.stdout, Contains(pkg_a.version))

    def test_no_translations(self, robot, packages, pkg_with_inputs, pkg_a):
        robot.cli('develop', pkg_with_inputs)
        robot.cd(pkg_with_inputs)
        robot.cause_amnesia()
        robot.cli('status')

        self.assertThat(robot.stdout, Not(Contains(pkg_with_inputs)))
        self.assertThat(robot.stdout, Not(Contains(pkg_a)))

        pkg_a = packages[pkg_a]
        pkg_with_inputs = packages[pkg_with_inputs]
        self.assertThat(robot.stdout, Contains(pkg_with_inputs.uuid))
        self.assertThat(robot.stdout, Contains(pkg_a.uuid))
        self.assertThat(robot.stdout, Not(Contains(pkg_a.timestamp_str)))
        self.assertThat(robot.stdout, Contains(pkg_a.version))

    def test_verbose2(self, robot, packages, pkg_with_inputs, pkg_a):
        robot.cli('develop', pkg_with_inputs)
        robot.cd(pkg_with_inputs)
        robot.cause_amnesia()
        robot.cli('status', '--verbose')

        self.assertThat(robot.stdout, Not(Contains(pkg_with_inputs)))
        self.assertThat(robot.stdout, Not(Contains(pkg_a)))

        pkg_a = packages[pkg_a]
        pkg_with_inputs = packages[pkg_with_inputs]
        self.assertThat(robot.stdout, Contains(pkg_with_inputs.uuid))
        self.assertThat(robot.stdout, Contains(pkg_a.uuid))
        self.assertThat(robot.stdout, Not(Contains(pkg_a.timestamp_str)))
        self.assertThat(robot.stdout, Contains(pkg_a.version))