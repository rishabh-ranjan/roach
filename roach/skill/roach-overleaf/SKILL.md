---
name: roach-overleaf
description: Habits for editing a paper in a local clone of an Overleaf project (origin is git.overleaf.com) — pull before editing, build, commit and push after each change. Use before and after any edit to the paper sources of such a clone, and whenever syncing with Overleaf comes up.
---

# roach overleaf

The repo is a clone of the Overleaf project. Collaborators type in the web
editor; their edits arrive as commits on `main`, the only branch Overleaf has.

```bash
git pull                                      # before touching any paper source
pixi run compile                              # after each logical change; it must pass
git commit -am "<what changed>" && git push
```

Do this unasked, after every logical change, not at the end of the session.

- A refused push means someone typed since your pull: `git pull`, build again
  if `.tex` came in, push. Never force, never rebase.
- A conflict keeps both people's intent. A collaborator's prose is never
  dropped; where the edits disagree on content, theirs stays in the text,
  yours goes in a `\todo{}`, and the human is told.
