"""The plugin's claim skill's git commands, run as the skill writes them,
land on the claim branch and nowhere else, whatever git's settings say.

git decides where a push goes from its own settings, which the push guard
(plugins/sdlc/scripts/guard.py) never reads. Under push.default upstream, or
its old name tracking, a branch that tracks the default branch pushes there
whatever the command names; under matching a push that names no branch sends
every branch that has a namesake on origin, a stale default branch among
them; under nothing it sends nothing. A clone made for one branch, as a
cloud session's is, fetches no other, so the board it reads goes stale, the
claim push records no upstream and a released branch is never there to carry
on from. And a lease that names no tip holds against whatever the last fetch
read, so after the rebase's own fetch it would force over a new claim of the
issue. So each command below is held to the step of the skill that gives it,
word for word, and then run in scratch repositories with a bare origin under
every push.default git knows, in a whole clone and in one made for one
branch: the claim and every push after it land on claude/N, the default
branch never moves, and the lease is refused once someone else has pushed to
claude/N. The checkpoint skill's push is held and run the same way. Every
other page of the plugin that gives a push or makes a branch, and the
README, are held to the same rules by their text. The template holds its own
skills to the same test; this repository's CI cannot read the template, so
each holds its own.
"""

import os
import re
import shlex
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins" / "sdlc"
CLAIM = PLUGIN / "skills" / "claim" / "SKILL.md"
CHECKPOINT = PLUGIN / "skills" / "checkpoint" / "SKILL.md"
WILDCARD = "+refs/heads/*:refs/remotes/origin/*"
SETTINGS = ("upstream", "tracking", "simple", "current", "matching", "nothing")
CLONES = {"whole": [], "made for one branch": ["--single-branch", "--branch", "main"]}
# The commands each step gives, word for word, with N for the issue, D for
# the default branch, as the skill writes both, and <that tip> for the tip
# step 7 has you note.
CLAIM_STEPS = {
    1: [f"git config --add remote.origin.fetch '{WILDCARD}'", "git fetch origin",
        "git fetch origin board && git show origin/board:STATE.md"],
    2: ["git switch -c claude/N --no-track origin/D"],
    4: ["git add docs/agents/claims/N.md", 'git commit -m "Claim #N"', "git push -u origin claude/N"],
    7: ["git push origin claude/N", "git rev-parse claude/N", "git fetch origin", "git rebase origin/D",
        "git push --force-with-lease=claude/N:<that tip> origin claude/N"],
}
CHECKPOINT_STEP = 6
CHECKPOINT_COMMANDS = ["git add .claude/session.md CLAUDE.md", 'git commit -m "Checkpoint"', "git push origin claude/N"]
GIT_ENV = {"GIT_AUTHOR_NAME": "Test", "GIT_AUTHOR_EMAIL": "test@example.invalid", "GIT_COMMITTER_NAME": "Test",
           "GIT_COMMITTER_EMAIL": "test@example.invalid", "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull}


def step_of(path, number):
    """One numbered step of a skill, its whole line."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith(f"{number}. "):
            return line
    raise AssertionError(f"{path.relative_to(ROOT)} has no step {number}")


def spans(text):
    return re.findall(r"`([^`]+)`", text)


class Scratch:
    """A bare origin with main and the board, and clones of it, in a folder
    of their own; every push is made only after the clone's origin is shown
    to be that folder's bare repository."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.origin = self.folder / "origin.git"
        self.admin = self.folder / "admin"
        for target, bare in ((self.origin, ["--bare"]), (self.admin, [])):
            subprocess.run(["git", "init", "-q", *bare, "--initial-branch=main", str(target)], check=True,
                           env=self.env(), capture_output=True)
        self.git(self.admin, "remote", "add", "origin", str(self.origin))
        self.write(self.admin, "README.md", "Start\n")
        self.git(self.admin, "add", "README.md")
        self.git(self.admin, "commit", "-q", "-m", "Start")
        self.push(self.admin, "origin", "main")
        self.git(self.admin, "switch", "-q", "--orphan", "board")
        self.move_board("board one")

    @staticmethod
    def env():
        return {k: v for k, v in os.environ.items() if not k.startswith("GIT_")} | GIT_ENV

    def git(self, repo, *args, check=True):
        done = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, env=self.env())
        if check and done.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed in {repo.name}: {done.stderr}")
        return done

    def push(self, repo, *args):
        url = self.git(repo, "remote", "get-url", "--push", "origin").stdout.strip()
        if Path(url) != self.origin:
            raise AssertionError(f"{repo.name} would push to {url}, not to this test's own origin")
        return self.git(repo, "push", "-q", *args, check=False)

    def clone(self, name, kind):
        target = self.folder / name
        subprocess.run(["git", "clone", "-q", *CLONES[kind], str(self.origin), str(target)], check=True,
                       env=self.env(), capture_output=True)
        return target

    @staticmethod
    def write(repo, path, text):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text, encoding="utf-8")

    def tip(self, ref, repo=None):
        done = self.git(repo or self.origin, "rev-parse", "--verify", "--quiet", ref, check=False)
        return done.stdout.strip() if done.returncode == 0 else None

    def move_board(self, text):
        """A new board, as the board workflow writes it on its own branch."""
        if self.tip("refs/heads/board", self.admin):
            self.git(self.admin, "switch", "-q", "board")
        self.write(self.admin, "STATE.md", text + "\n")
        self.git(self.admin, "add", "STATE.md")
        self.git(self.admin, "commit", "-q", "-m", "Board")
        self.push(self.admin, "origin", "board")
        self.git(self.admin, "switch", "-q", "main")

    def move_main(self, name):
        self.write(self.admin, name, name + "\n")
        self.git(self.admin, "add", name)
        self.git(self.admin, "commit", "-q", "-m", f"Main moves: {name}")
        self.push(self.admin, "origin", "main")


