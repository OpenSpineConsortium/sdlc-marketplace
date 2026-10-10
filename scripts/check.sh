#!/usr/bin/env bash
# The marketplace's checks, run by hand before every push. The tests come
# first because they need nothing but Python; claude plugin validate runs
# when the claude binary is on PATH, with --strict so that a warning fails
# as an error does: a warning is a field the runtime ignores, which is a
# manifest that does not say what it seems to.
set -eu
cd "$(dirname "$0")/.."

python3 -m unittest discover -s tests -v

if command -v claude >/dev/null 2>&1; then
  claude plugin validate --strict .
  claude plugin validate --strict plugins/sdlc
else
  echo "claude is not on PATH; claude plugin validate skipped"
fi

echo "checks ok"
