from __future__ import annotations


from dataclasses import dataclass, replace, field, asdict
import re
import textwrap

@dataclass(slots=True)
class Edge:
    node: "Trace | Bridge | Label | None"
    # Trace transitions
    weight: int = 0

    def __str__(self):
        return f"--({self.weight})-->{str(self.node)}"

@dataclass
class TraceLike:
    uuid: int
    id: int
    info: str
    labels_and_guards: list["Label" | "Guard"]

    # Terminator.
    jump: "Jump"
    enter_count: int = -1

    is_suboptimal_cause: "Guard | None" = None

    def __str__(self):
        res = []
        for lab in self.labels_and_guards:
            if isinstance(lab, Guard) and lab.bridge is None:
                continue
            res.append(str(lab))
        res.append(str(self.jump))
        indented = textwrap.indent('\n'.join(res), '    ')
        suboptimality_trailer = f" [!!!!!*SUBOPTIMAL ID={self.is_suboptimal_cause.id}*!!!!!]" if self.is_suboptimal_cause else ""
        return f"{type(self).__name__}<{self.id}, enters={self.enter_count}>{suboptimality_trailer}\n{indented}"

    def serialize(self) -> str:
        res = []
        for lab_or_guard in self.labels_and_guards:
            if isinstance(lab_or_guard, Guard):
                res.append(lab_or_guard.serialize())
            # We ignore labels, as those have a different address every run anwways.
        # Terminators need not be appended, as that is up to the pypy tracer to decide.
        # We're just responsible for the "shape" of the tree from guards.
        return {f"Trace:{self.uuid}" : res}
        

@dataclass(slots=True)
class Trace(TraceLike):
    pass

@dataclass(slots=True)
class Bridge(TraceLike):
    pass

GUARD_OP_INVERTED = {
    "guard_true": "guard_false",
    "guard_false": "guard_true",
    "guard_nonnull": "guard_isnull",
    "guard_isnull": "guard_nonnull",
}

@dataclass(slots=True)
class Guard:
    id: int
    op: str
    bridge: "Edge | None" = None
    inverted: bool = False
    expected_to_be_inverted: bool = False
    after_count: int = 0

    def __str__(self):
        post = "I" if self.inverted else ""
        if self.expected_to_be_inverted:
            post = "P"        
        bridge_repr = "" if self.bridge is None else str(self.bridge)
        return f"Guard{post}<{self.id}, op={self.op}, afters={self.after_count}, bridge={bridge_repr}>"

    def invert_guard(self, warn=True):
        if self.op not in GUARD_OP_INVERTED:
            # if warn:
            #     print("Not invertible: ", self.op)
            return None
        return GUARD_OP_INVERTED[self.op]

    def serialize(self):
        post = "I" if self.inverted else ""
        if self.expected_to_be_inverted:
            post = "P"
        if self.bridge is not None:
            return {f"Guard{post}:{self.op}": self.bridge.node.serialize()}
        return {f"Guard:{self.op}": None}


@dataclass(slots=True)
class Label:
    id: int
    before_count: int = 0
    after_count: int = 0

    def __str__(self):
        return f"Label<{self.id}, enters={self.before_count}, afters={self.after_count}>"

@dataclass(slots=True)
class Jump:
    id: int
    enter_count: int = 0
    jump_to_edge: "Edge" | None = None


DONE_WITH_THIS_FRAME = -0xDEAD

class PlaceHolderEdge(Edge):
    pass

class DoneWithThisFrame(Jump):
    pass


class PlaceHolderNode(TraceLike):
    pass

HEX_PAT = "0x\w+"

LOOP_PAT = "# Loop (\d+) (.+)"
LOOP_RE = re.compile(LOOP_PAT)
END_LOOP_MARKER = "--end of the loop--"

LABEL_PAT = f".+label\(.*descr=TargetToken\((\d+)\)\)"
LABEL_RE = re.compile(LABEL_PAT, re.IGNORECASE | re.MULTILINE)

GUARD_PAT = f".*(guard_\w*).*\(.*descr=<Guard({HEX_PAT})>.*\).*"
GUARD_RE = re.compile(GUARD_PAT)

