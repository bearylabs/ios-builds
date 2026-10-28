#!/usr/bin/env bash
set -euo pipefail
: "${APP_CONFIG:?}" "${SOURCE_SHA:?}" "${RUNNER_TEMP:?}" "${ARTIFACT_AGE_RECIPIENT:?}"
app_dir=$(python3 -c 'import json,os; print(json.loads(os.environ["APP_CONFIG"])["directory"])')
scheme=$(python3 -c 'import json,os; print(json.loads(os.environ["APP_CONFIG"])["scheme"])')
cd "$GITHUB_WORKSPACE/source/$app_dir"
# Source install hooks execute here, where no Apple credentials exist.
npm ci --no-audit --no-fund
bundle config set --local path "$RUNNER_TEMP/bundle"
bundle install
npx --no-install expo prebuild --platform ios --clean --no-install
(cd ios && bundle exec pod install)
workspace=$(find "$PWD/ios" -maxdepth 1 -name '*.xcworkspace' -type d -print)
[[ -n "$workspace" && "$workspace" != *$'\n'* ]] || { echo 'Expected exactly one workspace'; exit 1; }
mkdir -p "$RUNNER_TEMP/output"
xcodebuild archive \
  -workspace "$workspace" -scheme "$scheme" -configuration Release \
  -destination 'generic/platform=iOS' \
  -archivePath "$RUNNER_TEMP/output/App.xcarchive" \
  -derivedDataPath "$RUNNER_TEMP/DerivedData" \
  CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO CODE_SIGN_IDENTITY='' \
  CURRENT_PROJECT_VERSION="${GITHUB_RUN_NUMBER}.${GITHUB_RUN_ATTEMPT}" \
  | tee "$RUNNER_TEMP/output/xcodebuild.log"
python3 "$GITHUB_WORKSPACE/control/scripts/archive.py" "$RUNNER_TEMP/output/App.xcarchive"
ditto -c -k --sequesterRsrc --keepParent "$RUNNER_TEMP/output/App.xcarchive" "$RUNNER_TEMP/output/archive.zip"
age --encrypt --recipient "$ARTIFACT_AGE_RECIPIENT" \
  --output "$RUNNER_TEMP/output/archive.zip.age" "$RUNNER_TEMP/output/archive.zip"
rm -rf "$RUNNER_TEMP/output/App.xcarchive" "$RUNNER_TEMP/output/archive.zip"
python3 - <<'PY'
import json, os, subprocess
from pathlib import Path
metadata = {
    'app': json.loads(os.environ['APP_CONFIG']),
    'source_sha': os.environ['SOURCE_SHA'],
    'workflow_sha': os.environ.get('GITHUB_SHA'),
    'run': os.environ.get('GITHUB_RUN_ID'),
    'xcode': subprocess.check_output(['xcodebuild', '-version'], text=True).strip(),
    'distribution': 'age-encrypted unsigned archive, NOT installable',
}
Path(os.environ['RUNNER_TEMP'], 'output', 'build.json').write_text(json.dumps(metadata, indent=2))
PY
