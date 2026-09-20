---
name: roach-overleaf
description: Writing a paper with collaborators on Overleaf from a local git clone, through Overleaf's git bridge — setting up the overleaf remote, the pull-build-push routine, merge conflicts with web-editor edits, and source conventions that keep merges clean. Use whenever Overleaf, git.overleaf.com, syncing a paper, a collaborator's edits to the .tex, or pushing paper changes comes up, and before and after any edit to the paper sources of a project that has an `overleaf` remote.
---

# roach overleaf

Every Overleaf project is a git repository at
`https://git.overleaf.com/<project-id>`. Collaborators write in the web editor;
you write in a local clone; git carries both. Overleaf is one more remote, not
a place anything is copied to by hand. This needs Overleaf premium on the
project owner's account (Stanford provides it).

Do not use Overleaf's GitHub sync on the same project. It is a manual button
in each direction, and on divergence it dumps Overleaf's side into an
`overleaf-<date>` branch for someone to merge later. If the project already
uses it, stop pressing the button once the bridge is set up; the GitHub remote
stays, fed from the local clone.

## 1. Set up, once per clone

The human supplies two things: the project id (the hex string in the project
URL, `overleaf.com/project/<id>`) and a git token (Overleaf Account Settings,
Git Integration). Never ask for their password, and never write the token
into a remote URL, a file in the repo, or a commit.

```bash
git remote add overleaf https://git.overleaf.com/<project-id>
git config credential.https://git.overleaf.com.helper store
git config credential.https://git.overleaf.com.username git
git fetch overleaf
```

The first fetch prompts for the password: the human pastes the token, by
running the fetch themselves (`! git fetch overleaf`). `store` keeps it in
`~/.git-credentials`, outside the repo. After that nothing prompts.

Overleaf has one branch, `master`, and takes no force pushes and no other
branches. Mirror that locally: one branch, `main`, the same history on GitHub
and on Overleaf, pushed as `HEAD:master`. No personal or staging branch sits
between the clone and Overleaf; a second long-lived branch is exactly the
drift this workflow exists to remove. Short-lived worktree branches push
straight to both remotes and are deleted.

If the local repo and the Overleaf project have unrelated histories (the
project was started in the web editor and the repo elsewhere), merge once with
`git merge --allow-unrelated-histories overleaf/master` and resolve by hand,
with the human, before anything else. If the project was on GitHub sync, the
histories are already shared and the first merge is ordinary.

Write the routine of section 2, with the project's build command filled in,
into the project's `CLAUDE.md`, so every session follows it.

## 2. The routine

Before touching any paper source:

```bash
git fetch overleaf && git merge --no-edit overleaf/master
```

After each logical change, not at the end of the session:

```bash
<build>                                  # the project's latexmk task; it must pass
git commit -am "<what changed>"
git fetch overleaf && git merge --no-edit overleaf/master
git push overleaf HEAD:master
git push origin HEAD                     # if there is a GitHub remote too
```

- **Merge, do not rebase.** The branch also lives on GitHub; rebasing onto
  Overleaf rewrites commits already pushed there.
- **Small and often.** Overleaf commits web edits into `master` continuously.
  A local branch that drifts for a day is the only source of real conflicts;
  a push every few minutes of work almost never conflicts.
- **A rejected push** means someone typed in between: fetch, merge, build,
  push again. Never force.
- **Build before pushing.** Collaborators compile `master` in the browser the
  moment it lands; a broken push breaks their editor.
- **Build again after a merge that brought in `.tex` changes**, before
  pushing, and read what came in (`git log -p ORIG_HEAD..overleaf/master`):
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
  code. Build products (`build/`, `*.aux`, the environment) are gitignored.
- Overleaf refuses a push with a file over 50 MB or more than 2000 files, and
  names the offender in the rejection. Fix the tree; do not retry.

## 5. What git does not carry

Overleaf comments, tracked changes and chat live only in the web editor.
Anything a collaborator wants you to see goes in the source (`\todo{}`, a `%`
note) or through the human. Anything you want collaborators to see goes in
the source or the commit message, which Overleaf shows in its history panel.
