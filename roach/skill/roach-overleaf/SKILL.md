---
name: roach-overleaf
description: Writing a paper with collaborators on Overleaf from a local git clone, through Overleaf's git bridge — setting up the overleaf remote (Overleaf as the one upstream, GitHub as its mirror), the pull-commit-push routine, merge conflicts with web-editor edits, and source conventions that keep merges clean. Use whenever Overleaf, git.overleaf.com, syncing a paper, a collaborator's edits to the .tex, or pushing paper changes comes up, and before and after any edit to the paper sources of a project that has an `overleaf` remote.
---

# roach overleaf

Every Overleaf project is a git repository at
`https://git.overleaf.com/<project-id>`. Collaborators write in the web editor;
you write in a local clone; git carries both. This needs Overleaf premium on
the project owner's account (most universities provide it).

**Overleaf is the one remote anyone writes to.** Local `main` tracks
`overleaf/main`, so a plain `git pull` and `git push` talk to Overleaf.
GitHub is a mirror: every `git push` from a set-up clone also lands there, as
a second push URL of the `overleaf` remote, and nothing else writes to it. A
mirror can lag; it cannot diverge.

So nobody pushes to GitHub directly, and nobody uses Overleaf's GitHub sync
button: it pushes `overleaf-<date>` snapshot branches to GitHub and flattens
symlinks into text files, which breaks every committed skill link if merged.

## 1. The routine

```bash
git pull                                      # before touching any paper source
git commit -am "<what changed>" && git push   # after each logical change
```

That is all of it. Overleaf compiles; you do not. Build locally only when the
human asks, or when you need to see the PDF yourself (a figure's placement, a
page count).

- **`git config overleaf.sync`** says who runs it. `auto`: you do, unasked.
  `manual` or unset: the human owns every pull and push, and you never run
  either on your own; you edit and commit locally. When they say sync, pull or
  push, do it and say what came in and what went out. Do not nudge them to
  switch modes.
- **A refused push** means someone typed since your pull: `git pull && git
  push`. Never force, never rebase (`pull.rebase false` keeps pull a merge;
  commits on the mirror or in other clones must not be rewritten).
- **Small and often.** Overleaf commits web edits continuously; a clone that
  drifts for a day is the only source of real conflicts.
- **Read what a pull brought in** when it touched the file you are about to
  edit (`git log -p ORIG_HEAD..HEAD -- <file>`): it is the context for what
  you write next.
- **Be careful instead of compiling.** A push that does not compile breaks
  the editor for everyone, and Overleaf shows the error at once. Balance
  every brace and environment you touch, define every macro and label you
  use, and commit any file you `\input` or `\includegraphics`. If a
  collaborator reports a broken build after your push, fix it first.
- `git push` reports two destinations. If GitHub refuses, someone wrote to it
  directly: `git fetch origin && git merge origin/main && git push`, and tell
  the human the rule was broken.

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

## 4. Set up, once per clone

The remote and its credentials live in `.git/config`, which git never shares,
so every clone is set up once. When `git remote get-url overleaf` or `git
fetch overleaf` fails, run this top to bottom, stopping only where the human
acts. Every step is safe to repeat.

