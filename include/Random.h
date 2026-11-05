#ifndef RANDOM_H
#define RANDOM_H

#include <cstdint>

std::uint64_t hashRandom(
std::uint64_t seed,
std::uint64_t day,
std::uint64_t cell,
std::uint64_t stream);

double random01(
std::uint64_t seed,
std::uint64_t day,
std::uint64_t cell,
std::uint64_t stream );

#endif
