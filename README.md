# sdlc-marketplace

A Claude Code plugin marketplace with one plugin, `sdlc`: the Claude Code side of the way of working that OpenSpineConsortium/sdlc-template sets up, where the queue is GitHub Issues, a claim is the first push of a branch `claude/<issue>`, the board is the file STATE.md on the branch `board`, and the default branch takes only pull requests. The template's repository holds the rules; this plugin brings the procedures and the fences to every session that works in such a repository, so they arrive by a plugin update (`claude plugin update sdlc@sdlc-marketplace`) instead of by copying files from one repository into the next.

## What the plugin does

- Skills `/sdlc:claim`, `/sdlc:remember` and `/sdlc:checkpoint`: the three procedures a piece of work meets, in that order. Taking an issue the way the repository's docs/agents/PROTOCOL.md requires; adding or correcting a fact in docs/memory/ in the same pull request as the change it came from; recording where the work stands in .claude/session.md and in the marker section of CLAUDE.md. They are the template's own skills and act on the template's files, so they name the repository's tools as the template does (tools/marked_section.py, scripts/check.sh).
- Command `/sdlc:board`: fetches the board and prints it whole.
- A push guard, before every Bash call: refuses a push to the default branch or to `board`, a plain `--force` anywhere, a push of every branch at once, and `--force-with-lease` outside a `claude/` branch, with exit code 2 and the reason on stderr, which Claude Code feeds back into the session. Anything it cannot read it lets through, since branch protection on GitHub still stands behind it.
- A document check, after every Edit and Write that touches CLAUDE.md, README.md, .claude/, docs/, tools/ or .github/: runs the repository's own tools/check_docs.py, the checks its CI runs, and feeds any problem back at once with exit code 2. A repository without that file has no checks to run, and the hook stays silent.
- At session start: how far the checkout is ahead of and behind the default branch, and the first 120 lines of the board.

These are the hooks the template wires in its .claude/settings.json, with the same exit codes and the same messages. The push guard is the library's newer reading of a command, which ends a command at each unquoted newline as the shell does, so a push to main on the third line of a multi-line call is refused too. A repository that enables the plugin and keeps its own hooks runs each of them twice, and prints the board twice; keep one wiring or the other.

## Install

In Claude Code:

```
/plugin marketplace add OpenSpineConsortium/sdlc-marketplace
/plugin install sdlc@sdlc-marketplace
```

The install goes to the user scope by default, which turns the push guard on in every repository the user opens; the guard refuses a push to the default branch wherever it runs. For a repository made from the template, the project preset below is the better fit, or the shell form with the project scope: `claude plugin install sdlc@sdlc-marketplace --scope project`.

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
      }
    }
  },
  "enabledPlugins": {
    "sdlc@sdlc-marketplace": true
  }
}
```

Entries in a repository's settings apply only after each person accepts the workspace trust dialog for the folder.

## What a plugin cannot ship

Some of the template is not a plugin's to carry, and stays in the repository made from OpenSpineConsortium/sdlc-template:

- Rules: Claude Code has no plugin component for .claude/rules/; the board, memory and writing rules stay repository files. A rule that must always hold is enforced here as a hook, which is why the push guard is one.
- CLAUDE.md: a CLAUDE.md at a plugin's root is not loaded. The repository's CLAUDE.md, with its imports of docs/project.md, docs/agents/PROTOCOL.md and docs/memory/MEMORY.md, stays where it is.
- Permissions: a plugin's settings.json keeps only the keys agent and subagentStatusLine and drops the rest, so the allow list stays in the repository's .claude/settings.json.
- The files the skills act on: docs/agents/PROTOCOL.md, docs/agents/claims/, docs/memory/, tools/check_docs.py, tools/marked_section.py, scripts/check.sh, and the workflows that write the board.

## Where the code comes from

- The push guard's rules are plugins/sdlc/vendor/sdlc_protocol/guard.py, vendored unchanged from OpenSpineConsortium/sdlc-protocol, the library the template's tools are being extracted into; plugins/sdlc/vendor/README.md records the revision and its sha256, and plugins/sdlc/scripts/guard.py is the thin entry point that reads the hook's JSON and calls it.
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
tests/test_plugin.py
scripts/check.sh
```

## Checks

`bash scripts/check.sh` runs tests/test_plugin.py (Python 3.12, standard library) and, when the claude binary is on PATH, `claude plugin validate --strict` on the marketplace and on the plugin. Bump the version in plugins/sdlc/.claude-plugin/plugin.json, the one place it is set, with every release; `claude plugin tag plugins/sdlc` then tags the release as sdlc--v<version> after checking that the manifest and the marketplace entry agree.

## License

MIT; see LICENSE.
