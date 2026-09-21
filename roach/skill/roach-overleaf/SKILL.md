---
name: roach-overleaf
description: Habits for editing a paper in a local clone of an Overleaf project (origin is git.overleaf.com) — pull before editing, build, commit and push after each change, and a watcher that picks up `@claude` comments as collaborators leave them. Use before and after any edit to the paper sources of such a clone, and whenever syncing with Overleaf comes up.
---

# roach overleaf

The repo is a clone of the Overleaf project. Collaborators type in the web
editor; their edits arrive as commits on `main`, the only branch Overleaf has.

```bash
git pull                                      # before touching any paper source
pixi run compile                              # after each logical change; it must pass
git commit -am "<what changed>" && git push
```

Do this unasked, after every major set of changes, not at the end of the session.
The build passes with undefined references, so after any label or notation
change, yours or a collaborator's, also check the log:

```bash
grep -n 'Reference.*undefined' build/main.log
```

- A refused push means someone typed since your pull: `git pull`, build again
  if `.tex` came in, push. Never force, never rebase. While someone is typing
  this happens on most pushes; repeat pull and push a few times before treating
  it as a problem.
- A conflict keeps both people's intent. A collaborator's prose is never
  dropped; where the edits disagree on content, theirs stays in the text,
  yours goes in a `\todo{}`, and the human is told.

## Editing collaborators' text

The prose was written with care by other people. Make the smallest edit that
implements the request.

- Keep their sentences, terminology, headings and notation verbatim unless the
  request is to change them. Do not rephrase, restructure or tidy around the
  change.
- Before pushing, word-diff each touched section against its version before
  your edits. Every hunk should trace back to a request.

  ```bash
  git diff --word-diff <commit before your edits> -- Sections/Method.tex
  ```

- If a change forces edits elsewhere (renamed notation, a removed label, the
  appendix), keep those minimal too and list them in the reply.

## `@claude` comments

Requests arrive inside the authors' comment macros, e.g.
`\rishabh{@claude remove enumerate}`.

Start the watcher as soon as this skill loads, unasked, as a Bash command with
`run_in_background`, from the repo root:

```bash
bash .claude/skills/roach-overleaf/scripts/claude-watch.sh      # [poll-seconds], default 30
```

It fetches, never touching the working tree, and exits printing one `NEW
<file>:<line>: <comment>` line per `@claude` comment it has not reported before,
including the ones already open when it starts. Its exit is what wakes you. It
remembers what it reported in `.git/claude-watch.seen`, so a comment you left in
place does not fire again, and it holds `.git/claude-watch.lock`, so a second
copy exits at once.

On a `NEW` line, act at once, without waiting for the human: start the watcher
again first, then `git pull`, read the comment in full in the file (the line is
truncated and a comment may span lines), address it under the rules above,
build, commit, push. Then report what changed. If a comment is unclear, ask in
the reply and leave the comment in place.

The restart does not rest on your memory. A Stop hook refuses to let a turn end
while no watcher holds the lock, and tells you to start one. If
`.claude/settings.json` does not have it yet, add it, and tell the human that a
settings file created mid-session needs `/hooks` opened once or a restart
before it loads:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/skills/roach-overleaf/scripts/claude-watch-guard.sh"
          }
        ]
      }
    ]
  }
}
```

Address each one, then delete that comment and only that comment. Every other
author comment stays, including ones you believe are resolved, unless the human
says otherwise.
