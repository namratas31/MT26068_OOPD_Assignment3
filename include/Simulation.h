#ifndef SIMULATION_H
#define SIMULATION_H

#include "Grid.h"
#include <cstddef>
#include <cstdint>
#include <string>

struct SimulationConfig {
int gridSize = 1000;
int maxDays  = 200;
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
};

struct DailyStats {
int day = 0;
std::size_t susceptible = 0;
std::size_t infected = 0;
std::size_t recovered = 0;
std::size_t vaccinated = 0;
std::size_t dead = 0;
double betaEffective = 0.0;
std::uint64_t checksum = 0;
};

class Simulation {
private:
SimulationConfig config;
Grid current;
Grid next;

void initialize();
DailyStats simulateDay( int day, double betaEffective);
std::uint64_t calculateChecksum() const;

public:
explicit Simulation(const SimulationConfig& settings);

void run(const std::string& csvFilename);
};

#endif
