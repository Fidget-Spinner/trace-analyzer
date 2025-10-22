from dataclasses import dataclass
import re
import textwrap

@dataclass(slots=True, frozen=True)
class Trace:
    id: int
    info: str
    labels: list[int]
    guards: list[int]
    bridges: list["Bridge"]

    def __repr__(self):
        res = []
        for bridge in self.bridges:
            res.append(repr(bridge))
        indented = textwrap.indent('\n'.join(res), '    ')
        return f"Trunk<{self.id}>\n{indented}"

@dataclass(slots=True, frozen=True)
class Bridge:
    from_guard: int 
    info: str
    labels: list[int]
    guards: list[int]    
    bridges: list["Bridge"]

    def __repr__(self):
        res = []
        for bridge in self.bridges:
            res.append(repr(bridge))
        indented = textwrap.indent('\n'.join(res), '    ')
        return f"Bridge<{self.from_guard}>\n{indented}"

HEX_PAT = "0x\w+"

LOOP_PAT = "# Loop (\d+) (.+)"
LOOP_RE = re.compile(LOOP_PAT)
END_LOOP_MARKER = "--end of the loop--"

LABEL_PAT = f".+label\(.+ descr=TargetToken\((\d+)\)\)"
LABEL_RE = re.compile(LABEL_PAT, re.IGNORECASE | re.MULTILINE)

GUARD_PAT = f".+guard_.+\(.*descr=<Guard({HEX_PAT})>.*\).*"
GUARD_RE = re.compile(GUARD_PAT)

BRIDGE_PAT = f"# bridge out of Guard ({HEX_PAT}) (.+)"
BRIDGE_RE = re.compile(BRIDGE_PAT)

def find_bridge(all_bridges: list[Bridge], from_guard: int):
    for bridge in all_bridges:
        if bridge.from_guard == from_guard:
            return bridge
    return None

def parse_and_build_trace_trees(inputfile):
    entries = []
    all_bridges = []
    with open(inputfile) as fp:
        for line in fp:
            if line.startswith("# Loop"):
                match = re.match(LOOP_RE, line)
                labels = []
                guards = []
                while END_LOOP_MARKER not in line:
                    line = next(fp)
                    if label_match := re.match(LABEL_RE, line.strip()):
                        labels.append(int(label_match.group(1)))
                    if guard_match := re.match(GUARD_RE, line.strip()):
                        guards.append(int(guard_match.group(1), base=16))
                entries.append(Trace(match.group(1), match.group(2), labels, guards, []))
            elif line.startswith("# bridge out of"):
                match = re.match(BRIDGE_RE, line)
                labels = []
                guards = []                
                while END_LOOP_MARKER not in line:
                    line = next(fp)
                    if label_match := re.match(LABEL_RE, line.strip()):
                        labels.append(int(label_match.group(1)))
                    if guard_match := re.match(GUARD_RE, line.strip()):
                        guards.append(int(guard_match.group(1), base=16))
                entries.append(Trace(match.group(1), match.group(2), labels, guards, []))                
                all_bridges.append(Bridge(int(match.group(1), base=16), match.group(2), labels, guards, []))
    # print(entries, all_bridges)
    # Finally, match labels to bridges.
    for loop in entries + all_bridges:
        for guard in loop.guards:
            if bridge := find_bridge(all_bridges, guard):
                loop.bridges.append(bridge)
    # print(all_bridges)
    for entry in entries:
        print(entry)

import sys
parse_and_build_trace_trees(sys.argv[1])

