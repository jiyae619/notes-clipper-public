#!/usr/bin/env bash
# Every test in one command: bash tests/run.sh
# Known gaps are reported but don't fail the run; anything else that fails does.
here="$(cd "$(dirname "$0")" && pwd)"
rc=0
echo "== watcher (about 35 s: each run waits 2 s for Chrome to finish renaming downloads)"
bash "$here/test_watcher.sh" || rc=1
echo
echo "== capture records"
bash "$here/test_records.sh" || rc=1
echo
echo "== extension"
node --test --test-reporter=spec "$here/test_sidepanel.mjs" || rc=1
exit $rc
