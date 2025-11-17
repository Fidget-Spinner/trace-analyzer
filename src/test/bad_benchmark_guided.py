import pypyjit
pypyjit.set_param(shapefile="./src/test/bad_benchmark_guided_serialized")
# pypyjit.set_param(shapefile="empty")
def foo(x, loops):
    x = 0
    for i in range(loops):
        if i < 100000:
            x = 1
        else:
            x = x + 2
    return x


foo(1, loops=2000000000)

import time
start = time.time()
foo(1, loops=2000000000)
end = time.time()
print(f"{end - start}")
