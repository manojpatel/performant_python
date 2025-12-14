#!/bin/bash
set -e

echo "🔬 Performance Profiling Script"
echo "================================"
echo ""

# Note: We rely on py-spy being installed in the container (via pyproject.toml)

# Get container PID for granian worker
echo "🔍 Finding Python worker process..."
CONTAINER_PID=$(docker exec performant-python-app pgrep -f "granian" | head -1)

if [ -z "$CONTAINER_PID" ]; then
    echo "❌ Could not find granian process"
    exit 1
fi

echo "✅ Found process: PID $CONTAINER_PID"
echo ""

# Generate load in background
echo "📊 Generating load (30 seconds)..."
(
    for i in {1..100}; do
        curl -s "http://localhost:8080/benchmark/$((RANDOM % 500 + 100))" > /dev/null &
        curl -s "http://localhost:8080/search?q=python" > /dev/null &
        curl -s "http://localhost:8080/search?q=rust" > /dev/null &
        sleep 0.3
    done
    wait
) &
LOAD_PID=$!

# Profile for 30 seconds
echo "🔍 Profiling for 30 seconds..."
docker exec performant-python-app py-spy record \
    --pid $CONTAINER_PID \
    --duration 30 \
    --format speedscope \
    --output /tmp/profile.json \
    2>&1 || echo "⚠️  Profiling completed with warnings"

# Wait for load to finish
wait $LOAD_PID 2>/dev/null || true

# Copy profile out
echo "📥 Extracting profile data..."
docker cp performant-python-app:/tmp/profile.json ./profile.json 2>/dev/null || {
    echo "⚠️  Could not extract JSON, trying SVG format..."
    docker exec performant-python-app py-spy record \
        --pid $CONTAINER_PID \
        --duration 10 \
        --format svg \
        --output /tmp/profile.svg
    docker cp performant-python-app:/tmp/profile.svg ./profile.svg
    echo "✅ Profile saved to: profile.svg"
    echo "📖 Open profile.svg in a browser to view the flame graph"
    exit 0
}

echo "✅ Profile saved to: profile.json"
echo "📖 View at: https://www.speedscope.app/ (upload profile.json)"
echo ""
echo "🔍 Quick Analysis:"
docker exec performant-python-app py-spy top --pid $CONTAINER_PID --duration 5 2>&1 | head -30

echo ""
echo "✅ Profiling complete!"
