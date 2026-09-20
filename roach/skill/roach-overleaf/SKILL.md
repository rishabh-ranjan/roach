---
name: roach-overleaf
description: Writing a paper with collaborators on Overleaf from a local git clone of the Overleaf project itself (Overleaf's git bridge, the only remote) — cloning, the pull-build-push routine, merge conflicts with web-editor edits, and source conventions that keep merges clean. Use whenever Overleaf, git.overleaf.com, syncing a paper, a collaborator's edits to the .tex, or pushing paper changes comes up, and before and after any edit to the paper sources of a clone whose `origin` is git.overleaf.com.
---

# roach overleaf

Every Overleaf project is a git repository at
`https://git.overleaf.com/<project-id>`. The local repo is a clone of it and
has no other remote: `origin` is Overleaf, `main` tracks it, and plain `git
pull` and `git push` are the whole interface. Collaborators write in the web
editor; their edits arrive as commits. This needs Overleaf premium on the
project owner's account (most universities provide it).

There is no GitHub copy and Overleaf's GitHub sync button is not used: a
second place to write is a second thing to keep in step.

## 1. The routine

```bash
git pull                                      # before touching any paper source
pixi run compile                              # after each logical change; it must pass
git commit -am "<what changed>" && git push
```

That is all of it. Every project names its build task `compile`, so no
project restates this.

- **`git config overleaf.sync`** says who runs it. `auto`: you do, unasked.
  `manual` or unset: the human owns every pull and push, and you never run
  either on your own; you edit and commit locally. When they say sync, pull or
  push, do it and say what came in and what went out. Do not nudge them to
  switch modes.
- **A refused push** means someone typed since your pull: `git pull && git
  push`, building in between if the pull brought in `.tex` changes. Never
  force (Overleaf refuses it), never rebase (`pull.rebase false`).
- **Small and often.** Overleaf commits web edits continuously; a clone that
  drifts for a day is the only source of real conflicts.
- **Read what a pull brought in** when it touched the file you are about to
  edit (`git log -p ORIG_HEAD..HEAD -- <file>`).
- **Build before you push.** Collaborators compile the pushed sources in the
  browser the moment they land. This binds you, not the human: what they push
  from their own shell is their call.
- Overleaf has one branch and accepts no others. Local branches and worktrees
  are short-lived and merge into `main` before anything is pushed.

## 2. Conflicts

A conflict is two people editing the same lines. Resolve it keeping both
people's intent; a collaborator's prose is never dropped to make a merge go
through. When the two edits disagree on content, not just wording, keep the
collaborator's version in the text, put yours in a `\todo{}` or a comment next
to it, and tell the human. Commit the merge and push.

## 3. Sources that merge well

- **One sentence per line.** Git merges by line; a paragraph on one line
  conflicts whenever two people touch it. Write new prose this way. Reflow
  existing prose only in a single commit of its own, pushed at once, at a time
  the human says nobody is editing.
- **One file per section**, `\input` from the main file.
- **Generated figures and tables are committed** at the path the `.tex`
  includes (see `roach-paper`), so Overleaf compiles them without running any
  code. Build products (`build/`, `*.aux`, the paper's own PDF, the
  environment) are gitignored.
- Overleaf refuses a push with a file over 50 MB or more than 2000 files, and
  names the offender. Fix the tree; do not retry.
- Overleaf comments, tracked changes and chat do not travel through git.
  Notes for collaborators go in the source (`\todo{}`, a `%` line) or the
  commit message, which Overleaf's history panel shows.

## 4. Set up, once per machine and clone

**The token, once per machine.** The human creates one: Overleaf, Account
Settings, Git Integration, "Create token". It is theirs, good for all their
projects; never shared, and the account password is never asked for. It goes
in a file outside every repo, mode 600, holding the bare token: where the
human already keeps secrets, else `~/.config/overleaf/token`. Best, they write
it from their own terminal so it never passes through the conversation:

```bash
mkdir -p ~/.config/overleaf && chmod 700 ~/.config/overleaf
printf '%s' '<token>' > ~/.config/overleaf/token && chmod 600 ~/.config/overleaf/token
```

If they paste it to you instead, write that file yourself and never repeat
the token, in a reply, a commit, a remote URL or a file in the repo.

**The clone.** The project id is the hex string in
`overleaf.com/project/<id>`.

```bash
git clone \
  -c credential.https://git.overleaf.com.username=git \
  -c 'credential.https://git.overleaf.com.helper=!f() { test "$1" = get && echo "password=$(cat <token-file>)"; }; f' \
  -c pull.rebase=false \
  https://git.overleaf.com/<project-id> <dir>
cd <dir> && pixi install
```

`-c` on `clone` writes the settings into the new clone's own config and uses
them for the clone itself, so nothing prompts, then or later, and rotating
the token is rewriting one file. A 403 is a wrong or expired token, or an
account without access; a 404 is a wrong id. `pixi install` makes the
committed skill links resolve.

**Then**, in the clone: `pixi run compile` once (LaTeX is not in the pixi
env: if `latexmk` is missing the human installs MacTeX, TinyTeX or TeX Live;
a missing `.sty` is `tlmgr install <pkg>`). Ask the human one question:
should you pull and push on your own, or only when they say so? `git config
overleaf.sync auto` or `manual`; it binds this clone only. Tell them what
`git pull` and `git push` now do, and that a refused push wants a pull first.

**A project that lived in another git repo** (GitHub, with or without
Overleaf's sync button) moves once, by one person: clone from Overleaf as
above, and bring over whatever the old repo has that Overleaf lacks (`diff
-r` the two trees; copy files, not history), commit, push. The old repo is
then retired: say so in its README and stop pushing to it. Its history stays
there for reference.
