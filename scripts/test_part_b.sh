#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BUILD_DIR="$ROOT_DIR/build"
BINARY="$BUILD_DIR/PandemicSimulation"

GRID_SIZE="${GRID_SIZE:-128}"
DAYS="${DAYS:-30}"
SEED="${SEED:-42}"
CHUNKS="${CHUNKS:-32}"

RESULT_DIR="$ROOT_DIR/results/part_b_test"

mkdir -p "$RESULT_DIR"

echo "Building PandemicSimulation..."

cmake -S "$ROOT_DIR" -B "$BUILD_DIR"
cmake --build "$BUILD_DIR" -j

run_simulation() {
    local mode="$1"
    local threads="$2"
    local division="$3"
    local output="$4"

    "$BINARY" \
        --grid-size "$GRID_SIZE" \
        --days "$DAYS" \
        --seed "$SEED" \
        --threads "$threads" \
        --chunks "$CHUNKS" \
        --division "$division" \
        --mode "$mode" \
        --output "$output"
}

echo
echo "Creating sequential reference..."

REFERENCE="$RESULT_DIR/sequential.csv"

run_simulation \
    sequential 1 strips "$REFERENCE"

THREAD_COUNTS=(1 2 3 4 7 8 16)
DIVISIONS=(strips blocks interleaved)

echo
echo "Testing thread pool..."

for threads in "${THREAD_COUNTS[@]}"; do
    for division in "${DIVISIONS[@]}"; do

        OUTPUT="$RESULT_DIR/pool_${threads}_${division}.csv"

        echo "Testing T=$threads, C=$CHUNKS, division=$division"

        run_simulation pool "$threads" "$division" "$OUTPUT"

        if ! cmp -s "$REFERENCE" "$OUTPUT"; then
            echo "FAILED: T=$threads, division=$division"
            diff -u "$REFERENCE" "$OUTPUT" || true
            exit 1
        fi

        echo "PASS"
    done
done

echo
echo "Testing per-day threads..."

OUTPUT="$RESULT_DIR/per_day_threads.csv"

run_simulation threads 1 strips "$OUTPUT"

if ! cmp -s "$REFERENCE" "$OUTPUT"; then
    echo "FAILED: per-day threads"
    diff -u "$REFERENCE" "$OUTPUT" || true
    exit 1
fi

echo "PASS: per-day threads"

echo
echo "All Part B correctness tests passed."
