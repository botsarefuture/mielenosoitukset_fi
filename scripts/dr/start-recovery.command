#!/bin/bash
set -euo pipefail
cd -- "$(dirname -- "$0")/../.."
exec python3 scripts/dr/recovery_control.py "$@"