BRIDGE_PAT = f"# bridge out of Guard ({HEX_PAT}) (.+)"
BRIDGE_RE = re.compile(BRIDGE_PAT)

JUMP_PAT = f".*jump\(.*descr=TargetToken\((\d+)\)\)"
JUMP_RE = re.compile(JUMP_PAT)

FINISH_PAT = f".*finish\(.*descr=<DoneWithThisFrameDescr.*>\)"
FINISH_RE = re.compile(FINISH_PAT)

ENTRY_COUNT_PAT = "entry (-?\d+):(\d+)"
ENTRY_COUNT_RE = re.compile(ENTRY_COUNT_PAT)

BRIDGE_COUNT_PAT = "bridge (\d+):(\d+)"
BRIDGE_COUNT_RE = re.compile(BRIDGE_COUNT_PAT)

LABEL_COUNT_PAT = "TargetToken\((\d+)\):(\d+)"
LABEL_COUNT_RE = re.compile(LABEL_COUNT_PAT)

LABEL_PRIOR_COUNT_PAT = "PriorToTargetToken\((\d+)\):(\d+)"
LABEL_PRIOR_COUNT_RE = re.compile(LABEL_PRIOR_COUNT_PAT)

JUMP_COUNT_PAT = "ExitOfToken\((-?\d+):(\d+)\):(\d+)"
JUMP_COUNT_RE = re.compile(JUMP_COUNT_PAT)

AFTER_GUARD_PAT = "AfterGuardAt\((\d+)\):(\d+)"
AFTER_GUARD_RE = re.compile(AFTER_GUARD_PAT)

AFTER_EXPECTED_INVERTED_GUARD_PAT = "AfterExpectedInvertedGuardAt\((\d+)\):(\d+)"
AFTER_EXPECTED_INVERTED_GUARD_RE = re.compile(AFTER_EXPECTED_INVERTED_GUARD_PAT)


def find_jump_containing_trace(all_nodes: list[Bridge | Trace], jump: Jump):
    for node in all_nodes:
        if jump.id == node.jump.id:
            return node
    return None


def find_bridge(all_bridges: list[Bridge], from_guard: Guard):
    for bridge in all_bridges:
        if bridge.id == from_guard.id:
            return bridge
    return None

def find_label_obj_via_label(all_nodes: list[Label | Guard], label: int):
    for node in all_nodes:
        for label_obj in node.labels_and_guards:
            if isinstance(label_obj, Label):
                if label_obj.id == label:
                    return label_obj
    assert False, f"No corresponding node for label? {label}"

def find_bridge_via_label(all_nodes: list[Bridge | Trace], label: int) -> Bridge:
    visited = set()
    worklist = list(all_nodes)
    while worklist:
        node = worklist.pop()
        if id(node) in visited:
            continue
        visited.add(id(node))
        if isinstance(node, Guard) and node.id == label:
            return node
        if isinstance(node, Bridge) or isinstance(node, Trace):
            for node in node.labels_and_guards:
                worklist.append(node)
    assert False, f"Cannot find guard with label {label}"


def add_entry_count(all_entries: list[Trace], entry_id: int, count: int):
    for entry in all_entries:
        if entry.id == entry_id:
            entry.enter_count = count
            return
    assert False, f"Could not find entry trace {entry_id}"

def add_bridge_count(all_entries: list[Bridge], guard_id: int, count: int):
    for bridge in all_entries:
        if bridge.id == guard_id:
            bridge.enter_count = count
            return
    assert False, f"Could not find bridge trace {guard_id}"

def add_label_before_count(all_entries: list[Label], label_id: int, count: int):
    for label in all_entries:
        if label.id == label_id:
            label.before_count = count
            return
    assert False, "Could not find label"

def add_label_after_count(all_entries: list[Label], label_id: int, count: int):
    for label in all_entries:
        if label.id == label_id:
            label.after_count = count
            return
    assert False, "Could not find label"

