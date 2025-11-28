"""
Test file
"""

from __future__ import annotations
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
# Default to running the entire tests/ directory rather than a single file
PYTEST_PATH = "tests"


def run_pytest():
    env = os.environ.copy()
    env_pythonpath = env.get("PYTHONPATH", "")
    if REPO_ROOT not in env_pythonpath.split(os.pathsep):
        env["PYTHONPATH"] = os.pathsep.join(filter(None, [REPO_ROOT, env_pythonpath]))

    print(f"Running pytest for: {PYTEST_PATH}\n")
    # Running the tests directory will execute all tests under tests/ by default
    cmd = [sys.executable, "-m", "pytest", PYTEST_PATH]
    proc = subprocess.run(cmd, env=env)
    return proc.returncode == 0


# pytest will be run by default; interactive prompting has been removed.


def main(_argv=None):
    # Run pytest by default (no CLI flags supported)
    ok = run_pytest()

    if ok:
        print("\nAll requested tests completed successfully.")
        return 0
    else:
        print("\nSome tests failed (non-zero exit code).")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
