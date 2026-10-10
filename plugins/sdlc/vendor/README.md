# Vendored code

sdlc_protocol/ is a copy of part of the sdlc_protocol package of OpenSpineConsortium/sdlc-protocol, so that the plugin runs on a bare Python 3.12 with nothing installed and refuses the same pushes, with the same words, as the library and the template's tools/guard_push.py, which runs the same code. sdlc-protocol's ecosystem.json says what this repository takes, and the copy holds exactly that:

- sdlc_protocol/guard.py: the push guard. It imports only the standard library, so no other module of the package is needed.
- sdlc_protocol/__init__.py: the package's docstring and its version.
- sdlc_protocol/vendoring.py: the check of the copy, which every copy carries.

VENDORED is the one record of the copy: its first line names the release and the commit of sdlc-protocol it was made from, `sdlc-protocol <version> <commit>`, and each line after it the sha256 of one copied file and its path inside sdlc_protocol/. scripts/check.sh, the check CI runs on every pull request, holds the copy to it first of all:

```
python3 plugins/sdlc/vendor/sdlc_protocol/vendoring.py verify plugins/sdlc/vendor
```

which fails on a file whose bytes are not the ones recorded, a recorded file that is missing, or a file beside them that is not recorded. tests/test_plugin.py holds the record to the files the plugin needs and, when a clone of sdlc-protocol sits beside this repository, every file to the library's at the recorded commit.

The library's guard.py docstring speaks of its cli.py and a "guard" subcommand; in this plugin, scripts/guard.py plays that part, reading the hook's JSON from stdin and calling guard.run().

## How the copy is refreshed

Never edit the copy by hand: change the code in sdlc-protocol, by pull request there. When that change reaches sdlc-protocol's main, its sync workflow vendors the new package into this repository and opens the pull request `sdlc-protocol/sync` here, or updates the one already open, and sets it to merge by itself once this repository's check is green. The copy here then matches the library; a session with the plugin installed runs the new guard from the plugin's next release, the version bump in plugins/sdlc/.claude-plugin/plugin.json that the Checks section of the README at the repository root describes.

To vendor by hand, from a clone of sdlc-protocol:

```
python3 <sdlc-protocol>/scripts/vendor.py <this repository>
```

then run `bash scripts/check.sh` here and land the change by pull request.
