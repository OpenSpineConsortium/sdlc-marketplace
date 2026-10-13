---
description: Fetch the board and print it whole
allowed-tools: Bash(git fetch:*), Bash(git show:*)
---

The whole board, fetched now; the session hook shows only its first 120 lines, once, at the start:

!`git fetch --quiet origin +refs/heads/board:refs/remotes/origin/board 2>/dev/null; git show origin/board:STATE.md 2>/dev/null || echo "origin has no board branch yet; the first run of .github/workflows/board.yml makes it"`

Act on what it shows, as docs/agents/PROTOCOL.md requires: the claims, the open pull requests, the queue and the blockers.
