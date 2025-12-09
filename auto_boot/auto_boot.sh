#!/bin/bash
# autoBoot.sh
# This script activates the virtual environment and runs the XBee module.
# It is called by the systemd service (autoBoot.service).

# Resolve script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Change to project root
cd "$PROJECT_ROOT" || {
  echo "ERROR: Failed to change to project directory: $PROJECT_ROOT" >&2
  logger -t autoBoot "ERROR: Failed to change to project directory"
  exit 1
}

# Log startup
logger -t autoBoot "Starting autoBoot script from $PROJECT_ROOT"

# Activate virtual environment
if [[ ! -f .venv/bin/activate ]]; then
  echo "ERROR: Virtual environment not found at .venv/bin/activate" >&2
  logger -t autoBoot "ERROR: Virtual environment not found"
  exit 1
fi

source .venv/bin/activate || {
  echo "ERROR: Failed to activate virtual environment at .venv/bin/activate" >&2
  logger -t autoBoot "ERROR: Failed to activate virtual environment"
  exit 1
}

# Log success
logger -t autoBoot "Virtual environment activated successfully"

# Run the XBee module
if ! command -v python3 &> /dev/null; then
  echo "ERROR: python3 not found in PATH" >&2
  logger -t autoBoot "ERROR: python3 not found"
  exit 1
fi

python3 -m xbee || {
  echo "ERROR: Failed to run xbee module" >&2
  logger -t autoBoot "ERROR: Failed to run xbee module"
  exit 1
}
