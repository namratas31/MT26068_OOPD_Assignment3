# Part B – Threaded Implementation

This branch extends the sequential pandemic simulation with multithreading.

It implements two parallel execution approaches:
- Thread-per-day
- Fixed-size thread pool

It supports three grid division strategies: row strips, square blocks, and interleaved rows.

Deterministic random-number generation ensures consistent simulation results across different thread configurations.
