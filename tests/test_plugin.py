"""The marketplace holds together and its hooks answer as the template's do.

The manifests are checked for what Claude Code needs to install the plugin
(an entry name equal to the manifest's, a source that resolves to it), the
hooks for the scripts they name, and the scripts by running them the way
Claude Code does: JSON on stdin, an exit code and stderr back. The push
guard's expected messages are the template's tools/guard_push.py words,
and the edit check's cases are the template's tests/test_check_edit.py,
ported to a plugin that runs the repository's own checks. The vendored
copy of the guard is held to its record, vendor/VENDORED, and to the files
symphony-protocol's ecosystem.json names for this repository, never to a list
of its own here, and CI to the one job "check" that runs scripts/check.sh.
The plugin's version is held to what lets a new copy reach the sessions
that have it installed: the library names plugin.json as this repository's
version file, its sync raises it with each new copy, and the project
preset turns auto-update on.
"""

import hashlib
import importlib.util
import io
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "sdlc"
SCRIPTS = PLUGIN / "scripts"
VENDOR = PLUGIN / "vendor"
VENDORED = VENDOR / "VENDORED"
PACKAGE = VENDOR / "sdlc_protocol"
VENDORED_GUARD = PACKAGE / "guard.py"
MANIFEST = PLUGIN / ".claude-plugin" / "plugin.json"
REPOSITORY = "OpenSpineConsortium/symphony-marketplace"
# The library's ecosystem.json at the recorded commit, which predates the
# rename, knows this repository by its old name; either name is this one.
REPOSITORY_NAMES = {REPOSITORY.lower(), "openspineconsortium/sdlc-marketplace"}
SKILLS = ("claim", "remember", "checkpoint")

# What the plugin itself runs from the copy: the push guard, which the
# PreToolUse hook calls, and the copy's own check, which scripts/check.sh
# runs. Which files the copy holds beyond those is symphony-protocol's
# ecosystem.json to say, never a list here: the sync brings a new copy and
# its new record in one pull request, so a second list on this
# repository's main would fail that pull request whenever the library
# changed what this repository takes, and could not be changed first,
# since main's copy is still the old one.
NEEDED = {"guard.py", "vendoring.py"}

# The clone of the library SDLC_PROTOCOL names, which CI makes and names
# (.github/workflows/ci.yml), or else one beside this repository, as
# /home/user/symphony-protocol is beside /home/user/symphony-marketplace;
# a clone made before the rename is still called sdlc-protocol, and is
# taken under that name when no symphony-protocol is beside. A clone
# named on purpose is one the comparison with the library must have; a
# clone that only happens to sit beside this one may be absent or behind,
# and then the comparison is skipped.


def library_beside():
    """The clone beside this repository, by its new name, or by its old one
    when only a clone made before the rename is there."""
    new, old = ROOT.parent / "symphony-protocol", ROOT.parent / "sdlc-protocol"
    return old if old.exists() and not new.exists() else new


LIBRARY = Path(os.environ.get("SDLC_PROTOCOL") or library_beside())
LIBRARY_NAMED = bool(os.environ.get("SDLC_PROTOCOL"))
CI = ROOT / ".github" / "workflows" / "ci.yml"
CLONE = 'git clone --quiet https://github.com/OpenSpineConsortium/symphony-protocol "$RUNNER_TEMP/symphony-protocol"'
NAMED_IN_CI = "SDLC_PROTOCOL: ${{ runner.temp }}/symphony-protocol"
COMPARISON = "VendoredGuardTest.test_every_file_is_the_librarys_at_that_commit"

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
        self.assertEqual(self.marketplace["name"], "symphony-marketplace")
        self.assertTrue(self.marketplace["description"])
        self.assertEqual(self.marketplace["owner"], {"name": "OpenSpineConsortium"})
        self.assertEqual(len(self.marketplace["plugins"]), 1)

    def test_the_entry_names_and_finds_the_plugin(self):
        entry = self.marketplace["plugins"][0]
        self.assertEqual(entry["name"], "symphony")
        self.assertEqual(entry["source"], "./plugins/sdlc")
        self.assertTrue(entry["description"])
        self.assertEqual((ROOT / entry["source"]).resolve(), PLUGIN.resolve())

    def test_plugin_manifest_has_its_fields(self):
        self.assertEqual(self.plugin["name"], "symphony")
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertTrue(self.plugin["description"])
        self.assertEqual(self.plugin["author"], {"name": "OpenSpineConsortium"})
        self.assertEqual(self.plugin["repository"],
                         "https://github.com/OpenSpineConsortium/symphony-marketplace")
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
        the plugin nothing ever would. The vendored copy is left out: it is
        symphony-protocol's code, not the template's text, held to the library
        by verify, and a module the library gives this repository may use
        braces of its own, which no change here could ever take out."""
        for path in sorted(PLUGIN.rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and VENDOR not in path.parents:
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


def load_vendoring():
    """The vendored vendoring.py, loaded by its path as check.sh runs it,
    without the package around it."""
    spec = importlib.util.spec_from_file_location("vendored_vendoring", PACKAGE / "vendoring.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_verify(vendor_dir):
    """vendoring.py's verify, as scripts/check.sh runs it."""
    return subprocess.run([sys.executable, "-B", str(Path(vendor_dir) / "sdlc_protocol" / "vendoring.py"),
                           "verify", str(vendor_dir)], capture_output=True, text=True, timeout=60)


