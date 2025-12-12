#!/bin/bash
set -e

# Default to uvloop if not specified
LOOP_IMPL=${LOOP_IMPLEMENTATION:-uvloop}

if [ "$ENABLE_TRACING" = "true" ]; then
    echo "🔍 Tracing ENABLED. Manual spans will be exported."
    exec granian \
        --interface asgi \
        --host 0.0.0.0 \
        --port 8080 \
        --workers 1 \
        --loop $LOOP_IMPL \
        src.main:app
else
    echo "🚫 Tracing DISABLED."
    exec granian \
        --interface asgi \
        --host 0.0.0.0 \
        --port 8080 \
        --workers 1 \
        --loop $LOOP_IMPL \
        src.main:app
fi
