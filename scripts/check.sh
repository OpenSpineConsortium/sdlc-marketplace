#!/usr/bin/env bash
# The marketplace's checks, run by CI (.github/workflows/ci.yml, the job
# "check") and by hand before every push. The vendored push guard comes
# first: vendoring.py, which sdlc-protocol copies in beside it, holds the
# copy to the sha256 of each file its VENDORED records, so a hand edit of
# the copy fails here, offline, on the pull request that made it, and the
# change goes to sdlc-protocol instead. One that rewrote VENDORED to match
# passes this line and fails tests/test_plugin.py, which compares the copy
# with the library itself in the clone SDLC_PROTOCOL names (CI clones it;
# .github/workflows/ci.yml). The tests come next because they
# need nothing but Python; claude plugin validate runs when the claude
# binary is on PATH, with --strict so that a warning fails as an error
# does: a warning is a field the runtime ignores, which is a manifest that
# does not say what it seems to.
set -eu
cd "$(dirname "$0")/.."

python3 plugins/sdlc/vendor/sdlc_protocol/vendoring.py verify plugins/sdlc/vendor

python3 -m unittest discover -s tests -v

if command -v claude >/dev/null 2>&1; then
  claude plugin validate --strict .
  claude plugin validate --strict plugins/sdlc
else
  echo "claude is not on PATH; claude plugin validate skipped"
fi

echo "checks ok"
