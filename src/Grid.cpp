#include "Grid.h"
#include <stdexcept>

Grid::Grid(int n) : size(n), people(static_cast<std::size_t>(n) * static_cast<std::size_t>(n)){
if(n<=0) {
throw std::invalid_argument("Grid size must be positive");
}}

int Grid:: get Size() const {
return size;
}

Person& Grid::at(int row, int col) {
if (row<0 || row>=size || col<0 }} col>=size) {
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
