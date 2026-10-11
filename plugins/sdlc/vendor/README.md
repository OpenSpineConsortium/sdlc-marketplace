# Vendored code

sdlc_protocol/ is a copy of part of the sdlc_protocol package of OpenSpineConsortium/symphony-protocol, so that the plugin runs on a bare Python 3.12 with nothing installed and refuses the same pushes, with the same words, as the library and the template's tools/guard_push.py, which runs the same code. symphony-protocol's ecosystem.json says what this repository takes, and the copy holds exactly that:

- sdlc_protocol/guard.py: the push guard. It imports only the standard library, so no other module of the package is needed.
- sdlc_protocol/__init__.py: the package's docstring and its version.
- sdlc_protocol/vendoring.py: the check of the copy, which every copy carries.

VENDORED is the one record of the copy: its first line names the release and the commit of symphony-protocol it was made from, `sdlc-protocol <version> <commit>`, and each line after it the sha256 of one copied file and its path inside sdlc_protocol/. scripts/check.sh, the check CI runs on every pull request, holds the copy to it first of all:

```
python3 plugins/sdlc/vendor/sdlc_protocol/vendoring.py verify plugins/sdlc/vendor
```

which fails on a file whose bytes are not the ones recorded, a recorded file that is missing, or a file beside them that is not recorded. VENDORED sits in the same tree, so a pull request that edits the copy could rewrite it to match; tests/test_plugin.py therefore holds the record to the files the plugin needs and every file to the library's at the recorded commit, in the clone of symphony-protocol that SDLC_PROTOCOL names, or else one beside this repository. CI clones symphony-protocol, which is public, and names the clone, so there the comparison always runs, and fails when the clone has no such commit; with no clone named and none beside, as on a machine without one, it is skipped.

The library's guard.py docstring speaks of its cli.py and a "guard" subcommand; in this plugin, scripts/guard.py plays that part, reading the hook's JSON from stdin and calling guard.run().

## How the copy is refreshed

Never edit the copy by hand: change the code in symphony-protocol, by pull request there. When that change reaches symphony-protocol's main, its sync workflow vendors the new package into this repository and opens the pull request `symphony-protocol/sync` here, or updates the one already open, and sets it to merge by itself once this repository's check is green. When the copy's files change, the same commit raises the patch version in plugins/sdlc/.claude-plugin/plugin.json, which symphony-protocol's ecosystem.json names as this repository's version file: Claude Code keeps an installed plugin on its cached copy until that version changes, so the merge that brings a new guard is also the release that takes it to every session with the plugin installed, at its next plugin update. A sync that only moves VENDORED's commit, the copy's files being what they were, leaves the version alone.

To vendor by hand, from a clone of symphony-protocol:

```
python3 <symphony-protocol>/scripts/vendor.py <this repository>
```

which raises the plugin's version too when the copy's files change; then run `bash scripts/check.sh` here and land the change by pull request.
