import os
import time
import sys
import subprocess

N_ITERS = 25

MAX_NO_PROGRESS_THRESHOLD = 5

MAX_LOOPS_SUPPORTED = 30000

def disable_turbo_boost():
    os.system('echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

def enable_turbo_boost():
    os.system('echo "0" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

import time

PYPY_PATH = "~/Documents/GitHub/pypy/pypy/goal/pypy3.11-c"

LOOP_FILENAME = "loops"
# EXTRA_OPTS = "--jit enable_opts=intbounds:rewrite:virtualize:string:pure:earlyforce:heap"
EXTRA_OPTS = f"--jit counterfile={LOOP_FILENAME}"



# add/subtract by this much from the loop file.
PERTURB_BY = 1039

import random

def perturb_by(line):
    res = []
    for num in line.split(','):
        offset = random.choice(range(-PERTURB_BY, PERTURB_BY))
        res.append(f"{max(int(num) + offset, 1)}")
    return ",".join(res)


def mutate():
    with open(LOOP_FILENAME, "r") as fp:
        contents = fp.readlines()
        loop = contents[0]
        function = contents[1]
        bridges = contents[2]
    with open(LOOP_FILENAME, "w") as fp:
        fp.write(perturb_by(loop))
        fp.write("\n")
        fp.write(perturb_by(function))
        fp.write("\n")
        fp.write(perturb_by(bridges))
        fp.write("\n")   

import re
AVERAGE_PAT = re.compile(f".+ average: (\d+)")

class NoProgressException(Exception): pass

AWFY_BENCHMARKS = {
    "DeltaBlue": 12000,
    "Richards": 100,
    "Json": 100,
    "CD": 250,
    "Havlak": 1500,
    "Bounce": 1500,
    "List": 1500,
    "Mandelbrot": 500,
    "NBody": 250000,
    "Permute": 1000,
    "Queens": 1000,
    "Sieve": 3000,
    "Storage": 1000,
    "Towers": 600,
    "Go": 1,
}

STATS_FILE = "stats.txt"

def minimize(bench_name, inner_iterations):
    best_time_so_far = float('+inf')
    BEST_LOOP_FILENAME = f"loops_best_{bench_name}"
    for i in range(N_ITERS):
        print(i)
        no_progress_counter = 0
        try:
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
                if time_taken < best_time_so_far * 0.96:
                    best_time_so_far = time_taken
                    print(f"BETTER TIME FOUND: {best_time_so_far}")
                    os.system(f"cp {LOOP_FILENAME} {BEST_LOOP_FILENAME}")
                else:
                    no_progress_counter += 1
                    if no_progress_counter >= MAX_NO_PROGRESS_THRESHOLD:
                        raise NoProgressException()
                mutate()
        except NoProgressException:
            # reset the loop to the best one, and start mutating from there.
            os.system(f"cp {BEST_LOOP_FILENAME} {LOOP_FILENAME}")
            mutate()
    with open(STATS_FILE, "a") as fp:
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
        pct_reduction = (best_time_so_far - time_taken) / time_taken * 100
        fp.write(f"{bench_name},{time_taken},{best_time_so_far},{pct_reduction}")



def initialize_loopfile():
    with open(LOOP_FILENAME, "w") as fp:
        fp.write(','.join([f"{PERTURB_BY}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")
        fp.write(','.join([f"{PERTURB_BY}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")
        fp.write(','.join([f"{PERTURB_BY}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")
try:
    disable_turbo_boost()
    # Clear the file
    with open(STATS_FILE, "w") as fp:
        pass    
    for bench_name, inner_iterations in AWFY_BENCHMARKS.items():
        initialize_loopfile()
        minimize(bench_name, inner_iterations)
finally:
    enable_turbo_boost()