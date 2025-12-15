#!/bin/bash

# Consolidated Pre-Commit Check Script (Shell Version)
# Runs ruff, mypy, refurb, and bandit with nice formatting.

# ANSI Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
BLUE='\033[0;34m'
YELLOW='\033[0;33m'
RESET='\033[0m'

# Track failures
FAILURES=0
FAILED_LOGS=""

print_status() {
    local name="$1"
    local status="$2"
    local duration="$3"
    
    if [ "$status" == "0" ]; then
        echo -e "\r${BLUE}Running ${name}... ${GREEN}PASSED${RESET} (${duration}s)"
    else
        echo -e "\r${BLUE}Running ${name}... ${RED}FAILED${RESET} (${duration}s)"
        FAILURES=$((FAILURES + 1))
    fi
}

run_check() {
    local name="$1"
    shift
    local cmd=("$@")
    
    echo -ne "${BLUE}Running ${name}...${RESET}"
    
    start_ts=$(date +%s%N)
    
    # Run command and capture output
    output=$("${cmd[@]}" 2>&1)
    status=$?
    
    end_ts=$(date +%s%N)
    duration=$(( (end_ts - start_ts) / 1000000000 )).$(( ((end_ts - start_ts) / 10000000) % 100 ))
    
    print_status "$name" "$status" "$duration"
    
    if [ "$status" -ne 0 ]; then
        FAILED_LOGS="${FAILED_LOGS}\n${YELLOW}--- ${name} Output ---${RESET}\n${output}\n${YELLOW}-----------------------${RESET}\n"
    elif [ "$name" == "Pytest" ]; then
        # Always show output for Pytest to see coverage report
        echo -e "${output}"
    fi
}

echo -e "${BLUE}=== Starting Pre-Commit Checks (Shell) ===${RESET}\n"

# 1. Ruff Format
run_check "Ruff Format" uv run ruff format . --check

# 2. MyPy
# Use --no-incremental to fix persistent cache corruption issues
run_check "MyPy" uv run mypy . --no-incremental

# 3. Refurb
run_check "Refurb" uv run refurb .

# 4. Bandit
# 4. Bandit
# "parametrized for files by default and full for all"
BANDIT_ARGS="-r"
BANDIT_TARGET="src/"  # Default

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --bandit-all)
      BANDIT_TARGET=". -x .venv"
      shift # past argument
      ;;
    --bandit-folders)
      BANDIT_TARGET="$2"
      shift # past argument
      shift # past value
      ;;
    *)
      # unknown option
      shift # past argument
      ;;
  esac
done

run_check "Bandit" uv run bandit $BANDIT_ARGS $BANDIT_TARGET -q

# 5. Pytest
# Reports coverage for 'src' folder (Fail if < 80%)
run_check "Pytest" uv run pytest --cov=src --cov-report=term-missing --cov-fail-under=80

echo -e "\n${BLUE}=== Results ===${RESET}"

if [ $FAILURES -eq 0 ]; then
    echo -e "${GREEN}All checks passed! 🚀${RESET}"
    exit 0
else
    echo -e "${RED}Some checks failed! Details below:${RESET}"
    echo -e "$FAILED_LOGS"
    exit 1
fi