class Worker:
    """One worker's clone, running the skills' commands as they are written,
    with N the issue 7 and D the default branch, main."""

    def __init__(self, scratch, name, kind, setting="simple"):
        self.scratch, self.name = scratch, name
        self.repo = scratch.clone(name, kind)
        scratch.git(self.repo, "config", "push.default", setting)
        self.noted = None

    def run(self, command):
        """One command of a skill, filled in; a push goes through the
        scratch's check of where it goes. The result's code and output."""
        filled = (command.replace("origin/D", "origin/main").replace("<that tip>", self.noted or "")
                  .replace("claude/N", "claude/7").replace("#N", "#7").replace("claims/N.md", "claims/7.md"))
        words = shlex.split(filled)
        if words[:2] == ["git", "push"]:
            done = self.scratch.push(self.repo, *words[2:])
        else:
            done = self.scratch.git(self.repo, *words[1:], check=False)
        if words[:2] == ["git", "rev-parse"]:
            self.noted = done.stdout.strip()
        return done

    def step_one(self):
        """Step 1's fetches, the refspec first where the clone fetches only
        some branches, as the step says; the board as read."""
        fetched = self.scratch.git(self.repo, "config", "--get-all", "remote.origin.fetch").stdout.split()
        commands = CLAIM_STEPS[1] if WILDCARD not in fetched else CLAIM_STEPS[1][1:]
        for command in commands[:-1]:
            self.run(command)
        self.scratch.git(self.repo, "fetch", "-q", "origin", "board", check=False)
        board = self.scratch.git(self.repo, "show", "origin/board:STATE.md", check=False)
        return board.stdout.strip() if board.returncode == 0 else None

    def claim(self):
        """Steps 2 to 4: the branch, the claim file and the claim push."""
        self.run(CLAIM_STEPS[2][0])
        self.scratch.write(self.repo, "docs/agents/claims/7.md", f"# Claim: #7\n\n- Worker: {self.name}\n")
        return [self.run(command) for command in CLAIM_STEPS[4]][-1]

    def work(self, path):
        self.scratch.write(self.repo, path, f"{self.name}'s work\n")
        self.scratch.git(self.repo, "add", path)
        self.scratch.git(self.repo, "commit", "-q", "-m", f"Work on {path}")

    def rebase_and_lease(self):
        """Step 7's rebase, from pushing what the branch holds to the lease."""
        return [self.run(command) for command in CLAIM_STEPS[7]]


class TheStepsGiveTheseCommands(unittest.TestCase):
    def test_each_command_is_the_one_its_step_of_the_claim_skill_gives(self):
        for number, commands in CLAIM_STEPS.items():
            shown = spans(step_of(CLAIM, number))
            for command in commands:
                self.assertIn(command, shown, f"step {number} of the claim skill")

    def test_step_one_fetches_every_branch_only_where_the_clone_does_not(self):
        self.assertIn(f"where `git config --get-all remote.origin.fetch` does not print `{WILDCARD}`",
                      step_of(CLAIM, 1))

    def test_the_checkpoint_skill_pushes_its_commit_by_name(self):
        shown = spans(step_of(CHECKPOINT, CHECKPOINT_STEP))
        for command in CHECKPOINT_COMMANDS:
            self.assertIn(command, shown)


