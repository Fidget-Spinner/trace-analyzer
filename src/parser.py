from __future__ import annotations


from dataclasses import dataclass, replace
import re
import textwrap

@dataclass(slots=True)
class Trace:
    id: int
    info: str
    labels_and_guards: list["Label" | "Guard"]

    # Terminator.
    jump: int
    jump_to: "Label | None" = None 


    # This is how many times we enter this trace.
    # It is computed from other trace's back counts.
    enter_count: int = -1

    computed_jump_obj: "Trace | Bridge" = None

    is_suboptimal: bool = False

    def __repr__(self):
        res = []
        for lab in self.labels_and_guards:
            if isinstance(lab, Guard):
                if lab.bridge is None:
                    continue
            res.append(repr(lab))
        indented = textwrap.indent('\n'.join(res), '    ')
        suboptimality_trailer = " <--- SUBOPTIMAL!" if self.is_suboptimal else ""
        return f"Trunk<{self.id}, enters={self.enter_count}>{suboptimality_trailer}\n{indented}"

@dataclass(slots=True)
class Bridge:
    from_guard: int 
    info: str
    labels_and_guards: list["Label" | "Guard"]

    # Terminator.
    jump: int
    jump_to: "Label | None" = None 

    # Note: this is end of trace count. Usually that also corresponds
    # to a backedge.
    end_count: int = -1

    # This is how many times we enter this trace.
    # It is computed from other trace's back counts.
    enter_count: int = -1

    computed_jump_obj: "Trace | Bridge" = None

    is_suboptimal: bool = False

    def __repr__(self):
        res = []
        for lab in self.labels_and_guards:
            if isinstance(lab, Guard):
                if lab.bridge is None:
                    continue
            res.append(repr(lab))
        indented = textwrap.indent('\n'.join(res), '    ')
        suboptimality_trailer = " <--- SUBOPTIMAL!" if self.is_suboptimal else ""
        return f"Bridge<{self.from_guard}, enters={self.enter_count}>{suboptimality_trailer}\n{indented}"

@dataclass(slots=True)
class Guard:
    id: int
    enter_count: int = 0
    bridge: "Bridge | None" = None

    def __repr__(self):
        bridge_repr = "" if self.bridge is None else repr(self.bridge)
        return f"Guard<{self.id}, enters={self.enter_count}, bridge={bridge_repr}>"


@dataclass(slots=True)
class Label:
    id: int
    enter_count: int = 0

    def __repr__(self):
        return f"Label<{self.id}, enters={self.enter_count}>"


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

ENTRY_COUNT_PAT = "entry (\d+):(\d+)"
ENTRY_COUNT_RE = re.compile(ENTRY_COUNT_PAT)

BRIDGE_COUNT_PAT = "bridge (\d+):(\d+)"
BRIDGE_COUNT_RE = re.compile(BRIDGE_COUNT_PAT)

LABEL_COUNT_PAT = "TargetToken\((\d+)\):(\d+)"
LABEL_COUNT_RE = re.compile(LABEL_COUNT_PAT)

def find_bridge(all_bridges: list[Bridge], from_guard: Guard):
    for bridge in all_bridges:
        if bridge.from_guard == from_guard.id:
            return bridge
    return None

def find_label_obj_via_label(all_nodes: list[Bridge | Trace], label: int):
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
    assert False, "Could not find entry trace"

def add_bridge_count(all_entries: list[Bridge], guard_id: int, count: int):
    for bridge in all_entries:
        if bridge.from_guard == guard_id:
            bridge.enter_count = count
            return
    assert False, "Could not find bridge trace"

def add_label_count(all_entries: list[Label], label_id: int, count: int):
    for label in all_entries:
        if label.id == label_id:
            label.enter_count = count
            return
    assert False, "Could not find label"


def compute_entry_counts(all_entries: list[Trace]):
    # Computed entry jump counts.
    # The algorithm just sums up all the labels in the middle of the trace
    # and considers them an entry.
    # The reason is to support loop peeling and not treat a peeled loop as a
    # separate trace (or maybe we should?)
    
    for entry in all_entries:
        seen: set[int] = set()

        queue = list(entry.bridges)
        while queue:
            nxt = queue.pop(0)
            if id(nxt) in seen:
                continue
            seen.add(id(nxt))
            for bridge in nxt.bridges:
                queue.append(bridge)


def find_previous_label(labels_or_guards, idx):
    while idx >= 0:
        thing = labels_or_guards[idx]
        idx -= 1
        if isinstance(thing, Label):
            return thing
    return None

