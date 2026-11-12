#!/usr/bin/env python3

"""Repeatable epidemiology experiments for OOPD Assignment 3 Part E."""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys

from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BINARY = ROOT / "build" / "PandemicSimulation"
DEFAULT_OUT = ROOT / "results" / "part_e"


def run_checked(command):
    p = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    if p.returncode != 0:
        raise RuntimeError(
            "Command failed:\n"
            + " ".join(command)
            + "\n"
            + p.stdout
            + "\n"
            + p.stderr
        )


def read_csv(path):
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path, rows, fields=None):
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows and not fields:
        return

    names = fields or list(rows[0].keys())

    with path.open("w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=names,
        )
        writer.writeheader()
        writer.writerows(rows)


def run_one(
    binary,
    out_dir,
    *,
    n,
    days,
    seed,
    beta,
    vaccination=0.0,
    mask=1.0,
    lockdown_factor=0.3,
    lockdown_on=1.0,
    lockdown_off=0.0,
    infectious_days=7,
    mortality=0.01,
    initially_infected=10,
    tag,
):
    raw = (
        out_dir
        / "raw"
        / f"{tag}_seed_{seed}.csv"
    )

    raw.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    command = [
        str(binary),

        "--grid-size", str(n),
        "--days", str(days),
        "--seed", str(seed),

        "--beta", str(beta),
        "--infectious-days", str(infectious_days),
        "--mortality", str(mortality),
        "--initially-infected", str(initially_infected),

        "--vaccinated-fraction", str(vaccination),
        "--mask-factor", str(mask),

        "--lockdown-factor", str(lockdown_factor),
        "--lockdown-on", str(lockdown_on),
        "--lockdown-off", str(lockdown_off),

        "--mode", "sequential",
        "--threads", "1",
        "--chunks", "1",

        "--output", str(raw),
    ]

    run_checked(command)

    rows = read_csv(raw)

    if not rows:
        raise RuntimeError(
            f"No simulation rows produced: {raw}"
        )

    total = n * n

    initial_v = int(rows[0]["V"])

    peak_row = max(
        rows,
        key=lambda r: int(r["I"]),
    )

    final = rows[-1]

    # Total people ever infected includes people currently infected,
    # recovered or dead, but excludes people who were vaccinated.
    ever_infected = max(
        0,
        total - int(final["S"]) - int(final["V"]),
    )

    metrics = {
        "tag": tag,
        "seed": seed,
        "beta": beta,
        "vaccination": vaccination,
        "mask_factor": mask,
        "lockdown_factor": lockdown_factor,
        "initial_vaccinated": initial_v,

        "peak_infected_fraction":
            int(peak_row["I"]) / total,

        "peak_day":
            int(peak_row["day"]),

        "attack_rate":
            ever_infected / total,

        "total_deaths_fraction":
            int(final["D"]) / total,

        "days_simulated":
            int(final["day"]),
    }

    return rows, metrics


def aggregate_curves(series, n):
    max_day = max(
        int(rows[-1]["day"])
        for rows in series
    )

    columns = ("S", "I", "R", "D")
    result = []

    for day in range(max_day + 1):

        daily = {
            column: []
            for column in columns
        }

        for rows in series:

            # After an epidemic ends, carry the final population
            # counts forward so different run durations can be averaged.
            chosen = rows[
                min(day, len(rows) - 1)
            ]

            for column in columns:
                daily[column].append(
                    int(chosen[column]) / (n * n)
                )

        row = {"day": day}

        for column in columns:

            row[f"{column}_mean"] = mean(
                daily[column]
            )

            row[f"{column}_std"] = pstdev(
                daily[column]
            )

        result.append(row)

    return result


