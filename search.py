import os
import time
import sys
import subprocess

N_ITERS = 10

MAX_NO_PROGRESS_THRESHOLD = 8

MAX_LOOPS_SUPPORTED = 3000

NUM_OUTER_ITERATIONS = 20

def disable_turbo_boost():
    os.system('echo "1" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

def enable_turbo_boost():
    os.system('echo "0" | sudo tee /sys/devices/system/cpu/intel_pstate/no_turbo')

import time

# PYPY_PATH = "~/Documents/GitHub/pypy/pypy/goal/pypy3.11-c"
PYPY_PATH = sys.argv[1]

LOOP_FILENAME = "loops"
# EXTRA_OPTS = "--jit enable_opts=intbounds:rewrite:virtualize:string:pure:earlyforce:heap"
EXTRA_OPTS = f"--jit counterfile={LOOP_FILENAME}"



# add/subtract by this much from the loop file.
PERTURB_BY = 300

PYPY_DEFAULT_BRIDGE = 200
import random

def perturb(line, by):
    res = []
    for num in line.split(','):
        offset = random.choice(range(-by, by))
        res.append(f"{max(int(num) + offset, 1)}")
    return ",".join(res)


def mutate():
    with open(LOOP_FILENAME, "r") as fp:
        contents = fp.readlines()
        loop = contents[0]
        function = contents[1]
        bridges = contents[2]
    with open(LOOP_FILENAME, "w") as fp:
        fp.write(perturb(loop, PERTURB_BY))
        fp.write("\n")
        fp.write(perturb(function, PERTURB_BY))
        fp.write("\n")
        fp.write(perturb(bridges, PERTURB_BY // 4))
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
    # "Bounce": 1500, # too short
    "List": 1500,
    "Mandelbrot": 750,
    "NBody": 500000,
    "Permute": 1000,
    "Queens": 1000,
    "Sieve": 3000,
    "Storage": 1000,
    "Towers": 600,
    "Go": 1,
}

STATS_FILE = "stats.txt"
STATS_FILE_SORTED = "stats-sorted.txt"


def single_step(bench_name, inner_iterations, pypy_startup_time, best_time_so_far):
    BEST_LOOP_FILENAME = f"loops_best_{bench_name}"
    no_progress_counter = 0
    try:
        while True:
            start = time.time()
            os.system(f"{PYPY_PATH} {EXTRA_OPTS} -c 'pass'")
            end = time.time()
            pypy_startup_plus_readfile = end - start
            pypy_readfile_time = pypy_startup_plus_readfile - pypy_startup_time
            start = time.time()
            os.system(f"{PYPY_PATH} {EXTRA_OPTS} src/test/are-we-fast-yet/Python/harness.py {bench_name} {NUM_OUTER_ITERATIONS} {inner_iterations}")
            end = time.time()
            time_taken = end - start - pypy_readfile_time
            print(time_taken)
            if time_taken < best_time_so_far * 0.99:
                best_time_so_far = time_taken
                no_progress_counter = 0
                print(f"BETTER TIME FOUND: {best_time_so_far}")
                os.system(f"cp {LOOP_FILENAME} {BEST_LOOP_FILENAME}")
            else:
                no_progress_counter += 1
                if no_progress_counter >= MAX_NO_PROGRESS_THRESHOLD:
                    initialize_loopfile()
                    raise NoProgressException()
            mutate()
    except NoProgressException:
        # reset the loop to the best one, and start mutating from there.
        os.system(f"cp {BEST_LOOP_FILENAME} {LOOP_FILENAME}")
        mutate()
    return best_time_so_far

def minimize(bench_name, inner_iterations):
    best_time_so_far = float('+inf')
    print(bench_name)
    start = time.time()
    os.system(f"{PYPY_PATH} -c 'pass'")
    end = time.time()
    pypy_startup_time = end - start
    initialize_loopfile()
    for i in range(N_ITERS):
        print(i)
        best_time_so_far = single_step(bench_name, inner_iterations, pypy_startup_time, best_time_so_far)


def initialize_loopfile():
    with open(LOOP_FILENAME, "w") as fp:
        # pypy default loop counter
        fp.write(','.join([f"{1039}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")
        # pypy default function counter
        fp.write(','.join([f"{1619}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")
        # pypy default bridge counter
        fp.write(','.join([f"{PYPY_DEFAULT_BRIDGE}"] * MAX_LOOPS_SUPPORTED))
        fp.write("\n")

if __name__ == "__main__":
    try:
        # disable_turbo_boost()
        # Clear the file
        with open(STATS_FILE, "w") as fp:
            pass    
        for bench_name, inner_iterations in AWFY_BENCHMARKS.items():
            minimize(bench_name, inner_iterations)
        with open(STATS_FILE, "r") as fp:
            lines = fp.readlines()
            contents = [x.split(",") for x in lines]
            for t in contents:
                t[3] = float(t[3].strip())
            contents.sort(key=lambda a:a[3])
            for t in contents:
                t[3] = f"{t[3]:.2f}"
            with open(STATS_FILE_SORTED, "w") as fp:
                for line in contents:
                    fp.write(",".join(line) + "\n")
    finally:
        # enable_turbo_boost()
        pass