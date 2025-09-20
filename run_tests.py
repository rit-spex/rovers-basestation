"""
Test file
"""

from __future__ import annotations
import argparse
import os
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
PYTEST_PATH = os.path.join(REPO_ROOT, 'xbee', 'tests', 'test_system_pytest.py')
HUMAN_PATH = os.path.join(REPO_ROOT, 'xbee', 'tests', 'test_system_human.py')

def run_pytest():
    env = os.environ.copy()
    env_pythonpath = env.get('PYTHONPATH', '')
    if REPO_ROOT not in env_pythonpath.split(os.pathsep):
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [REPO_ROOT, env_pythonpath]))

    print(f"Running pytest for: {PYTEST_PATH}\n")

    cmd = [sys.executable, '-m', 'pytest', 'xbee/tests/test_system_pytest.py']
    proc = subprocess.run(cmd, env=env)
    return proc.returncode == 0

def run_human():
    env = os.environ.copy()
    if REPO_ROOT not in env.get('PYTHONPATH', '').split(os.pathsep):
        env['PYTHONPATH'] = os.pathsep.join(filter(None, [REPO_ROOT, env.get('PYTHONPATH', '')]))

    print(f"Running human test script: {HUMAN_PATH}\n")
    cmd = [sys.executable, '-m', 'xbee.tests.test_system_human']
    proc = subprocess.run(cmd, env=env)
    return proc.returncode == 0

def prompt() -> str:
    print("Select which tests to run:")
    print("1) pytest (automated tests)")
    print("2) human (has words, use when something wrong)")
    print("3) both")
    choice = input("Enter 1/2/3 (default 1): ").strip() or '1'
    return {'1': 'pytest', '2': 'human', '3': 'both'}.get(choice, 'pytest')

def main(argv=None):
    parser = argparse.ArgumentParser(description='Run project tests (pytest or human script)')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--pytest', action='store_true', help='Run pytest on xbee/tests/test_system_pytest.py')
    group.add_argument('--human', action='store_true', help='Run the human test script xbee/tests/test_system_human.py')
    group.add_argument('--both', action='store_true', help='Run both tests sequentially')
    args = parser.parse_args(argv)

    # Wut mode
    if not any([args.pytest, args.human, args.both]):
        mode = prompt()
    elif args.pytest:
        mode = 'pytest'
    elif args.human:
        mode = 'human'
    else:
        mode = 'both'

    ok = True
    if mode in ('pytest', 'both'):
        ok = run_pytest() and ok

    if mode in ('human', 'both'):
        ok = run_human() and ok

    if ok:
        print('\nAll requested tests completed successfully.')
        return 0
    else:
        print('\nSome tests failed (non-zero exit code).')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())