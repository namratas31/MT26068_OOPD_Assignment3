#include "Simulation.h"

#include <algorithm>
#include <chrono>
#include <cstddef>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <future>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

namespace {

struct SweepJob {
    std::size_t id = 0;
    double beta = 0.0;
    double vaccinatedFraction = 0.0;
    std::uint64_t seed = 0;
};

struct SweepCompletion {
    SweepJob job;
    SimulationSummary summary;
    std::chrono::steady_clock::time_point finishedAt;
};

struct ActiveSweepRun {
    std::future<SweepCompletion> future;
};

void printUsage(const char* program) {
    std::cout
        << "Usage: " << program << " [options]\n\n"
        << "Simulation options:\n"
        << "  --grid-size N\n"
        << "  --days N\n"
        << "  --seed N\n"
        << "  --beta X\n"
        << "  --infectious-days N\n"
        << "  --mortality X\n"
        << "  --initially-infected N\n"
        << "  --vaccinated-fraction X\n"
        << "  --mask-factor X\n"
        << "  --lockdown-factor X\n"
        << "  --lockdown-on X\n"
        << "  --lockdown-off X\n"
        << "  --threads T\n"
        << "  --chunks C\n"
        << "  --division strips|blocks|interleaved\n"
        << "  --mode sequential|threads|pool\n"
        << "  --output FILE\n\n"
        << "Part C1 snapshot options:\n"
        << "  --snapshot-every K       Save a snapshot every K days (0 disables)\n"
        << "  --snapshot-mode blocking|async\n"
        << "  --snapshot-prefix PATH   Output prefix for PPM snapshots\n"
        << "  --max-pending Q          Maximum pending asynchronous snapshots\n"
        << "  --io-latency MS          Artificial delay per snapshot write\n\n"
        << "Part C2 parameter-sweep options:\n"
        << "  --sweep                  Run a beta/vaccination/seed parameter sweep\n"
        << "  --sweep-betas LIST       Comma-separated beta values\n"
        << "  --sweep-vaccinations LIST  Comma-separated vaccination fractions\n"
        << "  --sweep-seeds LIST       Comma-separated integer seeds\n"
        << "  --sweep-workers W        Maximum simultaneous runs\n"
        << "  --sweep-time-limit SEC   Stop starting runs after this many seconds (0=no limit)\n"
        << "  --sweep-output FILE      Results CSV for sweep summaries\n"
        << "  --help\n";
}

std::string getValue(int& i, int argc, char* argv[]) {
    if (i + 1 >= argc) {
        throw std::invalid_argument(
            std::string("Missing value for ") + argv[i]
        );
    }
    return argv[++i];
}

template <typename T, typename Parser>
std::vector<T> parseList(const std::string& text, Parser parser) {
    std::vector<T> values;
    std::stringstream input(text);
    std::string item;

    while (std::getline(input, item, ',')) {
        if (item.empty()) {
            throw std::invalid_argument(
                "Empty item in comma-separated list"
            );
        }
        values.push_back(parser(item));
    }

    if (values.empty()) {
        throw std::invalid_argument(
            "Parameter list cannot be empty"
        );
    }
    return values;
}

std::vector<double> parseDoubleList(const std::string& text) {
    return parseList<double>(text, [](const std::string& item) {
        return std::stod(item);
    });
}

std::vector<std::uint64_t> parseSeedList(const std::string& text) {
    return parseList<std::uint64_t>(text, [](const std::string& item) {
        return static_cast<std::uint64_t>(std::stoull(item));
    });
}


void runParameterSweep(
    const SimulationConfig& baseConfig,
    const std::vector<double>& betas,
    const std::vector<double>& vaccinationFractions,
    const std::vector<std::uint64_t>& seeds,
    std::size_t workerCount,
    double timeLimitSeconds,
    const std::string& outputFilename
) {
    if (workerCount == 0) {
        throw std::invalid_argument(
            "Sweep worker count must be positive"
        );
    }

    if (timeLimitSeconds < 0.0) {
        throw std::invalid_argument(
            "Sweep time limit cannot be negative"
        );
    }

    std::vector<SweepJob> jobs;
    std::size_t id = 0;

    for (double beta : betas) {
        for (double vaccinated : vaccinationFractions) {
            for (std::uint64_t seed : seeds) {
                jobs.push_back({id++, beta, vaccinated, seed});
            }
        }
    }

    const std::filesystem::path outputPath(outputFilename);

    if (!outputPath.parent_path().empty()) {
        std::filesystem::create_directories(
            outputPath.parent_path()
        );
    }

    std::ofstream output(outputFilename);

    if (!output) {
        throw std::runtime_error(
            "Cannot open sweep output file: " + outputFilename
        );
    }

    output
        << "beta,vaccinated_fraction,seed,peak_infected_fraction,"
        << "peak_day,total_infected,total_deaths,days_simulated\n";

    const auto startTime = std::chrono::steady_clock::now();

    const auto deadline = timeLimitSeconds > 0.0
        ? startTime + std::chrono::duration_cast<
              std::chrono::steady_clock::duration>(
                  std::chrono::duration<double>(timeLimitSeconds)
              )
        : std::chrono::steady_clock::time_point::max();

    std::vector<ActiveSweepRun> active;
    active.reserve(workerCount);

    std::size_t nextJob = 0;
    std::size_t completedCount = 0;

    // Only launch a new run when a worker slot is available
    // and the time limit has not expired.
    auto launchAvailableRuns = [&]() {
        while (nextJob < jobs.size() &&
               active.size() < workerCount &&
               std::chrono::steady_clock::now() < deadline) {

            const SweepJob job = jobs[nextJob++];
            SimulationConfig config = baseConfig;

            // Sweep runs are independent. Use sequential simulation
            // inside each asynchronous run to avoid nested thread pools.
            config.beta = job.beta;
            config.vaccinatedFraction = job.vaccinatedFraction;
            config.seed = job.seed;

            config.executionMode = ExecutionMode::Sequential;
            config.threadCount = 1;
            config.chunks = 1;

            config.snapshotEvery = 0;
            config.asyncSnapshots = false;
            config.ioLatencyMs = 0;

            ActiveSweepRun run;

            run.future = std::async(
                std::launch::async,
                [config, job]() {
                    Simulation simulation(config);

                    SimulationSummary summary =
                        simulation.run("", false);

                    return SweepCompletion{
                        job,
                        summary,
                        std::chrono::steady_clock::now()
                    };
                }
            );

            active.push_back(std::move(run));
        }
    };

    launchAvailableRuns();

    while (!active.empty() ||
           (nextJob < jobs.size() &&
            std::chrono::steady_clock::now() < deadline)) {

        std::vector<SweepCompletion> justFinished;

        for (std::size_t i = 0; i < active.size();) {

            if (active[i].future.wait_for(
                    std::chrono::milliseconds(0)
                ) == std::future_status::ready) {

                try {
                    justFinished.push_back(
                        active[i].future.get()
                    );
                }
                catch (const std::exception& error) {
                    std::cerr
                        << "A sweep run failed: "
                        << error.what() << '\n';
                }

                active.erase(
                    active.begin() +
                    static_cast<std::ptrdiff_t>(i)
                );
            }
            else {
                ++i;
            }
        }

        // Several runs may finish between polling checks.
        // Sort them by their recorded completion timestamps.
        std::sort(
            justFinished.begin(),
            justFinished.end(),
            [](const SweepCompletion& a,
               const SweepCompletion& b) {
                return a.finishedAt < b.finishedAt;
            }
        );

        // Write each result as soon as it is collected.
        for (const SweepCompletion& result : justFinished) {

            output << result.job.beta << ','
                   << result.job.vaccinatedFraction << ','
                   << result.job.seed << ','
                   << result.summary.peakInfectedFraction << ','
                   << result.summary.peakDay << ','
                   << result.summary.totalInfected << ','
                   << result.summary.totalDeaths << ','
                   << result.summary.daysSimulated << '\n';

            output.flush();

            ++completedCount;

            std::cout
                << completedCount << '/' << jobs.size()
                << " runs done (completed in finish order)\n";
        }

        launchAvailableRuns();

        if (justFinished.empty() && !active.empty()) {
            std::this_thread::sleep_for(
                std::chrono::milliseconds(2)
            );
        }
    }

    // All started jobs have completed before this point.
    // Jobs still in the jobs vector were never submitted.
    output.close();

    if (!output) {
        throw std::runtime_error(
            "Failed while writing sweep results"
        );
    }

    if (nextJob < jobs.size()) {
        std::cout
            << "Time limit reached. "
            << (jobs.size() - nextJob)
            << " runs were not started and are missing:\n";

        for (std::size_t i = nextJob; i < jobs.size(); ++i) {
            std::cout
                << "  beta=" << jobs[i].beta
                << ", vaccination=" << jobs[i].vaccinatedFraction
                << ", seed=" << jobs[i].seed << '\n';
        }
    }

    std::cout
        << "Sweep results saved to: "
        << outputFilename << '\n';
}

} // namespace


