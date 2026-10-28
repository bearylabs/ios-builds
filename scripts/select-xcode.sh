#!/usr/bin/env bash
set -euo pipefail
if [[ -n "${XCODE_PATH:-}" ]]; then
  sudo xcode-select --switch "$XCODE_PATH/Contents/Developer"
fi
xcodebuild -version
python3 - <<'PY'
import subprocess
version = subprocess.check_output(['xcodebuild', '-version'], text=True).splitlines()[0].split()[1]
if tuple(map(int, version.split('.'))) < (26, 2):
    raise SystemExit('OpenWhispr requires Xcode 26.2 or later')
PY