def decide_sub_optimality_for_single_entry(entry: list[Trace | Bridge], working_set: list[Trace | Bridge]):
    """
    Decides if a trace is sub-optimal.

    The heuristic:
    If any bridge is entered more than 50% of the time, ie
    outflow / inflow >= 0.5

    Where outflow = how many times we enter the bridge
    inflow = how many times we enter the previous label

    We use entry count of the previous label as it's the number we have to the entry count
    *before* the bridge. Think about it: assuming no interrupts and random backedges into the trace,
    then the entry count before the bridge is just the count of the previous label since the control-flow
    is linear.
    """
    if not working_set:
        return
    for node in working_set:
        if isinstance(node, Bridge) or isinstance(node, Trace):
            node.is_suboptimal = False
            for idx, guard in enumerate(node.labels_and_guards):
                if isinstance(guard, Guard) and guard.bridge is not None:
                    print(guard)

                    bridge_entry_count = guard.bridge.enter_count
                    previous_label = find_previous_label(node.labels_and_guards, idx-1)
                    if previous_label is None:
                        previous_label = entry
                    inflow = previous_label.enter_count

                    if ((bridge_entry_count) / inflow) >= 0.5:
                        node.is_suboptimal = True
            decide_sub_optimality_for_single_entry(entry, node.labels_and_guards)



def reorder_subtree_to_decrease_suboptimality(all_nodes, node: Bridge | Trace | Label | Guard):
    # Trivial (base) case: this is a single node,
    # it is trivially optimal.
    if not node.labels_and_guards:
        return node
    # It's already non-suboptimal, nothing to do here.
    if not node.is_suboptimal:
        return node
    if isinstance(node, Label):
        return node
    if isinstance(node, Guard):
        return node
    

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

    # Greedy choice (decrease suboptimality): Now try swapping with the bridge that is most suboptimal
    worst_guard = None
    worst_bridge_pct = 0.0
    split = -1
    worst_bridge_remainder_count = -1
    for idx, label_or_guard in enumerate(node.labels_and_guards):
        assert isinstance(label_or_guard, Guard) or isinstance(label_or_guard, Label)
        if isinstance(label_or_guard, Guard) and label_or_guard.bridge is not None:
            bridge_entry_count = label_or_guard.bridge.enter_count
            previous_label = find_previous_label(node.labels_and_guards, idx-1)
            inflow = previous_label.enter_count 
            if ((bridge_entry_count) / inflow) >= worst_bridge_pct:
                worst_guard = label_or_guard
                split = idx
                worst_bridge_remainder_count = inflow - bridge_entry_count

    assert split != -1
    before_bridge_labels_and_guards = node.labels_and_guards[:split]
    after_bridge_labels_and_guards = node.labels_and_guards[split+1:]

    # Create the new alternative bridge from the rest of the existing trace.
    new_bridge = Bridge(
        worst_guard.id,
        f"swapped of {worst_guard.bridge.info}",
        labels_and_guards=after_bridge_labels_and_guards,
        jump=node.jump,
        computed_jump_obj=node.computed_jump_obj,
        enter_count=worst_bridge_remainder_count,
    )
    worst_guard = replace(worst_guard)
    worst_guard.enter_count = 0
    # Merge worst bridge with current trace.
    better_node = replace(node)
    better_node.labels_and_guards = before_bridge_labels_and_guards + [worst_guard] + worst_guard.bridge.labels_and_guards
    worst_guard.bridge = new_bridge    
    return better_node

def reorder_to_decrease_suboptimality(all_nodes, entries: list[Trace]):
    """
    Tries to swap the offending suboptimal bridge with the main trace to see if it makes things
    more optimal.
    """
    return [reorder_subtree_to_decrease_suboptimality(all_nodes, entry) for entry in entries]


def parse_and_build_trace_trees(inputfile):
    entries = []
    all_bridges = []
    all_labels = []
    with open(inputfile) as fp:
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
                        jump = int(jump_match.group(1))
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
                        jump = int(jump_match.group(1))
                assert jump is not None, f"No jump at end of bridge? {line}"
                all_bridges.append(Bridge(int(match.group(1), base=16), match.group(2), labels_and_guards, jump))
            elif "jit-backend-counts" in line:
                line = next(fp)
                while "jit-backend-counts" not in line:
                    if line.startswith("entry"):
                        entry = re.match(ENTRY_COUNT_RE, line)
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
                    guard.bridge = bridge

    # Match jumps to labels/traces
    for loop in entries + all_bridges:
        jump = loop.jump
        target_trace = find_label_obj_via_label(entries + all_bridges, jump)
        loop.computed_jump_obj = target_trace

    # compute_entry_counts(entries)
    for entry in entries:
        decide_sub_optimality_for_single_entry(entry, [entry])
    print("BEFORE")
    for entry in entries:
        print(entry)
    entries = reorder_to_decrease_suboptimality(entries + all_bridges, entries)
    # compute_entry_counts(entries)
    for entry in entries:
        decide_sub_optimality_for_single_entry(entry, [entry])
    print("AFTER")
    for entry in entries:
        print(entry)
import sys
parse_and_build_trace_trees(sys.argv[1])

