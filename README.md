# sdlc-marketplace

A Claude Code plugin marketplace with one plugin, `sdlc`: the Claude Code side of the way of working that OpenSpineConsortium/sdlc-template sets up, where the queue is GitHub Issues, a claim is the first push of a branch `claude/<issue>`, the board is the file STATE.md on the branch `board`, and the default branch takes only pull requests. The template's repository holds the rules; this plugin brings the procedures and the fences to every session that works in such a repository, so they arrive by a plugin update (`claude plugin update sdlc@sdlc-marketplace`) instead of by copying files from one repository into the next.

## Where this repository fits

This repository is one of the four that run a copy of the claim protocol's library, OpenSpineConsortium/sdlc-protocol. The library's [ECOSYSTEM.md](https://github.com/OpenSpineConsortium/sdlc-protocol/blob/main/ECOSYSTEM.md) shows them all: what each one is, which modules of the library each one copies, and how a change to the library reaches every copy by a pull request of its own. This one takes the push guard, with the two files every copy carries (the package's version and the check of the copy), into plugins/sdlc/vendor/, and names plugins/sdlc/.claude-plugin/plugin.json as its version file: the sync's pull request raises the plugin's version whenever the copy's files change, so one push to the library's main is also the plugin's release.

## What the plugin does

- Skills `/sdlc:claim`, `/sdlc:remember` and `/sdlc:checkpoint`: the three procedures a piece of work meets, in that order. Taking an issue the way the repository's docs/agents/PROTOCOL.md requires; adding or correcting a fact in docs/memory/ in the same pull request as the change it came from; recording where the work stands in .claude/session.md and in the marker section of CLAUDE.md. They are the template's own skills and act on the template's files, so they name the repository's tools as the template does (tools/marked_section.py, scripts/check.sh).
- Command `/sdlc:board`: fetches the board and prints it whole.
- A push guard, before every Bash call: refuses a push to the default branch or to `board`, a plain `--force` anywhere, a push of every branch at once, and `--force-with-lease` outside a `claude/` branch, with exit code 2 and the reason on stderr, which Claude Code feeds back into the session. Anything it cannot read it lets through, since branch protection on GitHub still stands behind it.
- A document check, after every Edit and Write that touches CLAUDE.md, README.md, .claude/, docs/, tools/ or .github/: runs the repository's own tools/check_docs.py, the checks its CI runs, and feeds any problem back at once with exit code 2. A repository without that file has no checks to run, and the hook stays silent.
- At session start: how far the checkout is ahead of and behind the default branch, and the first 120 lines of the board.

These are the hooks the template wires in its .claude/settings.json, with the same exit codes and the same messages. The push guard is the library's code, which the template's tools/guard_push.py runs too; it ends a command at each unquoted newline as the shell does, so a push to main on the third line of a multi-line call is refused. A repository that enables the plugin and keeps its own hooks runs each of them twice, and prints the board twice; keep one wiring or the other.

## Install

In Claude Code:

```
/plugin marketplace add OpenSpineConsortium/sdlc-marketplace
/plugin install sdlc@sdlc-marketplace
```

The install goes to the user scope by default, which turns the push guard on in every repository the user opens; the guard refuses a push to the default branch wherever it runs. For a repository made from the template, the project preset below is the better fit, or the shell form with the project scope: `claude plugin install sdlc@sdlc-marketplace --scope project`.

Claude Code turns auto-update off by default for a marketplace that is not Anthropic's, so an install made this way takes a new release only when asked: `claude plugin update sdlc@sdlc-marketplace`, or turn auto-update on once under `/plugin`, Marketplaces, sdlc-marketplace, Enable auto-update. The project preset below turns it on for everyone who works in the repository.

The marketplace needs only Python 3.12 or later, bash and git on the machine: the plugin's scripts use the standard library alone.

## The project preset

A repository made from the template enables the plugin for everyone who works in it with these two keys in its committed .claude/settings.json, beside the keys it already has:

```json
{
  "extraKnownMarketplaces": {
    "sdlc-marketplace": {
      "source": {
        "source": "github",
        "repo": "OpenSpineConsortium/sdlc-marketplace"
      },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "sdlc@sdlc-marketplace": true
  }
}
```

Entries in a repository's settings apply only after each person accepts the workspace trust dialog for the folder. `autoUpdate` keeps the marketplace refreshing in the background after a session starts, so a release reaches each session by itself: the new version is on disk within ten minutes of a session's first message and loads at `/reload-plugins` or the next session.

## What a plugin cannot ship

Some of the template is not a plugin's to carry, and stays in the repository made from OpenSpineConsortium/sdlc-template:

- Rules: Claude Code has no plugin component for .claude/rules/; the board, memory and writing rules stay repository files. A rule that must always hold is enforced here as a hook, which is why the push guard is one.
- CLAUDE.md: a CLAUDE.md at a plugin's root is not loaded. The repository's CLAUDE.md, with its imports of docs/project.md, docs/agents/PROTOCOL.md and docs/memory/MEMORY.md, stays where it is.
- Permissions: a plugin's settings.json keeps only the keys agent and subagentStatusLine and drops the rest, so the allow list stays in the repository's .claude/settings.json.
- The files the skills act on: docs/agents/PROTOCOL.md, docs/agents/claims/, docs/memory/, tools/check_docs.py, tools/marked_section.py, scripts/check.sh, and the workflows that write the board.

## Where the code comes from

- The push guard's rules are plugins/sdlc/vendor/sdlc_protocol/guard.py, vendored unchanged from OpenSpineConsortium/sdlc-protocol, the library the template's tools now run from as well; plugins/sdlc/scripts/guard.py is the thin entry point that reads the hook's JSON and calls it. plugins/sdlc/vendor/VENDORED records the release, the commit and the sha256 of every copied file, and the check holds the copy to it, so the copy is never edited here: sdlc-protocol's sync workflow opens the pull request `sdlc-protocol/sync` in this repository whenever the package changes on the library's main, with the plugin's version raised in the same commit when the copy's files changed, and plugins/sdlc/vendor/README.md says how to vendor by hand.
- plugins/sdlc/scripts/check_edit.py and plugins/sdlc/scripts/session-start.sh are the template's tools/check_edit.py and .claude/hooks/session-start.sh, changed only where the plugin's place differs: the edit check loads the repository's tools/check_docs.py instead of a sibling module, and the session hook falls back to main where the template fills in its own default branch.
- The skills and the command are the template's .claude/skills/ and .claude/commands/board.md; the claim skill reads the default branch from git where the template's copy has it filled in.

## Layout

```
.claude-plugin/marketplace.json     the marketplace: one plugin, sdlc
plugins/sdlc/.claude-plugin/plugin.json
plugins/sdlc/skills/                claim, remember, checkpoint
plugins/sdlc/commands/board.md
plugins/sdlc/hooks/hooks.json       SessionStart, PreToolUse on Bash, PostToolUse on Edit|Write
plugins/sdlc/scripts/               the hooks' scripts
plugins/sdlc/vendor/sdlc_protocol/  the vendored push guard
plugins/sdlc/vendor/VENDORED        its record: release, commit, sha256 of each file
tests/test_plugin.py
scripts/check.sh
.github/workflows/ci.yml            the job "check", which runs scripts/check.sh
```

## Checks

`bash scripts/check.sh` verifies the vendored push guard against plugins/sdlc/vendor/VENDORED, runs tests/test_plugin.py (Python 3.12, standard library) and, when the claude binary is on PATH, `claude plugin validate --strict` on the marketplace and on the plugin. CI runs the same script on every pull request and every push to main, as the job named `check` (.github/workflows/ci.yml); the runner has no claude binary, so the validation runs where the checks are run by hand. The version in plugins/sdlc/.claude-plugin/plugin.json, the one place it is set, is what tells an install there is a release: Claude Code keeps an installed plugin on its cached copy until that string changes, however many commits land here. A sync pull request raises its patch number by itself whenever the vendored copy's files change (sdlc-protocol's ecosystem.json names this file as the marketplace's version file), so a new guard is released by the same merge that brings it. A change to the plugin's own files (its skills, its command, its hooks and their scripts) takes a raise of the version by hand in the same pull request. `claude plugin tag plugins/sdlc` can then tag a release as sdlc--v<version>, after checking that the manifest and the marketplace entry agree, for whoever pins one; an install does not need the tag to update.

## License

MIT; see LICENSE.
