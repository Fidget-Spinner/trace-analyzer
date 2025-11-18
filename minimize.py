import os
import time
import sys

def minimize():
    shapefile = "empty"
    prev_suboptimal_count = float('+inf')
    times = []
    suboptimal_counts = []
    for i in range(15):
        write_to = f"{sys.argv[1]}_{i}"
        write_to_serialized = f"{sys.argv[1]}_{i}_serialized"
        start = time.time()
        os.system(f"PYPYLOG=jit-log-opt,jit-summary,jit-backend-counts,jit-abort-log:{write_to} ~/Documents/GitHub/pypy/pypy/goal/pypy3.11-c {sys.argv[1]}.py {shapefile}")
        end = time.time()
        times.append(end - start)
        os.system(f"pypy3 src/parser.py {write_to} before.txt after.txt {write_to_serialized}")
        with open("before.txt", "r") as fp:
            next_suboptimal_count = fp.read().count("SUBOPTIMAL")
        suboptimal_counts.append(next_suboptimal_count)
        # if next_suboptimal_count > prev_suboptimal_count:
        #     print("warning: Non monotonic")
            # break
        prev_suboptimal_count = next_suboptimal_count
        with open(shapefile, "r") as fp1:
            with open(write_to_serialized, "r") as fp2:
                str_contents_1 = fp1.read()
                str_contents_2 = fp2.read()
                if str_contents_1 == str_contents_2:
                    print("STABILIZED")
                    break
        shapefile = write_to_serialized
    print(suboptimal_counts)
    most_suboptimal = max(suboptimal_counts)
    least_suboptimal = min(suboptimal_counts)
    print(f"Worst: {most_suboptimal}, {suboptimal_counts.index(most_suboptimal)}th")
    print(f"Best: {least_suboptimal}, {suboptimal_counts.index(least_suboptimal)}th ")
minimize()