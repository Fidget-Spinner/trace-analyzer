
# PYPYLOG=jit-log-opt,jit-summary,jit-backend-counts,jit-abort-log:temp 
# Good trace
hyperfine "/home/ken/Documents/GitHub/cpython_tracing_jit_pgo_tc_2/python src/test/good_benchmark_cpython.py"
# Bad trace
hyperfine "/home/ken/Documents/GitHub/cpython_tracing_jit_pgo_tc_2/python src/test/bad_benchmark_cpython.py"