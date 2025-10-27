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


def decide_sub_optimality(all_nodes: list[Trace | Bridge], working_set: list[Trace | Bridge]):
    """
    Decides if a trace is sub-optimal.

    The heuristic:
    If any bridge is entered more than 50% of the time, ie
    (inflow - outflow) / inflow >= 0.5
    """
    if not working_set:
        return
    for node in working_set:
        if isinstance(node, Bridge) or isinstance(node, Trace):
            node.is_suboptimal = False
            for guard in node.labels_and_guards:
                if isinstance(guard, Guard):
                    # Guard has no bridge out. Great!
                    if guard.bridge is None:
                        continue

                    bridge_entry_count = guard.bridge.enter_count
                    corresponding_label = find_bridge_via_label(all_nodes, guard.id)
                    label_exit_count = corresponding_label.enter_count

                    if ((bridge_entry_count - label_exit_count) / bridge_entry_count) >= 0.5:
                        node.is_suboptimal = True
            decide_sub_optimality(all_nodes, node.labels_and_guards)


def reorder_subtree_to_decrease_suboptimality(node: Bridge | Trace):
    # Trivial (base) case: this is a single node,
    # it is trivially optimal.
    if not node.bridges:
        return node
    # It's already non-suboptimal, nothing to do here.
    if not node.is_suboptimal:
        return node
    
    node = replace(node)
    # Recurse in on the sub-traces to make them optimal first.
    node.bridges = [reorder_subtree_to_decrease_suboptimality(bridge) for bridge in node.bridges]
        
    # Greedy choice (decrease suboptimality): Now try swapping with the bridge that is most suboptimal
    worst_bridge = max(node.bridges, key=lambda b: b.computed_enter_count - node.computed_back_count)
    split = -1
    for split, label in enumerate(node.labels):
        if worst_bridge.from_guard == label.id:
            break
    assert split != -1
    before_bridge_labels = node.labels[:split]
    before_bridge_guards = node.guards[:split]
    before_bridge_bridges = node.bridges[:split]
    after_bridge_labels = node.labels[split:]
    after_bridge_guards = node.guards[split:]
    after_bridge_bridges = node.bridges[split+1:]

    # Create the new alternative bridge from the rest of the existing trace.
    new_bridge = Bridge(
        worst_bridge.from_guard,
        f"swapped of {worst_bridge.info}",
        labels=after_bridge_labels,
        guards=after_bridge_guards,
        bridges=after_bridge_bridges,
        jump=node.jump,
        computed_jump_obj=node.computed_jump_obj,
        reported_back_count=node.computed_back_count
    )
    # Merge worst bridge with current trace.
    better_node = replace(node)
    better_node.labels = before_bridge_labels + worst_bridge.labels
    better_node.guards = before_bridge_guards + worst_bridge.guards
    better_node.bridges = before_bridge_bridges + [new_bridge] + worst_bridge.bridges
    better_node.reported_back_count = worst_bridge.reported_back_count
    better_node.computed_enter_count += worst_bridge.computed_enter_count
    better_node.computed_back_count = worst_bridge.computed_back_count


    return better_node

def reorder_to_decrease_suboptimality(entries: list[Trace]):
    """
    Tries to swap the offending suboptimal bridge with the main trace to see if it makes things
    more optimal.
    """
    return [reorder_subtree_to_decrease_suboptimality(entry) for entry in entries]


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
    # TODO recursive descent this.
    for entry in entries:
        for guard in entry.labels_and_guards:
            if isinstance(guard, Guard):
                if bridge := find_bridge(all_bridges, guard):
                    print
                    guard.bridge = bridge
                
    # Match jumps to labels/traces
    for loop in entries + all_bridges:
        jump = loop.jump
        target_trace = find_label_obj_via_label(entries + all_bridges, jump)
        loop.computed_jump_obj = target_trace

    # compute_entry_counts(entries)
    decide_sub_optimality(entries + all_bridges, entries + all_bridges)
    print("BEFORE")
    for entry in entries:
        print(entry)
    # entries = reorder_to_decrease_suboptimality(entries)
    # # compute_entry_counts(entries)
    # decide_sub_optimality(entries, entries + all_bridges)
    # print("AFTER")
    # for entry in entries:
    #     print(entry)
import sys
parse_and_build_trace_trees(sys.argv[1])

