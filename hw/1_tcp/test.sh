#!/usr/bin/env bash
set -xeuo pipefail

python3 -m pytest -vv protocol_test.py  -o  log_cli=true --durations=0
