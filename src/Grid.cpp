#include "Grid.h"
#include <stdexcept>
#include <limits>

namespace {

std::size_t checkedCellCount(int n) {
	if(n<=0) {
throw std::invalid_argument("Grid size must be positive");
}
const std::size_t size = static_cast<std::size_t>(n);

if(size > std::numeric_limits<std::size_t>::max()/size) {
throw std::length_error("Grid is too large");
}

return size * size;
}
}

Grid::Grid(int n) : size(n), people(checkedCellCount(n)) {
}

int Grid:: getSize() const {
return size;
}

Person& Grid::at(int row, int col) {
if (row<0 || row>=size || col<0 || col>=size) {
throw std::out_of_range("Grid position out of range");
}

return people[static_cast<std::size_t>(row) * size + col];
}


const Person& Grid::at(int row, int col) const {
if(row<0 || row>=size || col<0 || col>=size) {
throw std::out_of_range("Grid position out of range");
}
return people[static_cast<std::size_t>(row) * size + col];
}

std::size_t Grid:: totalPeople() const {
return people.size();
}
