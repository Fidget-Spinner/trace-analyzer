import os
import time
import sys
import subprocess

N_ITERS = 50

MAX_NO_PROGRESS_THRESHOLD = 3

def disable_turbo_boost():
    os.system('echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

def enable_turbo_boost():
    os.system('echo "0" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

import time

PYPY_PATH = "~/Documents/GitHub/pypy-instrument/pypy/goal/pypy3.11-c"

# EXTRA_OPTS = "--jit enable_opts=intbounds:rewrite:virtualize:string:pure:earlyforce:heap"
EXTRA_OPTS = ""

class FoundBetterTime(Exception): pass

class SeenBefore(Exception): pass

def minimize():
    shapefile = "empty"
    prev_suboptimal_count = float('+inf')
    times = []
    suboptimal_counts = []
    seen_strcontent = set()
    best_time_so_far = float('+inf')
    best_shapefile = "empty"
    explored_fully = [False] * N_ITERS
    enable_turbo_boost()
    while not all(explored_fully):
        # find the first that has not been explored fully
        if False in explored_fully:
            i = explored_fully.index(False)
        else:
            # All fully epxlored
            break
        no_progress_counter = 0
        try:
            for _ in range(N_ITERS):
                # write_to = f"{sys.argv[1]}_{i}"
                write_to = f"scratch"
                write_to_serialized = f"{sys.argv[1]}_{i}_serialized"
                # mutate
                os.system(f"PYPYLOG=jit-log-opt,jit-summary,jit-backend-counts,jit-abort-log:{write_to} {PYPY_PATH} {EXTRA_OPTS} {sys.argv[1]}.py {shapefile} profile")
                os.system(f"pypy3 src/parser.py {write_to} before.txt after.txt {write_to_serialized}")
                with open("before.txt", "r") as fp:
                    next_suboptimal_count = fp.read().count("SUBOPTIMAL")
                suboptimal_counts.append(next_suboptimal_count)
                contents = os.popen(f'{PYPY_PATH} {EXTRA_OPTS} {sys.argv[1]}.py "{write_to_serialized}" run').readlines()
                for line in contents:
                    if line.startswith("TIME:"):
                        tim = float(line[len("TIME:"):])
                        print(i, tim)
                        shapefile = write_to_serialized
                        # beats our best time by 5%, use that serialized file.
                        if tim < (best_time_so_far * 0.95):
                            best_time_so_far = tim
                            best_shapefile = write_to_serialized
                            print("FOUND BETTER TIME")
                            raise FoundBetterTime()
                        else:
                            no_progress_counter += 1
                            if no_progress_counter > MAX_NO_PROGRESS_THRESHOLD:
                                print("NO PROGRESS")
                                # Restart search
                                best_shapefile = "empty"
                                raise FoundBetterTime()
                        break

                else:
                    print("COULD NOT FIND TIME")
                    assert False
                print(i, next_suboptimal_count)
                with open(shapefile, "r") as fp1:
                    with open(write_to_serialized, "r") as fp2:
                        str_contents_1 = fp1.read()
                        str_contents_2 = fp2.read()
                        if str_contents_2 in seen_strcontent:
                            print("SEEN BEFORE")
                            explored_fully[i] = True
                            raise SeenBefore()
                        seen_strcontent.add(str_contents_2)
        except FoundBetterTime:
            explored_fully[i] = True  
            shapefile = best_shapefile
        except SeenBefore:
            break
            

    write_to_serialized = f"empty"
    contents = os.popen(f"{PYPY_PATH} {EXTRA_OPTS} {sys.argv[1]}.py {write_to_serialized} run").readlines()
    for line in contents:
        if line.startswith("TIME:"):
            tim = float(line[len("TIME:"):])
            print("empty", tim)
            times.append(tim)
            break
    else:
        print("COULD NOT FIND TIME")
        assert False
    for x in range(i):
        write_to_serialized = f"{sys.argv[1]}_{x}_serialized"
        contents = os.popen(f'{PYPY_PATH} {EXTRA_OPTS} {sys.argv[1]}.py "{write_to_serialized}" run').readlines()
        for line in contents:
            if line.startswith("TIME:"):
                tim = float(line[len("TIME:"):])
                print(x, tim)
                times.append(tim)
                break
        else:
            print("COULD NOT FIND TIME")
            assert False
    with open("stats.txt", "w") as fp:
        print(times, file=fp)
        print(suboptimal_counts, file=fp)
        most_suboptimal = max(suboptimal_counts)
        least_suboptimal = min(suboptimal_counts)
        print(f"Worst: {most_suboptimal}, {suboptimal_counts.index(most_suboptimal)}th", file=fp)
        print(f"Best: {least_suboptimal}, {suboptimal_counts.index(least_suboptimal)}th ", file=fp)

try:
    minimize()
finally:
    enable_turbo_boost()