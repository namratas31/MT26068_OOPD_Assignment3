#ifndef SIMULATION_H
#define SIMULATION_H

#include "Grid.h"
#include "ThreadPool.h"

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

// Part B grid partition methods.
enum class GridDivision {
    Strips,
    Blocks,
    Interleaved
};

enum class ExecutionMode {
    Sequential,
    PerDayThreads,
    ThreadPool
};

struct SimulationConfig {
    int gridSize = 1000;
    int maxDays = 200;
    std::uint64_t seed = 42;

    double beta = 0.08;
    int infectiousDays = 7;
    double mortality = 0.01;

    int initiallyInfected = 10;
    double vaccinatedFraction = 0.0;

    double maskFactor = 1.0;
    double lockdownFactor = 0.3;
    double lockdownOn = 0.02;
    double lockdownOff = 0.005;

    // Part B settings.
    std::size_t threadCount = 4;
    std::size_t chunks = 16;
    GridDivision division = GridDivision::Strips;
    ExecutionMode executionMode = ExecutionMode::ThreadPool;

    // Part C1 snapshot settings.
    int snapshotEvery = 0;
    bool asyncSnapshots = false;
    std::size_t maxPendingSnapshots = 2;
    int ioLatencyMs = 0;
    std::string snapshotPrefix = "results/snapshot";
};

struct DailyStats {
    int day = 0;
    std::size_t susceptible = 0;
    std::size_t infected = 0;
    std::size_t recovered = 0;
    std::size_t vaccinated = 0;
    std::size_t dead = 0;
    std::size_t newlyInfected = 0;

    double betaEffective = 0.0;
    std::uint64_t checksum = 0;
};

// Summary returned by each independent parameter-sweep run.
struct SimulationSummary {
    double peakInfectedFraction = 0.0;
    int peakDay = 0;
    std::size_t totalInfected = 0;
    std::size_t totalDeaths = 0;
    int daysSimulated = 0;
};

class Simulation {
private:
    SimulationConfig config;
    Grid current;
    Grid next;

    std::unique_ptr<ThreadPool> pool;

    void initialize();

    DailyStats simulateDay(
        int day,
        double betaEffective
    );

    std::uint64_t calculateChecksum() const;

public:
    explicit Simulation(const SimulationConfig& settings);

    SimulationSummary run(
        const std::string& csvFilename,
        bool writeCsv = true
    );
};

#endif