int main(int argc, char* argv[]) {
    try {
        SimulationConfig config;

        std::string csvFilename = "results/simulation.csv";

        bool sweepMode = false;
        bool benchmarkMode = false;

        std::vector<double> sweepBetas{
    0.04, 0.06, 0.08, 0.10
};

std::vector<double> sweepVaccinations{
    0.0, 0.1, 0.2, 0.3
};

std::vector<std::uint64_t> sweepSeeds{
    41, 42
};

        std::size_t sweepWorkers = 4;
        double sweepTimeLimit = 0.0;
        std::string sweepOutput = "results/sweep.csv";

        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];

            if (arg == "--help") {
                printUsage(argv[0]);
                return 0;
            }
            else if (arg == "--sweep") {
                sweepMode = true;
            }
            else if (arg == "--grid-size") {
                config.gridSize =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--days") {
                config.maxDays =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--seed") {
                config.seed =
                    std::stoull(getValue(i, argc, argv));
            }
            else if (arg == "--beta") {
                config.beta =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--infectious-days") {
                config.infectiousDays =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--mortality") {
                config.mortality =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--initially-infected") {
                config.initiallyInfected =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--vaccinated-fraction") {
                config.vaccinatedFraction =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--mask-factor") {
                config.maskFactor =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--lockdown-factor") {
                config.lockdownFactor =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--lockdown-on") {
                config.lockdownOn =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--lockdown-off") {
                config.lockdownOff =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--threads") {
                config.threadCount =
                    std::stoull(getValue(i, argc, argv));
            }
            else if (arg == "--chunks") {
                config.chunks =
                    std::stoull(getValue(i, argc, argv));
            }
                else if (arg == "--benchmark") {
    benchmarkMode = true;
}
else if (arg == "--fixed-days") {
    config.stopWhenNoInfected = false;
}
            else if (arg == "--division") {
                const std::string value =
                    getValue(i, argc, argv);

                if (value == "strips") {
                    config.division = GridDivision::Strips;
                }
                else if (value == "blocks") {
                    config.division = GridDivision::Blocks;
                }
                else if (value == "interleaved") {
                    config.division = GridDivision::Interleaved;
                }
                else {
                    throw std::invalid_argument(
                        "Unknown division method: " + value
                    );
                }
            }
            else if (arg == "--mode") {
                const std::string value =
                    getValue(i, argc, argv);

                if (value == "sequential") {
                    config.executionMode =
                        ExecutionMode::Sequential;
                }
                else if (value == "threads") {
                    config.executionMode =
                        ExecutionMode::PerDayThreads;
                }
                else if (value == "pool") {
                    config.executionMode =
                        ExecutionMode::ThreadPool;
                }
                else {
                    throw std::invalid_argument(
                        "Unknown execution mode: " + value
                    );
                }
            }
            else if (arg == "--output") {
                csvFilename = getValue(i, argc, argv);
            }
            else if (arg == "--snapshot-every") {
                config.snapshotEvery =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--snapshot-mode") {
                const std::string value =
                    getValue(i, argc, argv);

                if (value == "blocking") {
                    config.asyncSnapshots = false;
                }
                else if (value == "async") {
                    config.asyncSnapshots = true;
                }
                else {
                    throw std::invalid_argument(
                        "Snapshot mode must be blocking or async"
                    );
                }
            }
            else if (arg == "--snapshot-prefix") {
                config.snapshotPrefix =
                    getValue(i, argc, argv);
            }
            else if (arg == "--max-pending") {
                config.maxPendingSnapshots =
                    std::stoull(getValue(i, argc, argv));
            }
            else if (arg == "--io-latency") {
                config.ioLatencyMs =
                    std::stoi(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-betas") {
                sweepBetas =
                    parseDoubleList(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-vaccinations") {
                sweepVaccinations =
                    parseDoubleList(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-seeds") {
                sweepSeeds =
                    parseSeedList(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-workers") {
                sweepWorkers =
                    std::stoull(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-time-limit") {
                sweepTimeLimit =
                    std::stod(getValue(i, argc, argv));
            }
            else if (arg == "--sweep-output") {
                sweepOutput = getValue(i, argc, argv);
            }
            else {
                throw std::invalid_argument(
                    "Unknown option: " + arg
                );
            }
        }

        if (sweepMode) {
            runParameterSweep(
                config,
                sweepBetas,
                sweepVaccinations,
                sweepSeeds,
                sweepWorkers,
                sweepTimeLimit,
                sweepOutput
            );

            return 0;
        }

        Simulation simulation(config);

const SimulationSummary summary =
    simulation.run(csvFilename, !benchmarkMode);

if (benchmarkMode) {
    std::cout
        << "BENCHMARK_SECONDS="
        << summary.elapsedSeconds << '\n';
}
else {
    std::cout
        << "Peak infected fraction: "
        << summary.peakInfectedFraction
        << " on day " << summary.peakDay << '\n'
        << "Total infected: "
        << summary.totalInfected << '\n'
        << "Total deaths: "
        << summary.totalDeaths << '\n'
        << "Days simulated: "
        << summary.daysSimulated << '\n';
}

return 0;
    }
    catch (const std::exception& error) {
        std::cerr
            << "Error: " << error.what() << '\n';

        return 1;
    }
}
