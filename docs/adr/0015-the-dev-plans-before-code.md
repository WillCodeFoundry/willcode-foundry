# TASK.md says what, and the dev's PLAN.md says how, approved before code

`TASK.md` holds only behaviour and scope: its goal, acceptance criteria (`AC1`…), out of scope (`OS1`…), risks, terms and open questions. Before writing code, the dev writes `PLAN.md`: the approach, steps, public names, error messages, a test for each criterion, and the docs to update. The reviewer approves it in a plan round, before any code, or the architect does when it trips a trigger: it adds or breaks a design rule or ADR, adds or moves a module, changes an interface used outside the task, or makes a choice that's hard to reverse. The human may approve it in the dev's session instead. The architect stops writing a `DESIGN.md` per task, and owns the design rules and ADRs. `NAMES.md` and `DESIGN.md` go.

In wcf-0031, most rework came from decisions made in the wrong document, or too late. `TASK.md` fixed implementation details, and two design reversals came from its out-of-scope lines. Nobody saw the design or the names before the code: the human changed eight choices in the session, and review round 1 had four Blocking name findings. Across wcf-0026 to wcf-0032, the 95 review findings cluster where a plan reviewed before code catches them: names (15, 12 Blocking), criteria shown only by reading the code (11), docs a change made untrue (10), and duplicated test setup.

An approved plan stays true. A change to a public name, an error message, a test's seam or the approach goes back for approval before the code that depends on it, and the reviewer reviews the code against the plan's diff since its approved commit. When a second review finding lands on the same function, group of names or step, the dev stops fixing findings one at a time and revises the plan. Every rule has one home and an id, and a decision cites it with "Because:". A design rule the human states in a session goes into `ARCHITECTURE.md` on the task's branch, written by the architect.

This supersedes the parts of [ADR 0013](0013-roles-talk-through-a-log.md) that route a task through the architect for a `DESIGN.md`: the outcomes `needs-design` and `designed` go, and the dev no longer asks design questions. The reviewer still does, for a finding whose fix would break a design rule or an ADR.

## Considered options

- **The architect writes a `DESIGN.md` for every task that changes the structure, as before.** It left names and tests to be found in review, and it split how a task is built across two documents and two roles.
- **The human approves every plan.** Their taste applies before code, but every task would wait for them. The reviewer already judges names, tests and rules, so it approves by default, and the human approves when present.
- **The dev reads `python-naming-smells` while writing the plan.** It would catch names before the plan round, but the dev's skills stay as they are: the plan round judges names.
- **Tasks whose only output is ADRs, taken by the architect up to a pull request.** They needed five outcomes and a second path through the routing table, for a rare kind of task. A decision is made in the first task that needs it instead, and the architect records it there.
- **Plans only for tasks that change names or interfaces.** Deciding which tasks qualify is itself a judgement made too early. A one-line fix gets a three-line plan instead.

## Consequences

- Open tasks with a `DESIGN.md` or `NAMES.md` (wcf-0028, wcf-0031) finish under the workflow they started with.
- A plan round is a review round like any other in `REVIEW.md`, so finding ids continue across plan and code rounds.
