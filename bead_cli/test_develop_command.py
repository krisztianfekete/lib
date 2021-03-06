import os

from bead.test import TestCase

from bead.workspace import Workspace
from bead import layouts
from . import test_fixtures as fixtures


class Test_develop(TestCase, fixtures.RobotAndBeads):

    # tests
    def test_by_name(self, robot, bead_a):
        robot.cli('develop', bead_a)

        assert Workspace(robot.cwd / bead_a).is_valid
        self.assert_file_contains(robot.cwd / bead_a / 'README', bead_a)

    def test_missing_bead(self, robot, bead_a):
        robot.cli('box', 'forget', 'box')
        try:
            robot.cli('develop', bead_a)
        except SystemExit:
            assert 'Bead' in robot.stderr
            assert 'not found' in robot.stderr
        else:
            self.fail('develop should have exited on missing bead')

    def assert_develop_version(self, robot, timestamp, *bead_spec):
        assert bead_spec[0] == 'bead_with_history'
        robot.cli('develop', *bead_spec)
        self.assert_file_exists(robot.cwd / 'bead_with_history' / 'sentinel-' + timestamp)

    def test_last_version(self, robot, bead_with_history):
        self.assert_develop_version(robot, fixtures.TS_LAST, bead_with_history)

    def test_at_time(self, robot, bead_with_history):
        self.assert_develop_version(robot, fixtures.TS1, 'bead_with_history', '-t', fixtures.TS1)

    def test_hacked_bead_is_detected(self, robot, hacked_bead):
        self.assertRaises(SystemExit, robot.cli, 'develop', hacked_bead)
        assert 'ERROR' in robot.stderr

    def test_extract_output(self, robot, bead_a):
        robot.cli('develop', '-x', bead_a)
        ws = robot.cwd / bead_a

        assert Workspace(ws).is_valid

        # output must be unpacked as well!
        self.assert_file_contains(ws / layouts.Workspace.OUTPUT / 'README', bead_a)

    def test_dies_if_directory_exists(self, robot, bead_a):
        os.makedirs(robot.cwd / bead_a)
        self.assertRaises(SystemExit, robot.cli, 'develop', bead_a)
        assert 'ERROR' in robot.stderr
