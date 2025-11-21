import pypyjit
import sys
# pypyjit.set_param(shapefile="./src/test/bad_benchmark_2_guided_gold")
# pypyjit.set_param(shapefile="empty")
pypyjit.set_param(shapefile=sys.argv[1])
# pypyjit.set_param(shapefile="./src/test/bad_benchmark_2_guided_2_serialized")
def foo(x, loops):
    x = 0
    y = 0
    for i in range(loops):
        if y % 10 == 0:
            x = x + 3
        else:
            x = x + 4
            if y < 100000:
                x = x + 3
            else:
                x = x + 4
        y = y + 1
    return x

print(foo(1, loops=500000000))


if sys.argv[2] != "profile":
    pypyjit.set_param(shapefile="empty")
    import time
    start = time.time()
    foo(1, loops=500000000)
    end = time.time()
    print(f"TIME:{end-start}")