#include "Simulation.h"

#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

void printUsage(const char* program) {
    std::cout
        << "Usage: " << program << " [options]\n\n"
        << "Options:\n"
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
        << "  --output FILE\n"
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

} // namespace


int main(int argc, char* argv[]) {
    try {
        SimulationConfig config;

        std::string csvFilename = "results/simulation.csv";

        for (int i = 1; i < argc; ++i) {
            const std::string arg = argv[i];

            if (arg == "--help") {
                printUsage(argv[0]);
                return 0;
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
            else {
                throw std::invalid_argument(
                    "Unknown option: " + arg
                );
            }
        }

        Simulation simulation(config);

        simulation.run(csvFilename);

        return 0;
    }
    catch (const std::exception& e) {
        std::cerr << "Error: " << e.what() << '\n';
        return 1;
    }
}
