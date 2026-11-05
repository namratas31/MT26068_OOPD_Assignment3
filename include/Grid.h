#ifndef GRID_H
#define GRID_H

#include "Person.h"
#include <vector>
#include <cstddef>

class Grid {
private:
int size;
std::vector<Person> people;

public:
explicit Grid(int n);

int getSize() const;
Person& at(int row, int col);
const Person& at(int row, int col) const;

std::size_t totalPeople() const;
};

#endif