def add_jump_count(all_entries: list[TraceLike], jump_id: int, count: int):
    if jump_id < 0:
        return
    for trace in all_entries:
        if trace.id == jump_id:
            trace.jump.enter_count = count
            return
    assert False, f"Could not find jump {jump_id}"

def add_guard_after_count(all_guards: list[Guard], guard_id: int, count: int, expected_inversion: bool = False):
    for guard in all_guards:
        if guard.id == guard_id:
            guard.after_count = count
            guard.expected_to_be_inverted = expected_inversion
            return
    print(all_guards)
    assert False, f"Could not find guard {guard_id}"


def compute_edges(all_entries: list[Trace], all_nodes: list):
    """
    For a guard, the edge weight is just the guard entry count. Simple!

    Likewise for a backwards edge.
    """
    for entry in all_entries:
        seen: set[int] = set()

        queue = [entry]
        while queue:
            nxt = queue.pop(0)
            if id(nxt) in seen:
                continue
            seen.add(id(nxt))
            if isinstance(nxt, Guard):
                if nxt.bridge is not None:
                    nxt.bridge.weight = nxt.bridge.node.enter_count
                    queue.append(nxt.bridge.node)
            elif isinstance(nxt, Trace | Bridge):
                # We should not be recomputing things!
                if nxt.jump.jump_to_edge.weight != 0:
                    # print("Warning: wasteful recomputation")
                    continue
                nxt.jump.jump_to_edge.weight = nxt.jump.enter_count
                queue.extend(nxt.labels_and_guards)
                # Find the jump label in the labels and guards
                # deduct the backedge weight to eventually find the initial entry for that label.
                if isinstance(nxt.jump.jump_to_edge.node, Label):
                    queue.append(nxt.jump.jump_to_edge.node)
            elif isinstance(nxt, Label):
                pass
            elif isinstance(nxt, type(None)):
                pass
            else:
                assert False, f"Unknown node type {nxt}"


def find_previous_label(labels_or_guards, idx):
    while idx >= 0:
        thing = labels_or_guards[idx]
        if isinstance(thing, Label):
            return thing, idx        
        idx -= 1
    return None, None

def decide_sub_optimality_for_single_entry(entry: TraceLike, node: TraceLike | None):
    """
    Decides if a trace is sub-optimal.

    The heuristic:
    If the heaviest weighted edge of a trace is not the terminator but rather a bridge.
    Then the trace is suboptimal.

    
    """
    if not node:
        return
    if isinstance(node, TraceLike):
        node.is_suboptimal_cause = None
        jump_weight = node.jump.jump_to_edge.weight
        for guard in node.labels_and_guards:
            if isinstance(guard, Guard) and guard.bridge is not None:
                if guard.bridge.weight > jump_weight:
                    node.is_suboptimal_cause = guard
                decide_sub_optimality_for_single_entry(entry, guard.bridge.node)
    elif isinstance(node, Edge):
        decide_sub_optimality_for_single_entry(entry, node.node)

def decide_sub_optimality(entries: list[TraceLike]):
    for entry in entries:
        decide_sub_optimality_for_single_entry(entry, entry)

def count_suboptimality(all_entries: list[Trace]):
    """
    Count number of suboptimal nodes.
    """
    count = 0
    for entry in all_entries:
        seen: set[int] = set()

        queue = [entry]
        while queue:
            nxt = queue.pop(0)
            if id(nxt) in seen:
                continue
            seen.add(id(nxt))
            if isinstance(nxt, Guard):
                if nxt.bridge is not None:
                    nxt.bridge.weight = nxt.bridge.node.enter_count
                    queue.append(nxt.bridge.node)
            elif isinstance(nxt, TraceLike):
                if nxt.is_suboptimal_cause is not None:
                    count += 1
                nxt.jump.jump_to_edge.weight = nxt.jump.enter_count
                queue.extend(nxt.labels_and_guards)
                # Find the jump label in the labels and guards
                # deduct the backedge weight to eventually find the initial entry for that label.
                if isinstance(nxt.jump.jump_to_edge.node, Label):
                    queue.append(nxt.jump.jump_to_edge.node)
            elif isinstance(nxt, Label):
                pass
            elif isinstance(nxt, type(None)):
                pass
            else:
                assert False, f"Unknown node type {nxt}"
    return count


