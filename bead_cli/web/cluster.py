from typing import Dict, Iterable

from bead.tech.timestamp import EPOCH_STR

from .metabead import MetaBead
from .bead_state import BeadState
from . import graphviz


class Cluster:
    """
    Versions of beads having the same name.

    .head: Latest bead, that is not phantom, or the first phantom bead, if all are phantoms.
    """
    def __init__(self, name):
        self.name = name
        self.beads_by_content_id = {}

        # use a phantom bead instead of None for default value
        phantom_head = MetaBead(
            name=name, timestamp_str=EPOCH_STR,
            content_id=None, kind='EMPTY CLUSTER')
        phantom_head.set_state(BeadState.PHANTOM)
        self.head = phantom_head

    def add(self, bead):
        assert bead.name == self.name
        assert bead.content_id not in self.beads_by_content_id
        self.beads_by_content_id[bead.content_id] = bead

        def head_order(bead):
            return (bead.is_not_phantom, bead.timestamp)

        if head_order(bead) >= head_order(self.head):
            self.head = bead

    def beads(self):
        """
        Time sorted list of beads, most recent first.
        """
        return (
            sorted(
                self.beads_by_content_id.values(),
                key=(lambda bead: bead.timestamp),
                reverse=True))

    def has(self, content_id):
        return content_id in self.beads_by_content_id

    def get(self, content_id):
        return self.beads_by_content_id[content_id]

    @property
    def as_dot(self):
        return ''.join(graphviz.dot_cluster_as_fragments(self.beads()))


def create_cluster_index(beads: Iterable[MetaBead]) -> Dict[str, Cluster]:
    cluster_by_name: Dict[str, Cluster] = {}
    for bead in beads:
        if bead.name not in cluster_by_name:
            cluster_by_name[bead.name] = Cluster(bead.name)
        cluster_by_name[bead.name].add(bead)
    return cluster_by_name