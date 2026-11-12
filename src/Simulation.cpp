#include "Simulation.h"
#include "Random.h"

#include <algorithm>
#include <chrono>
#include <cmath>
#include <deque>
#include <exception>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

namespace {

struct LocalCounts {
    std::size_t susceptible = 0;
    std::size_t infected = 0;
    std::size_t recovered = 0;
    std::size_t vaccinated = 0;
    std::size_t dead = 0;
    std::size_t newlyInfected = 0;
};

void countState(LocalCounts& counts, State state) {
    switch (state) {
        case State::Susceptible: ++counts.susceptible; break;
        case State::Infected: ++counts.infected; break;
        case State::Recovered: ++counts.recovered; break;
        case State::Vaccinated: ++counts.vaccinated; break;
        case State::Dead: ++counts.dead; break;
    }
}

void writeSnapshot(const Grid& grid,
                   const std::string& filename,
                   int latencyMs) {
    if (latencyMs > 0) {
        std::this_thread::sleep_for(
            std::chrono::milliseconds(latencyMs)
        );
    }

    const std::filesystem::path path(filename);
    if (!path.parent_path().empty()) {
        std::filesystem::create_directories(path.parent_path());
    }

    std::ofstream image(filename);
    if (!image) {
        throw std::runtime_error("Cannot open snapshot file: " + filename);
    }

    const int n = grid.getSize();
    image << "P3\n" << n << ' ' << n << "\n255\n";

    // One RGB colour for each state:
    // S=light gray, I=red, R=green, V=blue, D=black.
    for (int row = 0; row < n; ++row) {
        for (int col = 0; col < n; ++col) {
            switch (grid.at(row, col).state) {
                case State::Susceptible:
                    image << "220 220 220 ";
                    break;
                case State::Infected:
                    image << "230 40 40 ";
                    break;
                case State::Recovered:
                    image << "40 180 70 ";
                    break;
                case State::Vaccinated:
                    image << "40 100 220 ";
                    break;
                case State::Dead:
                    image << "0 0 0 ";
                    break;
            }
        }
        image << '\n';
    }

    if (!image) {
        throw std::runtime_error(
            "Failed while writing snapshot: " + filename
        );
    }
}

} // namespace


Simulation::Simulation(const SimulationConfig& settings)
    : config(settings), current(settings.gridSize), next(settings.gridSize) {

    if (config.gridSize <= 0 ||
        config.maxDays < 0 ||
        config.infectiousDays <= 0 ||
        config.initiallyInfected < 0 ||
        config.beta < 0.0 || config.beta > 1.0 ||
        config.mortality < 0.0 || config.mortality > 1.0 ||
        config.vaccinatedFraction < 0.0 ||
        config.vaccinatedFraction > 1.0 ||
        config.maskFactor <= 0.0 || config.maskFactor > 1.0 ||
        config.lockdownFactor < 0.0 || config.lockdownFactor > 1.0 ||
        config.lockdownOn < 0.0 || config.lockdownOn > 1.0 ||
        config.lockdownOff < 0.0 ||
        config.lockdownOff > config.lockdownOn ||
        config.threadCount == 0 || config.chunks == 0 ||
        config.snapshotEvery < 0 || config.ioLatencyMs < 0 ||
        config.maxPendingSnapshots == 0) {
        throw std::invalid_argument("Invalid simulation parameters");
    }

    if (config.executionMode == ExecutionMode::PerDayThreads &&
        config.division != GridDivision::Strips) {
        throw std::invalid_argument(
            "Per-day thread mode supports row strips only"
        );
    }

    if (config.executionMode == ExecutionMode::ThreadPool) {
        pool = std::make_unique<ThreadPool>(config.threadCount);
    }

    initialize();
}


