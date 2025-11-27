"""
Some graph algorithm benchmarks using networkx

This uses the public domain Amazon data set from the SNAP benchmarks:

    https://snap.stanford.edu/data/amazon0302.html

Choice of benchmarks inspired by Timothy Lin's work here:

    https://www.timlrx.com/blog/benchmark-of-popular-graph-network-packages
"""

import collections
from pathlib import Path

import networkx


DATA_FILE = Path(__file__).parent / "data" / "amazon0302.txt.gz"


graph = networkx.read_adjlist(DATA_FILE)


def bench_shortest_path():
    collections.deque(networkx.shortest_path_length(graph, "0"))



from benchmark import Benchmark


class ShortestPath(Benchmark):
    def inner_benchmark_loop(self, inner_iterations):
        for _ in range(inner_iterations):
            bench_shortest_path()
        return True

    def benchmark(self):
        raise Exception("should never be reached")

    def verify_result(self, result):
        raise Exception("should never be reached")

