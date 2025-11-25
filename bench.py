import os
import time
import sys
import subprocess

N_ITERS = 30

from search import AWFY_BENCHMARKS, AVERAGE_PAT

PYPY_PATH = sys.argv[1]

BENCH_FILE = "bench.txt"
BENCH_FILE_SORTED = "bench-sorted.txt"

def bench(bench_name, inner_iterations):
    BEST_LOOP_FILENAME = f"loops_best_{bench_name}"
    EXTRA_OPTS = f"--jit counterfile={BEST_LOOP_FILENAME}"
    best_loopfile_timings = []
    for _ in range(N_ITERS):
        contents = os.popen(f"{PYPY_PATH} {EXTRA_OPTS} src/test/are-we-fast-yet/Python/harness.py {bench_name} 10 {inner_iterations}").readlines()
        last_iteration = None
        for line in contents:
            if line.strip().startswith(f"{bench_name}: iterations="):
                last_iteration = line
        assert last_iteration is not None
        print(last_iteration)
        match = AVERAGE_PAT.match(last_iteration)
        time_taken = float(match.group(1))
        best_loopfile_timings.append(time_taken)

    default_pypy_timings = []
    for _ in range(N_ITERS):
        # Note: no extra opts here, so it's just default pypy!
        contents = os.popen(f"{PYPY_PATH} src/test/are-we-fast-yet/Python/harness.py {bench_name} 10 {inner_iterations}").readlines()
        last_iteration = None
        for line in contents:
            if line.strip().startswith(f"{bench_name}: iterations="):
                last_iteration = line
        assert last_iteration is not None
        print(last_iteration)
        match = AVERAGE_PAT.match(last_iteration)
        time_taken = float(match.group(1))
        default_pypy_timings.append(time_taken)
    low_best, high_best = confidence_interval(best_loopfile_timings, confidence=0.99)
    low_default, high_default = confidence_interval(default_pypy_timings, confidence=0.99)

    best_mean = sum(best_loopfile_timings) / N_ITERS
    default_mean = sum(default_pypy_timings) / N_ITERS

    reduction = ((best_mean - default_mean) / default_mean * 100)
    probably_significant = not ((low_best < default_mean < high_best) or (low_default < best_mean < high_default))
    with open(BENCH_FILE, "a") as fp:
        fp.write(f"{bench_name},{default_mean} ({low_default:.2f}--{high_default:.2f}),{best_mean:.2f} ({low_best:.2f}--{high_best:.2f}),{reduction:.2f},{probably_significant}\n")


from statistics import NormalDist

# Credits to https://stackoverflow.com/questions/15033511/compute-a-confidence-interval-from-sample-data
def confidence_interval(data, confidence=0.99):
    dist = NormalDist.from_samples(data)
    z = NormalDist().inv_cdf((1 + confidence) / 2.)
    h = dist.stdev * z / ((len(data) - 1) ** .5)
    return dist.mean - h, dist.mean + h

if __name__ == "__main__":
    try:
        # disable_turbo_boost()
        # Clear the file
        with open(BENCH_FILE, "w") as fp:
            pass    
        for bench_name, inner_iterations in AWFY_BENCHMARKS.items():
            bench(bench_name, inner_iterations)
        with open(BENCH_FILE, "r") as fp:
            lines = fp.readlines()
            contents = [x.split(",") for x in lines]
            for t in contents:
                t[3] = float(t[3].strip())
            contents.sort(key=lambda a:a[3])
            for t in contents:
                t[3] = f"{t[3]:.2f}"
            with open(BENCH_FILE_SORTED, "w") as fp:
                for line in contents:
                    fp.write(",".join(line) + "\n")            
    finally:
        # enable_turbo_boost()
        pass