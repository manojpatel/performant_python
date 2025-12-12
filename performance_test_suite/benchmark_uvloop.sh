#!/bin/bash
set -e

echo "🔬 Performance Benchmark: uvloop vs default asyncio"
echo "=================================================="
echo ""

# Configuration
ENDPOINT="http://localhost:8080/benchmark/500"
DURATION=10
CONCURRENCY=50

echo "📊 Test Configuration:"
echo "  Endpoint: $ENDPOINT"
echo "  Duration: ${DURATION}s"
echo "  Concurrency: $CONCURRENCY"
echo ""

# Check if hey is installed
if ! command -v hey &> /dev/null; then
    echo "⚠️  'hey' not found. Installing..."
    if command -v brew &> /dev/null; then
        brew install hey
    else
        echo "❌ Please install 'hey' manually:"
        echo "   brew install hey"
        echo "   OR download from: https://github.com/rakyll/hey"
        exit 1
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🟢 Test 1: WITH uvloop (current setup)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

hey -z ${DURATION}s -c $CONCURRENCY $ENDPOINT > /tmp/bench_with_uvloop.txt
cat /tmp/bench_with_uvloop.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔴 Test 2: WITHOUT uvloop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Temporarily disabling uvloop..."
echo ""

# Restart container with asyncio loop
LOOP_IMPLEMENTATION=asyncio docker compose up -d performant-python-app
sleep 5

echo "Running benchmark without uvloop..."
hey -z ${DURATION}s -c $CONCURRENCY $ENDPOINT > /tmp/bench_without_uvloop.txt
cat /tmp/bench_without_uvloop.txt

# Restore uvloop
LOOP_IMPLEMENTATION=uvloop docker compose up -d performant-python-app

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📈 Performance Comparison"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Extract key metrics
RPS_WITH=$(grep "Requests/sec:" /tmp/bench_with_uvloop.txt | awk '{print $2}')
RPS_WITHOUT=$(grep "Requests/sec:" /tmp/bench_without_uvloop.txt | awk '{print $2}')

P50_WITH=$(grep "50%:" /tmp/bench_with_uvloop.txt | awk '{print $2}')
P50_WITHOUT=$(grep "50%:" /tmp/bench_without_uvloop.txt | awk '{print $2}')

P99_WITH=$(grep "99%:" /tmp/bench_with_uvloop.txt | awk '{print $2}')
P99_WITHOUT=$(grep "99%:" /tmp/bench_without_uvloop.txt | awk '{print $2}')

echo "Requests per second:"
echo "  WITH uvloop:    $RPS_WITH req/s"
echo "  WITHOUT uvloop: $RPS_WITHOUT req/s"
echo ""

echo "Latency (p50):"
echo "  WITH uvloop:    $P50_WITH"
echo "  WITHOUT uvloop: $P50_WITHOUT"
echo ""

echo "Latency (p99):"
echo "  WITH uvloop:    $P99_WITH"
echo "  WITHOUT uvloop: $P99_WITHOUT"
echo ""

# Calculate improvement
IMPROVEMENT=$(echo "scale=2; ($RPS_WITH - $RPS_WITHOUT) / $RPS_WITHOUT * 100" | bc)
echo "⚡ Performance Improvement: ${IMPROVEMENT}%"
echo ""
echo "✅ Benchmark complete!"
