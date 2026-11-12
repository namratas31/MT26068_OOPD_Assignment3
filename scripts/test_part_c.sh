#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
BINARY="$BUILD_DIR/PandemicSimulation"
RESULTS="$ROOT_DIR/results/part_c_test"

mkdir -p "$RESULTS"

cmake -S "$ROOT_DIR" -B "$BUILD_DIR"
cmake --build "$BUILD_DIR" -j

COMMON=(
  --grid-size 64
  --days 6
  --seed 42
  --initially-infected 3
  --infectious-days 100
  --mortality 0
  --mode sequential
  --snapshot-every 2
)

# C1: Blocking snapshots.
"$BINARY" "${COMMON[@]}" \
  --snapshot-mode blocking \
  --snapshot-prefix "$RESULTS/blocking" \
  --output "$RESULTS/blocking.csv"

# C1: Asynchronous snapshots.
# At most two writes may be pending.
"$BINARY" "${COMMON[@]}" \
  --snapshot-mode async \
  --max-pending 2 \
  --io-latency 5 \
  --snapshot-prefix "$RESULTS/async" \
  --output "$RESULTS/async.csv"

# Compare the PPM images produced by both modes.
for day in 2 4 6; do
  cmp "$RESULTS/blocking_day_${day}.ppm" \
      "$RESULTS/async_day_${day}.ppm"
done

echo "PASS: blocking and asynchronous snapshots match"

# C2: Parameter sweep.
# 2 beta values x 2 vaccination values x 2 seeds = 8 runs.
"$BINARY" \
  --sweep \
  --grid-size 32 \
  --days 4 \
  --initially-infected 2 \
  --infectious-days 100 \
  --mortality 0 \
  --sweep-betas 0.04,0.08 \
  --sweep-vaccinations 0.0,0.2 \
  --sweep-seeds 41,42 \
  --sweep-workers 2 \
  --sweep-time-limit 0 \
  --sweep-output "$RESULTS/sweep.csv"

LINES=$(wc -l < "$RESULTS/sweep.csv")

if [[ "$LINES" -ne 9 ]]; then
  echo "FAIL: expected 8 sweep results plus header."
  echo "Found $((LINES - 1)) results."
  exit 1
fi

echo "PASS: parameter sweep generated all 8 summaries"
echo "All Part C tests passed."
