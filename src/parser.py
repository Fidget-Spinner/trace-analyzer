from __future__ import annotations


from dataclasses import dataclass, replace, field
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

@dataclass(slots=True)
class Trace(TraceLike):
    pass

@dataclass(slots=True)
class Bridge(TraceLike):
    pass

@dataclass(slots=True)
class Guard:
    id: int
    bridge: "Edge | None" = None

    def __str__(self):
        bridge_repr = "" if self.bridge is None else str(self.bridge)
        return f"Guard<{self.id}, bridge={bridge_repr}>"


@dataclass(slots=True)
class Label:
    id: int
    enter_count: int = 0
    # enter count counts back edges. this doesn't
    real_first_time_entry_count: int = 0

    def __str__(self):
        return f"Label<{self.id}, enters={self.enter_count}>"


@dataclass(slots=True)
class Jump:
    id: int
    jump_to_edge: "Edge" | None = None


DONE_WITH_THIS_FRAME = -0xDEAD

class PlaceHolderEdge(Edge):
    pass

class DoneWithThisFrame(Jump):
    pass

HEX_PAT = "0x\w+"

LOOP_PAT = "# Loop (\d+) (.+)"
LOOP_RE = re.compile(LOOP_PAT)
END_LOOP_MARKER = "--end of the loop--"

LABEL_PAT = f".+label\(.*descr=TargetToken\((\d+)\)\)"
LABEL_RE = re.compile(LABEL_PAT, re.IGNORECASE | re.MULTILINE)

GUARD_PAT = f".+guard_.+\(.*descr=<Guard({HEX_PAT})>.*\).*"
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
    assert False, "Could not find bridge trace"

def add_label_count(all_entries: list[Label], label_id: int, count: int):
    for label in all_entries:
        if label.id == label_id:
            label.enter_count = count
            label.real_first_time_entry_count = count # to compute later
            return
    assert False, "Could not find label"