def summarise_metrics(rows, key):
    groups = {}

    for row in rows:
        value = float(row[key])
        groups.setdefault(value, []).append(row)

    output = []

    for value in sorted(groups):

        group = groups[value]

        item = {
            key: value,
            "runs": len(group),
        }

        metrics = (
            "peak_infected_fraction",
            "peak_day",
            "attack_rate",
            "total_deaths_fraction",
            "days_simulated",
        )

        for metric in metrics:

            values = [
                float(x[metric])
                for x in group
            ]

            item[f"{metric}_mean"] = mean(values)
            item[f"{metric}_std"] = pstdev(values)

        # Operational quick-extinction criterion:
        # cumulative infection does not exceed 1% of population.
        item["quick_extinction_runs"] = sum(
            x["attack_rate"] <= 0.01
            for x in group
        )

        output.append(item)

    return output


# ==========================================================
# E1: S, I, R AND D OVER TIME
# ==========================================================

def run_e1(binary, out, n, days, seeds):

    import matplotlib.pyplot as plt

    print("E1: Default epidemic, 10 seeds")

    all_series = []
    metrics = []

    for seed in seeds:

        rows, summary = run_one(
            binary,
            out,
            n=n,
            days=days,
            seed=seed,
            beta=0.08,
            vaccination=0.0,
            mask=1.0,
            lockdown_factor=0.3,
            lockdown_on=0.02,
            lockdown_off=0.005,
            tag="E1_default",
        )

        all_series.append(rows)
        metrics.append(summary)

        print(
            f"  seed {seed}: "
            f"peak={summary['peak_infected_fraction']:.4f}, "
            f"day={summary['peak_day']}"
        )

    curve = aggregate_curves(
        all_series,
        n,
    )

    write_csv(
        out / "E1_daily_mean.csv",
        curve,
    )

    write_csv(
        out / "E1_seed_metrics.csv",
        metrics,
    )

    plt.figure()

    for state in ("S", "I", "R", "D"):

        x = [
            row["day"]
            for row in curve
        ]

        y = [
            row[f"{state}_mean"]
            for row in curve
        ]

        sd = [
            row[f"{state}_std"]
            for row in curve
        ]

        plt.plot(
            x,
            y,
            label=state,
        )

        lower = [
            max(0.0, a - b)
            for a, b in zip(y, sd)
        ]

        upper = [
            min(1.0, a + b)
            for a, b in zip(y, sd)
        ]

        plt.fill_between(
            x,
            lower,
            upper,
            alpha=0.15,
        )

    plt.xlabel("Day")
    plt.ylabel("Population fraction")

    plt.title(
        "E1: Mean S, I, R and D over time "
        "(shaded region = ±1 SD)"
    )

    plt.legend()
    plt.grid(True)

    plt.savefig(
        out / "E1_SIRD_over_time.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()

    return metrics


# ==========================================================
# E2: VARY BETA
# ==========================================================

def run_e2(binary, out, n, days, seeds):

    import matplotlib.pyplot as plt

    print("E2: Beta sweep, 10 seeds per beta")

    metrics = []

    betas = (
        0.005,
        0.01,
        0.015,
        0.02,
        0.03,
        0.04,
        0.06,
        0.08,
    )

    for beta in betas:

        for seed in seeds:

            _, summary = run_one(
                binary,
                out,
                n=n,
                days=days,
                seed=seed,
                beta=beta,
                vaccination=0.0,
                mask=1.0,
                lockdown_on=1.0,
                lockdown_off=0.0,
                tag=f"E2_beta_{beta:.3f}",
            )

            metrics.append(summary)

        print(f"  completed beta={beta}")

    write_csv(
        out / "E2_seed_metrics.csv",
        metrics,
    )

    summary = summarise_metrics(
        metrics,
        "beta",
    )

    write_csv(
        out / "E2_beta_summary.csv",
        summary,
    )

    # Estimate the first tested beta where at least half of the
    # seeds exceed 1% cumulative attack rate.
    candidates = [
        row["beta"]
        for row in summary
        if row["quick_extinction_runs"] <= len(seeds) // 2
    ]

    threshold = (
        min(candidates)
        if candidates
        else None
    )

    (out / "E2_threshold.txt").write_text(
        "Operational criterion: quick extinction means cumulative "
        "infected <= 1% of population.\n"
        f"Lowest tested beta where at least half the seeds exceed "
        f"1% attack rate: {threshold}\n"
        "This is an empirical threshold for the tested grid size, "
        "seed set and parameters, not a universal constant.\n"
    )

    plt.figure()

    plt.errorbar(
        [row["beta"] for row in summary],
        [row["attack_rate_mean"] for row in summary],
        yerr=[
            row["attack_rate_std"]
            for row in summary
        ],
        marker="o",
        capsize=3,
    )

    plt.xlabel("Beta")
    plt.ylabel("Mean cumulative infected fraction")

    plt.title(
        "E2: Effect of beta (mean ± SD, 10 seeds)"
    )

    plt.grid(True)

    plt.savefig(
        out / "E2_beta_outbreaks.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()


# ==========================================================
# E3: VARY VACCINATION
# ==========================================================

def run_e3(binary, out, n, days, seeds):

    import matplotlib.pyplot as plt

    print("E3: Vaccination sweep, 10 seeds per level")

    metrics = []

    vaccination_levels = (
        0.0, 0.1, 0.2, 0.3, 0.4,
        0.5, 0.6, 0.7, 0.8,
    )

    for vaccination in vaccination_levels:

        for seed in seeds:

            _, summary = run_one(
                binary,
                out,
                n=n,
                days=days,
                seed=seed,
                beta=0.08,
                vaccination=vaccination,
                mask=1.0,
                lockdown_on=1.0,
                lockdown_off=0.0,
                tag=f"E3_v_{vaccination:.1f}",
            )

            metrics.append(summary)

        print(
            f"  completed vaccination={vaccination:.1f}"
        )

    write_csv(
        out / "E3_seed_metrics.csv",
        metrics,
    )

    summary = summarise_metrics(
        metrics,
        "vaccination",
    )

    write_csv(
        out / "E3_vaccination_summary.csv",
        summary,
    )

    # Operational herd-immunity estimate:
    # at least 9 of the 10 seeds have <=1% cumulative attack rate.
    candidates = [
        row["vaccination"]
        for row in summary
        if row["quick_extinction_runs"] >= 9
    ]

    threshold = (
        min(candidates)
        if candidates
        else None
    )

    (out / "E3_herd_immunity_estimate.txt").write_text(
        "Operational criterion: at least 9 of 10 seeds have "
        "cumulative infected <= 1% of population.\n"
        f"Lowest tested vaccination fraction meeting this "
        f"criterion: {threshold}\n"
        "This is an empirical estimate for the tested grid, "
        "beta and seeds, not a universal threshold.\n"
    )

    plt.figure()

    plt.errorbar(
        [row["vaccination"] for row in summary],
        [row["attack_rate_mean"] for row in summary],
        yerr=[
            row["attack_rate_std"]
            for row in summary
        ],
        marker="o",
        capsize=3,
    )

    plt.xlabel("Vaccinated fraction")
    plt.ylabel("Mean cumulative infected fraction")

    plt.title(
        "E3: Vaccination effect (mean ± SD, 10 seeds)"
    )

    plt.grid(True)

    plt.savefig(
        out / "E3_vaccination.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()


# ==========================================================
# E4: MASKS AND LOCKDOWN
# ==========================================================

def run_e4(binary, out, n, days, seeds):

    import matplotlib.pyplot as plt

    print(
        "E4: Masks and lockdown, "
        "10 seeds per scenario"
    )

    scenarios = {

        "baseline": {
            "mask": 1.0,
            "lockdown_on": 1.0,
            "lockdown_off": 0.0,
            "lockdown_factor": 0.3,
        },

        "masks_only": {
            "mask": 0.5,
            "lockdown_on": 1.0,
            "lockdown_off": 0.0,
            "lockdown_factor": 0.3,
        },

        "lockdown_only": {
            "mask": 1.0,
            "lockdown_on": 0.02,
            "lockdown_off": 0.005,
            "lockdown_factor": 0.3,
        },

        "masks_and_lockdown": {
            "mask": 0.5,
            "lockdown_on": 0.02,
            "lockdown_off": 0.005,
            "lockdown_factor": 0.3,
        },
    }

    all_metrics = []
    curves = {}

    for name, params in scenarios.items():

        series = []

        for seed in seeds:

            rows, summary = run_one(
                binary,
                out,
                n=n,
                days=days,
                seed=seed,
                beta=0.08,
                vaccination=0.0,
                mask=params["mask"],
                lockdown_factor=params["lockdown_factor"],
                lockdown_on=params["lockdown_on"],
                lockdown_off=params["lockdown_off"],
                tag=f"E4_{name}",
            )

            summary["scenario"] = name

            all_metrics.append(summary)
            series.append(rows)

        curves[name] = aggregate_curves(
            series,
            n,
        )

        print(f"  completed scenario={name}")

    write_csv(
        out / "E4_seed_metrics.csv",
        all_metrics,
    )

    grouped = []

    for name in scenarios:

        group = [
            row
            for row in all_metrics
            if row["scenario"] == name
        ]

        grouped.append({
            "scenario": name,

            "peak_fraction_mean": mean(
                row["peak_infected_fraction"]
                for row in group
            ),

            "peak_fraction_std": pstdev(
                row["peak_infected_fraction"]
                for row in group
            ),

            "peak_day_mean": mean(
                row["peak_day"]
                for row in group
            ),

            "peak_day_std": pstdev(
                row["peak_day"]
                for row in group
            ),
        })

    write_csv(
        out / "E4_scenario_summary.csv",
        grouped,
    )

    # Compare average infected trajectories.
    plt.figure()

    for name, curve in curves.items():

        plt.plot(
            [row["day"] for row in curve],
            [row["I_mean"] for row in curve],
            label=name,
        )

    plt.xlabel("Day")
    plt.ylabel("Mean infected fraction")

    plt.title(
        "E4: Masks and lockdown effect on infection peak"
    )

    plt.legend()
    plt.grid(True)

    plt.savefig(
        out / "E4_peak_comparison.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()

    # Compare mean peak height with standard deviation.
    plt.figure()

    plt.bar(
        [row["scenario"] for row in grouped],
        [row["peak_fraction_mean"] for row in grouped],
        yerr=[
            row["peak_fraction_std"]
            for row in grouped
        ],
        capsize=3,
    )

    plt.xticks(
        rotation=20,
        ha="right",
    )

    plt.ylabel("Mean peak infected fraction")
    plt.title("E4: Mean peak height by intervention (± SD)")
    plt.grid(axis="y")

    plt.savefig(
        out / "E4_peak_height.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()


# ==========================================================
# E5: STANDARD SIR MODEL COMPARISON
# ==========================================================

def run_e5(
    out,
    n,
    days,
    beta=0.08,
    infectious_days=7,
    mortality=0.01,
    initially_infected=10,
):

    import matplotlib.pyplot as plt

    print("E5: Standard SIR model comparison")

    grid_path = out / "E1_daily_mean.csv"

    if not grid_path.exists():
        raise RuntimeError(
            "Run E1 before E5. E1_daily_mean.csv is missing."
        )

    grid = read_csv(grid_path)

    # Homogeneous approximation:
    # each infected person has up to eight neighbouring contacts.
    transmission = 8.0 * beta

    removal = 1.0 / infectious_days

    recovery = removal * (1.0 - mortality)
    death = removal * mortality

    dt = 0.1
    steps = int(days / dt)

    total = n * n

    s = (total - initially_infected) / total
    i = initially_infected / total

    r = 0.0
    d = 0.0

    lockdown = False
    beta_effective = beta

    lockdown_factor = 0.3
    lockdown_on = 0.02
    lockdown_off = 0.005

    sir_rows = [{
        "day": 0.0,
        "S": s,
        "I": i,
        "R": r,
        "D": d,
    }]

    for step in range(1, steps + 1):

        # Apply the same default lockdown trigger and release
        # policy used in the E1 grid simulation.
        if not lockdown and i > lockdown_on:

            lockdown = True
            beta_effective = beta * lockdown_factor

        elif lockdown and i < lockdown_off:

            lockdown = False
            beta_effective = beta

        inf = (
            transmission
            * (beta_effective / beta)
            * s
            * i
        )

        ds = -inf
        di = inf - removal * i

        dr = recovery * i
        dd = death * i

        s = max(0.0, s + ds * dt)
        i = max(0.0, i + di * dt)
        r = max(0.0, r + dr * dt)
        d = max(0.0, d + dd * dt)

        if step % 10 == 0:

            sir_rows.append({
                "day": step * dt,
                "S": s,
                "I": i,
                "R": r,
                "D": d,
            })

    write_csv(
        out / "E5_sir_model.csv",
        sir_rows,
    )

    plt.figure()

    for state in ("S", "I", "R", "D"):

        plt.plot(
            [float(row["day"]) for row in grid],
            [float(row[f"{state}_mean"]) for row in grid],
            label=f"Grid {state}",
        )

        plt.plot(
            [row["day"] for row in sir_rows],
            [row[state] for row in sir_rows],
            linestyle="--",
            label=f"SIR {state}",
        )

    plt.xlabel("Day")
    plt.ylabel("Population fraction")

    plt.title(
        "E5: Grid simulation vs standard SIR model"
    )

    plt.legend(ncol=2)
    plt.grid(True)

    plt.savefig(
        out / "E5_grid_vs_SIR.png",
        dpi=160,
        bbox_inches="tight",
    )

    plt.close()

    (out / "E5_method.txt").write_text(
        "The standard SIR comparison uses a homogeneous-mixing approximation.\n"
        "The grid model has local neighbourhood transmission. For an approximate comparison,\n"
        "the SIR transmission rate is set to 8*beta because each cell has up to eight neighbours.\n"
        "The same default lockdown trigger (2% infected), release threshold (0.5%), and\n"
        "lockdown factor (0.3) are applied to the SIR transmission rate.\n"
        "The removal rate is 1/infectious_days, split into recovery and death using mortality.\n"
        "This mapping is approximate: local spatial clustering, boundaries and discrete daily\n"
        "infection probabilities make the grid dynamics differ from homogeneous SIR.\n"
    )


# ==========================================================
# MAIN
# ==========================================================

def main():

    parser = argparse.ArgumentParser(
        description="Run Part E epidemiology experiments"
    )

    parser.add_argument(
        "--binary",
        type=Path,
        default=DEFAULT_BINARY,
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUT,
    )

    parser.add_argument(
        "--grid-size",
        type=int,
        default=500,
    )

    parser.add_argument(
        "--days",
        type=int,
        default=500,
    )

    parser.add_argument(
        "--seeds",
        type=int,
        default=10,
    )

    parser.add_argument(
        "--only",
        choices=("all", "E1", "E2", "E3", "E4", "E5"),
        default="all",
    )

    args = parser.parse_args()

    if args.grid_size < 500 or args.grid_size > 1000:
        parser.error(
            "Part E requires grid size between 500 and 1000"
        )

    if args.seeds < 10:
        parser.error(
            "Part E requires at least 10 seeds per setting"
        )

    if not args.binary.exists():
        parser.error(
            f"Simulation executable not found: {args.binary}. "
            "Build Part C first."
        )

    try:
        import matplotlib.pyplot
    except ImportError:
        parser.error(
            "matplotlib is required. Install it using: "
            "python3 -m pip install --user matplotlib"
        )

    args.output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    seeds = list(
        range(41, 41 + args.seeds)
    )

    selected = (
        ("E1", "E2", "E3", "E4", "E5")
        if args.only == "all"
        else (args.only,)
    )

    for section in selected:

        if section == "E1":

            run_e1(
                args.binary,
                args.output_dir,
                args.grid_size,
                args.days,
                seeds,
            )

        elif section == "E2":

            run_e2(
                args.binary,
                args.output_dir,
                args.grid_size,
                args.days,
                seeds,
            )

        elif section == "E3":

            run_e3(
                args.binary,
                args.output_dir,
                args.grid_size,
                args.days,
                seeds,
            )

        elif section == "E4":

            run_e4(
                args.binary,
                args.output_dir,
                args.grid_size,
                args.days,
                seeds,
            )

        elif section == "E5":

            run_e5(
                args.output_dir,
                args.grid_size,
                args.days,
            )

    print(
        f"Part E outputs saved under: {args.output_dir}"
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
