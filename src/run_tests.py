import unittest
import pathlib

from parser import (
    Trace,
    Guard,
    TraceLike,
    Guard,
    Label,
    Bridge,
    Edge,
    Jump,
    parse_and_build_trace_trees,
    compute_edges,
    decide_sub_optimality,
    reorder_to_decrease_suboptimality,
)

PARENT_DIR = pathlib.Path("./src/test")

class Test(unittest.TestCase):
    def build_from_log(self, infile) -> list[TraceLike]:
        with open(infile) as fp:
            entries, all_bridges = parse_and_build_trace_trees(fp)
        compute_edges(entries, entries + all_bridges)
        decide_sub_optimality(entries)
        return entries, all_bridges

    def assert_graph_shape_matches(self, result: list[TraceLike], expected: list[TraceLike]):
        for entry1, entry2 in zip(result, expected):
            worklist1 = [entry1]
            worklist2 = [entry2]
            visited = set()
            while worklist1:
                assert len(worklist1) == len(worklist2)
                nxt1 = worklist1.pop(0)
                nxt2 = worklist2.pop(0)
                if id(nxt1) in visited:
                    assert id(nxt2) in visited
                    continue
                visited.add(id(nxt1))
                visited.add(id(nxt2))
                self.assertEqual(type(nxt1), type(nxt2))
                self.assertIsInstance(nxt1, TraceLike)
                with self.subTest(trace1=nxt1.id, trace2=nxt2.id):
                    self.assertEqual(nxt1.id, nxt2.id)
                    self.assertEqual(type(nxt1.is_suboptimal_cause), type(nxt2.is_suboptimal_cause))
                    if nxt1.is_suboptimal_cause is not None:
                        self.assertEqual(nxt1.is_suboptimal_cause.id, nxt2.is_suboptimal_cause.id)
                    # ignore unused guards:
                    used_guards = [guard for guard in nxt1.labels_and_guards if isinstance(guard, Label) or (isinstance(guard, Guard) and guard.bridge is not None)]
                    self.assertEqual(len(used_guards), len(nxt2.labels_and_guards))                    
                    for label_or_guard1, label_or_guard2 in zip(used_guards, nxt2.labels_and_guards):
                        with self.subTest(item1=label_or_guard1.id, item2=label_or_guard2.id):
                            self.assertEqual(type(label_or_guard1), type(label_or_guard2))
                            self.assertEqual(label_or_guard1.id, label_or_guard2.id)
                            if isinstance(label_or_guard1, Guard) and label_or_guard1.bridge is not None:
                                self.assertEqual(type(label_or_guard1.bridge), type(label_or_guard2.bridge))
                                worklist1.append(label_or_guard1.bridge.node)
                                worklist2.append(label_or_guard2.bridge.node)

            assert len(worklist1) == len(worklist2)

    def test_bad_input(self):
        """
        See src/test/bad_input.py

        BEFORE
        Trace<1, enters=202> [!!!!!*SUBOPTIMAL ID=129081921693024*!!!!!]
            Label<129081921749408, enters=9900000>
            Guard<129081921693024, bridge=--(9899798)-->Bridge<129081921693024, enters=9899798>
                Jump(id=129081921749408, jump_to_edge=Edge(node=Label(id=129081921749408, enter_count=9900000), weight=9899798))>
            Label<129081921749472, enters=98958>
            Jump(id=129081921749472, jump_to_edge=Edge(node=Label(id=129081921749472, enter_count=98958), weight=98958))
        AFTER
        Trace<1, enters=202>
            Label<129081921749408, enters=9900000>
            Guard<129081921693024, bridge=--(202)-->Bridge<129081921693024, enters=202>
                Label<129081921749472, enters=98958>
                Jump(id=129081921749472, jump_to_edge=Edge(node=Label(id=129081921749472, enter_count=98958), weight=98958))>
            Jump(id=129081921749408, jump_to_edge=Edge(node=Label(id=129081921749408, enter_count=9900000), weight=9899798))        
        """
        entries, all_bridges = self.build_from_log(PARENT_DIR / "bad_input")
        side_exit = Guard(
            129081921693024, bridge=Edge(
            node=Bridge(
                129081921693024,
                "side exit for branch",
                labels_and_guards=[],
                # To top of the loop! We defeated loop peeling!
                jump=Jump(129081921749408),
            )
        ))
        self.assert_graph_shape_matches(
            entries,
            [
                Trace(
                    1,
                    "entry",
                    labels_and_guards=[
                        # Top of the loop
                        Label(129081921749408),
                        side_exit,
                        # Peeled loop 1
                        Label(129081921749472),
                    ],
                    # To peeled loop 1
                    jump=Jump(129081921749472),
                    is_suboptimal_cause=side_exit,
                )
            ]
        )
        reordered_entries = reorder_to_decrease_suboptimality(entries+all_bridges, entries)
        decide_sub_optimality(reordered_entries)
        # swapped the bad side exit
        new_side_exit = Guard(
            129081921693024, bridge=Edge(
            node=Bridge(
                129081921693024,
                "side exit for branch",
                labels_and_guards=[
                    # Peeled loop 1
                    Label(129081921749472),
                ],
                # To peeled loop 1.
                jump=Jump(129081921749472),
            )
        ))
        self.assert_graph_shape_matches(
            reordered_entries,
            [
                Trace(
                    1,
                    "entry",
                    labels_and_guards=[
                        Label(129081921749408),
                        new_side_exit,
                    ],
                    # To top of the loop.
                    jump=Jump(129081921749408),
                    is_suboptimal_cause=None,
                )
            ]
        )        
if __name__ == "__main__":
    unittest.main()