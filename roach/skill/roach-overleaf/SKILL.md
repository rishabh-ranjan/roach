---
name: roach-overleaf
description: Writing a paper with collaborators on Overleaf from a local git clone, through Overleaf's git bridge — setting up the overleaf remote, the pull-build-push routine, merge conflicts with web-editor edits, and source conventions that keep merges clean. Use whenever Overleaf, git.overleaf.com, syncing a paper, a collaborator's edits to the .tex, or pushing paper changes comes up, and before and after any edit to the paper sources of a project that has an `overleaf` remote.
---

# roach overleaf

Every Overleaf project is a git repository at
`https://git.overleaf.com/<project-id>`. Collaborators write in the web editor;
you write in a local clone; git carries both. Overleaf is one more remote, not
a place anything is copied to by hand. This needs Overleaf premium on the
project owner's account (most universities provide it).

Do not use Overleaf's GitHub sync on the same project. It is a manual button
in each direction, and on divergence it dumps Overleaf's side into an
`overleaf-<date>` branch for someone to merge later. If the project already
uses it, stop pressing the button once the bridge is set up; the GitHub remote
stays, fed from the local clone.

## 1. Set up, once per clone

The remote and its credentials live in `.git/config`, which git never shares,
so every clone is set up once, by whoever works in it. When this skill is
invoked in a clone where `git remote get-url overleaf` fails, or where `git
fetch overleaf` does not succeed, run this section top to bottom, doing each
step yourself and stopping only where it says the human acts. It is safe to
re-run: every step first checks whether it is already done.

**1. One branch, current.** `git switch main && git pull`. Overleaf has one
branch and takes no force pushes and no other branches; mirror that locally:
one `main`, the same history on GitHub and on Overleaf. No personal or staging
branch sits between the clone and Overleaf; a second long-lived branch is
exactly the drift this workflow exists to remove. A local branch with commits
`main` lacks (`git log main..<branch>`) is merged into `main` now, then
deleted, locally and on GitHub. Uncommitted work is committed first.
Short-lived worktree branches push straight to both remotes and are deleted.

**2. The environment builds.** Run the project's install (`pixi install`) and
its build (`CLAUDE.md` names it, usually `pixi run compile`). LaTeX is not in
the pixi env: if `latexmk` is not on `PATH`, the human installs a TeX
distribution (MacTeX on a Mac, TinyTeX or TeX Live elsewhere) and you add its
`bin` directory to `PATH`. A missing `.sty` is `tlmgr install <pkg>`. Do not
go on until the build passes on the untouched sources: a clone that cannot
build cannot push safely.

**3. The project id.** The hex string in the project's URL,
`overleaf.com/project/<id>`. The project's `CLAUDE.md` records it; otherwise
the human reads it off their browser.

**4. The token.** The human creates one: Overleaf, Account Settings, Git
Integration, "Create token". It is theirs, one per account, good for every
project they can open; a token is never shared between people and the account
password is never asked for. It goes in a file outside every repo, mode 600,
holding the bare token: where the human already keeps secrets, else
`~/.config/overleaf/token`. Best, the human writes it from their own terminal
so it never passes through the conversation:

```bash
mkdir -p ~/.config/overleaf && chmod 700 ~/.config/overleaf
printf '%s' '<token>' > ~/.config/overleaf/token && chmod 600 ~/.config/overleaf/token
```

If they paste it to you instead, write that file yourself and never repeat
the token, in a reply, a commit, a remote URL or a file in the repo.

**5. The remote.**

```bash
git remote add overleaf https://git.overleaf.com/<project-id>
git config credential.https://git.overleaf.com.username git
git config credential.https://git.overleaf.com.helper \
  '!f() { test "$1" = get && echo "password=$(cat <token-file>)"; }; f'
git fetch overleaf
git ls-remote --heads overleaf
```

