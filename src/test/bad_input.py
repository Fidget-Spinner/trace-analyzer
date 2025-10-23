def foo(x, loops):
    x = 0
    for i in range(loops):
        if i < 100000:
            x = x + 1
        else:
            x = x + 2
    return x

print(foo(1, loops=10000000))