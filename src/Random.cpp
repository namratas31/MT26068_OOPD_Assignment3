#include "Random.h"

namespace {

std::uint64_t splitMix64(std::uint64_t x) {
x += 0x9E3779B97F4A7C15ULL;

x = (x^(x>>30)) * 0xBF58476D1CE4E5B9ULL;
x = (x^(x>>27)) * 0x94D049BB133111EBULL;

return x^(x>>31);
}
}

std::uint64_t hashRandom(
std::uint64_t seed,
std::uint64_t day,
std::uint64_t cell,
std::uint64_t stream ) {

std::uint64_t value = splitMix64(seed);
value = splitMix64( value ^ day);
value = splitMix64(value ^ cell);
value = splitMix64(value ^ stream);

return value; }

double random01(
std::uint64_t seed,
std::uint64_t day,
std::uint64_t cell,
std::uint64_t stream ) 
{
const std::uint64_t value =
hashRandom(seed, day , cell ,stream);

return static_cast<double>(value>> 11) * (1.0 / 9007199254740992.0);

}
