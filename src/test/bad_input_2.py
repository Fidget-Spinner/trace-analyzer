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

print(foo(1, loops=10000000))