The helper reads the file on each fetch and push, so nothing ever prompts and
rotating the token is rewriting one file. A 403 is a wrong or expired token,
or an account without access to the project; a 404 is a wrong id. `ls-remote`
names Overleaf's branch: `main` on current projects, `master` on old ones.
Below it is written `main`.

**6. Shared history?** `git merge-base main overleaf/main`.

- It prints a commit: someone already joined this project to its repo, and
  you are joining them. `git merge --no-edit overleaf/main`, build, and go to
  step 7. This is the usual case for everyone after the first person.
- It prints nothing: you are the first. Join the histories as in "First join"
  below, then record in the project's `CLAUDE.md` only what is the project's
  own: that it syncs with Overleaf by this skill, the build command,
  Overleaf's branch name, the project id, and one bootstrap line for the next
  person, since the skill is not loadable in a clone that has not installed
  yet: "if the `roach-overleaf` skill is missing, `git switch main && git
  pull && pixi install`, then invoke it". Do not copy the routine there; it
  lives here.

**7. Prove both directions.** `git push --dry-run overleaf HEAD:main` proves
write access without changing anything. If the merge or the build left
commits to push, push them for real by section 2.

**8. Retire the GitHub sync button.** Tell the human, in these words or
better: from now on nobody presses "GitHub" sync in the Overleaf menu. It is
not merely redundant. On any divergence it pushes a snapshot to GitHub as an
`overleaf-<date>` branch, and it flattens symlinks into text files, so
merging such a branch with GitHub's button breaks every committed skill link.
For each `origin/overleaf-*` branch that exists: if `git diff <branch> main --
'*.tex' '*.bib'` is empty, or shows only lines where `main` is newer, its
sources are already in `main`: `git merge -s ours <branch>`, push, delete the
branch. Otherwise take the source changes by hand, never the flattened links.

**9. Who pushes.** Ask the human one question: should you sync on your own
after each change, or only when they say so? Record the answer in this clone,
where it binds every later session and nobody else's clone:

```bash
git config overleaf.sync auto      # or: manual
```

Then make sure the routine exists as project tasks, for the human's own
shell. The first person adds them to `pixi.toml`, with Overleaf's branch name
filled in, and commits; everyone after finds them there:

```toml
pull = "git fetch overleaf && git merge --no-edit overleaf/main && git fetch origin && git merge --no-edit origin/main"
push = "pixi run pull && pixi run compile && git push overleaf HEAD:main && git push origin HEAD"
```

Tell the human what they are for. A plain `git push` goes to GitHub only:
nothing appears in the Overleaf editor until someone also pushes to
`overleaf`, and a direct `git push overleaf HEAD:main` is refused whenever a
collaborator has typed since the last merge. `pixi run push` merges both
remotes, builds, and pushes to both, stopping at the first failure (a
conflict, a broken build, a clone with no `overleaf` remote yet) with nothing
pushed; within seconds the web editor shows the edits, and open editors
update in place. `pixi run pull` is the first half alone. Neither commits
anything: uncommitted work stays local.

**10. Report** to the human: the clone's branch, that fetch and push work,
what the first merge brought in, and which sync mode is set and how to change
it.

### First join

The bridge's history is Overleaf's own, a few squashed "Update on Overleaf"
commits, and shares no commit with the repo even when the project was on
GitHub sync. Find what Overleaf holds relative to local history:

```bash
T=$(git rev-parse overleaf/main^{tree})
git rev-list main | while read c; do
  [ "$(git rev-parse $c^{tree})" = "$T" ] && git log -1 --oneline $c; done