def library_git(*args):
    return subprocess.run(["git", "-C", str(LIBRARY), *args], capture_output=True, env=clean_env())


def files_the_library_names(eco, consumer, commit):
    """The files ecosystem.json has the consumer take, as the library's
    vendor.py chooses them: every file of the package at that commit for
    "all", else the consumer's modules and the files every copy takes."""
    if consumer["modules"] == "all":
        listed = library_git("ls-tree", "-r", "--name-only", commit, "--", "sdlc_protocol/")
        return sorted(name.removeprefix("sdlc_protocol/") for name in listed.stdout.decode("ascii").splitlines())
    return sorted(set(consumer["modules"]) | set(eco["always_copied"]))


def why_the_library_cannot_compare(commit):
    """What stands in the way of comparing the copy with the library at
    commit, or "" when nothing does."""
    if not (LIBRARY / ".git").exists():
        return f"no clone of symphony-protocol at {LIBRARY}"
    if library_git("cat-file", "-e", f"{commit}^{{commit}}").returncode != 0:
        return (f"the clone at {LIBRARY} does not have {commit}, the commit VENDORED names: "
                "vendor a commit of symphony-protocol's, never write one into the record by hand")
    return ""


def compare_with(clone):
    """The comparison with the library run on its own, in a process of its
    own, with SDLC_PROTOCOL naming clone, as CI names its own."""
    return subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), COMPARISON],
                          cwd=ROOT, env=clean_env(SDLC_PROTOCOL=str(clone)), capture_output=True,
                          text=True, timeout=60)


def ci_steps():
    """The steps of ci.yml's one job, each as its lines with the indent
    stripped. The workflow is read as text, the standard library having no
    YAML parser; each step starts with a dash six spaces in."""
    steps = CI.read_text(encoding="utf-8").split("\n    steps:\n", 1)[1]
    return [[line.strip() for line in step.splitlines()] for step in re.split(r"\n(?=      - )", steps)]


