def foo(x, loops):
    x = 0
    for i in range(loops):
        # Uncommon branch
        if i % 654:
            x = i + 10
        else:
            x = i + 1
    return x

print(foo(1, loops=10000000))