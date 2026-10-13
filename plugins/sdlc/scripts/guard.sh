#!/usr/bin/env bash
# The PreToolUse hook on the Bash tool, from the plugin's hooks/hooks.json:
# it hands the tool call on stdin to the push guard, guard.py, and answers
# with the guard's own exit code and reason. It is here so that the guard
# fails closed. Claude Code reads exit code 2 as "stop this call" and every
# other failure as no objection, so a guard that cannot run would pass
# every push in silence; on Windows python3 is often the Microsoft Store's
# stub, which only says that Python is not installed. When the guard could
# not decide, a command that may push is refused with the way to fix it,
# and any other command goes ahead, so a missing Python never wedges the
# session.

set -u

# guard.py beside this script, by swapping the name, since on Windows the
# path may be written with backslashes, which dirname does not split.
guard="${0%guard.sh}guard.py"
payload=$(cat)
code=127
if [ -f "$guard" ]; then
  reason=$(printf '%s' "$payload" | python3 "$guard" 2>&1 >/dev/null)
  code=$?
fi

case "$code" in
  0)
    exit 0
    ;;
  2)
    printf '%s\n' "$reason" >&2
    exit 2
    ;;
esac

if printf '%s' "$payload" | grep -q 'git.*push'; then
  printf '%s\n' "the push guard could not run (python3 exited $code), so this push is refused: install Python 3.12 or later and put it first on PATH, then push again (docs/agents/PROTOCOL.md)" >&2
  exit 2
fi
exit 0
