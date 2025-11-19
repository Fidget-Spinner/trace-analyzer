import os
import time
import sys
import subprocess

def minimize():
    shapefile = "empty"
    prev_suboptimal_count = float('+inf')
    times = []
    suboptimal_counts = []
    seen_strcontent = set()
    for i in range(15):
        # write_to = f"{sys.argv[1]}_{i}"
        write_to = "scratch"
        write_to_serialized = f"{sys.argv[1]}_{i}_serialized"
        os.popen(f"PYPYLOG=jit-log-opt,jit-summary,jit-backend-counts,jit-abort-log:{write_to} ~/Documents/GitHub/pypy/pypy/goal/pypy3.11-c {sys.argv[1]}.py {shapefile} profile").readlines()
        contents = os.popen(f"~/Documents/GitHub/pypy/pypy/goal/pypy3.11-c {sys.argv[1]}.py {shapefile} run").readlines()
        os.system(f"pypy3 src/parser.py {write_to} before.txt after.txt {write_to_serialized}")
        with open("before.txt", "r") as fp:
            next_suboptimal_count = fp.read().count("SUBOPTIMAL")
        suboptimal_counts.append(next_suboptimal_count)
        # if next_suboptimal_count > prev_suboptimal_count:
        #     print("warning: Non monotonic")
            # break
        for line in contents:
            if line.startswith("TIME:"):
                tim = float(line[len("TIME:"):])
                print(i, next_suboptimal_count, tim)
                times.append(tim)
                break
        else:
            print("COULD NOT FIND TIME")
            assert False
        with open(shapefile, "r") as fp1:
            with open(write_to_serialized, "r") as fp2:
                str_contents_1 = fp1.read()
                str_contents_2 = fp2.read()
                if str_contents_1 == str_contents_2:
                    print("STABILIZED")
                    break
                if str_contents_2 in seen_strcontent:
                    print("REEPATING")
                    break
                seen_strcontent.add(str_contents_2)
        shapefile = write_to_serialized
    with open("stats.txt", "w") as fp:
        print(times, file=fp)
        print(suboptimal_counts, file=fp)
        most_suboptimal = max(suboptimal_counts)
        least_suboptimal = min(suboptimal_counts)
        print(f"Worst: {most_suboptimal}, {suboptimal_counts.index(most_suboptimal)}th", file=fp)
        print(f"Best: {least_suboptimal}, {suboptimal_counts.index(least_suboptimal)}th ", file=fp)
minimize()