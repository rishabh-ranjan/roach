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
  dropped; where the edits disagree on content, theirs stays in the text and
  yours goes in a `\claude{}` note.
- Conflicts on the paragraph you are editing are normal while a collaborator
  types in it. Resolve by taking their side wholesale and re-applying your one
  edit on top, rather than hand-merging:

  ```bash
  git checkout --theirs Sections/Results.tex   # their paragraph, verbatim
  # re-apply your single edit (it may already be moot), then:
  git add Sections/Results.tex && git commit -m "Merge Overleaf"
  ```

  Re-check afterwards that your edit is still in the file. A collaborator who
  edits the same sentence can silently absorb it.

## Talking to the authors

**Nobody reads your chat replies.** The paper is the only channel. Anything the
authors must know goes into the `.tex` as a `\claude{}` note, pushed like any other change. If
the project has no such macro, add one beside the authors' own comment macros
(`\liana{}`, `\rishabh{}`), honoring whatever switch hides them at submission:

```latex
\providecommand{\claude}[1]{{\color{teal}{/* claude: #1 */}}}
```

- One or two sentences, no formatting, placed where the issue is.
- Only for what cannot be done directly: a wrong number, an ambiguous request,
  a claim the data does not support, a change that needs their decision.
- Never for narrating work you completed. A comment you addressed leaves no
  note; the diff is the report.
- A `\claude{}` note is a question to a human, so leave the `@claude` comment
  you were answering in place only when you did nothing else; if you both
  answered and edited, delete the comment and let the note carry the caveat.

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
  appendix), keep those minimal too and note them in a `\claude{}` if a human
  has to act on them.
- Numbers in the text are checked against the run data, never against other
  prose. When a request is "is this right?", recompute from the CSVs the figure
  scripts read (`gen/`), and report the answer in a `\claude{}` note with the
  corrected value, without editing the claim unless asked.

## `@claude` comments

Requests arrive inside the authors' comment macros, e.g.
`\rishabh{@claude remove enumerate}`, or bare as `@claude{...}`. Any
capitalization counts (`@Claude`).

Only when the human explicitly asks to watch for comments, start the watcher as
a Bash command with `run_in_background`, from the repo root. Never start it
unasked, and not merely because this skill loaded:

```bash
bash .claude/skills/roach-overleaf/scripts/claude-watch.sh      # [poll-seconds], default 60
```

It polls until there is something to say: it fetches, never touching the working
tree, and prints one `NEW <file>:<line>\t<comment>` line per comment it has not
reported before, then exits. Its exit is what wakes you, and its last line tells
you to start it again. It remembers what it reported in `.git/claude-watch.seen`,
so a comment you left in place does not fire again.

The watcher is deliberately slow and quiet:

- A comment is reported only when its text has been unchanged for two polls in
  a row, and never while its `{` is still unclosed. Both mean a comment being
  typed in the web editor does not reach you half-written.
- `flock` keeps one poller per repo. Do not run a second watcher, and do not add
  your own `git fetch` or `git pull` polling loop beside it.
- Overleaf rate-limits its git endpoint per project. Exceeding it breaks
  `git pull` and `git push` for several minutes, for you *and* for the authors'
  sync. The watcher backs off to 15 minutes when it sees `Rate-limit exceeded`
  or `no git access`. Keep the poll at 60s or slower, and never poll in
  parallel with it.

When it exits, the first thing you do, before reading anything, is start it
again the same way (the human's request covers restarts until they say stop).
Only then: `git pull`, read each comment in full in the file (a comment may span
lines and may sit mid-sentence), address it under the rules above, build, commit,
push. Report nothing to chat that a human needs; use `\claude{}`.

Address each one, then delete that comment and only that comment. Every other
author comment stays, including ones you believe are resolved, unless the human
says otherwise.
