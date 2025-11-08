def foo(x, loops):
    x = 0
    for i in range(loops):
        if i < 3090:
            x = 1
        else:
            x = x + 2
        x = 0
    return x

print(foo(1, loops=100000000))