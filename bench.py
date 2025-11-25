import os
import time
import sys
import subprocess

N_ITERS = 30

from search import AWFY_BENCHMARKS, AVERAGE_PAT

PYPY_PATH = sys.argv[1]

BENCH_FILE = "bench.txt"

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
    best_ci = confidence_interval(best_loopfile_timings, confidence=0.99)
    default_ci = confidence_interval(default_pypy_timings, confidence=0.99)

    best_mean = sum(best_loopfile_timings) / N_ITERS
    default_mean = sum(default_pypy_timings) / N_ITERS

    with open(BENCH_FILE, "a") as fp:
        fp.write(f"{bench_name}, {default_mean} {default_ci}, {best_mean} {best_ci}, {((best_mean - default_mean) / default_mean * 100):.2f} \n")


from statistics import NormalDist

# Credits to https://stackoverflow.com/questions/15033511/compute-a-confidence-interval-from-sample-data
def confidence_interval(data, confidence=0.99):
    dist = NormalDist.from_samples(data)
    z = NormalDist().inv_cdf((1 + confidence) / 2.)
    h = dist.stdev * z / ((len(data) - 1) ** .5)
    return f"({dist.mean - h:.2f}--{dist.mean + h:.2f})"

if __name__ == "__main__":
    try:
        # disable_turbo_boost()
        # Clear the file
        with open(BENCH_FILE, "w") as fp:
            pass    
        for bench_name, inner_iterations in AWFY_BENCHMARKS.items():
            bench(bench_name, inner_iterations)
    finally:
        # enable_turbo_boost()
        pass