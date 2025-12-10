#!/bin/bash
set -e

if [ "$ENABLE_TRACING" = "true" ]; then
    echo "🔍 Tracing ENABLED. Manual spans will be exported."
    exec granian \
        --interface asgi \
        --host 0.0.0.0 \
        --port 8080 \
        --workers 1 \
        --loop uvloop \
        src.main:app
else
    echo "🚫 Tracing DISABLED."
    exec granian \
        --interface asgi \
        --host 0.0.0.0 \
        --port 8080 \
        --workers 1 \
        --loop uvloop \
        src.main:app
fi
