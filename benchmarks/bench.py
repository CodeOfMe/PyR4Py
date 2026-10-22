#!/usr/bin/env python3
"""Benchmark the current backend: NumPy fast path vs pure-Python fallback.

python3 benchmarks/bench.py                 # auto (NumPy when installed)
PYRLANG_NO_NUMPY=1 python3 benchmarks/bench.py
"""

from __future__ import annotations

import random
import time

import PyRlang.vector as pv
from PyRlang import c, mean, sd, sort, sum, unique

N = 200_000
REPEAT = 3


def best_ms(fn):
    best = None
    for _ in range(REPEAT):
        t0 = time.perf_counter()
        fn()
        dt = time.perf_counter() - t0
        best = dt if best is None or dt < best else best
    return best * 1000.0


def main():
    backend = "NumPy" if pv._np is not None else "pure-Python"
    shuffled = list(range(1, N + 1))
    random.Random(42).shuffle(shuffled)  # sorting a presorted list flatters Timsort
    v = c(shuffled)
    ops = [
        ("v + v", lambda: v + v),
        ("v * 2.5", lambda: v * 2.5),
        ("v > 100000", lambda: v > 100000),
        ("mean(v)", lambda: mean(v)),
        ("sd(v)", lambda: sd(v)),
        ("sum(v)", lambda: sum(v)),
        ("sort(v)", lambda: sort(v)),
        ("unique(v)", lambda: unique(v)),
    ]
    print(f"backend: {backend}   N = {N:,}   best of {REPEAT}")
    total = 0.0
    for label, fn in ops:
        ms = best_ms(fn)
        total += ms
        print(f"  {label:>10}: {ms:8.2f} ms")
    print(f"  {'total':>10}: {total:8.2f} ms")


if __name__ == "__main__":
    main()
