#!/bin/bash
# ------------------------------------------------------------------
#                          SPEX ROVER 2026
# ------------------------------------------------------------------
# file name     : setup.sh
# purpose       : rebuild the venv from requirements.txt and rewire
#                 the autoboot systemd service for this machine
# usage         : ./auto_boot/setup.sh [--install-service]
# created on    : 11/20/2026
# ------------------------------------------------------------------
set -euo pipefail

# A sourced ROS setup.bash sets PYTHONPATH to its site-packages, which
# shadows the local basestation package (and confuses pip's resolver).
# The venv is self-contained, so drop any inherited PYTHONPATH.
unset PYTHONPATH

cd "$(dirname "${BASH_SOURCE[0]}")/.."
REPO_ROOT="$(pwd)"

usage() {
    echo "usage: $0 [--install-service]"
    echo
    echo "  Rebuilds .venv from requirements.txt, verifies the imports,"
    echo "  and runs the test suite."
    echo
    echo "  --install-service   additionally write, enable, and restart the"
    echo "                      auto_boot.service systemd unit for the current"
    echo "                      user and repo path (prompts for sudo)."
}

INSTALL_SERVICE=0
for arg in "$@"; do
    case "$arg" in
        --install-service) INSTALL_SERVICE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown argument: $arg" >&2; usage; exit 2 ;;
    esac
done

# ------------------------------------------------------------------
# 1. Make sure the rovers-protocol submodule is present
# ------------------------------------------------------------------
echo "==> Checking git submodules"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git submodule update --init --recursive
else
    echo "not a git checkout - skipping submodule update"
fi

# ------------------------------------------------------------------
# 2. Rebuild the venv
# ------------------------------------------------------------------
echo "==> Rebuilding venv at $REPO_ROOT/.venv"
python3 -m venv --clear .venv
./.venv/bin/python3 -m pip install --upgrade pip
./.venv/bin/python3 -m pip install -r requirements.txt

# ------------------------------------------------------------------
# 3. Verify the imports (same ones the app and auto_boot.py use)
# ------------------------------------------------------------------
echo "==> Verifying imports"
./.venv/bin/python3 - <<'PY'
from basestation.gui import create_display  # noqa: F401
from basestation.protocol import CONSTANTS
import digi.xbee  # noqa: F401
print("imports OK - XBee port:", CONSTANTS.COMMUNICATION.DEFAULT_PORT)
PY

if ! ./.venv/bin/python3 -c "import tkinter" >/dev/null 2>&1; then
    echo "warning: tkinter unavailable - GUI falls back to headless" >&2
    echo "         (install python3-tk to enable the GUI)" >&2
fi

# ------------------------------------------------------------------
# 4. Run the test suite (pytest is a dev-only dependency)
# ------------------------------------------------------------------
echo "==> Running tests"
./.venv/bin/python3 -m pip install pytest
./.venv/bin/python3 -m pytest tests/ -q

# ------------------------------------------------------------------
# 5. Optionally install the systemd service for this machine
# ------------------------------------------------------------------
if [ "$INSTALL_SERVICE" -eq 1 ]; then
    if [ "$(id -u)" -eq 0 ] && [ -n "${SUDO_USER:-}" ]; then
        SERVICE_USER="$SUDO_USER"
    else
        SERVICE_USER="$(id -un)"
    fi
    SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
    SERVICE_HOME="$(getent passwd "$SERVICE_USER" | cut -d: -f6)"

    UNIT_FILE="$(mktemp)"
    trap 'rm -f "$UNIT_FILE"' EXIT
    cat > "$UNIT_FILE" <<EOF
[Unit]
Description=SPEX rover basestation
After=network-online.target
Wants=network-online.target
StartLimitBurst=5
StartLimitIntervalSec=60

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_GROUP
Restart=on-failure
RestartSec=10
TimeoutStopSec=10
Environment=HOME=$SERVICE_HOME
Environment=XBEE_NO_GUI=1
Environment=PYTHONUNBUFFERED=1
WorkingDirectory=$REPO_ROOT
ExecStart=/bin/bash $REPO_ROOT/auto_boot/auto_boot.sh

[Install]
WantedBy=multi-user.target
EOF

    echo "==> Installing auto_boot.service for $SERVICE_USER (sudo may prompt)"
    sudo bash -c "install -m 644 '$UNIT_FILE' /etc/systemd/system/auto_boot.service &&
                  systemctl daemon-reload &&
                  systemctl enable auto_boot.service &&
                  systemctl restart auto_boot.service"

    echo
    echo "service installed and started - watch the logs with:"
    echo "  journalctl -u auto_boot -f"
    echo "stop / disable it with:"
    echo "  sudo systemctl stop auto_boot && sudo systemctl disable auto_boot"
fi

echo
echo "done - run the basestation manually with:"
echo "  ./.venv/bin/python3 -m basestation"
