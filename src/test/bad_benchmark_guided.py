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

if sys.argv[2] != "profile":
    pypyjit.set_param(shapefile="empty")
    import time
    start = time.time()
    foo(1, loops=200000000)
    end = time.time()
    print(f"TIME:{end - start}")
