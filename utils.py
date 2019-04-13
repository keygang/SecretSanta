import random


def rand_id(n=16):
    random_id = ''
    for i in range(n):
        random_id += str(hex(random.randint(0, 16)))[2:]
    return random_id
