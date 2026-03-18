#!/bin/bash

# dev.sh - Development script that watches for changes and reloads the application
# Usage: ./dev.sh [--ramses-port PORT] [additional args...]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if inotifywait is available
if ! command -v inotifywait &> /dev/null; then
    echo -e "${RED}Error: inotifywait not found${NC}"
    echo "Please install inotify-tools:"
    echo "  Debian/Ubuntu: sudo apt-get install inotify-tools"
    echo "  Fedora/RHEL:   sudo dnf install inotify-tools"
    echo "  Arch:          sudo pacman -S inotify-tools"
    exit 1
fi

# Get the script directory and project root
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
cd "$PROJECT_ROOT"

echo -e "${BLUE}Project root: $PROJECT_ROOT${NC}"

# Prefer .venv, then venv
if [ -d "$PROJECT_ROOT/.venv/bin" ]; then
    echo -e "${BLUE}Activating .venv...${NC}"
    source "$PROJECT_ROOT/.venv/bin/activate"
elif [ -d "$PROJECT_ROOT/venv/bin" ]; then
    echo -e "${BLUE}Activating venv...${NC}"
    source "$PROJECT_ROOT/venv/bin/activate"
else
    echo -e "${YELLOW}Warning: No .venv or venv — using system python${NC}"
    echo -e "${YELLOW}Create: python3 -m venv .venv && .venv/bin/pip install -e .${NC}"
fi

echo -e "${BLUE}Ensuring package deps (pip install -e .)...${NC}"
pip install -q -e "$PROJECT_ROOT" || true

# Default arguments - you can modify these or pass via command line
DEFAULT_RAMSES_PORT="/dev/ttyACM0"
DEFAULT_PORT="8000"
DEFAULT_LOG_LEVEL="INFO"

# Parse command line arguments or use defaults
ARGS="$@"
if [ -z "$ARGS" ]; then
    ARGS="--ramses-port ${DEFAULT_RAMSES_PORT} --port ${DEFAULT_PORT} --log-level ${DEFAULT_LOG_LEVEL}"
    echo -e "${YELLOW}No arguments provided, using defaults: ${ARGS}${NC}"
fi

# Extract port from args (supports `--port 8000` and `--port=8000`)
PORT="${DEFAULT_PORT}"
if [[ "$ARGS" =~ --port[=[:space:]]*([0-9]+) ]]; then
    PORT="${BASH_REMATCH[1]}"
fi

# Process ID tracking
APP_PID=""

# Kill anything listening on the configured HTTP port (prevents "address in use")
kill_on_port() {
    local port="$1"
    local pids=""
    # Example line:
    # users:(("python",pid=3852599,fd=6))
    while IFS= read -r line; do
        pid="$(echo "$line" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p')"
        if [ -n "$pid" ]; then
            pids="$pids $pid"
        fi
    done < <(ss -ltnp "sport = :$port" 2>/dev/null | awk 'NR>1')

    # shellcheck disable=SC2086
    for pid in $pids; do
        if kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Killing listener PID on :${port}: ${pid}${NC}"
            kill -TERM "$pid" 2>/dev/null || true
        fi
    done

    # Give processes a moment to shutdown gracefully.
    sleep 0.5

    # Escalate if anything is still listening.
    while IFS= read -r line; do
        pid="$(echo "$line" | sed -n 's/.*pid=\([0-9]\+\).*/\1/p')"
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            echo -e "${YELLOW}Force killing listener PID on :${port}: ${pid}${NC}"
            kill -KILL "$pid" 2>/dev/null || true
        fi
    done < <(ss -ltnp "sport = :$port" 2>/dev/null | awk 'NR>1')
}

# Cleanup function to kill the app when script exits
cleanup() {
    echo -e "\n${YELLOW}Stopping development server...${NC}"
    if [ ! -z "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        echo -e "${BLUE}Killing process $APP_PID${NC}"
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi

    # Also kill anything else that might still be bound to the port
    # (e.g. if a previous run of this script left an orphan process).
    kill_on_port "$PORT"
    echo -e "${GREEN}Development server stopped${NC}"
    exit 0
}

# Set up trap to handle Ctrl+C and other termination signals
trap cleanup SIGINT SIGTERM EXIT

# Function to start the application
start_app() {
    if [ ! -z "$APP_PID" ] && kill -0 "$APP_PID" 2>/dev/null; then
        echo -e "${BLUE}Stopping previous instance (PID: $APP_PID)...${NC}"
        kill -TERM "$APP_PID" 2>/dev/null || true
        wait "$APP_PID" 2>/dev/null || true
    fi

    # If an older dev.sh (or crashed run) left something on the port,
    # kill it before starting a new instance.
    kill_on_port "$PORT"
    
    echo -e "${GREEN}Starting application with args: ${ARGS}${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    
    # Start the application in the background
    cd "$PROJECT_ROOT"
    python -m honeywell_radio_exporter $ARGS &
    APP_PID=$!
    
    echo -e "${GREEN}Application started with PID: $APP_PID${NC}"
    echo -e "${BLUE}Watching for changes in: honeywell_radio_exporter/, tests/, pyproject.toml${NC}"
    echo -e "${BLUE}Press Ctrl+C to stop${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}\n"
}

# Start the application initially
start_app

# Watch for changes in Python files and configuration files
while true; do
    # Wait for file changes using inotifywait
    # Watch: .py files, pyproject.toml, requirements.txt
    # Events: modify, create, delete, move
    cd "$PROJECT_ROOT"
    FILE_CHANGED=$(inotifywait -r -e modify,create,delete,move \
        --exclude '(__pycache__|\.pyc$|\.git|venv|\.venv|htmlcov|\.tox|\.pytest_cache|coverage\.xml|bandit-report\.json|\.swp$|\.swx$)' \
        --format '%w%f' \
        "$PROJECT_ROOT/honeywell_radio_exporter/" \
        "$PROJECT_ROOT/tests/" \
        "$PROJECT_ROOT/pyproject.toml" \
        "$PROJECT_ROOT/requirements.txt" 2>/dev/null || true)
    
    if [ ! -z "$FILE_CHANGED" ]; then
        echo -e "\n${YELLOW}Change detected in: $FILE_CHANGED${NC}"
        echo -e "${YELLOW}Reloading application...${NC}"
        
        # Small delay to allow file writes to complete
        sleep 0.5
        
        # Restart the application
        start_app
    fi
done

