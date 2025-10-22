import random

random.seed(0)


def foo(x, loops):
    prob = 0.5
    for i in range(loops):
        if random.random() <= prob:
            x = x + i + 3
        else:
            x = x + 3
        if random.random() <= prob:
            x = x + i + 3
        else:
            x = x + 3
        # if random.random() <= 0.5:
        #     x = x + 1
        # else:
        #     x = x + 2
    return x

print(foo(1, loops=10000000))