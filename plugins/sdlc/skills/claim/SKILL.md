---
name: claim
description: Use before the first change for an open issue labelled todo, to take the issue the way docs/agents/PROTOCOL.md requires.
---

# Claim an issue

A claim is the first push of the branch `claude/<issue>`; whoever pushes first has the issue, because GitHub refuses the second push of the same name. The steps below are PROTOCOL.md's, in order. N stands for the issue's number throughout, and D for the default branch: the name `git symbolic-ref --short refs/remotes/origin/HEAD` prints after `origin/`, or main when it prints nothing.

1. Fetch and read the board: `git fetch origin`, then `git fetch origin board && git show origin/board:STATE.md`. The board is the file STATE.md on the branch `board`, which the session hook prints too; docs/agents/STATE.md on the default branch only describes it. Take an issue the Queue section shows as unclaimed, labelled todo, with no open blocker in its way. An issue with a branch `claude/N` on origin or a file `docs/agents/claims/N.md` on the default branch belongs to another account.
2. Branch from the default branch: `git switch -c claude/N origin/D`.
3. Write the claim file `docs/agents/claims/N.md` from the template in docs/agents/claims/README.md: the account, the plan in a few sentences, the files you expect to touch, the issue's link.
4. Commit it alone, as the branch's first commit, and push: `git add docs/agents/claims/N.md`, `git commit -m "Claim #N"`, `git push -u origin claude/N`. Never with force.
5. If the push is refused because the branch exists, another account claimed it between your fetch and your push. Delete your local branch (`git switch D`, then `git branch -D claude/N`) and go back to step 1 with another issue.
6. Announce it on the issue: add the label claimed and your account's label (account:main for the main account), and post the plan as a comment. With gh: `gh issue edit N --add-label claimed,account:main` and `gh issue comment N --body-file docs/agents/claims/N.md`; without it, the issue's page.
7. Open a draft pull request at once from `claude/N` to D, with "Closes #N" in its body, so the board lists the work from its first minute: `gh pr create --draft --base D --title "..." --body "Closes #N"`. Push often. When the board comments "main moved", rebase on `origin/D` and push with `--force-with-lease`, the one forced push the protocol allows, and only on this branch.
8. Finishing is in PROTOCOL.md: the pull request deletes the claim file, says "Closes #N", passes `bash scripts/check.sh` and is marked ready; the issue gets the label in-review, and the merge closes it.
