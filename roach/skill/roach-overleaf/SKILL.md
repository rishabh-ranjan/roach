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
bash .claude/skills/roach-overleaf/scripts/claude-watch.sh
```

It polls until there is something to say, never touching the working tree, then
prints one `NEW <file>:<line> by <author>: <comment>` line per comment it has
not reported before and exits. The author is who to address in a reply. Its exit
is what wakes you, and its last lines tell you what to do next. It remembers what
it reported in `.git/claude-watch.seen`, so a comment you left in place does not
fire again.

It aims to reach you within a couple of seconds of the keystroke that closes the
comment:

- Each poll is a `git ls-remote` for one ref, which asks only whether anything
  changed. A real `git fetch` happens on a change, so probing is the lightest
  request there is. Measured on Overleaf: a probe every 2s ran clean for three
  minutes straight, 60 probes in a minute ran clean, and 400 an hour sustained
  ran clean. It was two `git fetch` loops at 300 an hour that tripped the limit.
  Probes are cheap; fetches are not.
- So there is one rate, a probe every 2s, with no slow tier and no cold wait.
  It can afford that because it runs only while nobody is acting on a comment:
  it exits on the first report, and is started again after that work is pushed.
  Probing through the minutes you spend editing would be pure waste, since a
  comment arriving then could not be picked up any sooner anyway.
- A comment fires the moment it is well-formed, with no settling delay. It
  never fires while its `{` is unclosed, which is what keeps a half-typed
  comment from reaching you at all.
- Because it does not wait for the author to finish, **check the comment again
  before you push**. Merge upstream as usual, then compare the comment in the
  file against the text the watcher reported. If it grew, redo the work for the
  new text before pushing. If it is gone, drop your edit. Acting on a stale
  version costs one retry; waiting for certainty would cost every comment
  several minutes.
- A token bucket caps requests at 1500 an hour, and past that the probe eases
  to 8s until the hour drains. Exceeding Overleaf's git rate limit breaks
  `pull` and `push` for several minutes, for you *and* for the authors' editor
  sync, so the watcher also backs off to 15 minutes when it sees
  `Rate-limit exceeded` or `no git access`. Never poll beside it, and never add
  your own `git fetch` or `git pull` loop.
- `CLAUDE_WATCH_PROBE`, `EASE`, `SETTLE` and `BUDGET` change the numbers. A
  positional argument is not a poll interval.
- A comment is tracked by its file and text, not its line, so a paragraph added
  above one does not make it look new, while an edit to the comment itself is
  correctly a new one.
- `flock` keeps one poller per repo, but a watcher that is wedged or running a
  script since replaced is worse than none, since it holds the lock and hears
  nothing. So it exits on its own once the script changes on disk, and a new
  instance takes the lock from a holder that has stopped polling or is running
  an older copy. Do not run a second watcher yourself.
- Starting it is therefore always safe, and its answer is worth reading. Only
  `another claude-watch (pid N) is polling this repo on this same script` means
  one is genuinely live; anything else is it taking over or saying why it could
  not.

When it exits it has stopped watching, deliberately. Work first: `git merge
--ff-only @{u}`, not `git pull`, since the watcher fetched seconds ago and the
commit is already local. Read each comment in full in the file (one may span
lines and may sit mid-sentence), address it under the rules above, build,
re-check the comment text as above, commit, push. Then start the watcher again,
and treat that as part of finishing: a turn that ends with nothing watching is
an unfinished turn. The human's request covers restarts until they say stop.

Address each one, then delete that comment and only that comment. Every other
author comment stays, including ones you believe are resolved, unless the human
says otherwise.