def compute_edges(all_entries: list[Trace], all_nodes: list):
    """
    For a guard, the edge weight is just the guard entry count. Simple!

    For a back edge, It's just the last label (before) the back edge.
    This makes sense because traces are linear control-flow, so a label that
    leads to a backedge must have the same count.
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
                    print("Warning: wasteful recomputation")
                    continue                
                queue.extend(nxt.labels_and_guards)
                # Find the jump label in the labels and guards
                previous_label, idx = find_previous_label(nxt.labels_and_guards, len(nxt.labels_and_guards) - 1)
                # No label found, so it's the entry count of the bridge itself
                if previous_label is None:
                    entry_count = nxt.enter_count
                    idx = 0
                else:
                    assert isinstance(previous_label, Label)
                    entry_count = previous_label.enter_count
                    idx += 1
                # Finally, deduct all outgoing edges to guards
                outgoing = 0
                # print("ENTRY", entry_count)
                for i in range(idx, len(nxt.labels_and_guards)):
                    lbl_or_g = nxt.labels_and_guards[i]
                    if isinstance(lbl_or_g, Guard) and lbl_or_g.bridge is not None:
                        # print(lbl_or_g.bridge.node.enter_count)                        
                        outgoing += lbl_or_g.bridge.node.enter_count
                    # Should have no label
                    assert not isinstance(lbl_or_g, Label)
                entry_count -= outgoing
                assert entry_count >= 0
                nxt.jump.jump_to_edge.weight = entry_count
                # print(nxt.jump.jump_to_edge)
                # deduct the backedge weight to eventually find the initial entry for that label.
                if isinstance(nxt.jump.jump_to_edge.node, Label):
                    nxt.jump.jump_to_edge.node.real_first_time_entry_count -= entry_count
                    # if it drops below 0, this indicates that there was a deopt that was not recorded by pypy.
                    # TODO: Fix me later by instrumenting pypy
                    # For now, this is fine as it accounts for fewer than 0.1% of all execution counts.
                    if nxt.jump.jump_to_edge.node.real_first_time_entry_count < 0:
                        print(f"WARNING: entry count is {nxt.jump.jump_to_edge.node.real_first_time_entry_count}")
                        nxt.jump.jump_to_edge.node.real_first_time_entry_count = 0
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



def reorder_subtree_to_decrease_suboptimality(all_nodes, edge: Edge):
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
            copy.bridge = reorder_subtree_to_decrease_suboptimality(all_nodes, guard.bridge)
            res.append(copy)
        else:
            res.append(guard)
    node.labels_and_guards = res

    # It's already non-suboptimal, nothing to do here.
    if not node.is_suboptimal_cause:
        return edge

    # Greedy choice (decrease suboptimality): Now try swapping with the bridge that is most suboptimal
    # We just take the hottest bridge.
    worst_guard = None
    split = -1
    worst_bridge_hotness = -1
    incoming_weight = -1
    for idx, label_or_guard in enumerate(node.labels_and_guards):
        assert isinstance(label_or_guard, Guard) or isinstance(label_or_guard, Label)
        if isinstance(label_or_guard, Guard) and label_or_guard.bridge is not None:
            if label_or_guard.bridge.weight > worst_bridge_hotness:
                worst_bridge_hotness = label_or_guard.bridge.weight
                worst_guard = label_or_guard
                split = idx
                # Compute the incoming edge's weight from the previous label
                # Find the previous label in the labels and guards
                previous_label, label_idx = find_previous_label(node.labels_and_guards, idx)
                # No label found, so it's the entry count of the bridge itself              
                if previous_label is None:
                    incoming_weight = edge.weight
                    label_idx = 0
                else:
                    incoming_weight = previous_label.enter_count
                    label_idx += 1
                outgoing = 0                    
                # Finally, deduct all outgoing edges to guards
                # Stop when we hit the label right after that one, as that might itself be a peeled loop.
                stopped_early = False
                for i in range(label_idx, len(node.labels_and_guards)):
                    lbl_or_g = node.labels_and_guards[i]
                    if isinstance(lbl_or_g, Guard) and lbl_or_g.bridge is not None:
                        # # Skip ourselves
                        # if i == idx:
                        #     continue
                        outgoing += lbl_or_g.bridge.weight
                    if isinstance(lbl_or_g, Label):
                        assert lbl_or_g.real_first_time_entry_count <= lbl_or_g.enter_count
                        outgoing += lbl_or_g.real_first_time_entry_count
                        stopped_early = True
                        break
                # Now: add backedge to the outgoing (if needed)
                # if not stopped_early:
                #     outgoing += node.jump.jump_to_edge.weight
                # Finally, compute the actual incoming weight
                incoming_weight -= outgoing

    assert split != -1
    assert incoming_weight != -1
    before_bridge_labels_and_guards = node.labels_and_guards[:split]
    after_bridge_labels_and_guards = node.labels_and_guards[split+1:]

    # Sometimes the weights are slightly off due to deopt
    # (pypy doesn't count deopts in the logs)
    if incoming_weight < 0:
        print(f"WARNING: weight slightly off due to deopts! {incoming_weight}")
        incoming_weight = 0
        # print(incoming_weight)
        # print(outgoing)
        # print(previous_label)
        # print(label_idx)
        # print(worst_guard.bridge.weight)
        # print(node.enter_count)
        # assert False, node

    # Create the new alternative bridge from the rest of the existing trace.
    new_bridge = Bridge(
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

    # Merge worst bridge with current trace.
    better_node.labels_and_guards = before_bridge_labels_and_guards + [worst_guard] + worst_guard.bridge.node.labels_and_guards
    worst_guard.bridge.node = new_bridge
    # print(incoming_weight, outgoing)
    worst_guard.bridge.weight =  incoming_weight
    return Edge(better_node, weight=edge.weight)

def reorder_to_decrease_suboptimality(all_nodes, entries: list[Trace]):
    """
    Tries to swap the offending suboptimal bridge with the main trace to see if it makes things
    more optimal.
    """
    return [reorder_subtree_to_decrease_suboptimality(all_nodes, Edge(entry, entry.enter_count)).node for entry in entries]


def parse_and_build_trace_trees(fp):
    entries = []
    all_bridges = []
    all_labels = []
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
                    guard = int(guard_match.group(1), base=16)
                    labels_and_guards.append(Guard(guard))
                if jump_match := re.match(JUMP_RE, line.strip()):
                    jump = Jump(int(jump_match.group(1)))
                if finish_match := re.match(FINISH_RE, line.strip()):
                    jump = DoneWithThisFrame(DONE_WITH_THIS_FRAME, PlaceHolderEdge(None, 0))
            assert jump is not None, f"No jump at end of loop? {line}"
            entries.append(Trace(int(match.group(1)), match.group(2), labels_and_guards, jump))
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
                    guard = int(guard_match.group(1), base=16)
                    labels_and_guards.append(Guard(guard))
                if jump_match := re.match(JUMP_RE, line.strip()):
                    jump = Jump(int(jump_match.group(1)))
                if finish_match := re.match(FINISH_RE, line.strip()):
                    jump = DoneWithThisFrame(DONE_WITH_THIS_FRAME, PlaceHolderEdge(None, 0))
            assert jump is not None, f"No jump at end of bridge? {line}"
            all_bridges.append(Bridge(int(match.group(1), base=16), match.group(2), labels_and_guards, jump))
        elif "jit-backend-counts" in line:
            line = next(fp)
            while "jit-backend-counts" not in line:
                if line.startswith("entry"):
                    entry = re.match(ENTRY_COUNT_RE, line)
                    if int(entry.group(1)) >= 0:
                        add_entry_count(entries, int(entry.group(1)), int(entry.group(2)))
                elif line.startswith("bridge"):
                    entry = re.match(BRIDGE_COUNT_RE, line)
                    add_bridge_count(all_bridges, int(entry.group(1)), int(entry.group(2)))   
                elif line.startswith("TargetToken"):
                    entry = re.match(LABEL_COUNT_RE, line)
                    add_label_count(all_labels, int(entry.group(1)), int(entry.group(2)))  
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
        if jump.id == DONE_WITH_THIS_FRAME:
            assert loop.jump.jump_to_edge is not None            
            continue
        target_trace = find_label_obj_via_label(entries + all_bridges, jump.id)
        # loop.jump = Jump(jump.id, Edge(replace(target_trace)))
        loop.jump.jump_to_edge = Edge(target_trace)
        assert loop.jump.jump_to_edge is not None

    return entries, all_bridges

if __name__ == "__main__":
    import sys
    with open(sys.argv[1]) as fp:
        entries, all_bridges = parse_and_build_trace_trees(fp)
    compute_edges(entries, entries + all_bridges)
    decide_sub_optimality(entries)
    with open(sys.argv[2], "w") as fp:
        for entry in entries:
            print(entry, file=fp)
    entries = reorder_to_decrease_suboptimality(entries + all_bridges, entries)
    # compute_edges(entries, entries + all_bridges)
    clear_sub_optimality(entries)
    decide_sub_optimality(entries)
    with open(sys.argv[3], "w") as fp:
        for entry in entries:
            print(entry, file=fp)   

