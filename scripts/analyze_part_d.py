#!/usr/bin/env python3

"""
Analyze Part D measurements and generate graphs.

Input:
    results/part_d/*.csv

Output:
    results/part_d/summaries/
    results/part_d/plots/
"""

import csv

from collections import defaultdict
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]

DATA = ROOT / "results" / "part_d"

PLOTS = DATA / "plots"

SUMMARY = DATA / "summaries"


def read_rows(name):

    path = DATA / f"{name}.csv"

    if not path.exists():
        return []

    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(row, key, default=0.0):

    value = row.get(key, "")

    if value in (None, ""):
        return default

    return float(value)


def summarize(rows, keys):

    groups = defaultdict(list)

    for row in rows:

        key = tuple(
            row.get(k, "")
            for k in keys
        )

        groups[key].append(
            number(row, "seconds")
        )

    result = {}

    for key, values in groups.items():

        result[key] = {
            "median": median(values),
            "min": min(values),
            "max": max(values),
        }

    return result


def write_summary(path, rows):

    if not rows:
        return

    with path.open("w", newline="") as stream:

        writer = csv.DictWriter(
            stream,
            fieldnames=list(rows[0]),
        )

        writer.writeheader()
        writer.writerows(rows)


def main():

    try:
        import matplotlib.pyplot as plt

    except ImportError:

        print(
            "Matplotlib is missing. Install it using:\n"
            "python3 -m pip install matplotlib"
        )

        return 1

    PLOTS.mkdir(
        parents=True,
        exist_ok=True,
    )

    SUMMARY.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ==============================================
    # D1: STRONG SCALING
    # ==============================================

    d1 = read_rows("D1")

    if d1:

        groups = summarize(
            d1,
            ("threads",),
        )

        base = groups.get(
            ("1",),
            {},
        ).get("median")

        items = sorted(
            (
                int(key[0]),
                value["median"],
            )
            for key, value in groups.items()
        )

        output = []
        karp_values = []

        for threads, seconds in items:

            speedup = (
                base / seconds
                if base
                else float("nan")
            )

            efficiency = speedup / threads

            karp = float("nan")

            if threads > 1 and speedup > 0:

                karp = (
                    1.0 / speedup - 1.0 / threads
                ) / (
                    1.0 - 1.0 / threads
                )

                karp_values.append(karp)

            values = groups[(str(threads),)]

            output.append({
                "threads": threads,
                "median_seconds": seconds,
                "speedup": speedup,
                "efficiency": efficiency,
                "karp_flatt_serial_fraction": karp,
                "min_seconds": values["min"],
                "max_seconds": values["max"],
            })

        write_summary(
            SUMMARY / "D1_summary.csv",
            output,
        )

        ts = [
            row["threads"]
            for row in output
        ]

        plt.figure()

        plt.plot(
            ts,
            [row["speedup"] for row in output],
            marker="o",
            label="Measured speedup",
        )

        plt.plot(
            ts,
            ts,
            linestyle="--",
            label="Ideal speedup",
        )

        plt.xlabel("Threads T")
        plt.ylabel("Speedup")
        plt.title("D1 Strong scaling: speedup")
        plt.legend()
        plt.grid(True)

        plt.savefig(
            PLOTS / "D1_speedup.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

        plt.figure()

        plt.plot(
            ts,
            [row["efficiency"] for row in output],
            marker="o",
        )

        plt.xlabel("Threads T")
        plt.ylabel("Efficiency")
        plt.title("D1 Strong scaling: efficiency")
        plt.grid(True)

        plt.savefig(
            PLOTS / "D1_efficiency.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

        if karp_values:

            f = sum(karp_values) / len(karp_values)

            max_threads = max(ts)

            p_values = list(
                range(1, max_threads + 1)
            )

            amdahl = [
                1.0 / (
                    f + (1.0 - f) / p
                )
                for p in p_values
            ]

            plt.figure()

            plt.plot(
                ts,
                [row["speedup"] for row in output],
                "o",
                label="Measured",
            )

            plt.plot(
                p_values,
                amdahl,
                label=f"Amdahl model, f={f:.4f}",
            )

            plt.xlabel("Threads T")
            plt.ylabel("Speedup")
            plt.title("D1 Measured speedup vs Amdahl's law")
            plt.legend()
            plt.grid(True)

            plt.savefig(
                PLOTS / "D1_amdahl.png",
                dpi=160,
                bbox_inches="tight",
            )

            plt.close()

    # ==============================================
    # D2: WEAK SCALING
    # ==============================================

    d2 = read_rows("D2")

    if d2:

        groups = summarize(
            d2,
            ("threads", "grid_size"),
        )

        base = next(
            (
                value["median"]
                for key, value in groups.items()
                if key[0] == "1"
            ),
            None,
        )

        output = []

        for (threads, grid), values in sorted(
            groups.items(),
            key=lambda item: int(item[0][0]),
        ):

            t = int(threads)

            efficiency = (
                base / values["median"]
                if base
                else float("nan")
            )

            output.append({
                "threads": t,
                "grid_size": int(grid),
                "median_seconds": values["median"],
                "efficiency": efficiency,
                "min_seconds": values["min"],
                "max_seconds": values["max"],
            })

        write_summary(
            SUMMARY / "D2_summary.csv",
            output,
        )

        plt.figure()

        plt.plot(
            [row["threads"] for row in output],
            [row["efficiency"] for row in output],
            marker="o",
        )

        plt.xlabel("Threads T")
        plt.ylabel("Weak-scaling efficiency")
        plt.title("D2 Weak scaling efficiency")
        plt.grid(True)

        plt.savefig(
            PLOTS / "D2_weak_efficiency.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

    # ==============================================
    # D3.1: CHUNK COUNT
    # ==============================================

    d3 = read_rows("D3_chunks")

    if d3:

        groups = summarize(
            d3,
            ("chunks",),
        )

        output = []

        for key, values in sorted(
            groups.items(),
            key=lambda item: int(item[0][0]),
        ):

            output.append({
                "chunks": int(key[0]),
                "median_seconds": values["median"],
                "min_seconds": values["min"],
                "max_seconds": values["max"],
            })

        write_summary(
            SUMMARY / "D3_chunks_summary.csv",
            output,
        )

        plt.figure()

        plt.plot(
            [row["chunks"] for row in output],
            [row["median_seconds"] for row in output],
            marker="o",
        )

        plt.xlabel("Chunks C")
        plt.ylabel("Median simulation-loop time (s)")
        plt.title("D3.1 Effect of chunk count")
        plt.grid(True)

        plt.savefig(
            PLOTS / "D3_chunks.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

        best = min(
            output,
            key=lambda row: row["median_seconds"],
        )

        (SUMMARY / "D3_best_chunks.txt").write_text(
            f"Best measured C={best['chunks']} "
            f"with median {best['median_seconds']:.6f} seconds.\n"
            "This is the best among the chunk counts tested "
            "on this machine.\n"
        )

    # ==============================================
    # D3.2: GRID DIVISIONS
    # ==============================================

    divisions = read_rows("D3_divisions")

    if divisions:

        groups = summarize(
            divisions,
            ("division",),
        )

        output = []

        for key, values in groups.items():

            output.append({
                "division": key[0],
                "median_seconds": values["median"],
                "min_seconds": values["min"],
                "max_seconds": values["max"],
            })

        write_summary(
            SUMMARY / "D3_divisions_summary.csv",
            output,
        )

        plt.figure()

        plt.bar(
            [row["division"] for row in output],
            [row["median_seconds"] for row in output],
        )

        plt.xlabel("Grid division")
        plt.ylabel("Median simulation-loop time (s)")
        plt.title("D3.2 Compare grid divisions")
        plt.grid(axis="y")

        plt.savefig(
            PLOTS / "D3_divisions.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

    # ==============================================
    # D3.3: SMALL GRIDS
    # ==============================================

    small = read_rows("D3_small_grids")

    if small:

        groups = summarize(
            small,
            ("grid_size", "mode"),
        )

        output = []

        for (grid, mode), values in sorted(
            groups.items(),
            key=lambda item: int(item[0][0]),
        ):

            output.append({
                "grid_size": int(grid),
                "mode": mode,
                "median_seconds": values["median"],
                "min_seconds": values["min"],
                "max_seconds": values["max"],
            })

        write_summary(
            SUMMARY / "D3_small_grids_summary.csv",
            output,
        )

        plt.figure()

        for mode in (
            "sequential",
            "threads",
            "pool",
        ):

            selected = [
                row
                for row in output
                if row["mode"] == mode
            ]

            plt.plot(
                [row["grid_size"] for row in selected],
                [row["median_seconds"] for row in selected],
                marker="o",
                label=mode,
            )

        plt.xlabel("Grid size N")
        plt.ylabel("Median simulation-loop time (s)")
        plt.title("D3.3 Small-grid overhead")
        plt.legend()
        plt.grid(True)

        plt.savefig(
            PLOTS / "D3_small_grids.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

        sequential = {
            row["grid_size"]: row["median_seconds"]
            for row in output
            if row["mode"] == "sequential"
        }

        crossover = {}

        for mode in ("threads", "pool"):

            candidates = [
                row["grid_size"]
                for row in output
                if row["mode"] == mode
                and row["grid_size"] in sequential
                and row["median_seconds"] < sequential[row["grid_size"]]
            ]

            crossover[mode] = (
                min(candidates)
                if candidates
                else None
            )

        (SUMMARY / "D3_small_grid_crossover.txt").write_text(
            "Smallest tested N where parallel mode beats sequential:\n"
            f"Thread-per-day: {crossover['threads']}\n"
            f"Thread pool: {crossover['pool']}\n"
        )

    # ==============================================
    # D4: RUNS PER SECOND
    # ==============================================

    d4 = read_rows("D4")

    if d4:

        groups = defaultdict(list)
        times = defaultdict(list)

        for row in d4:

            key = (
                int(row["runs_at_once"]),
                int(row["threads"]),
            )

            groups[key].append(
                number(row, "runs_per_second")
            )

            times[key].append(
                number(row, "seconds")
            )

        output = []

        for (r, t), values in sorted(groups.items()):

            output.append({
                "runs_at_once_R": r,
                "threads_per_run_T": t,
                "median_runs_per_second": median(values),
                "median_wall_seconds": median(times[(r, t)]),
                "min_runs_per_second": min(values),
                "max_runs_per_second": max(values),
            })

        write_summary(
            SUMMARY / "D4_summary.csv",
            output,
        )

        plt.figure()

        labels = [
            f"R={row['runs_at_once_R']}, T={row['threads_per_run_T']}"
            for row in output
        ]

        plt.bar(
            labels,
            [row["median_runs_per_second"] for row in output],
        )

        plt.xticks(rotation=25, ha="right")
        plt.ylabel("Runs completed per second")
        plt.title("D4 Parallelism within vs across runs")
        plt.grid(axis="y")

        plt.savefig(
            PLOTS / "D4_throughput.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

    # ==============================================
    # D5: SNAPSHOT I/O
    # ==============================================

    d5 = read_rows("D5")

    if d5:

        groups = defaultdict(list)
        rss_groups = defaultdict(list)

        for row in d5:

            key = (
                row["mode"],
                int(number(row, "snapshot_every")),
                int(number(row, "io_latency_ms")),
                int(number(row, "max_pending")),
            )

            groups[key].append(
                number(row, "seconds")
            )

            if row.get("max_rss_kb", ""):
                rss_groups[key].append(
                    float(row["max_rss_kb"])
                )

        output = []

        for key, values in groups.items():

            mode, k, latency, q = key

            output.append({
                "mode": mode,
                "snapshot_every_K": k,
                "io_latency_ms": latency,
                "Q": q,
                "median_seconds": median(values),
                "min_seconds": min(values),
                "max_seconds": max(values),
                "median_max_rss_kb": (
                    median(rss_groups[key])
                    if rss_groups[key]
                    else ""
                ),
            })

        write_summary(
            SUMMARY / "D5_summary.csv",
            output,
        )

        plt.figure()

        for mode in ("blocking", "async"):

            selected = [
                row
                for row in output
                if row["mode"] == mode
                and row["snapshot_every_K"] == 10
                and (mode != "async" or row["Q"] == 2)
            ]

            selected.sort(
                key=lambda row: row["io_latency_ms"]
            )

            if selected:

                plt.plot(
                    [row["io_latency_ms"] for row in selected],
                    [row["median_seconds"] for row in selected],
                    marker="o",
                    label=mode,
                )

        plt.xlabel("Artificial I/O latency (ms)")
        plt.ylabel("Median elapsed time (s)")
        plt.title("D5 Blocking vs asynchronous snapshots")
        plt.legend()
        plt.grid(True)

        plt.savefig(
            PLOTS / "D5_io_latency.png",
            dpi=160,
            bbox_inches="tight",
        )

        plt.close()

        plt.figure()

        selected = [
            row
            for row in output
            if row["mode"] == "async"
            and row["snapshot_every_K"] == 10
            and row["io_latency_ms"] == 30
            and row["median_max_rss_kb"] != ""
        ]

        selected.sort(
            key=lambda row: row["Q"]
        )

        if selected:

            plt.plot(
                [row["Q"] for row in selected],
                [
                    float(row["median_max_rss_kb"]) / 1024
                    for row in selected
                ],
                marker="o",
            )

            plt.xlabel("Maximum pending snapshots Q")
            plt.ylabel("Maximum resident memory (MiB)")
            plt.title("D5 Effect of Q on memory")
            plt.grid(True)

            plt.savefig(
                PLOTS / "D5_pending_memory.png",
                dpi=160,
                bbox_inches="tight",
            )

            plt.close()

    print("Analysis completed.")
    print(f"Summaries saved in: {SUMMARY}")
    print(f"Graphs saved in: {PLOTS}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
