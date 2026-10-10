# Vendored code

sdlc_protocol/guard.py is the push guard of the sdlc_protocol library, copied unchanged from OpenSpineConsortium/sdlc-protocol, so that the plugin runs on a bare Python 3.12 with nothing installed and refuses the same pushes, with the same words, as the library and the template's tools/guard_push.py. It imports only the standard library, so no other module of the package is needed; sdlc_protocol/__init__.py is the plugin's own, a docstring and nothing else.

- Source: https://github.com/OpenSpineConsortium/sdlc-protocol, file sdlc_protocol/guard.py.
- Taken: 2026-10-10, from the branch wip/extract as its working tree stood, which is commit bb0cff3 with the change that adds run(), command_of() and where_to_ask() not yet committed there.
- sha256 of guard.py: d17f7217f00ad9c7182f5b980838e2696a6889e8fced7158e95d46740688a889

The library's docstring speaks of its cli.py and a "guard" subcommand; in this plugin, its scripts/guard.py plays that part, reading the hook's JSON from stdin and calling guard.run().

To refresh: copy sdlc_protocol/guard.py from a tagged release of sdlc-protocol over this one, change nothing in it, record the release and the new sha256 above, and run `bash scripts/check.sh` at the repository root; tests/test_plugin.py fails when the file and the recorded sha256 disagree, so an edit made here by hand cannot pass unnoticed.
