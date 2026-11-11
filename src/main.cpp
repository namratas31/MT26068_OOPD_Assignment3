#include "Simulation.h"
#include <iostream>
#include <exception>

int main() {
try{
SimulationConfig config;

Simulation simulation(config);

simulation.run("results/simulation.csv");

return 0;
}
catch(const std::exception& e) {
std::cerr << "Error: "<< e.what() << '\n';
return 1;
}
}
