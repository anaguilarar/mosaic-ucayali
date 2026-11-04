"""Run a command under a memory watch: log peak memory, stop it cleanly if the machine runs short.

Samples every 2 s the resident memory of the command (with its children) and the system's available memory.
If available memory stays below --min-free-gb for 3 samples in a row, the command is terminated (finished
blocks of step 20 stay cached, so a re-run resumes) and memwatch exits with code 99.
Writes one summary line, and a sample line whenever the command's peak grows by >= 256 MB.

Usage:  python scripts/memwatch.py [--min-free-gb 4] [--log FILE] -- <command ...>
"""
import argparse
import subprocess
import sys
import time

import psutil


def rss(p):
    tot = 0
    for q in [p] + p.children(recursive=True):
        try:
            tot += q.memory_info().rss
        except psutil.Error:
            pass
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-free-gb", type=float, default=4.0)
    ap.add_argument("--log")
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    cmd = a.cmd[1:] if a.cmd and a.cmd[0] == "--" else a.cmd
    log = open(a.log, "a", encoding="utf-8") if a.log else sys.stdout

    def say(msg):
        print(f"[{time.strftime('%H:%M:%S')}] memwatch {msg}", file=log, flush=True)

    t0 = time.time()
    proc = subprocess.Popen(cmd)
    p = psutil.Process(proc.pid)
    peak = last = 0; low_free = 1e18; low = 0; stopped = False
    while proc.poll() is None:
        try:
            m = rss(p)
        except psutil.Error:
            break
        free = psutil.virtual_memory().available
        low_free = min(low_free, free)
        if m > peak:
            peak = m
            if peak - last >= 256 * 2**20:
                say(f"peak {peak / 2**30:.2f} GB (free {free / 2**30:.1f} GB)"); last = peak
        low = low + 1 if free < a.min_free_gb * 2**30 else 0
        if low >= 3:
            say(f"free memory {free / 2**30:.1f} GB < {a.min_free_gb} GB: stopping the run cleanly")
            for q in p.children(recursive=True) + [p]:
                try:
                    q.terminate()
                except psutil.Error:
                    pass
            stopped = True
            proc.wait(60)
            break
        time.sleep(2)
    rc = 99 if stopped else proc.wait()
    say(f"exit {rc} after {(time.time() - t0) / 60:.1f} min | peak {peak / 2**30:.2f} GB | "
        f"lowest free {low_free / 2**30:.1f} GB | {' '.join(cmd[-6:])}")
    sys.exit(rc)


if __name__ == "__main__":
    main()