class VendoredGuardTest(unittest.TestCase):
    """The copy of the push guard is symphony-protocol's, unchanged, and
    vendor/VENDORED is its one record: the release, the commit and the
    sha256 of every file, which scripts/check.sh holds the copy to. A hand
    edit here would make the plugin and the library disagree."""

    def setUp(self):
        self.vendoring = load_vendoring()
        self.version, self.commit, self.digests = self.vendoring.parse_record(
            VENDORED.read_text(encoding="ascii"))

    def test_the_copy_is_exactly_what_vendored_records(self):
        self.assertEqual(self.vendoring.problems(VENDOR), [])

    def test_vendored_records_what_the_plugin_runs(self):
        self.assertLessEqual(NEEDED, set(self.digests),
                             "symphony-protocol's ecosystem.json must give this repository the push guard")

    def test_the_vendored_guard_is_the_copy_its_record_records(self):
        actual = hashlib.sha256(VENDORED_GUARD.read_bytes()).hexdigest()
        self.assertEqual(actual, self.digests["guard.py"])

    def test_the_package_states_the_version_vendored_names(self):
        init = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
        self.assertIn(f'__version__ = "{self.version}"\n', init)

    def test_vendored_names_a_whole_commit_with_no_changes_on_top(self):
        """A copy made from a library with uncommitted changes, or from no
        checkout at all, is a copy no commit of symphony-protocol holds."""
        self.assertRegex(self.commit, r"^[0-9a-f]{40}$")

    def recorded_commit_in_the_library(self):
        """VENDORED sits in this tree, so a pull request that edits the copy
        can rewrite the file's line in it too and verify passes; the
        comparison with the library is what fails it. It reads the clone
        SDLC_PROTOCOL names, as CI's, and fails when that clone is missing
        or has no such commit, so a made-up commit does not pass as
        skipped; with SDLC_PROTOCOL unset it reads a clone beside this
        repository and is skipped when there is none or when it is
        behind."""
        missing = why_the_library_cannot_compare(self.commit)
        if missing and LIBRARY_NAMED:
            self.fail(f"{missing} (SDLC_PROTOCOL names it)")
        if missing:
            self.skipTest(missing)

    def test_every_file_is_the_librarys_at_that_commit(self):
        self.recorded_commit_in_the_library()
        for name in sorted(self.digests):
            with self.subTest(name=name):
                theirs = library_git("show", f"{self.commit}:sdlc_protocol/{name}")
                self.assertEqual(theirs.returncode, 0, theirs.stderr)
                self.assertEqual((PACKAGE / name).read_bytes(), theirs.stdout)

    def test_the_librarys_ecosystem_names_these_files_for_this_repository(self):
        """The exact set of files, as the library's ecosystem.json at the
        recorded commit has this repository take them."""
        self.recorded_commit_in_the_library()
        shown = library_git("show", f"{self.commit}:ecosystem.json")
        if shown.returncode != 0:
            self.skipTest(f"the library at {self.commit} has no ecosystem.json")
        eco = json.loads(shown.stdout)
        ours = [c for c in eco["consumers"] if c["repository"].lower() in REPOSITORY_NAMES]
        self.assertEqual(len(ours), 1)
        self.assertEqual(ROOT / ours[0]["vendor_dir"], VENDOR)
        self.assertEqual(files_the_library_names(eco, ours[0], self.commit), sorted(self.digests))

    def test_verify_passes_on_the_copy_as_it_is(self):
        done = run_verify(VENDOR)
        self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
        self.assertEqual(done.stdout, f"vendored sdlc-protocol {self.version} at {self.commit[:7]}: "
                                      f"{len(self.digests)} files match VENDORED\n")

    def test_verify_fails_on_a_hand_edit_of_the_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            copy = Path(folder) / "vendor"
            shutil.copytree(VENDOR, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            with (copy / "sdlc_protocol" / "guard.py").open("a", encoding="ascii") as guard:
                guard.write("# a hand edit\n")
            done = run_verify(copy)
        self.assertEqual(done.returncode, 1)
        self.assertIn("guard.py was edited by hand", done.stdout)

    def test_the_checks_verify_the_copy_before_the_tests(self):
        lines = (ROOT / "scripts" / "check.sh").read_text(encoding="utf-8").splitlines()
        verify = lines.index("python3 plugins/sdlc/vendor/sdlc_protocol/vendoring.py verify plugins/sdlc/vendor")
        tests = next(number for number, line in enumerate(lines) if "-m unittest" in line)
        self.assertLess(verify, tests)


def project_preset():
    """The JSON block of the README's section "The project preset"."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("\n## The project preset\n", 1)[1].split("\n## ", 1)[0]
    return json.loads(re.search(r"```json\n(.*?)```", section, re.DOTALL).group(1))


def next_patch(version):
    major, minor, patch = version.split(".")
    return f"{major}.{minor}.{int(patch) + 1}"


class ReleaseTest(unittest.TestCase):
    """Claude Code keeps an installed plugin on its cached copy until the
    version in plugin.json changes, so a new copy of the guard that came
    without a new version would land here and reach no session. The
    library's sync raises the version with each new copy; these tests hold
    this repository to the parts of that it owns."""

    def library_consumer(self):
        if not (LIBRARY / "ecosystem.json").is_file():
            self.skipTest(f"no clone of symphony-protocol at {LIBRARY}")
        eco = read_json(LIBRARY / "ecosystem.json")
        return next(c for c in eco["consumers"] if c["repository"].lower() in REPOSITORY_NAMES)

    def test_the_library_names_this_manifest_as_the_version_file(self):
        consumer = self.library_consumer()
        self.assertEqual(ROOT / consumer["vendor_dir"], VENDOR)
        self.assertEqual(ROOT / consumer["version_file"], MANIFEST)

    def test_a_new_copy_raises_the_version_and_nothing_else_in_the_manifest(self):
        """The library's vendor.py on a scratch copy of this repository whose
        guard is not the library's, as main's is before a sync."""
        # --consumer takes the name the library's ecosystem.json has, which
        # may still be the old one.
        consumer = self.library_consumer()
        with tempfile.TemporaryDirectory() as folder:
            scratch = Path(folder) / "marketplace"
            shutil.copytree(ROOT, scratch, ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"))
            guard = scratch / VENDORED_GUARD.relative_to(ROOT)
            guard.write_text(guard.read_text(encoding="ascii") + "# an older guard\n", encoding="ascii")
            done = subprocess.run([sys.executable, "-B", str(LIBRARY / "scripts" / "vendor.py"), str(scratch),
                                   "--consumer", consumer["repository"]], capture_output=True, text=True, timeout=60,
                                  env=clean_env())
            self.assertEqual(done.returncode, 0, done.stderr)
            before = MANIFEST.read_text(encoding="ascii")
            version = read_json(MANIFEST)["version"]
            after = (scratch / MANIFEST.relative_to(ROOT)).read_text(encoding="ascii")
        self.assertEqual(after, before.replace(f'"version": "{version}"', f'"version": "{next_patch(version)}"'))
        self.assertNotEqual(after, before)

    def test_the_project_preset_turns_auto_update_on(self):
        """Claude Code leaves auto-update off for a marketplace that is not
        Anthropic's; the preset turns it on, so a release reaches every
        session in the repository by itself."""
        preset = project_preset()
        name = read_json(ROOT / ".claude-plugin" / "marketplace.json")["name"]
        entry = preset["extraKnownMarketplaces"][name]
        self.assertEqual(entry["source"], {"source": "github", "repo": REPOSITORY})
        self.assertIs(entry["autoUpdate"], True)
        self.assertEqual(preset["enabledPlugins"], {f"symphony@{name}": True})


class WorkflowTest(unittest.TestCase):
    """CI runs the same checks as a person does, as the one job "check",
    the name a ruleset requires and the sync's auto-merge waits on."""

    def setUp(self):
        self.text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    def test_the_one_job_is_named_check(self):
        jobs = self.text.split("\njobs:\n", 1)[1]
        self.assertEqual(re.findall(r"^  ([\w-]+):$", jobs, re.MULTILINE), ["check"])

    def test_it_runs_the_checks_on_python_3_12(self):
        self.assertIn("python-version: \"3.12\"\n", self.text)
        self.assertIn("run: bash scripts/check.sh\n", self.text)

    def test_it_runs_on_pull_requests_and_pushes_to_main(self):
        self.assertIn("on:\n  pull_request:\n  push:\n    branches: [main]\n", self.text)

    def test_every_action_is_pinned_to_a_major_tag(self):
        actions = re.findall(r"uses: (\S+)", self.text)
        self.assertTrue(actions)
        for action in actions:
            self.assertRegex(action, r"^actions/[\w-]+@v\d+$")

    def test_it_clones_the_library_and_names_the_clone_to_the_checks(self):
        steps = ci_steps()
        clone = next(number for number, step in enumerate(steps) if f"run: {CLONE}" in step)
        checks = next(number for number, step in enumerate(steps) if "run: bash scripts/check.sh" in step)
        self.assertLess(clone, checks)
        self.assertIn(NAMED_IN_CI, steps[checks])


class TheComparisonOnCITest(unittest.TestCase):
    """CI names its clone of symphony-protocol to the checks, so the comparison
    with the library runs on every pull request; where the clone it names
    is missing, or has no commit of the one VENDORED names, the comparison
    fails rather than skips."""

    def test_a_named_clone_that_is_not_there_fails_the_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            done = compare_with(Path(folder) / "symphony-protocol")
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("no clone of symphony-protocol at", done.stderr)
        self.assertNotIn("skipped", done.stderr)

    def test_a_named_clone_without_the_recorded_commit_fails_the_comparison(self):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run(["git", "init", "--quiet", folder], check=True, capture_output=True, env=clean_env())
            done = compare_with(folder)
        self.assertEqual(done.returncode, 1, done.stderr)
        self.assertIn("the commit VENDORED names", done.stderr)
        self.assertNotIn("skipped", done.stderr)


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