void Simulation::initialize() {
    const int n = config.gridSize;
    const std::size_t total =
        static_cast<std::size_t>(n) * static_cast<std::size_t>(n);

    const std::size_t vaccinatedCount =
        static_cast<std::size_t>(
            config.vaccinatedFraction * static_cast<double>(total)
        );

    if (vaccinatedCount +
        static_cast<std::size_t>(config.initiallyInfected) > total) {
        throw std::invalid_argument(
            "Too many vaccinated and initially infected people"
        );
    }

    std::vector<std::size_t> ids(total);
    std::iota(ids.begin(), ids.end(), 0);

    std::sort(ids.begin(), ids.end(), [this](std::size_t a, std::size_t b) {
        const auto ha = hashRandom(
            config.seed, 0, static_cast<std::uint64_t>(a), 2
        );
        const auto hb = hashRandom(
            config.seed, 0, static_cast<std::uint64_t>(b), 2
        );
        return ha == hb ? a < b : ha < hb;
    });

    for (std::size_t i = 0; i < vaccinatedCount; ++i) {
        const int row = static_cast<int>(ids[i] / n);
        const int col = static_cast<int>(ids[i] % n);
        current.at(row, col).state = State::Vaccinated;
    }

    for (int i = 0; i < config.initiallyInfected; ++i) {
        const std::size_t id =
            ids[vaccinatedCount + static_cast<std::size_t>(i)];
        const int row = static_cast<int>(id / n);
        const int col = static_cast<int>(id % n);
        current.at(row, col).state = State::Infected;
        current.at(row, col).daysInfected = 0;
    }

    next = current;
}


DailyStats Simulation::simulateDay(int day, double betaEffective) {
    const int n = config.gridSize;
    const std::size_t chunkCount = config.chunks;
    const std::size_t threadCount = config.threadCount;

    double probabilities[9];
    for (int k = 0; k <= 8; ++k) {
        probabilities[k] = 1.0 - std::pow(1.0 - betaEffective, k);
    }

    auto updateCell = [&](int row, int col, LocalCounts& counts) {
        const Person& person = current.at(row, col);
        Person updated = person;

        if (person.state == State::Susceptible) {
            int infectedNeighbours = 0;

            for (int dr = -1; dr <= 1; ++dr) {
                for (int dc = -1; dc <= 1; ++dc) {
                    if (dr == 0 && dc == 0) continue;

                    const int r = row + dr;
                    const int c = col + dc;

                    if (r >= 0 && r < n && c >= 0 && c < n &&
                        current.at(r, c).state == State::Infected) {
                        ++infectedNeighbours;
                    }
                }
            }

            const std::uint64_t id =
                static_cast<std::uint64_t>(row) * n + col;
            const double randomValue = random01(
                config.seed, static_cast<std::uint64_t>(day), id, 0
            );

            if (randomValue < probabilities[infectedNeighbours]) {
                updated.state = State::Infected;
                updated.daysInfected = 0;
                ++counts.newlyInfected;
            }
        }
        else if (person.state == State::Infected) {
            updated.daysInfected++;

            if (updated.daysInfected >= config.infectiousDays) {
                const std::uint64_t id =
                    static_cast<std::uint64_t>(row) * n + col;
                const double randomValue = random01(
                    config.seed, static_cast<std::uint64_t>(day), id, 1
                );

                if (randomValue < config.mortality) {
                    updated.state = State::Dead;
                } else {
                    updated.state = State::Recovered;
                }
                updated.daysInfected = 0;
            }
        }

        next.at(row, col) = updated;
        countState(counts, updated.state);
    };

    auto processRows = [&](int rowStart, int rowEnd,
                           int colStart, int colEnd,
                           LocalCounts& counts) {
        for (int row = rowStart; row < rowEnd; ++row) {
            for (int col = colStart; col < colEnd; ++col) {
                updateCell(row, col, counts);
            }
        }
    };

    auto processChunk = [&](std::size_t taskIndex) -> LocalCounts {
        LocalCounts counts;

        if (config.division == GridDivision::Strips) {
            const int rowStart = static_cast<int>(
                taskIndex * static_cast<std::size_t>(n) / chunkCount
            );
            const int rowEnd = static_cast<int>(
                (taskIndex + 1) * static_cast<std::size_t>(n) / chunkCount
            );
            processRows(rowStart, rowEnd, 0, n, counts);
        }
        else if (config.division == GridDivision::Interleaved) {
            for (std::size_t lane = taskIndex;
                 lane < threadCount; lane += chunkCount) {
                for (std::size_t row = lane;
                     row < static_cast<std::size_t>(n);
                     row += threadCount) {
                    processRows(
                        static_cast<int>(row), static_cast<int>(row) + 1,
                        0, n, counts
                    );
                }
            }
        }
        else if (config.division == GridDivision::Blocks) {
            const std::size_t blocksPerSide =
                static_cast<std::size_t>(std::ceil(
                    std::sqrt(static_cast<double>(chunkCount))
                ));
            const std::size_t totalBlocks = blocksPerSide * blocksPerSide;

            for (std::size_t block = taskIndex;
                 block < totalBlocks; block += chunkCount) {
                const std::size_t blockRow = block / blocksPerSide;
                const std::size_t blockCol = block % blocksPerSide;

                const int rowStart = static_cast<int>(
                    blockRow * static_cast<std::size_t>(n) / blocksPerSide
                );
                const int rowEnd = static_cast<int>(
                    (blockRow + 1) * static_cast<std::size_t>(n) / blocksPerSide
                );
                const int colStart = static_cast<int>(
                    blockCol * static_cast<std::size_t>(n) / blocksPerSide
                );
                const int colEnd = static_cast<int>(
                    (blockCol + 1) * static_cast<std::size_t>(n) / blocksPerSide
                );

                processRows(rowStart, rowEnd, colStart, colEnd, counts);
            }
        }

        return counts;
    };

    std::vector<LocalCounts> taskCounts(chunkCount);

    if (config.executionMode == ExecutionMode::Sequential) {
        processRows(0, n, 0, n, taskCounts[0]);
    }
    else if (config.executionMode == ExecutionMode::PerDayThreads) {
        std::vector<std::thread> workers;
        std::vector<std::exception_ptr> errors(chunkCount);
        workers.reserve(chunkCount);

        for (std::size_t t = 0; t < chunkCount; ++t) {
            workers.emplace_back([&, t]() {
                try {
                    taskCounts[t] = processChunk(t);
                } catch (...) {
                    errors[t] = std::current_exception();
                }
            });
        }

        for (std::thread& worker : workers) worker.join();
        for (const auto& error : errors) {
            if (error) std::rethrow_exception(error);
        }
    }
    else if (config.executionMode == ExecutionMode::ThreadPool) {
        std::vector<std::future<LocalCounts>> futures;
        futures.reserve(chunkCount);

        for (std::size_t t = 0; t < chunkCount; ++t) {
            futures.push_back(pool->submit([&, t]() {
                return processChunk(t);
            }));
        }

        std::exception_ptr taskError;
        for (std::size_t t = 0; t < futures.size(); ++t) {
            try {
                taskCounts[t] = futures[t].get();
            } catch (...) {
                if (!taskError) taskError = std::current_exception();
            }
        }
        if (taskError) std::rethrow_exception(taskError);
    }

    // All workers/tasks have completed before the grids are swapped.
    std::swap(current, next);

    DailyStats stats;
    stats.day = day;
    stats.betaEffective = betaEffective;

    for (const LocalCounts& counts : taskCounts) {
        stats.susceptible += counts.susceptible;
        stats.infected += counts.infected;
        stats.recovered += counts.recovered;
        stats.vaccinated += counts.vaccinated;
        stats.dead += counts.dead;
        stats.newlyInfected += counts.newlyInfected;
    }

    stats.checksum = calculateChecksum();
    return stats;
}


