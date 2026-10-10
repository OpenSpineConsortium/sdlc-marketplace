"""Refuse a git push the board rules forbid, before it runs.

Claude Code runs this as a PreToolUse hook on the Bash tool, wired in the
plugin's hooks/hooks.json: the tool call arrives as JSON on stdin, exit
code 2 stops it, and stderr goes back into the session as the reason. The
rules are not here but in the vendored push guard of sdlc_protocol
(vendor/sdlc_protocol/guard.py, copied from OpenSpineConsortium/
sdlc-protocol), so the plugin, the template and the library refuse the
same pushes with the same words; this file only does what the template's
tools/guard_push.py main does around them, reading stdin and speaking the
hook's exit codes.

A payload that is not JSON passes, as the library lets pass every payload
it cannot read: the hook is the first fence and branch protection on
GitHub the second, and a hook that wedged the session would be worse than
one that missed a push GitHub still refuses.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "vendor"))

from sdlc_protocol import guard  # noqa: E402


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return guard.PASS
    code, reason = guard.run(payload)
    if reason:
        print(reason, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
