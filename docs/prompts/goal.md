## Agents.md

**Start of every session prompt:**
> "Read AGENTS.md. Check current sprint goal and system state. Read INVARIANTS.md for coding rules. Then read docs/project/tasks.md and tell me the next uncompleted task, your plan for it, and any questions before you touch any files."

**After every completed task:**
> "Task [X] is complete and tests pass. Update AGENTS.md — move it to completed, add any gotchas discovered, update immediate next steps. Then commit with message: `[commit type](scope): description`"


## docs/project/tasks.md

Each task is designed to be completable in a single Codex session (30–90 minutes).
Every task has:
- **Acceptance criteria** — the exact conditions that mean "done"
- **Test requirement** — what test must pass before the commit
- **Touches** — which files are created or modified

When a task is done: mark `[x]`, commit, update AGENTS.md.

**Prompt to start any task:**
> "Read AGENTS.md and INVARIANTS.md. I want to work on Task [ID]: [title]. Outline your plan for this task and any questions before touching any files."

---