def clear_sub_optimality_for_single_entry(entry: TraceLike, node: TraceLike | None):
    """
    Decides if a trace is sub-optimal.

    The heuristic:
    If the heaviest weighted edge of a trace is not the terminator but rather a bridge.
    Then the trace is suboptimal.

    
    """
    if not node:
        return
    if isinstance(node, TraceLike):
        node.is_suboptimal_cause = None
        jump_weight = node.jump.jump_to_edge.weight
        for guard in node.labels_and_guards:
            if isinstance(guard, Guard) and guard.bridge is not None:
                clear_sub_optimality_for_single_entry(entry, guard.bridge.node)
    elif isinstance(node, Edge):
        clear_sub_optimality_for_single_entry(entry, node.node)

def clear_sub_optimality(entries: list[TraceLike]):
    for entry in entries:
        clear_sub_optimality_for_single_entry(entry, entry)



def reorder_subtree_to_decrease_suboptimality(all_nodes, edge: Edge, requires_invertible_guard: bool):
    # TODO: account for donewiththisframe exit counts

    # Trivial (base) case: this is a single node,
    # it is trivially optimal.
    node = edge.node
    if not node.labels_and_guards:
        return edge
    if isinstance(node, Label):
        return edge
    if isinstance(node, Guard):
        return edge
    

    node = replace(node)
    # Recurse in on the sub-traces to make them optimal first.
    res = []
    for guard in node.labels_and_guards:
        if isinstance(guard, Guard) and guard.bridge is not None:
            copy = replace(guard)
            copy.bridge = reorder_subtree_to_decrease_suboptimality(all_nodes, guard.bridge, requires_invertible_guard)
            res.append(copy)
        else:
            res.append(guard)
    node.labels_and_guards = res

    # It's already non-suboptimal, nothing to do here.
    if not node.is_suboptimal_cause:
        return Edge(node, weight=edge.weight)

    seen_an_expected_inverted_guard_idxes = []
    for idx, guard in enumerate(node.labels_and_guards):
        if isinstance(guard, Guard) and guard.expected_to_be_inverted:
            seen_an_expected_inverted_guard_idxes.append(idx)

    # Greedy choice (decrease suboptimality): Now try swapping with the bridge that is most suboptimal
    # We just take the hottest bridge.
    worst_guard = None
    split = -1
    worst_bridge_hotness = -1
    incoming_weight = -1
    jump_hotness = node.jump.enter_count
    for idx, label_or_guard in enumerate(node.labels_and_guards):
        assert isinstance(label_or_guard, Guard) or isinstance(label_or_guard, Label)
        if isinstance(label_or_guard, Guard) and label_or_guard.bridge is not None:
            if label_or_guard.bridge.weight > jump_hotness and label_or_guard.bridge.weight > worst_bridge_hotness:
                if requires_invertible_guard and label_or_guard.invert_guard() is not None:
                    # We can only swap if there are no already inverted guards AFTER this bridge.
                    # The reason is that we want to steadily decrease the number of suboptimal guards,
                    # not thrash around!                    
                    if any(already_inverted_idx >= idx for already_inverted_idx in seen_an_expected_inverted_guard_idxes):
                        continue
                    worst_bridge_hotness = label_or_guard.bridge.weight
                    worst_guard = label_or_guard
                    split = idx
                    incoming_weight = label_or_guard.after_count

    if split == -1:
        # Non-invertible. In theory, we could still invert them by swapping out the guards and their identities
        # the problem however is that the identities are dependent on pypy addresses, which make them near impossible
        # to predict at runtime if we use some sort of training data to guide our traces.
        # Still, it's useful to know if "in theory" we could make these more optimal, as a higher-tier optimizing
        # compiler should still be able to make use of this information.
        return Edge(node, weight=edge.weight)
    assert incoming_weight != -1
    before_bridge_labels_and_guards = node.labels_and_guards[:split]
    after_bridge_labels_and_guards = node.labels_and_guards[split+1:]

    assert incoming_weight >= 0

    # Create the new alternative bridge from the rest of the existing trace.
    new_bridge = Bridge(
        worst_guard.bridge.node.uuid,
        worst_guard.id,
        f"swapped of {worst_guard.bridge.node.info}",
        labels_and_guards=after_bridge_labels_and_guards,
        jump=node.jump,
        enter_count=incoming_weight
    )
    
    worst_guard = replace(worst_guard)
    # Merge worst bridge with current trace.
    better_node = replace(node)

    # swap out the jumps
    tmp = better_node.jump
    better_node.jump = replace(worst_guard.bridge.node.jump)
    worst_guard.bridge.node.jump = replace(tmp)

    # invert the guard op
    worst_guard.op = worst_guard.invert_guard()
    worst_guard.inverted = True    
    new_trunk_after_labels_and_guards = worst_guard.bridge.node.labels_and_guards


    # Merge worst bridge with current trace.
    better_node.labels_and_guards = before_bridge_labels_and_guards + [worst_guard] + new_trunk_after_labels_and_guards
    worst_guard.bridge.node = new_bridge
    # print(incoming_weight, outgoing)
    worst_guard.bridge.weight =  incoming_weight
    return Edge(better_node, weight=edge.weight)

