
# PYPYLOG=jit-log-opt,jit-summary,jit-backend-counts,jit-abort-log:temp 
# Good trace
hyperfine "/home/ken/Documents/GitHub/pypy/pypy/goal/pypy3.11-c --jit threshold=100080 src/test/bad_benchmark.py"
# Bad trace
hyperfine "/home/ken/Documents/GitHub/pypy/pypy/goal/pypy3.11-c --jit threshold=100090 src/test/bad_benchmark.py"