#include "Simulation.h"
#include "Random.h"

#include <algorithm>
#include <cmath>
#include <fstream>
#include <iostream>
#include <numeric>
#include <stdexcept>
#include <vector>

Simulation::Simulation(const SimulationConfig& settings)
:config(settings), current(settings.gridSize), next(settings.gridSize) {

if(config.gridSize <=0 || config.maxDays <0 || config.infectiousDays <=0 || config.initiallyInfected < 0 ||
config.beta < 0.0 || config.beta > 1.0 || config.mortality < 0.0 || config.mortality > 1.0 || 
config.vaccinatedFraction < 0.0 || config.vaccinatedFraction > 1.0 || config.maskFactor <= 0.0 ||
config.maskFactor > 1.0 || config.lockdownFactor < 0.0 || config.lockdownFactor > 1.0 ||
config.lockdownOff < 0.0 || config.lockdownOn > 1.0 || config.lockdownOff > config.lockdownOn) {
throw std::invalid_argument("Invalid simulation parameters");
}

initialize();
}

void Simulation::initialize() {
const int n = config.gridSize;
const std::size_t total =
static_cast<std::size_t>(n) * static_cast<std::size_t>(n);

const std::size_t vaccinatedCount =
static_cast<std::size_t> (
config.vaccinatedFraction * static_cast<double>(total));

if (vaccinatedCount +
static_cast<std::size_t>(config.initiallyInfected) > total) {
throw std::invalid_argument(
"Too many vaccinated and initially infected people");
}

std::vector<std::size_t> ids(total);
std::iota(ids.begin(),ids.end(),0);

std::sort(ids.begin(), ids.end(),
[this](std::size_t a, std::size_t b) {
const auto ha = hashRandom(
config.seed, 0, static_cast <std::uint64_t>(a), 2);
const auto hb = hashRandom(
config.seed, 0, static_cast<std::uint64_t>(b), 2);

return ha == hb ? a< b : ha < hb;
});



for(std::size_t i =0; i<vaccinatedCount; ++i)
{
const int row = static_cast<int>(ids[i]/n);
const int col = static_cast<int>(ids[i] % n);
current.at(row,col).state = State::Vaccinated;}

for(int i=0; i<config.initiallyInfected; ++i){
const std::size_t id =
ids[vaccinatedCount + static_cast<std::size_t>(i)];

const int row = static_cast<int>( id /n);
const int col = static_cast<int>( id % n);

current.at(row,col).state = State::Infected;
current.at(row,col).daysInfected = 0;
}
next = current;
}


DailyStats Simulation::simulateDay(int day, double betaEffective) {
const int n = config.gridSize;
double probabilities[9];

for(int k =0; k<=8; ++k)
{
probabilities[k] = 1.0 - std::pow(1.0 - betaEffective,k ); }

for(int row=0; row<n; ++row){
for(int col=0; col<n; ++col) {
const Person& person = current.at(row,col);
Person& updated = next.at(row,col);

updated = person;

if(person.state == State::Susceptible) {
int infectedNeighbours = 0;

for(int dr = -1; dr<=1;++dr){
for(int dc = -1; dc<=1; ++dc) {
if(dr == 0 && dc == 0){
continue;
}

const int r = row +dr;
const int c= col + dc;

if(r>=0 && r<n && c>=0 && c<n && current.at(r,c).state == State::Infected) {
++infectedNeighbours;
}}}

const std::uint64_t id = 
static_cast<std::uint64_t>(row) * n + col;

const double randomValue = random01(
config.seed, static_cast<std::uint64_t>(day),id, 0);

if(randomValue < probabilities[infectedNeighbours]) {
updated.state = State::Infected;
updated.daysInfected = 0;
}}
else if (person.state == State::Infected) {
updated.daysInfected++;

if(updated.daysInfected >= config.infectiousDays) {
const std::uint64_t id =
static_cast<std::uint64_t>(row)* n + col;
const double randomValue = random01(
config.seed, static_cast<std::uint64_t>(day),id, 1);

if(randomValue < config.mortality) {
updated.state = State::Dead;}
else
{
updated.state= State::Recovered; }

updated.daysInfected = 0;
}}}}

std::swap(current, next);

DailyStats stats;
stats.day = day;
stats.betaEffective = betaEffective;

for(int row=0; row<n; ++row) {
for(int col = 0;col<n; ++col) {
switch(current.at(row,col).state){
case State::Susceptible: ++stats.susceptible;
break;
case State::Infected: ++stats.infected;
break;
case State::Recovered: ++stats.recovered;
break;
case State::Vaccinated: ++stats.vaccinated;
break;
case State::Dead: ++stats.dead;
break;
}}}

stats.checksum = calculateChecksum();
return stats;
}

std::uint64_t Simulation::calculateChecksum() const {
std::uint64_t hash = 14695981039346656037ULL;
const std::uint64_t prime = 1099511628211ULL;

const int n = config.gridSize;

for(int row = 0; row<n; ++row) {
for(int col=0; col<n;++col) {
const Person& person = current.at(row,col);

hash ^= static_cast<std::uint64_t>(person.state);
hash*= prime;

hash^= static_cast<std::uint64_t>(person.daysInfected);
hash*= prime;
}}
return hash;
}

void Simulation::run(const std::string& csvFilename) {
std::ofstream output(csvFilename);

if(!output) {
throw std::runtime_error("Cannot open CSV output file"); }

output<< "day,S,I,R,V,D,beta_eff,checksum\n";

double betaEffective = config.beta * config.maskFactor;
bool lockdown = false;

DailyStats stats;
stats.day=0;
stats.betaEffective = betaEffective;

for(int row=0; row<config.gridSize;++row){
for(int col=0; col<config.gridSize; ++col){
switch(current.at(row,col).state) {
case State::Susceptible: ++stats.susceptible; break;
case State::Infected: ++stats.infected; break;
case State::Recovered: ++stats.recovered; break;
case State::Vaccinated: ++stats.vaccinated; break;
case State::Dead: ++stats.dead; break;
}}}

stats.checksum = calculateChecksum();

output<< stats.day<< ',' << stats.susceptible << ',' << stats.infected << ',' <<
stats.recovered << ',' << stats.vaccinated << ',' << stats.dead << ',' <<
stats.betaEffective << ',' << stats.checksum <<'\n' ;

for(int day=1; day<=config.maxDays; ++day) {
stats = simulateDay (day,betaEffective);

output << stats.day <<',' <<stats.susceptible << ',' << stats.infected << ',' <<
stats.recovered << ',' << stats.vaccinated << ',' <<stats.dead <<',' << 
stats.betaEffective<< ',' << stats.checksum<< '\n';


const double infectedFraction = static_cast<double>(stats.infected) /
(static_cast<double>(config.gridSize) * config.gridSize);

if(!lockdown && infectedFraction > config.lockdownOn) {
lockdown = true;
betaEffective = config.beta * config.maskFactor * config.lockdownFactor;}
else if(lockdown && infectedFraction < config.lockdownOff) {
lockdown = false;
betaEffective = config.beta * config.maskFactor; }

if(stats.infected == 0) {
break;
}}

std:: cout <<"Simulation completed. CSV saved to : " << csvFilename<< '\n';
}