std::uint64_t Simulation::calculateChecksum() const {
    std::uint64_t hash = 14695981039346656037ULL;
    const std::uint64_t prime = 1099511628211ULL;
    const int n = config.gridSize;

    for (int row = 0; row < n; ++row) {
        for (int col = 0; col < n; ++col) {
            const Person& person = current.at(row, col);
            hash ^= static_cast<std::uint64_t>(person.state);
            hash *= prime;
            hash ^= static_cast<std::uint64_t>(person.daysInfected);
            hash *= prime;
        }
    }

    return hash;
}


SimulationSummary Simulation::run(const std::string& csvFilename,
                                  bool writeCsv) {
    std::ofstream output;
    if (writeCsv) {
        const std::filesystem::path csvPath(csvFilename);
        if (!csvPath.parent_path().empty()) {
            std::filesystem::create_directories(csvPath.parent_path());
        }
        output.open(csvFilename);
        if (!output) {
            throw std::runtime_error("Cannot open CSV output file: " + csvFilename);
        }
        output << "day,S,I,R,V,D,beta_eff,checksum\n";
    }

    double betaEffective = config.beta * config.maskFactor;
    bool lockdown = false;

    DailyStats stats;
    stats.day = 0;
    stats.betaEffective = betaEffective;

    stats.susceptible = 0;
    stats.infected = 0;
    stats.recovered = 0;
    stats.vaccinated = 0;
    stats.dead = 0;
    for (int row = 0; row < config.gridSize; ++row) {
        for (int col = 0; col < config.gridSize; ++col) {
            switch (current.at(row, col).state) {
                case State::Susceptible: ++stats.susceptible; break;
                case State::Infected: ++stats.infected; break;
                case State::Recovered: ++stats.recovered; break;
                case State::Vaccinated: ++stats.vaccinated; break;
                case State::Dead: ++stats.dead; break;
            }
        }
    }

    if (writeCsv) {
        output << stats.day << ',' << stats.susceptible << ','
               << stats.infected << ',' << stats.recovered << ','
               << stats.vaccinated << ',' << stats.dead << ','
               << stats.betaEffective << ',' << calculateChecksum() << '\n';
    }

    SimulationSummary summary;
    const double totalCells =
        static_cast<double>(config.gridSize) * config.gridSize;
    summary.peakInfectedFraction =
        static_cast<double>(stats.infected) / totalCells;
    summary.peakDay = 0;
    summary.totalInfected = stats.infected;
    summary.totalDeaths = stats.dead;
    summary.daysSimulated = 0;

    std::deque<std::future<void>> pendingSnapshots;
    std::exception_ptr snapshotError;

    auto waitOldestSnapshot = [&]() {
        std::future<void> oldest = std::move(pendingSnapshots.front());
        pendingSnapshots.pop_front();
        try {
            oldest.get();
        } catch (...) {
            if (!snapshotError) snapshotError = std::current_exception();
        }
    };

    auto saveSnapshot = [&](int day) {
        const std::string filename =
            config.snapshotPrefix + "_day_" + std::to_string(day) + ".ppm";

        if (!config.asyncSnapshots) {
            // Blocking version writes the current grid in the main thread.
            writeSnapshot(current, filename, config.ioLatencyMs);
            std::cout << "Snapshot saved: " << filename << '\n';
            return;
        }

        // Copy is essential: the simulation will change current on the next day.
        while (pendingSnapshots.size() >= config.maxPendingSnapshots) {
            waitOldestSnapshot();
        }

        Grid snapshotCopy = current;
        const int latency = config.ioLatencyMs;
        pendingSnapshots.push_back(std::async(
            std::launch::async,
            [snapshot = std::move(snapshotCopy), filename, latency]() {
                writeSnapshot(snapshot, filename, latency);
            }
        ));
    };
        
const auto benchmarkStart =
    std::chrono::steady_clock::now();
        
    for (int day = 1; day <= config.maxDays; ++day) {
        stats = simulateDay(day, betaEffective);

        if (writeCsv) {
            output << stats.day << ',' << stats.susceptible << ','
                   << stats.infected << ',' << stats.recovered << ','
                   << stats.vaccinated << ',' << stats.dead << ','
                   << stats.betaEffective << ',' << stats.checksum << '\n';
        }

        ++summary.daysSimulated;
        summary.totalInfected += stats.newlyInfected;

        const double infectedFraction =
            static_cast<double>(stats.infected) / totalCells;
        if (infectedFraction > summary.peakInfectedFraction) {
            summary.peakInfectedFraction = infectedFraction;
            summary.peakDay = day;
        }
        summary.totalDeaths = stats.dead;

        if (config.snapshotEvery > 0 &&
            day % config.snapshotEvery == 0) {
            saveSnapshot(day);
        }

        if (!lockdown && infectedFraction > config.lockdownOn) {
            lockdown = true;
            betaEffective =
                config.beta * config.maskFactor * config.lockdownFactor;
        }
        else if (lockdown && infectedFraction < config.lockdownOff) {
            lockdown = false;
            betaEffective = config.beta * config.maskFactor;
        }

        if (config.stopWhenNoInfected && stats.infected == 0) {
    break;
}
    }

    // Wait for every pending snapshot, even if one writer failed.
    while (!pendingSnapshots.empty()) {
        waitOldestSnapshot();
    }

        summary.elapsedSeconds =
    std::chrono::duration<double>(
        std::chrono::steady_clock::now() - benchmarkStart
    ).count();
    if (snapshotError) std::rethrow_exception(snapshotError);

    if (writeCsv) {
        output.close();
        if (!output) {
            throw std::runtime_error("Failed while writing CSV output");
        }
        std::cout << "Simulation completed. CSV saved to: "
                  << csvFilename << '\n';
    }

    return summary;
}
