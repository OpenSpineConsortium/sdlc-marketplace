"""The marketplace holds together and its hooks answer as the template's do.

The manifests are checked for what Claude Code needs to install the plugin
(an entry name equal to the manifest's, a source that resolves to it), the
hooks for the scripts they name, and the scripts by running them the way
Claude Code does: JSON on stdin, an exit code and stderr back. The push
guard's expected messages are the template's tools/guard_push.py words,
and the edit check's cases are the template's tests/test_check_edit.py,
ported to a plugin that runs the repository's own checks.
"""

import hashlib
import io
import json
import os
import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "sdlc"
SCRIPTS = PLUGIN / "scripts"
VENDORED_GUARD = PLUGIN / "vendor" / "sdlc_protocol" / "guard.py"
SKILLS = ("claim", "remember", "checkpoint")

sys.path.insert(0, str(SCRIPTS))

import check_edit  # noqa: E402

MAIN_REFUSAL = ("a push to main is refused: the default branch takes only "
                "pull requests (.claude/rules/board.md)\n")
BOARD_REFUSAL = ("a push to board is refused: only the board workflow writes that "
                 "branch (.claude/rules/board.md)\n")
FORCE_REFUSAL = ("--force overwrites history another account may hold; the one forced push "
                 "the protocol allows is --force-with-lease on your own claude/ branch "
                 "after a rebase (.claude/rules/board.md)\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def frontmatter(path):
    """The key: value lines between a Markdown file's opening --- pair."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not match:
        return {}
    pairs = (line.split(":", 1) for line in match.group(1).splitlines() if ":" in line)
    return {key.strip(): value.strip() for key, value in pairs}


def hook_commands():
    """(event, matcher, command) for every hook in the plugin's hooks.json."""
    hooks = read_json(PLUGIN / "hooks" / "hooks.json")["hooks"]
    return [(event, group.get("matcher"), hook["command"])
            for event, groups in hooks.items()
            for group in groups
            for hook in group["hooks"]]


def clean_env(**extra):
    """The environment without git's own variables, which would point git at
    another repository than the one a test made."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra)
    return env


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=test", "-c", "user.email=test@example.com",
                    "-c", "commit.gpgsign=false", *args],
                   cwd=cwd, check=True, capture_output=True, env=clean_env())


def make_git_repo(folder, branch):
    """A repository with one commit on branch and no remote, so the guard
    finds the current branch and falls back to main as the default."""
    git(folder, "init", "-q")
    git(folder, "symbolic-ref", "HEAD", f"refs/heads/{branch}")
    git(folder, "commit", "-q", "--allow-empty", "-m", "init")
    return Path(folder)


def run_script(script, stdin, cwd=ROOT, **env):
    return subprocess.run([sys.executable, str(SCRIPTS / script)], input=stdin, cwd=cwd,
                          capture_output=True, text=True, timeout=60, env=clean_env(**env))


class MarketplaceManifestTest(unittest.TestCase):
    def setUp(self):
        self.marketplace = read_json(ROOT / ".claude-plugin" / "marketplace.json")
        self.plugin = read_json(PLUGIN / ".claude-plugin" / "plugin.json")

    def test_marketplace_has_its_required_fields(self):
        self.assertEqual(self.marketplace["name"], "sdlc-marketplace")
        self.assertTrue(self.marketplace["description"])
        self.assertEqual(self.marketplace["owner"], {"name": "OpenSpineConsortium"})
        self.assertEqual(len(self.marketplace["plugins"]), 1)

    def test_the_entry_names_and_finds_the_plugin(self):
        entry = self.marketplace["plugins"][0]
        self.assertEqual(entry["name"], "sdlc")
        self.assertEqual(entry["source"], "./plugins/sdlc")
        self.assertTrue(entry["description"])
        self.assertEqual((ROOT / entry["source"]).resolve(), PLUGIN.resolve())

    def test_plugin_manifest_has_its_fields(self):
        self.assertEqual(self.plugin["name"], "sdlc")
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(self.plugin["description"])
        self.assertEqual(self.plugin["author"], {"name": "OpenSpineConsortium"})
        self.assertEqual(self.plugin["repository"],
                         "https://github.com/OpenSpineConsortium/sdlc-marketplace")
        self.assertTrue(self.plugin["keywords"])

    def test_entry_and_manifest_carry_the_same_name(self):
        """An install by the manifest's name fails when the two differ."""
        self.assertEqual(self.marketplace["plugins"][0]["name"], self.plugin["name"])

    def test_the_version_is_set_in_one_place(self):
        """plugin.json's version wins over the entry's; two would drift."""
        self.assertNotIn("version", self.marketplace["plugins"][0])

    def test_the_license_is_the_mit_text_the_manifest_names(self):
        self.assertEqual(self.plugin["license"], "MIT")
        self.assertTrue((ROOT / "LICENSE").read_text(encoding="utf-8").startswith("MIT License\n"))


class ComponentsTest(unittest.TestCase):
    def test_each_skill_names_itself_and_says_when_to_use_it(self):
        for name in SKILLS:
            meta = frontmatter(PLUGIN / "skills" / name / "SKILL.md")
            self.assertEqual(meta.get("name"), name)
            self.assertTrue(meta.get("description"), name)

    def test_the_board_command_has_a_description(self):
        self.assertTrue(frontmatter(PLUGIN / "commands" / "board.md").get("description"))

    def test_no_template_placeholder_is_left_unfilled(self):
        """The template fills {{...}} when a repository is made from it; in
        the plugin nothing ever would."""
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                self.assertNotIn("{{", path.read_text(encoding="utf-8"), path)


class HooksTest(unittest.TestCase):
    def test_hooks_are_wired_as_the_template_wires_them(self):
        wiring = sorted((event, matcher) for event, matcher, _ in hook_commands())
        self.assertEqual(wiring, [("PostToolUse", "Edit|Write"), ("PreToolUse", "Bash"),
                                  ("SessionStart", None)])

    def test_every_hook_command_names_a_script_that_exists(self):
        for event, _, command in hook_commands():
            self.assertIn('"${CLAUDE_PLUGIN_ROOT}/scripts/', command, event)
            words = shlex.split(command.replace("${CLAUDE_PLUGIN_ROOT}", str(PLUGIN)))
            self.assertEqual(len(words), 2, command)
            interpreter, script = words
            self.assertIn(interpreter, ("python3", "bash"), command)
            self.assertTrue(Path(script).is_file(), command)
            self.assertEqual(Path(script).parent, SCRIPTS, command)


class VendoredGuardTest(unittest.TestCase):
    def test_the_vendored_guard_is_the_copy_its_readme_records(self):
        """vendor/README.md records the sha256 of the file as copied; a hand
        edit here would make the plugin and the library disagree."""
        readme = (PLUGIN / "vendor" / "README.md").read_text(encoding="utf-8")
        recorded = re.search(r"sha256 of guard\.py: ([0-9a-f]{64})", readme).group(1)
        actual = hashlib.sha256(VENDORED_GUARD.read_bytes()).hexdigest()
        self.assertEqual(actual, recorded)


class GuardHookTest(unittest.TestCase):
    """The guard run as Claude Code runs it, in a repository on claude/7
    with no remote, from another directory, so that only the payload's cwd
    can tell it where the session is."""

    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.repo = make_git_repo(cls.folder.name, "claude/7")

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_guard(self, command):
        payload = json.dumps({"tool_input": {"command": command}, "cwd": str(self.repo)})
        done = run_script("guard.py", payload)
        return done.returncode, done.stderr

    def test_a_push_to_main_is_refused_with_the_templates_message(self):
        self.assertEqual(self.run_guard("git push origin main"), (2, MAIN_REFUSAL))

    def test_the_claim_push_passes(self):
        self.assertEqual(self.run_guard("git push -u origin claude/7"), (0, ""))

    def test_a_bare_push_from_the_claim_branch_passes(self):
        self.assertEqual(self.run_guard("git push"), (0, ""))

    def test_a_push_to_the_board_branch_is_refused(self):
        self.assertEqual(self.run_guard("git push origin HEAD:board"), (2, BOARD_REFUSAL))

    def test_a_plain_force_is_refused_even_on_the_claim_branch(self):
        self.assertEqual(self.run_guard("git push --force origin claude/7"), (2, FORCE_REFUSAL))

    def test_a_lease_on_the_claim_branch_passes(self):
        self.assertEqual(self.run_guard("git push --force-with-lease origin claude/7"), (0, ""))

    def test_a_push_to_main_after_other_commands_is_refused(self):
        self.assertEqual(self.run_guard("git fetch origin && git push origin main"),
                         (2, MAIN_REFUSAL))

    def test_a_command_without_a_push_passes(self):
        self.assertEqual(self.run_guard("git status"), (0, ""))

    def test_a_payload_that_is_not_json_passes(self):
        done = run_script("guard.py", "not json")
        self.assertEqual((done.returncode, done.stderr), (0, ""))


MARKERS = "<!-- cswap:checkpoint:begin -->\n<!-- cswap:checkpoint:end -->\n"

# A repository's tools/check_docs.py as the hook sees it: run_checks(root)
# returning the problems and a file count. This one checks the memory
# index alone, with the template's wording, which is all the cases need;
# the checks themselves belong to the repository and are tested there.
STAND_IN_CHECKS = '''\
from pathlib import Path


def run_checks(root):
    folder = Path(root) / "docs" / "memory"
    index = (folder / "MEMORY.md").read_text(encoding="utf-8")
    facts = sorted(p.name for p in folder.glob("*.md") if p.name != "MEMORY.md")
    problems = [f"docs/memory/MEMORY.md: does not list {name}"
                for name in facts if f"({name})" not in index]
    return problems, len(facts)
'''

FAILING_CHECKS = "def run_checks(root):\n    raise RuntimeError('broken checks')\n"


def make_repo(folder, broken, checks=STAND_IN_CHECKS):
    """A minimal repository: CLAUDE.md with its marker pair, one memory
    fact, an index that lists it or, when broken, forgets it, and the
    repository's document checks unless checks is None."""
    root = Path(folder)
    (root / "CLAUDE.md").write_text("# t\n\n" + MARKERS, encoding="utf-8")
    memory = root / "docs" / "memory"
    memory.mkdir(parents=True)
    (memory / "a-fact.md").write_text("One fact.\n", encoding="utf-8")
    index = "# Memory index\n" + ("" if broken else "- [a fact](a-fact.md): one line\n")
    (memory / "MEMORY.md").write_text(index, encoding="utf-8")
    if checks is not None:
        (root / "tools").mkdir()
        (root / "tools" / "check_docs.py").write_text(checks, encoding="utf-8")
    return root


def run_hook(root, file_path):
    payload = json.dumps({"tool_input": {"file_path": str(file_path)}, "cwd": str(root)})
    err = io.StringIO()
    with mock.patch.object(sys, "stdin", io.StringIO(payload)), \
         mock.patch.object(sys, "stderr", err), \
         mock.patch.object(sys, "path", list(sys.path)), \
         mock.patch.dict("os.environ", {"CLAUDE_PROJECT_DIR": str(root)}):
        code = check_edit.main()
    return code, err.getvalue()


class CheckEditTest(unittest.TestCase):
    """The template's cases for its edit hook, which speaks only when an
    edit touched the documents and the checks then fail."""

    def test_document_edit_with_broken_index_is_reported(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            code, message = run_hook(root, root / "docs" / "memory" / "a-fact.md")
        self.assertEqual(code, 2)
        self.assertTrue(message.startswith(
            "The document checks fail after this edit (tools/check_docs.py):\n"))
        self.assertIn("does not list", message)

    def test_document_edit_with_healthy_documents_is_silent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=False)
            code, message = run_hook(root, root / "CLAUDE.md")
        self.assertEqual(code, 0)
        self.assertEqual(message, "")

    def test_edit_outside_the_documents_runs_no_checks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            with mock.patch.object(check_edit, "load_checks") as checks:
                code, _ = run_hook(root, root / "src" / "app.py")
        self.assertEqual(code, 0)
        checks.assert_not_called()

    def test_path_outside_the_root_is_not_a_document(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            self.assertFalse(check_edit.is_document(root, "/elsewhere/docs/x.md"))

    def test_broken_payload_passes(self):
        with mock.patch.object(sys, "stdin", io.StringIO("not json")):
            self.assertEqual(check_edit.main(), 0)

    def test_a_repository_without_the_checks_passes_in_silence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True, checks=None)
            self.assertEqual(run_hook(root, root / "CLAUDE.md"), (0, ""))

    def test_checks_that_fail_to_run_pass_in_silence(self):
        for checks in (FAILING_CHECKS, "this is not python\n"):
            with tempfile.TemporaryDirectory() as folder:
                root = make_repo(folder, broken=True, checks=checks)
                self.assertEqual(run_hook(root, root / "CLAUDE.md"), (0, ""), checks)

    def test_the_script_answers_as_a_hook(self):
        """The same broken index, through the script as Claude Code runs it."""
        with tempfile.TemporaryDirectory() as folder:
            root = make_repo(folder, broken=True)
            payload = json.dumps({"tool_input": {"file_path": str(root / "CLAUDE.md")},
                                  "cwd": str(root)})
            done = run_script("check_edit.py", payload, CLAUDE_PROJECT_DIR=str(root))
        self.assertEqual(done.returncode, 2)
        self.assertEqual(done.stderr,
                         "The document checks fail after this edit (tools/check_docs.py):\n"
                         "docs/memory/MEMORY.md: does not list a-fact.md\n")


class SessionStartTest(unittest.TestCase):
    def run_hook(self, folder):
        return subprocess.run(["bash", str(SCRIPTS / "session-start.sh")], cwd=folder,
                              capture_output=True, text=True, timeout=60,
                              env=clean_env(CLAUDE_PROJECT_DIR=str(folder)))

    def test_without_a_remote_it_says_so_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as folder:
            make_git_repo(folder, "claude/7")
            done = self.run_hook(folder)
        self.assertEqual(done.returncode, 0)
        self.assertIn("Branch claude/7; origin/main is not known here", done.stdout)
        self.assertIn("The board has not been written yet", done.stdout)

    def test_outside_a_repository_it_is_silent(self):
        with tempfile.TemporaryDirectory() as folder:
            done = self.run_hook(folder)
        self.assertEqual((done.returncode, done.stdout), (0, ""))


class WritingTest(unittest.TestCase):
    def test_every_file_is_ascii_with_lf_and_ends_with_a_newline(self):
        """The writing rule of the template, held here for every file."""
        for path in sorted(ROOT.rglob("*")):
            parts = set(path.relative_to(ROOT).parts)
            if not path.is_file() or parts & {".git", "__pycache__"}:
                continue
            data = path.read_bytes()
            self.assertTrue(data.isascii(), path)
            self.assertNotIn(b"\r", data, path)
            self.assertTrue(data.endswith(b"\n"), path)


if __name__ == "__main__":
    unittest.main()
