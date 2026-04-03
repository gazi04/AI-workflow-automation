from typing import Dict, List
from workflow.schemas.edges import Edge


def build_adjacency_list(edges: List[Edge]) -> Dict[str, List[Edge]]:
    """Maps a Node ID to a list of its outgoing edges for O(1) lookups."""
    adj_list = {}
    for edge in edges:
        if edge.source not in adj_list:
            adj_list[edge.source] = []
        adj_list[edge.source].append(edge)
    return adj_list