```

- A hit means Overleaf's tree is exactly an ancestor: it has nothing local
  lacks. `git merge --allow-unrelated-histories -s ours overleaf/main`.
- No hit means there are web edits local never saw. Usually Overleaf is a
  recent local commit plus those edits: find it (`git diff --stat <commit>
  overleaf/main` over the last few commits, smallest diff wins). If local has
  not touched the same files since, `git merge --allow-unrelated-histories -s
  ours --no-commit overleaf/main`, then `git checkout overleaf/main -- <the
  edited files>`, and commit. Otherwise merge without `-s ours` and resolve by
  hand, with the human: every file conflicts as add/add, and for each the
  question is which side's lines are newer.

Then build and push. From here on every merge is ordinary.

## 2. The routine

`git config overleaf.sync` decides who runs it. Unset counts as `manual`.

- **`auto`**: you run it unasked, as written below.
- **`manual`**: the human owns every exchange with a remote. You edit, build
  and commit locally; you never merge from or push to `overleaf` or `origin`
  on your own, not even when a push is plainly due. `git fetch` changes
  nothing and stays allowed: fetch before editing, and if `git log
  main..overleaf/main` shows commits, say so and say what they touch, since
  the human may want them merged before you edit the same lines. When the
  human says to sync, pull or push, run the routine below in full, once: a
  bare push without the fetch, merge and build is not on offer, because
  Overleaf rejects it or collaborators get a broken build. Afterwards say
  what came in and what went out. Do not nudge the human to switch modes.

Before touching any paper source:

```bash
git fetch overleaf && git merge --no-edit overleaf/main
```

After each logical change, not at the end of the session:

```bash
<build>                                  # the project's latexmk task; it must pass
git commit -am "<what changed>"
git fetch overleaf && git merge --no-edit overleaf/main
git push overleaf HEAD:main
git push origin HEAD                     # if there is a GitHub remote too
```

With a GitHub remote that other people also push to (a collaborator's own
clone, or someone still pressing Overleaf's GitHub sync button), fetch and
merge `origin/main` in the same two places as `overleaf/main`.

- **Merge, do not rebase.** The branch also lives on GitHub; rebasing onto
  Overleaf rewrites commits already pushed there.
- **Small and often.** Overleaf commits web edits into its branch continuously.
  A local branch that drifts for a day is the only source of real conflicts;
  a push every few minutes of work almost never conflicts.
- **A rejected push** means someone typed in between: fetch, merge, build,
  push again. Never force.
- **Build before pushing.** Collaborators compile the pushed sources in the browser the
  moment it lands; a broken push breaks their editor.
- **Build again after a merge that brought in `.tex` changes**, before
  pushing, and read what came in (`git log -p ORIG_HEAD..overleaf/main`):
  collaborators' edits are the context for the next thing you write.

## 3. Conflicts

A conflict is two people editing the same lines. Resolve it keeping both
people's intent; a collaborator's prose is never dropped to make a merge go
through. When the two edits disagree on content, not just wording, keep the
collaborator's version in the text, put yours in a `\todo{}` or a comment next
to it, and tell the human. Then build, commit the merge, push.

## 4. Sources that merge well

- **One sentence per line.** Git merges by line; a paragraph on one line
  conflicts whenever two people touch it. Write new prose this way. Reflow
  existing prose only in a single commit of its own, pushed at once, at a time
  the human says nobody is editing: a reflow conflicts with every edit in
  flight.
- **One file per section**, `\input` from the main file, so people working on
  different sections never share a file.
- **Generated figures and tables are committed** at the path the `.tex`
  includes (see `roach-paper`), so Overleaf compiles them without running any
  code. Build products (`build/`, `*.aux`, the paper's own PDF, the
  environment) are gitignored: a tracked `main.pdf` changes on every build,
  so every sync would carry a binary nobody can merge, and Overleaf compiles
  its own.
- Overleaf refuses a push with a file over 50 MB or more than 2000 files, and
  names the offender in the rejection. Fix the tree; do not retry.

## 5. What git does not carry

Overleaf comments, tracked changes and chat live only in the web editor.
Anything a collaborator wants you to see goes in the source (`\todo{}`, a `%`
note) or through the human. Anything you want collaborators to see goes in
the source or the commit message, which Overleaf shows in its history panel.
