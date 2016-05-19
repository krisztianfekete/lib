from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from __future__ import print_function

from bead.test import TestCase
from testtools.matchers import Contains

from . import test_fixtures as fixtures
from collections import namedtuple
from bead import spec as bead_spec
from bead.workspace import Workspace


class Test(TestCase, fixtures.RobotAndBeads):

    def test_invalid_workspace_causes_error(self, robot):
        self.assertRaises(SystemExit, robot.cli, 'save')
        self.assertThat(robot.stderr, Contains('ERROR'))

    def test_on_success_there_is_feedback(self, robot, box):
        robot.cli('new', 'bead')
        robot.cd('bead')
        robot.cli('save')
        self.assertNotEquals(
            robot.stdout, '', 'Expected some feedback, but got none :(')


class Test_no_box(TestCase):

    # fixtures
    def robot(self):
        return self.useFixture(fixtures.Robot())

    # tests
    def test_missing_box_causes_error(self, robot):
        robot.cli('new', 'bead')
        self.assertRaises(SystemExit, robot.cli, 'save', 'bead')
        self.assertThat(robot.stderr, Contains('ERROR'))


Box = namedtuple('Box', 'name directory')


def bead_count(robot, box, bead_uuid):
    with robot.environment as env:
        query = [(bead_spec.BEAD_UUID, bead_uuid)]
        return sum(1 for _ in env.get_box(box.name).find_beads(query))


class Test_more_than_one_boxes(TestCase):
    # fixtures
    def robot(self):
        return self.useFixture(fixtures.Robot())

    def make_box(self, robot, name):
        directory = self.new_temp_dir()
        robot.cli('box', 'add', name, directory)
        return Box(name, directory)

    def box1(self, robot):
        return self.make_box(robot, 'box1')

    def box2(self, robot):
        return self.make_box(robot, 'box2')

    # tests
    def test_save_dies_without_explicit_box(self, robot, box1, box2):
        robot.cli('new', 'bead')
        self.assertRaises(SystemExit, robot.cli, 'save', 'bead')
        self.assertThat(robot.stderr, Contains('ERROR'))

    def test_save_stores_bead_in_specified_box(self, robot, box1, box2):
        robot.cli('new', 'bead')
        robot.cli('save', box1.name, '--workspace=bead')
        with robot.environment:
            bead_uuid = Workspace('bead').bead_uuid
        self.assertEquals(1, bead_count(robot, box1, bead_uuid))
        self.assertEquals(0, bead_count(robot, box2, bead_uuid))
        robot.cli('save', box2.name, '-w', 'bead')
        self.assertEquals(1, bead_count(robot, box1, bead_uuid))
        self.assertEquals(1, bead_count(robot, box2, bead_uuid))

    def test_invalid_box_specified(self, robot, box1, box2):
        robot.cli('new', 'bead')
        self.assertRaises(
            SystemExit,
            robot.cli, 'save', 'unknown-box', '--workspace', 'bead')
        self.assertThat(robot.stderr, Contains('ERROR'))