def reorder_to_decrease_suboptimality(all_nodes, entries: list[Trace], requires_invertible_guard: bool=False):
    """
    Tries to swap the offending suboptimal bridge with the main trace to see if it makes things
    more optimal.
    """
    return [reorder_subtree_to_decrease_suboptimality(all_nodes, Edge(entry, entry.enter_count), requires_invertible_guard).node for entry in entries]


def parse_and_build_trace_trees(fp):
    entries = []
    all_bridges = []
    all_labels = []
    all_guards = []
    tracelike_uuid = 0
    for line in fp:
        if line.startswith("# Loop"):
            match = re.match(LOOP_RE, line)
            labels_and_guards = []
            jump = None
            while END_LOOP_MARKER not in line:
                line = next(fp)
                if label_match := re.match(LABEL_RE, line.strip()):
                    lab = Label(int(label_match.group(1)))
                    all_labels.append(lab)
                    labels_and_guards.append(lab)
                if guard_match := re.match(GUARD_RE, line.strip()):
                    guard = Guard(int(guard_match.group(2), base=16), guard_match.group(1))
                    assert guard_match.group(1) is not None, guard_match
                    labels_and_guards.append(guard)
                    all_guards.append(guard)
                if jump_match := re.match(JUMP_RE, line.strip()):
                    jump = Jump(int(jump_match.group(1)))
                if finish_match := re.match(FINISH_RE, line.strip()):
                    jump = DoneWithThisFrame(match.group(1), 0, PlaceHolderEdge(None, 0))
            assert jump is not None, f"No jump at end of loop? {line}"
            # Sometimes pypy gives negative IDs for fake traces.
            if int(match.group(1)) >= 0:
                entries.append(Trace(tracelike_uuid, int(match.group(1)), match.group(2), labels_and_guards, jump))
            tracelike_uuid += 1
        elif line.startswith("# bridge out of"):
            match = re.match(BRIDGE_RE, line)
            labels_and_guards = []              
            while END_LOOP_MARKER not in line:
                line = next(fp)
                if label_match := re.match(LABEL_RE, line.strip()):
                    lab = Label(int(label_match.group(1)))
                    all_labels.append(lab)
                    labels_and_guards.append(lab)
                if guard_match := re.match(GUARD_RE, line.strip()):
                    guard = Guard(int(guard_match.group(2), base=16), guard_match.group(1))
                    assert guard_match.group(1) is not None, line
                    labels_and_guards.append(guard)
                    all_guards.append(guard)
                if jump_match := re.match(JUMP_RE, line.strip()):
                    jump = Jump(int(jump_match.group(1)))
                if finish_match := re.match(FINISH_RE, line.strip()):
                    jump = DoneWithThisFrame(match.group(1), 0, PlaceHolderEdge(None, 0))
            assert jump is not None, f"No jump at end of bridge? {line}"          
            all_bridges.append(Bridge(tracelike_uuid, int(match.group(1), base=16), match.group(2), labels_and_guards, jump))
            tracelike_uuid += 1
        elif "jit-backend-counts" in line:
            line = next(fp)
            while "jit-backend-counts" not in line:
                if line.startswith("entry"):
                    entry = re.match(ENTRY_COUNT_RE, line)
                    if int(entry.group(1)) >= 0:
                        add_entry_count(entries, int(entry.group(1)), int(entry.group(2)))
                if int(entry.group(1)) >= 0:
                    if line.startswith("bridge"):
                        entry = re.match(BRIDGE_COUNT_RE, line)
                        add_bridge_count(all_bridges, int(entry.group(1)), int(entry.group(2)))   
                    elif line.startswith("TargetToken"):
                        entry = re.match(LABEL_COUNT_RE, line)
                        add_label_after_count(all_labels, int(entry.group(1)), int(entry.group(2))) 
                    elif line.startswith("PriorToTargetToken"):
                        entry = re.match(LABEL_PRIOR_COUNT_RE, line)
                        add_label_before_count(all_labels, int(entry.group(1)), int(entry.group(2))) 
                    elif line.startswith("ExitOfToken"):
                        entry = re.match(JUMP_COUNT_RE, line)
                        add_jump_count(entries + all_bridges, int(entry.group(1)), int(entry.group(3)))
                    elif line.startswith("AfterGuardAt"):
                        entry = re.match(AFTER_GUARD_RE, line)
                        add_guard_after_count(all_guards, int(entry.group(1)), int(entry.group(2)))
                    elif line.startswith("AfterExpectedInvertedGuardAt"):
                        entry = re.match(AFTER_EXPECTED_INVERTED_GUARD_RE, line)
                        add_guard_after_count(all_guards, int(entry.group(1)), int(entry.group(2)), expected_inversion=True)                        
                line = next(fp)
    # Match labels to bridges.
    for entry in entries + all_bridges:
        for guard in entry.labels_and_guards:
            if isinstance(guard, Guard):
                if bridge := find_bridge(all_bridges, guard):
                    guard.bridge = Edge(replace(bridge))

    # Match jumps to labels/traces
    for loop in entries + all_bridges:
        jump = loop.jump
        # is a terminator
        if isinstance(jump, DoneWithThisFrame):        
            continue
        target_trace = find_label_obj_via_label(entries + all_bridges, jump.id)
        # loop.jump = Jump(jump.id, Edge(replace(target_trace)))
        loop.jump.jump_to_edge = Edge(target_trace)
        assert loop.jump.jump_to_edge is not None

    return entries, all_bridges


