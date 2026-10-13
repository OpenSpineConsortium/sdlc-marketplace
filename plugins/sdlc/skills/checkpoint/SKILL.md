---
name: checkpoint
description: Use at the end of a session, or before handing work to another account or session, to record where things stand in .claude/session.md and in the marker section of CLAUDE.md.
---

# Write a checkpoint

A checkpoint is what the next session reads first. It is two things: `.claude/session.md`, the whole state of the work, and the block between `<!-- cswap:checkpoint:begin -->` and `<!-- cswap:checkpoint:end -->` at the end of CLAUDE.md, the durable part. The markers are cswap's, so `cswap checkpoint write` and this skill update the same block.

1. Collect from the conversation: what was completed, where things stand now (the branch, the pull request, what is pushed and what is not), what remains, and every line tagged `Decision:` or `Constraint:`, word for word.
2. Write `.claude/session.md` with these sections, in this order: `# Session checkpoint`, `## Completed work`, `## Current state`, `## Remaining tasks`, `## Decisions`, `## Constraints`. Plain prose and short lists; under 16 KB; ASCII and LF; no secrets, no tokens, no tool output, no logs. Say plainly what is not known rather than guessing.
3. Write the marker section to a scratch file outside the repository, `section.md`: the whole block, from the begin marker to the end marker, shaped as CLAUDE.md has it now: the heading `## Session checkpoint (kept by cswap)`, a blank line, the intro sentence unchanged, a blank line, then `### Durable decisions` and `### Constraints`, each followed by one `- ` line per item, or `- (none recorded)`. Decisions and constraints from earlier checkpoints stay unless a later one reverses them.
4. Refresh CLAUDE.md in place. Where the repository has tools/marked_section.py, run `python3 tools/marked_section.py CLAUDE.md < section.md`: the helper replaces what is between the markers and touches nothing else, and it refuses a file with one marker and not the other, which means someone edited the block by hand, so fix the markers first rather than forcing anything. Where it has not, as in a repository adopted with the protocol only, replace what is between the two markers with section.md by hand and leave every other line of CLAUDE.md as it is; a CLAUDE.md without the markers gets the whole block at its end, after one blank line.
5. Run the repository's checks: `bash scripts/check.sh` where it has that script, which fails when the marker pair is missing or doubled. Without one, read CLAUDE.md back and make sure each marker is there exactly once.
6. Commit both files on the issue's branch, in the pull request of the work: `git add .claude/session.md CLAUDE.md`, `git commit -m "Checkpoint"`, push. A checkpoint reaches the default branch by pull request like everything else. Where the repository's CLAUDE.md says checkpoints go elsewhere, such as a comment on the pull request, do what it says instead.

What belongs here and not in docs/memory/: the state of one piece of work. A fact that holds for the project as a whole is a memory (the remember skill, /symphony:remember).
