#!/usr/bin/env python
"""
Pure-Python Implementation of the AES block-cipher.

Benchmark AES in CTR mode using the pyaes module.
"""

import pyaes

# 23,000 bytes
CLEARTEXT = b"This is a test. What could possibly go wrong? " * 500

# 128-bit key (16 bytes)
KEY = b'\xa1\xf6%\x8c\x87}_\xcd\x89dHE8\xbf\xc9,'


def bench_pyaes(loops):
    range_it = range(loops)
    for loops in range_it:
        aes = pyaes.AESModeOfOperationCTR(KEY)
        ciphertext = aes.encrypt(CLEARTEXT)

        # need to reset IV for decryption
        aes = pyaes.AESModeOfOperationCTR(KEY)
        plaintext = aes.decrypt(ciphertext)

        # explicitly destroy the pyaes object
        aes = None

    if plaintext != CLEARTEXT:
        raise Exception("decrypt error!")

    return None


from benchmark import Benchmark



class Aes(Benchmark):
    def inner_benchmark_loop(self, inner_iterations):
        bench_pyaes(inner_iterations)
        return True

    def benchmark(self):
        raise Exception("should never be reached")

    def verify_result(self, result):
        raise Exception("should never be reached")
    