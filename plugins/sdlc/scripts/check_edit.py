"""Run the document checks the moment an edit touches the documents.

Claude Code runs this as a PostToolUse hook on Edit and Write, wired in
the plugin's hooks/hooks.json; it is the template's tools/check_edit.py
moved into the plugin. CI runs the same checks (tools/check_docs.py) on
every pull request, but a session that hears about a broken import or a
forgotten index line only from CI has long moved on; exit code 2 feeds
the problems straight back while the edit is still in hand.

The checks stay with the repository: this runs the repository's own
tools/check_docs.py, the file its CI runs, so the hook and CI can never
disagree about what a broken document is, and a repository not made from
the template, which has no such file, has no checks to run. An edit
outside the document folders, a payload this script cannot read, or a
repository without the checks passes in silence: CI remains the fence
that counts.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path

# The places whose files are the project's instructions and memory, the
# same ones tools/check_docs.py holds to ASCII and LF.
DOCUMENT_ROOTS = {".claude", "docs", "tools", ".github"}
DOCUMENT_FILES = {"CLAUDE.md", "README.md"}

# Where a repository made from the template keeps its document checks.
CHECKS = Path("tools") / "check_docs.py"


def is_document(root, file_path):
    """Whether an edited path is one the document checks cover."""
    try:
        rel = Path(file_path).resolve().relative_to(Path(root).resolve())
    except (ValueError, OSError):
        return False
    return rel.parts[0] in DOCUMENT_ROOTS or rel.as_posix() in DOCUMENT_FILES


def load_checks(root):
    """The repository's own check_docs module, or None when it has none or
    the file does not load. Its folder goes first on the path, as it does
    for the template's hook, which lives beside it, so that whatever the
    checks import from their own folder resolves the same way."""
    path = Path(root) / CHECKS
    if not path.is_file():
        return None
    sys.path.insert(0, str(path.parent))
    try:
        spec = importlib.util.spec_from_file_location("check_docs", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    except Exception:
        return None
    return module


def main():
    try:
        payload = json.load(sys.stdin)
    except ValueError:
        return 0
    file_path = (payload.get("tool_input") or {}).get("file_path") or ""
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    if not file_path or not is_document(root, file_path):
        return 0
    check_docs = load_checks(Path(root).resolve())
    if check_docs is None:
        return 0
    try:
        problems, _ = check_docs.run_checks(Path(root).resolve())
    except Exception:
        return 0
    if not problems:
        return 0
    print("The document checks fail after this edit (tools/check_docs.py):", file=sys.stderr)
    for problem in problems:
        print(problem, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
