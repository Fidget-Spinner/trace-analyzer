import pypyjit
import sys
pypyjit.set_param(shapefile=sys.argv[1])
# pypyjit.set_param(shapefile="empty")
def foo(x, loops):
    x = 0
    for i in range(loops):
        if i < 100000:
            x = 1
        else:
            x = x + 2
    return x


foo(1, loops=200000000)

import time
start = time.time()
foo(1, loops=200000000)
end = time.time()
print(f"{end - start}")
