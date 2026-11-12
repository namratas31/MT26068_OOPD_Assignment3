# MT26068 – OOPD Assignment 3
## Parallel and Asynchronous Simulation of Pandemic Spread

**Course:** CSE600 – Object Oriented Programming Design  
**Assignment:** Assignment 3  
**Student:** Namrata Sharma  
**Roll Number:** MT26068  

---

## 1. Project Overview

This project implements a pandemic-spread simulation on a two-dimensional grid and explores sequential execution, multithreading, asynchronous programming and performance analysis.

Each cell represents one person. A person can be in one of five states:

- **S – Susceptible:** Can become infected.
- **I – Infected:** Can infect neighbouring cells and has an infection counter.
- **R – Recovered:** Has recovered and is immune.
- **V – Vaccinated:** Immune due to vaccination.
- **D – Dead:** Has died and does not change state.

Each cell interacts with its eight neighbouring cells. The simulation advances day by day, with all cells updated using the previous day's grid.

## 2. Repository Structure

The implementation is maintained in separate Git branches for the different assignment parts.

| Branch | Description |
|---|---|
| `part-a-sequential` | Sequential simulation |
| `part-b-threaded` | Thread-per-day and thread-pool implementations |
| `part-c-async` | Asynchronous snapshot writing and parameter sweep |
| `part-d-performance` | Performance experiments and analysis scripts |
| `part-e-epidemiology` | Epidemiology experiment script |

Main project files:

```text
MT26068_OOPD_Assignment3/
│
├── include/
│   ├── Grid.h
│   ├── Person.h
│   ├── Random.h
│   ├── Simulation.h
│   └── ThreadPool.h
│
├── src/
│   ├── Grid.cpp
│   ├── Random.cpp
│   ├── Simulation.cpp
│   └── main.cpp
│
├── scripts/
│   ├── test_part_b.sh
│   ├── test_part_c.sh
│   ├── run_part_d.py
│   ├── analyze_part_d.py
│   └── run_part_e.py
│
├── CMakeLists.txt
└── README.md
```

Experiment outputs are generated in the `results/` directory when the corresponding scripts are executed.

## 3. Requirements

- C++17 compatible compiler (GCC/G++)
- CMake 3.16 or later
- Python 3
- Python Matplotlib for generating experiment plots
- Linux environment recommended

Install Matplotlib:

```bash
python3 -m pip install matplotlib
```

## 4. Build Instructions

Clone the repository:

```bash
git clone https://github.com/namratas31/MT26068_OOPD_Assignment3.git
cd MT26068_OOPD_Assignment3
```

Switch to the required implementation branch. For example:

```bash
git switch part-c-async
```

Configure and build:

```bash
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build -j
```

The executable is generated at:

```text
build/PandemicSimulation
```

## 5. Implementation Details

### Part A – Sequential Simulation

The initial implementation executes the simulation using a single thread.

It supports command-line configuration of simulation parameters and generates daily CSV output containing population counts and grid checksums.

### Part B – Threaded Simulation

Two parallel execution approaches are implemented:

1. **Thread-per-day:** Creates worker threads for grid partitions on each simulation day and joins them before proceeding.
2. **Thread pool:** Creates a fixed pool of worker threads and submits grid-partition tasks for each day.

Three grid-division strategies are supported:

- Strips of rows
- Square blocks
- Interleaved rows

A deterministic random-number function based on the seed, day, cell and random stream ensures that simulation results do not depend on thread scheduling.

### Part C – Asynchronous Programming

This part implements:

- Blocking snapshot writing.
- Asynchronous snapshot writing using copied grid states.
- A configurable limit on pending snapshot writes.
- Artificial I/O latency.
- Waiting for pending operations and reporting failures.
- Asynchronous parameter sweeps with completion-order result handling.
- Time-limit handling for parameter sweeps.

The snapshot copy ensures that the background writer uses a consistent grid state even while the simulation continues updating its grids.

### Part D – Performance Study

The performance scripts cover the following experiments:

- **D1:** Strong scaling, speedup, efficiency, Amdahl's law and Karp–Flatt serial fraction.
- **D2:** Weak scaling and Gustafson's law.
- **D3:** Chunk-count comparison, grid-division strategies and small-grid overhead.
- **D4:** Parallelism within a simulation versus parallelism across independent simulations.
- **D5:** Blocking and asynchronous snapshot I/O performance.

Run the experiments from the `part-d-performance` branch:

```bash
git switch part-d-performance
python3 scripts/run_part_d.py
```

The script performs five repetitions per measurement by default and records hardware details.

Generate summaries and graphs:

```bash
python3 scripts/analyze_part_d.py
```

Outputs are saved under:

```text
results/part_d/
├── D1.csv
├── D2.csv
├── ...
├── hardware.txt
├── summaries/
└── plots/
```

Individual experiments can be selected using:

```bash
python3 scripts/run_part_d.py --only D1
```

Replace `D1` with `D2`, `D3`, `D4` or `D5` as required.

### Part E – Epidemiology Study

The epidemiology script evaluates:

- S, I, R and D population trends over time.
- The effect of transmission probability (β).
- The vaccination fraction required to suppress outbreaks.
- The effect of masks and lockdown.
- Comparison with the standard SIR mathematical model.

Run from the `part-e-epidemiology` branch:

```bash
git switch part-e-epidemiology
python3 scripts/run_part_e.py
```

The default configuration uses a grid size of 500, 500 maximum days and 10 random seeds per setting.

Custom parameters can be supplied:

```bash
python3 scripts/run_part_e.py --grid-size 500 --days 500 --seeds 10
```

To run an individual experiment:

```bash
python3 scripts/run_part_e.py --only E1
```

Replace `E1` with `E2`, `E3`, `E4` or `E5`.

**Note:** E5 uses the mean daily output produced by E1, so run E1 before running E5 separately.

Outputs are saved under:

```text
results/part_e/
├── raw/
├── E1_daily_mean.csv
├── E1_seed_metrics.csv
├── E1_SIRD_over_time.png
├── E2_beta_summary.csv
├── E3_vaccination_summary.csv
├── E4_scenario_summary.csv
├── E5_sir_model.csv
└── ...
```

## 6. Testing

Part B correctness testing:

```bash
bash scripts/test_part_b.sh
```

Part C testing:

```bash
bash scripts/test_part_c.sh
```

The Part B testing script compares the sequential and parallel simulation outputs for different thread counts and grid-division strategies.

The Part C testing script checks blocking and asynchronous snapshot behaviour and parameter-sweep execution.

## 7. Performance Measurement Methodology

The performance experiments are designed to:

- Measure simulation-loop execution time.
- Repeat measurements at least five times.
- Use median and spread to summarize performance.
- Record hardware and software details.
- Generate CSV files and plots for analysis.

Part E uses at least ten random seeds per setting and reports averages and standard deviations.

## 8. Output and Results

Generated CSV files contain simulation statistics and experiment measurements. PNG files contain plots generated by the analysis scripts. Hardware information is recorded separately for the performance study.

The `results/` directory is generated by running the corresponding experiment scripts.

## 9. Conclusion

This project explores how a grid-based pandemic simulation can be implemented sequentially, parallelized using threads, and extended through asynchronous operations. It also provides scripts to study the effect of thread count, workload distribution, asynchronous I/O, transmission probability, vaccination and public-health interventions.

The experiments are intended to demonstrate the trade-offs between correctness, parallel execution overhead, resource utilization and simulation behaviour.