def dump_entries(entries: list[TraceLike], file) -> None:
    import json
    new_list = []
    entry_id = 0
    for entry in entries:
        entry.id = entry_id
        entry_id += 1
        new_list.append(entry.serialize())
    json.dump(new_list, file, separators=(',', ':'))


if __name__ == "__main__":
    import sys
    with open(sys.argv[1]) as fp:
        entries, all_bridges = parse_and_build_trace_trees(fp)
    compute_edges(entries, entries + all_bridges)
    decide_sub_optimality(entries)
    with open(sys.argv[2], "w") as fp:
        for entry in entries:
            print(entry, file=fp)
    # Run to fixpoint.
    prev_count = float('+inf')
    for _ in range(11):
        prev_count = count_suboptimality(entries)
        entries = reorder_to_decrease_suboptimality(entries + all_bridges, entries, requires_invertible_guard=True)
        clear_sub_optimality(entries)
        decide_sub_optimality(entries)
    # compute_edges(entries, entries + all_bridges)
    # entries = reorder_to_decrease_suboptimality(entries + all_bridges, entries, requires_invertible_guard=True)
    clear_sub_optimality(entries)
    decide_sub_optimality(entries)
    with open(sys.argv[3], "w") as fp:
        for entry in entries:
            print(entry, file=fp)

    with open(sys.argv[4], "w") as fp:
        dump_entries(entries, fp)