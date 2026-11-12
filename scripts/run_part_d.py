#!/usr/bin/env python3

"""
Repeatable performance experiments for OOPD Assignment 3, Part D.

Experiments:
D1 - Strong scaling
D2 - Weak scaling
D3 - Chunk count, grid divisions, small-grid overhead
D4 - Parallelism within a run vs across runs
D5 - Hiding snapshot I/O time

Each measurement is repeated at least five times by default.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time

from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]

BUILD_DIR = ROOT / "build-partd"
BINARY = BUILD_DIR / "PandemicSimulation"

OUT_DIR = ROOT / "results" / "part_d"

REPEATS = int(os.environ.get("PART_D_REPEATS", "5"))

FIELDS = [
    "section",
    "repeat",
    "threads",
    "chunks",
    "division",
    "mode",
    "grid_size",
    "days",
    "runs_at_once",
    "io_latency_ms",
    "snapshot_every",
    "max_pending",
    "seconds",
    "runs_per_second",
    "max_rss_kb",
]


def run_checked(command):
    result = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n\n"
            + result.stdout
            + "\n"
            + result.stderr
        )

    return result


def build_program():
    print("Building optimized Part D executable...")

    run_checked([
        "cmake",
        "-S", str(ROOT),
        "-B", str(BUILD_DIR),
        "-DCMAKE_BUILD_TYPE=Release",
    ])

    run_checked([
        "cmake",
        "--build",
        str(BUILD_DIR),
        "-j",
    ])

    if not BINARY.exists():
        raise RuntimeError("PandemicSimulation executable not found")


def hardware_details():
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    logical = os.cpu_count() or 1
    physical = logical

    lines = []

    if shutil.which("lscpu"):
        result = subprocess.run(
            ["lscpu"],
            text=True,
            capture_output=True,
        )

        lines.append("===== CPU DETAILS =====")
        lines.append(result.stdout)

        values = {}

        for line in result.stdout.splitlines():
            if ":" in line:
                key, value = line.split(":", 1)
                values[key.strip()] = value.strip()

        try:
            logical = int(values["CPU(s)"])

            physical = (
                int(values["Core(s) per socket"])
                * int(values["Socket(s)"])
            )
        except (KeyError, ValueError):
            physical = logical

    lines.append(f"Physical cores: {physical}")
    lines.append(f"Logical CPUs: {logical}")
    lines.append(f"OS: {platform.platform()}")
    lines.append(f"Machine: {platform.machine()}")

    for command in (
        ["g++", "--version"],
        ["cmake", "--version"],
        ["uname", "-a"],
    ):
        if shutil.which(command[0]):
            result = subprocess.run(
                command,
                text=True,
                capture_output=True,
            )
            lines.append(result.stdout + result.stderr)

    meminfo = Path("/proc/meminfo")

    if meminfo.exists():
        lines.append(meminfo.read_text())

    report = OUT_DIR / "hardware.txt"
    report.write_text("\n".join(lines))

    print(f"Hardware details saved to {report}")
    print(f"Physical cores: {physical}")
    print(f"Logical CPUs: {logical}")

    return max(1, physical), max(1, logical)


def powers_of_two(maximum):
    values = [1]

    while values[-1] * 2 <= maximum:
        values.append(values[-1] * 2)

    return values


def record(section, row):
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    path = OUT_DIR / f"{section}.csv"
    exists = path.exists()

    with path.open("a", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=FIELDS,
        )

        if not exists:
            writer.writeheader()

        complete = {
            field: ""
            for field in FIELDS
        }

        complete.update(row)
        complete["section"] = section

        writer.writerow(complete)
        stream.flush()


def benchmark(
    *,
    grid,
    days,
    threads,
    chunks,
    mode,
    division="strips",
    extra=None,
    measure_rss=False,
):

    command = [
        str(BINARY),

        "--benchmark",
        "--fixed-days",

        "--grid-size", str(grid),
        "--days", str(days),

        "--seed", "42",
        "--initially-infected", "10",
        "--beta", "0.08",
        "--infectious-days", "7",
        "--mortality", "0.01",

        "--threads", str(threads),
        "--chunks", str(chunks),

        "--division", division,
        "--mode", mode,
    ]

    if extra:
        command.extend(extra)

    timed_command = command

    time_binary = "/usr/bin/time"

    if measure_rss and Path(time_binary).exists():
        timed_command = [
            time_binary,
            "-f",
            "MAX_RSS_KB=%M",
        ] + command

    result = run_checked(timed_command)

    combined = result.stdout + "\n" + result.stderr

    match = re.search(
        r"BENCHMARK_SECONDS=([0-9.eE+-]+)",
        combined,
    )

    if not match:
        raise RuntimeError(
            "BENCHMARK_SECONDS was not printed.\n"
            + combined
        )

    seconds = float(match.group(1))

    rss_match = re.search(
        r"MAX_RSS_KB=(\d+)",
        combined,
    )

    rss = (
        int(rss_match.group(1))
        if rss_match
        else None
    )

    return seconds, rss


# --------------------------------------------------
# D1: STRONG SCALING
# --------------------------------------------------

def run_d1(logical):

    grid = int(os.environ.get("D1_GRID_SIZE", "4000"))
    days = int(os.environ.get("D1_DAYS", "200"))

    thread_values = powers_of_two(2 * logical)

    print("\nD1: Strong scaling")
    print(f"Grid: {grid}, Days: {days}")
    print(f"Thread counts: {thread_values}")

    for threads in thread_values:

        mode = "sequential" if threads == 1 else "pool"
        chunks = max(1, 4 * threads)

        for rep in range(1, REPEATS + 1):

            seconds, _ = benchmark(
                grid=grid,
                days=days,
                threads=threads,
                chunks=chunks,
                mode=mode,
            )

            record("D1", {
                "repeat": rep,
                "threads": threads,
                "chunks": chunks,
                "division": "strips",
                "mode": mode,
                "grid_size": grid,
                "days": days,
                "seconds": seconds,
            })

            print(
                f"T={threads}, "
                f"repeat={rep}/{REPEATS}, "
                f"time={seconds:.4f}s"
            )


# --------------------------------------------------
# D2: WEAK SCALING
# --------------------------------------------------

def run_d2(logical):

    cells_per_thread = int(
        os.environ.get(
            "D2_CELLS_PER_THREAD",
            "1000000",
        )
    )

    days = int(
        os.environ.get("D2_DAYS", "200")
    )

    thread_values = powers_of_two(2 * logical)

    print("\nD2: Weak scaling")

    for threads in thread_values:

        grid = int(
            round(
                math.sqrt(cells_per_thread * threads)
            )
        )

        mode = "sequential" if threads == 1 else "pool"
        chunks = max(1, 4 * threads)

        for rep in range(1, REPEATS + 1):

            seconds, _ = benchmark(
                grid=grid,
                days=days,
                threads=threads,
                chunks=chunks,
                mode=mode,
            )

            record("D2", {
                "repeat": rep,
                "threads": threads,
                "chunks": chunks,
                "division": "strips",
                "mode": mode,
                "grid_size": grid,
                "days": days,
                "seconds": seconds,
            })

            print(
                f"T={threads}, N={grid}, "
                f"repeat={rep}/{REPEATS}, "
                f"time={seconds:.4f}s"
            )


# --------------------------------------------------
# D3: CHUNKS, DIVISIONS AND SMALL GRIDS
# --------------------------------------------------

def run_d3(physical):

    threads = physical

    grid = int(
        os.environ.get("D3_GRID_SIZE", "1000")
    )

    days = int(
        os.environ.get("D3_DAYS", "100")
    )

    chunk_values = [
        threads * factor
        for factor in (1, 2, 4, 8, 16, 32, 64)
    ]

    print("\nD3.1: Chunk count comparison")

    chunk_medians = {}

    for chunks in chunk_values:

        times = []

        for rep in range(1, REPEATS + 1):

            seconds, _ = benchmark(
                grid=grid,
                days=days,
                threads=threads,
                chunks=chunks,
                mode="pool",
            )

            times.append(seconds)

            record("D3_chunks", {
                "repeat": rep,
                "threads": threads,
                "chunks": chunks,
                "division": "strips",
                "mode": "pool",
                "grid_size": grid,
                "days": days,
                "seconds": seconds,
            })

            print(
                f"C={chunks}, "
                f"repeat={rep}/{REPEATS}, "
                f"time={seconds:.4f}s"
            )

        chunk_medians[chunks] = median(times)

    best_chunks = min(
        chunk_medians,
        key=chunk_medians.get,
    )

    print(f"Best measured chunk count: C={best_chunks}")

    print("\nD3.2: Grid division comparison")

    for division in (
        "strips",
        "blocks",
        "interleaved",
    ):

        for rep in range(1, REPEATS + 1):

            seconds, _ = benchmark(
                grid=grid,
                days=days,
                threads=threads,
                chunks=best_chunks,
                mode="pool",
                division=division,
            )

            record("D3_divisions", {
                "repeat": rep,
                "threads": threads,
                "chunks": best_chunks,
                "division": division,
                "mode": "pool",
                "grid_size": grid,
                "days": days,
                "seconds": seconds,
            })

            print(
                f"{division}: "
                f"repeat={rep}/{REPEATS}, "
                f"time={seconds:.4f}s"
            )

    print("\nD3.3: Small-grid comparison")

    small_days = int(
        os.environ.get("D3_SMALL_DAYS", "100")
    )

    for n in (50, 100, 200, 500, 1000):

        for mode in (
            "sequential",
            "threads",
            "pool",
        ):

            run_threads = (
                1 if mode == "sequential" else threads
            )

            chunks = (
                1 if mode == "sequential" else max(1, threads)
            )

            times = []

            for rep in range(1, REPEATS + 1):

                seconds, _ = benchmark(
                    grid=n,
                    days=small_days,
                    threads=run_threads,
                    chunks=chunks,
                    mode=mode,
                )

                times.append(seconds)

                record("D3_small_grids", {
                    "repeat": rep,
                    "threads": run_threads,
                    "chunks": chunks,
                    "division": "strips",
                    "mode": mode,
                    "grid_size": n,
                    "days": small_days,
                    "seconds": seconds,
                })

            print(
                f"N={n}, mode={mode}, "
                f"median={median(times):.4f}s"
            )


# --------------------------------------------------
# D4: PARALLELISM WITHIN AND ACROSS RUNS
# --------------------------------------------------

def run_d4(physical):

    grid = int(
        os.environ.get("D4_GRID_SIZE", "1000")
    )

    days = int(
        os.environ.get("D4_DAYS", "200")
    )

    betas = (0.04, 0.06, 0.08, 0.10)
    vaccinations = (0.0, 0.1, 0.2, 0.3)
    seeds = (41, 42)

    jobs = [
        (beta, vaccination, seed)
        for beta in betas
        for vaccination in vaccinations
        for seed in seeds
    ]

    run_counts = [
        r
        for r in range(1, physical + 1)
        if physical % r == 0
    ]

    print("\nD4: Parallelism within and across runs")
    print(f"Physical cores P={physical}")
    print(f"32 independent runs")
    print(f"Run configurations R={run_counts}")

    for runs_at_once in run_counts:

        threads = physical // runs_at_once

        for rep in range(1, REPEATS + 1):

            wave_maxima = []
            all_rss = []

            overall_start = time.perf_counter()

            for start in range(0, len(jobs), runs_at_once):

                batch = jobs[
                    start:start + runs_at_once
                ]

                def execute_one(job):

                    beta, vaccination, seed = job

                    return benchmark(
                        grid=grid,
                        days=days,
                        threads=threads,
                        chunks=max(1, 4 * threads),
                        mode="pool",
                        extra=[
                            "--beta", str(beta),
                            "--vaccinated-fraction", str(vaccination),
                            "--seed", str(seed),
                        ],
                        measure_rss=True,
                    )

                with concurrent.futures.ThreadPoolExecutor(
                    max_workers=len(batch)
                ) as executor:

                    results = list(
                        executor.map(execute_one, batch)
                    )

                wave_maxima.append(
                    max(result[0] for result in results)
                )

                all_rss.extend(
                    result[1]
                    for result in results
                    if result[1] is not None
                )

            wall_seconds = (
                time.perf_counter() - overall_start
            )

            throughput = len(jobs) / wall_seconds

            record("D4", {
                "repeat": rep,
                "threads": threads,
                "chunks": 4 * threads,
                "division": "strips",
                "mode": "pool",
                "grid_size": grid,
                "days": days,
                "runs_at_once": runs_at_once,
                "seconds": wall_seconds,
                "runs_per_second": throughput,
                "max_rss_kb": max(all_rss) if all_rss else "",
            })

            print(
                f"R={runs_at_once}, T={threads}, "
                f"repeat={rep}/{REPEATS}, "
                f"wall time={wall_seconds:.3f}s, "
                f"throughput={throughput:.4f} runs/s"
            )


# --------------------------------------------------
# D5: HIDING SNAPSHOT I/O TIME
# --------------------------------------------------

def run_d5():

    grid = int(
        os.environ.get("D5_GRID_SIZE", "128")
    )

    days = int(
        os.environ.get("D5_DAYS", "40")
    )

    k_values = (5, 10, 20)
    latencies = (10, 30, 60)
    q_values = (1, 2, 4)

    print("\nD5: Hiding I/O time")

    def run_case(
        mode,
        k,
        latency,
        q,
        rep,
    ):

        if mode == "no_snapshots":

            seconds, rss = benchmark(
                grid=grid,
                days=days,
                threads=1,
                chunks=1,
                mode="sequential",
                measure_rss=True,
            )

        else:

            with tempfile.TemporaryDirectory(
                prefix="d5_",
                dir=OUT_DIR,
            ) as temp_dir:

                prefix = str(
                    Path(temp_dir) / "snapshot"
                )

                extra = [
                    "--snapshot-every", str(k),
                    "--snapshot-mode", mode,
                    "--snapshot-prefix", prefix,
                    "--io-latency", str(latency),
                ]

                if mode == "async":
                    extra.extend([
                        "--max-pending",
                        str(q),
                    ])

                seconds, rss = benchmark(
                    grid=grid,
                    days=days,
                    threads=1,
                    chunks=1,
                    mode="sequential",
                    extra=extra,
                    measure_rss=True,
                )

        record("D5", {
            "repeat": rep,
            "threads": 1,
            "chunks": 1,
            "division": "none",
            "mode": mode,
            "grid_size": grid,
            "days": days,
            "io_latency_ms": latency,
            "snapshot_every": k,
            "max_pending": q if mode == "async" else "",
            "seconds": seconds,
            "max_rss_kb": rss if rss is not None else "",
        })

        print(
            f"{mode}, K={k}, "
            f"latency={latency}ms, Q={q}, "
            f"repeat={rep}/{REPEATS}: "
            f"{seconds:.4f}s"
        )

    for rep in range(1, REPEATS + 1):
        run_case(
            "no_snapshots",
            0, 0, 0,
            rep,
        )

    for k in k_values:

        for latency in latencies:

            for rep in range(1, REPEATS + 1):
                run_case(
                    "blocking",
                    k,
                    latency,
                    0,
                    rep,
                )

            for q in q_values:

                for rep in range(1, REPEATS + 1):
                    run_case(
                        "async",
                        k,
                        latency,
                        q,
                        rep,
                    )


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--only",
        choices=("all", "D1", "D2", "D3", "D4", "D5"),
        default="all",
    )

    args = parser.parse_args()

    if REPEATS < 5:
        parser.error(
            "PART_D_REPEATS must be at least 5"
        )

    OUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    build_program()

    physical, logical = hardware_details()

    selected = (
        ("D1", "D2", "D3", "D4", "D5")
        if args.only == "all"
        else (args.only,)
    )

    # Start fresh measurement files for selected experiments.
    for section in selected:

        path = OUT_DIR / f"{section}.csv"

        if path.exists():
            path.unlink()

    try:

        if "D1" in selected:
            run_d1(logical)

        if "D2" in selected:
            run_d2(logical)

        if "D3" in selected:
            run_d3(physical)

        if "D4" in selected:
            run_d4(physical)

        if "D5" in selected:
            run_d5()

    except Exception as error:

        print(
            f"ERROR: {error}",
            file=sys.stderr,
        )

        return 1

    print("\nSelected Part D experiments completed.")
    print(f"Raw results: {OUT_DIR}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
