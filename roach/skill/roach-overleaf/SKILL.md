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

Never push on a failed build, not even when the breakage came in with a
collaborator's commit; a broken `main` blocks their compile too, so fix it
first, silently. latexmk caches a failure and then
reports `gave an error in previous invocation`, so confirm any fix with a clean
`rm -rf build` rebuild. Two frequent breakages, both from the web editor: a
stray `}` left behind when a macro is deleted around a phrase, and two `\cite`
keys differing only in case, which aborts bibtex for the whole document.

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

**Nobody reads your chat replies.** The paper is the only channel, and it is a
channel you use almost never.

A `\claude{}` note answers one thing only: an `@claude` ask you could not carry
out as written. Nothing else earns a note. Not a fix, not a caveat you can live
with, not anything you already did.

It opens with `@` and the name of whoever left that ask, since it is a reply to
them, then **a few words**. Not a sentence, not an explanation, not an apology:

```latex
\claude{@liana 0.990 not lossless}
\claude{@rishabh no cite for data agents}
```

The watcher names the author of each comment it reports. For an `@claude` inside
someone's own macro (`\rishabh{@claude ...}`), that macro names them instead.

Everything else is silence. A typo you corrected, a build you unbroke, a
comment you carried out, a merge you resolved: the diff already says it. Adding
a note about work that went fine is noise in someone's paper.

Write the note as plain prose. LaTeX expands what is inside it, so a `\cite` or
a stray brace quoted in a note breaks the build you were reporting on.

If the project has no such macro, add one beside the authors' own comment macros
(`\liana{}`, `\rishabh{}`), honoring whatever switch hides them at submission:

```latex
\providecommand{\claude}[1]{{\color{teal}{/* claude: #1 */}}}
```

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
  appendix), keep those minimal too.
- Numbers in the text are checked against the run data, never against other
  prose. When a request is "is this right?", recompute from the CSVs the figure
  scripts read (`gen/`). If the prose is wrong, correct the number; if what is
  wrong is the claim around it, reply to the asker in a few words.

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
tree, and prints one `NEW <file>:<line> by <author>: <comment>` line per comment
it has not reported before, then exits. The author is who to address in a reply. Its exit is what wakes you, and its last line tells
you to start it again. It remembers what it reported in `.git/claude-watch.seen`,
so a comment you left in place does not fire again.

The watcher is deliberately slow and quiet:

- A comment is tracked by its file and text, not its line, so a paragraph added
  above one does not make it look new.
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
push, and say nothing anywhere unless a `\claude{}` note is truly earned.

Address each one, then delete that comment and only that comment. Every other
author comment stays, including ones you believe are resolved, unless the human
says otherwise.