**1. One branch.** `git switch main && git pull` (this one pull is from
GitHub, the fresh clone's `origin`). A local branch with commits `main` lacks
is merged into `main` and deleted; uncommitted work is committed. There is no
personal or staging branch between the clone and Overleaf.

**2. The project id**, the hex string in `overleaf.com/project/<id>`. The
project's `CLAUDE.md` records it; otherwise the human reads it off their
browser.

**3. The token.** The human creates one: Overleaf, Account Settings, Git
Integration, "Create token". It is theirs, one per account, good for all
their projects; never shared, and the account password is never asked for.
It goes in a file outside every repo, mode 600, holding the bare token: where
the human already keeps secrets, else `~/.config/overleaf/token`. Best, they
write it from their own terminal so it never passes through the conversation:

```bash
mkdir -p ~/.config/overleaf && chmod 700 ~/.config/overleaf
printf '%s' '<token>' > ~/.config/overleaf/token && chmod 600 ~/.config/overleaf/token
```

If they paste it to you instead, write that file yourself and never repeat
the token, in a reply, a commit, a remote URL or a file in the repo.

**4. The remote.**

```bash
git remote add overleaf https://git.overleaf.com/<project-id>
git config credential.https://git.overleaf.com.username git
git config credential.https://git.overleaf.com.helper \
  '!f() { test "$1" = get && echo "password=$(cat <token-file>)"; }; f'
git fetch overleaf

git remote set-url --add --push overleaf https://git.overleaf.com/<project-id>
git remote set-url --add --push overleaf "$(git remote get-url origin)"
git branch --set-upstream-to=overleaf/main main
git config remote.pushDefault overleaf
git config pull.rebase false
```

A 403 is a wrong or expired token, or an account without access; a 404 is a
wrong id. The last five lines make Overleaf the upstream and GitHub its
mirror; `origin` stays as a read-only name for GitHub. With no GitHub repo,
skip the two `set-url` lines. An old project whose Overleaf branch is
`master` (`git ls-remote --heads overleaf`): leave out the GitHub push URL and
`pushDefault`, push with `git push overleaf HEAD:master`, mirror with `git
push origin main`.

**5. Shared history?** `git merge-base main overleaf/main`.

- It prints a commit: the project is already joined. `git pull`. The usual
  case for everyone after the first person.
- It prints nothing: you are the first. Do "First join" below, then record in
  the project's `CLAUDE.md` only what is the project's own: that it syncs by
  this skill, the project id, and a bootstrap line for the next person, since
  the skill cannot load in a clone that has not installed yet: "if the
  `roach-overleaf` skill is missing, `git switch main && git pull && pixi
  install`, then invoke it". The routine is not copied there.

**6. Old paths.** `git fetch origin`. If `git log main..origin/main` shows
commits, someone wrote to GitHub: `git merge origin/main` once. For each
`origin/overleaf-*` branch: if `git diff <branch> main -- '*.tex' '*.bib'` is
empty or shows only lines where `main` is newer, `git merge -s ours <branch>`
and delete the branch; otherwise take its source changes by hand, never the
flattened links.

**7. Who syncs.** Ask the human one question: should you pull and push on
your own, or only when they say so? `git config overleaf.sync auto` or
`manual`. It binds this clone only.

**8. Finish.** `git push` (with nothing to send it still proves write access
to both). Tell the human: the sync mode and how to change it; that `git pull`
brings in what collaborators typed and `git push` puts their commits in the
Overleaf editor within seconds and mirrors them to GitHub; that a refused
push wants `git pull` first; and that the sync button and direct GitHub
pushes are retired.

### First join

The bridge's history is Overleaf's own, a few squashed "Update on Overleaf"
commits, sharing no commit with the repo even when the project was on GitHub
sync. Find what Overleaf holds relative to local history:

```bash
T=$(git rev-parse overleaf/main^{tree})
git rev-list main | while read c; do
  [ "$(git rev-parse $c^{tree})" = "$T" ] && git log -1 --oneline $c; done
```

- A hit: Overleaf's tree is exactly an ancestor and has nothing local lacks.
  `git merge --allow-unrelated-histories -s ours overleaf/main`.
- No hit: there are web edits local never saw. Usually Overleaf is a recent
  local commit plus those edits: find it (`git diff --stat <commit>
  overleaf/main` over the last few commits, smallest diff wins). If local has
  not touched the same files since, `git merge --allow-unrelated-histories -s
  ours --no-commit overleaf/main`, `git checkout overleaf/main -- <the edited
  files>`, commit. Otherwise merge without `-s ours` and resolve by hand, with
  the human: every file conflicts as add/add, and for each the question is
  which side's lines are newer.

Then push. From here on every merge is ordinary.
