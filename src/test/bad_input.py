def foo(x, loops):
    x = 0
    for i in range(loops):
        if i < 100000:
            if x <= 1:
                x = 1
            else:
                x = 4
        else:
            x = x + 2
    return x

print(foo(1, loops=10000000))