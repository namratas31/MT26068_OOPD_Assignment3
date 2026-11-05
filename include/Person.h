#ifndef PERSON_H
#define PERSON_H

enum class State {
Susceptible,
Infected,
Recovered,
Vaccinated,
Dead
};

struct Person {
State state = State::Susceptible;
int daysInfected = 0;
};

#endif