class TheCommandsLandOnTheClaimBranchAlone(unittest.TestCase):
    def test_the_claim_and_every_push_after_it_land_on_claude_n_and_main_never_moves(self):
        for setting in SETTINGS:
            for kind in CLONES:
                with self.subTest(setting=setting, clone=kind), tempfile.TemporaryDirectory() as folder:
                    self.one_claim(Scratch(folder), setting, kind)

    def one_claim(self, scratch, setting, kind):
        worker = Worker(scratch, "ann", kind, setting)
        scratch.move_board("board two")
        self.assertEqual(worker.step_one(), "board two", "step 1 reads the board as it is now")
        scratch.move_main("other.txt")
        main = scratch.tip("refs/heads/main")
        claimed = worker.claim()
        self.assertEqual(claimed.returncode, 0, claimed.stderr)
        self.assert_landed(scratch, worker, main)
        upstream = scratch.git(worker.repo, "rev-parse", "--abbrev-ref", "claude/7@{u}", check=False)
        self.assertEqual(upstream.stdout.strip(), "origin/claude/7", "the claim push gives claude/7 its upstream")
        worker.work("work.txt")
        pushed = worker.run("git push origin claude/N")
        self.assertEqual(pushed.returncode, 0, pushed.stderr)
        self.assert_landed(scratch, worker, main)
        scratch.write(worker.repo, ".claude/session.md", "# Session checkpoint\n")
        scratch.write(worker.repo, "CLAUDE.md", "# x\n")
        done = [worker.run(command) for command in CHECKPOINT_COMMANDS][-1]
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assert_landed(scratch, worker, main)
        steps = worker.rebase_and_lease()
        self.assertEqual([done.returncode for done in steps], [0] * len(steps), [done.stderr for done in steps])
        self.assert_landed(scratch, worker, main)
        self.assertEqual(scratch.git(worker.repo, "merge-base", "--is-ancestor", main, "claude/7",
                                     check=False).returncode, 0, "claude/7 is rebased on the moved main")

    def assert_landed(self, scratch, worker, main):
        self.assertEqual(scratch.tip("refs/heads/claude/7"), scratch.tip("claude/7", worker.repo),
                         "origin's claude/7 is the worker's")
        self.assertEqual(scratch.tip("refs/heads/main"), main, "origin's main never moves")

    def test_the_lease_refuses_a_claim_made_since_and_the_next_worker_carries_the_released_work_on(self):
        for kind in CLONES:
            with self.subTest(clone=kind), tempfile.TemporaryDirectory() as folder:
                scratch = Scratch(folder)
                ann = Worker(scratch, "ann", kind)
                ann.step_one()
                self.assertEqual(ann.claim().returncode, 0)
                ann.work("ann.txt")
                ann.run("git push origin claude/N")
                held = scratch.tip("refs/heads/claude/7")
                released = f"released/7-{held[:7]}"
                scratch.git(scratch.origin, "branch", "-m", "claude/7", released)
                bob = Worker(scratch, "bob", kind)
                bob.step_one()
                self.assertIsNotNone(scratch.tip(f"origin/{released}", bob.repo), "step 1 fetches the released branch")
                self.assertEqual(bob.claim().returncode, 0)
                picked = scratch.git(bob.repo, "cherry-pick", f"origin/{released}~1..origin/{released}", check=False)
                self.assertEqual(picked.returncode, 0, picked.stderr)
                bob.run("git push origin claude/N")
                scratch.move_main("other.txt")
                steps = ann.rebase_and_lease()
                self.assertNotEqual(steps[-1].returncode, 0, "the lease is refused once bob has pushed")
                claim = scratch.git(scratch.origin, "show", "refs/heads/claude/7:docs/agents/claims/7.md")
                self.assertIn("- Worker: bob", claim.stdout)
                carried = scratch.git(scratch.origin, "show", "refs/heads/claude/7:ann.txt")
                self.assertEqual(carried.stdout, "ann's work\n")


PUSH = re.compile(r"\bgit push\b([^`\n]*)")
BRANCHING = re.compile(r"\bgit (?:switch -c|checkout -b)\b([^`\n]*)")
FILLED_IN = re.compile(r"<[^<>\n]*>")


def pages():
    """The plugin's skills and command, and the README, by their path from
    the root: what tells a session how to push or make a branch."""
    found = [ROOT / "README.md", *sorted((PLUGIN / "skills").rglob("*.md")),
             *sorted((PLUGIN / "commands").rglob("*.md"))]
    for path in found:
        yield path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")


def push_words(rest):
    """A push command's words after "push", up to where the command ends in
    the text: the end of a code span or a line, a shell operator, or
    punctuation that closes the sentence or the parenthesis around it. A
    word in angle brackets is one the reader fills in."""
    words = []
    for word in FILLED_IN.sub("FILLED", rest).split():
        if word in ("&&", "||", "|", ";", "\\"):
            break
        clean = word.rstrip(".,;:)").replace('"', "").replace("'", "")
        words.append(clean)
        if clean != word.replace('"', "").replace("'", ""):
            break
    return words


class EveryPageNamesWhatItPushes(unittest.TestCase):
    def pushes(self):
        for name, text in pages():
            for found in PUSH.finditer(text):
                yield name, found.group(0), push_words(found.group(1))

    def test_every_push_names_the_remote_and_the_branch(self):
        for name, command, words in self.pushes():
            positional = [word for word in words if not word.startswith("-")]
            self.assertGreaterEqual(len(positional), 2, f"{name}: {command}")

    def test_every_lease_names_the_tip_it_expects_and_pushes_the_branch_it_leases(self):
        for name, command, words in self.pushes():
            for word in words:
                if word.startswith("--force-with-lease"):
                    ref, _, tip = word.partition("=")[2].partition(":")
                    self.assertTrue(ref and tip, f"{name}: a lease that names no tip: {command}")
                    if ref.startswith("claude/"):
                        self.assertIn(ref, words[words.index(word) + 1:], f"{name}: {command}")

    def test_every_branch_made_from_the_default_branch_is_made_with_no_upstream(self):
        for name, text in pages():
            for found in BRANCHING.finditer(text):
                self.assertIn("--no-track", found.group(1), f"{name}: {found.group(0)}")


if __name__ == "__main__":
    unittest.main()
