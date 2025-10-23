from dataclasses import dataclass
import re
import textwrap

@dataclass(slots=True)
class Trace:
    id: int
    info: str
    labels: list["Label"]
    guards: list[int]
    bridges: list["Bridge"]

    # Terminator.
    jump: int

    # Note: this is BACKEDGE (right before jump) count.
    reported_back_count: int = -1
    
    # This takes into account loop peeling along with the reported back count.
    # The problem is that a peeled loop has 2 jumps back. So to accurately report it,
    # we must sum up the jumps.
    computed_back_count: int = 0

    # This is how many times we enter this trace.
    # It is computed from other trace's back counts.
    computed_enter_count: int = 0

    computed_jump_obj: "Trace | Bridge" = None

    # Points back to the parent trace (if any).
    _backpointer: "Trace | Bridge" = None

    is_suboptimal: bool = False

    def __repr__(self):
        res = []
        for bridge in self.bridges:
            res.append(repr(bridge))
        indented = textwrap.indent('\n'.join(res), '    ')
        pct_completed = self.computed_back_count / self.computed_enter_count * 100
        suboptimality_trailer = " <--- SUBOPTIMAL!" if self.is_suboptimal else ""
        return f"Trunk<{self.id}, backedge={self.computed_back_count}, enter_count={self.computed_enter_count}, \
pct_completed={pct_completed:.2f}%>{suboptimality_trailer}\n{indented}"

@dataclass(slots=True)
class Bridge:
    from_guard: int 
    info: str
    labels: list["Label"]
    guards: list[int]    
    bridges: list["Bridge"]

    # Terminator.
    jump: int

    # Note: this is end of trace count. Usually that also corresponds
    # to a backedge.
    reported_back_count: int = -1


    # This is how many times we enter this trace.
    # It is computed from other trace's back counts.
    computed_enter_count: int = 0

    computed_jump_obj: "Trace | Bridge" = None

    # Points back to the parent trace (if any).
    _backpointer: "Trace | Bridge" = None

    is_suboptimal: bool = False

    def __repr__(self):
        res = []
        for bridge in self.bridges:
            res.append(repr(bridge))
        indented = textwrap.indent('\n'.join(res), '    ')
        pct_completed = self.reported_back_count / self.computed_enter_count * 100
        suboptimality_trailer = " <--- SUBOPTIMAL!" if self.is_suboptimal else ""        
        return f"Bridge<{self.from_guard}, backedge={self.reported_back_count}, enter_count={self.computed_enter_count} \
pct_completed={pct_completed:.2f}%>{suboptimality_trailer}\n{indented}"

@dataclass(slots=True)
class Label:
    id: int
    reported_enter_count: int = 0

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

def find_bridge(all_bridges: list[Bridge], from_guard: int):
    for bridge in all_bridges:
        if bridge.from_guard == from_guard:
            return bridge
    return None

def find_trace_via_label(all_nodes: list[Bridge | Trace], label: int):
    for node in all_nodes:
        if label in [label.id for label in node.labels]:
            return node
    assert False, "No corresponding node for label?"

def add_entry_count(all_entries: list[Trace], entry_id: int, count: int):
    for entry in all_entries:
        if entry.id == entry_id:
            entry.reported_back_count = count
            return
    assert False, "Could not find entry trace"

def add_bridge_count(all_entries: list[Bridge], guard_id: int, count: int):
    for bridge in all_entries:
        if bridge.from_guard == guard_id:
            bridge.reported_back_count = count
            return
    assert False, "Could not find bridge trace"

def add_label_count(all_entries: list[Label], label_id: int, count: int):
    for label in all_entries:
        if label.id == label_id:
            label.reported_enter_count = count
            return
    assert False, "Could not find label"


def compute_entry_counts(all_entries: list[Trace]):
    # Computed entry jump counts.
    # The algorithm is based on as simple idea: for very backwards jump occured in the trunk,
    # then add one to entry count, as it must have entered the trunk for it to jump backwards.
    # For every backward jump occured in a side trace, add one to entry count of the trunk, for similar reasons.
    # As this is a trace tree, do this in bottom-up order (reverse postorder) to get the correct numbers.

    # Do a reverse breadth-first traversal first.
    for entry in all_entries:
        # the last label is the backward jump of a loop.
        # this deals with peeled iterations.
        entry.computed_back_count += entry.labels[-1].reported_enter_count
        # all labels pointing to this trace with a count must mean it's entering this trace.
        for lab in entry.labels:
            entry.computed_enter_count += lab.reported_enter_count
        queue = list(entry.bridges)
        order = []
        while queue:
            nxt = queue.pop(0)
            order.append(nxt)
            for bridge in nxt.bridges:
                bridge._backpointer = nxt
                queue.append(bridge)
        order.reverse()

        # Note: we don't care about peeled iterations here, as they
        # are later summed into one anyways. Ie if you enter into the middle of
        # another trace, we just treat it as an entry.
        for node in order:
            node.computed_enter_count += node.reported_back_count
            if node._backpointer:
                node._backpointer.computed_enter_count += node.computed_enter_count

def decide_sub_optimality(all_nodes: list[Trace | Bridge]):
    """
    Decides if a trace is sub-optimal.

    The heuristic:
    If a bridge is entered more times than its trunk trace's backedge, it's suboptimal.
    """
    for node in all_nodes:
        for bridge in node.bridges:
            if bridge.computed_enter_count > node.computed_back_count:
                node.is_suboptimal = True

def parse_and_build_trace_trees(inputfile):
    entries = []
    all_bridges = []
    all_labels = []
    with open(inputfile) as fp:
        for line in fp:
            if line.startswith("# Loop"):
                match = re.match(LOOP_RE, line)
                labels = []
                guards = []
                jump = None
                while END_LOOP_MARKER not in line:
                    line = next(fp)
                    if label_match := re.match(LABEL_RE, line.strip()):
                        labels.append(Label(int(label_match.group(1))))
                    if guard_match := re.match(GUARD_RE, line.strip()):
                        guards.append(int(guard_match.group(1), base=16))
                    if jump_match := re.match(JUMP_RE, line.strip()):
                        jump = int(jump_match.group(1))
                assert jump is not None, f"No jump at end of loop? {line}"
                all_labels.extend(labels)
                entries.append(Trace(int(match.group(1)), match.group(2), labels, guards, [], jump))
            elif line.startswith("# bridge out of"):
                match = re.match(BRIDGE_RE, line)
                labels = []
                guards = []                
                while END_LOOP_MARKER not in line:
                    line = next(fp)
                    if label_match := re.match(LABEL_RE, line.strip()):
                        labels.append(Label(int(label_match.group(1))))
                    if guard_match := re.match(GUARD_RE, line.strip()):
                        guards.append(int(guard_match.group(1), base=16))
                    if jump_match := re.match(JUMP_RE, line.strip()):
                        jump = int(jump_match.group(1))
                assert jump is not None, f"No jump at end of bridge? {line}"
                all_labels.extend(labels)
                all_bridges.append(Bridge(int(match.group(1), base=16), match.group(2), labels, guards, [], jump))
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
    for loop in entries + all_bridges:
        for guard in loop.guards:
            if bridge := find_bridge(all_bridges, guard):
                loop.bridges.append(bridge)
    # Match jumps to labels/traces
    for loop in entries + all_bridges:
        jump = loop.jump
        target_trace = find_trace_via_label(entries + all_bridges, jump)
        loop.computed_jump_obj = target_trace

    compute_entry_counts(entries)
    decide_sub_optimality(entries)
    for entry in entries:
        print(entry)

import sys
parse_and_build_trace_trees(sys.argv[1])

