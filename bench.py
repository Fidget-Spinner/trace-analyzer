import os
import time
import sys
import subprocess

N_ITERS = 30

from search import AWFY_BENCHMARKS, AVERAGE_PAT, NUM_OUTER_ITERATIONS

PYPY_PATH = sys.argv[1]

BENCH_FILE = "bench.txt"
BENCH_FILE_SORTED = "bench-sorted.txt"

def bench(bench_name, inner_iterations):
    print(bench_name)
    BEST_LOOP_FILENAME = f"loops_best_{bench_name}"
    EXTRA_OPTS = f"--jit counterfile={BEST_LOOP_FILENAME}"
    best_loopfile_timings = []
    for _ in range(N_ITERS):
        start = time.time()
        os.system(f"{PYPY_PATH} -c 'pass'")
        end = time.time()
        pypy_startup_time = end - start
        start = time.time()
        os.system(f"{PYPY_PATH} {EXTRA_OPTS} -c 'pass'")
        end = time.time()
        pypy_startup_plus_readfile = end - start
        pypy_readfile_time = pypy_startup_plus_readfile - pypy_startup_time
        start = time.time()
        os.system(f"{PYPY_PATH} {EXTRA_OPTS} src/test/are-we-fast-yet/Python/harness.py {bench_name} {NUM_OUTER_ITERATIONS} {inner_iterations}")
        end = time.time()
        time_taken = end - start - pypy_readfile_time
        best_loopfile_timings.append(time_taken)

    default_pypy_timings = []
    for _ in range(N_ITERS):
        start = time.time()
        # Note: no extra opts here, so it's just default pypy!
        os.system(f"{PYPY_PATH} src/test/are-we-fast-yet/Python/harness.py {bench_name} {NUM_OUTER_ITERATIONS} {inner_iterations}")
        end = time.time()
        time_taken = end - start
        default_pypy_timings.append(time_taken)
    best_mean, low_best, high_best = confidence_interval(best_loopfile_timings, confidence=0.99)
    default_mean, low_default, high_default = confidence_interval(default_pypy_timings, confidence=0.99)

    reduction = ((best_mean - default_mean) / default_mean * 100)
    probably_significant = not (high_best >= low_default and high_default  >= low_best)
    with open(BENCH_FILE, "a") as fp:
        fp.write(f"{bench_name},{default_mean:.2f} (±{(high_default-low_default):.2f}),{best_mean:.2f} (±{(high_best - low_best):.2f}),{reduction:.2f},{probably_significant}\n")

from statistics import NormalDist

# Credits to https://stackoverflow.com/questions/15033511/compute-a-confidence-interval-from-sample-data
def confidence_interval(data, confidence=0.99):
    dist = NormalDist.from_samples(data)
    z = NormalDist().inv_cdf((1 + confidence) / 2.)
    h = dist.stdev * z / ((len(data) - 1) ** .5)
    return dist.mean, dist.mean - h, dist.mean + h

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