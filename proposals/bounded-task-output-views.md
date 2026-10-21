# SEP-{NUMBER}: Bounded Task-Output Views

- **Status**: Draft
- **Type**: Extensions Track
- **Created**: 2026-10-20
- **Author(s)**: Girish Konda (@girishkvs)
- **Sponsor**: None (seeking sponsor)
- **Extension Identifier**: `io.modelcontextprotocol/tasks`
- **Issue**: https://github.com/modelcontextprotocol/agents-wg/issues/26
- **PR**: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/{NUMBER}

## Abstract

This proposal defines a bounded view of a running task's output: a size-limited snapshot of the task's current output that replaces the previous one, not an unbounded log. A client can show what is done so far, and a client that joins late or misses updates reads the current view instead of replaying history.

Each view carries a revision, so duplicate and late copies do not change what a client shows. An available empty view, an unavailable view and a message that carries no view mean different things. The task's final result stays separate and is never built from views.

The proposal adds no task status, retry mechanism or replay. The existing Tasks rules for authorization, retention, cancellation and final results stay authoritative.

This is a draft for the Tasks and Events Working Group, which owns Tasks, and it has no sponsor yet. The carrier and the wire representation are still open, so this document does not define fields or methods (see [Carrier](#carrier) and [Open Questions](#open-questions)). Negotiation would follow agents-wg#29, which proposes `io.modelcontextprotocol/tasks-v2` for new Tasks behavior. It builds on SEP-2509, SEP-2679 and the Intermediary Results discussion in agents-wg#26.

## Motivation

The [Tasks extension](https://github.com/modelcontextprotocol/ext-tasks/blob/899c1bbc869567670093face3591b39c28ce3219/specification/draft/tasks.md) gives a running task a status, an optional `statusMessage` and, at the end, a result. `tasks/get` returns, and `notifications/tasks` carries, a `DetailedTask`, and a `working` task carries no output. `notifications/progress` and `notifications/message` are not supported on tasks. [Intermediary Results (agents-wg#26)](https://github.com/modelcontextprotocol/agents-wg/issues/26) describes this gap and the options for closing it.

Servers can already expose partial output through their own tools or resources. [ext-tasks#26](https://github.com/modelcontextprotocol/ext-tasks/pull/26) (write-up in [agents-wg#28](https://github.com/modelcontextprotocol/agents-wg/pull/28)) would also let a client name a running task when it calls a sibling tool, such as `get_ci_logs` next to `run_ci`, so that tool can read the task's output. This proposal does not claim that MCP prevents any of that.

What a generic client cannot do is interpret that output without learning each server's own rules:

- A value of `["A"]` followed by `["A", "B"]` can mean replace or append. Two clients can accept the same JSON and show different output.
- An absent field, an empty list and output that is not available right now are not the same thing.
- A final result is not necessarily the last view, or all views joined together.

These are examples of how clients can read the same output differently, not defects observed in named implementations. The proposal is worth pursuing only if real producers and clients want a common contract. If application-specific tools and resources meet their needs, there is no reason to add another extension.

### Prior Work

This proposal does not claim snapshots or the separation of partial and final output as new.

| Work | What it contributes | How this proposal relates |
|---|---|---|
| [SEP-2509](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2509), closed without merging | `tasks/read` for the current output snapshot of a running task, with an `available` flag, while `tasks/result` stayed final-only | Same core idea, adapted to the current Tasks extension, adding revisions and ruling out truncated output presented as the complete view |
| [SEP-2679](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2679), closed without merging when Tasks moved to the extension track | Pushed `notifications/tasks/partial` chunks with sequence numbers, duplicate detection and gap warnings | The append model. This proposal takes the bounded replacement alternative and does not require notifications |
| [agents-wg#26](https://github.com/modelcontextprotocol/agents-wg/issues/26) | Use cases, and open questions on the carrier, the unit of increment and delivery | One concrete answer: the unit is a whole snapshot with a revision, not chunks or deltas |
| [modelcontextprotocol#3237](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3237) | Asks for an interoperable partial-output surface and suggests a task-scoped log resource | Close to the resource option below, with a bounded view instead of an ordered log. A [comment there](https://github.com/modelcontextprotocol/modelcontextprotocol/issues/3237#issuecomment-6299543124) proposes a `task-log://` append log with sequence numbers and resume, the opposite model |
| [ext-tasks#26](https://github.com/modelcontextprotocol/ext-tasks/pull/26) and [agents-wg#28](https://github.com/modelcontextprotocol/agents-wg/pull/28) | `relatedTaskIds`, which would let a client name a running task on a call to a sibling tool that reads its state | The application-specific route. The rules here are meant to hold on that route too |
| [agents-wg#29](https://github.com/modelcontextprotocol/agents-wg/pull/29) | Negotiating new Tasks behavior under a separate identifier | Negotiation for this view would follow what the WG settles there |
| [A2A `TaskArtifactUpdateEvent`](https://github.com/a2aproject/A2A/blob/98279d62316361ba8451eaef300f72b72e169185/specification/a2a.proto#L308-L319) | Artifact chunks with explicit `append` and `last_chunk` flags | Another answer to replace or append: the producer labels each chunk. This proposal replaces the whole view instead |
| [Agents WG meeting, 2026-08-21](https://github.com/modelcontextprotocol/agents-wg/blob/137d88bd7e23f9ce17933248c6924505a6f5ec00/meetings/2026-08-21.md#tasks-and-intermediate-outputs) | Discussed intermediate outputs on tasks, and task management through resource namespaces (Resources 2.0) | Background for the resource option |
| [ext-tasks#24](https://github.com/modelcontextprotocol/ext-tasks/issues/24) | How a client learns about status changes it missed after a `subscriptions/listen` reconnect | The same catch-up problem for status. A fresh read of the current view is this proposal's answer for output |

## Specification

### Scope and Terms

This proposal covers **one size-limited current view per task**. It is not a log, a set of separate artifacts, or a stream of every intermediate event. The view is output, not status: it sits next to the task status and does not change it.

- An **observation** is one statement about the view: a revision, whether a value is available, and the value when it is.
- An **available** value is the complete current view. It may be empty.
- An **unavailable** observation says there is no current value.

The type below is notation for this document, not a wire format:

```typescript
type OutputObservation<Value, Revision> =
  | { revision: Revision; availability: "available"; value: Value }
  | { revision: Revision; availability: "unavailable" };
```

The value type, the revision encoding, field names, the carrier and negotiation are open.

### Identity and Revisions

A server **MUST** tie each observation to the server, the task and the caller's authorization context. A client **MUST NOT** reuse a cached view under a different server or authorization context just because the task ID matches.

A revision **MUST** always mean the same availability and content for that task. Any change to the view or its availability **MUST** get a greater revision. Revisions do not have to be consecutive, and they do not count events or order task status messages.

A server **MUST NOT** reuse a revision for different content after a restart or a replica change. It either keeps its revision state across the change or stops offering the view. How a client learns about that change is part of the open wire design.

### Replacement, Duplicates and Conflicts

An available observation that a client accepts **MUST** replace the previous view completely. The client **MUST NOT** append it, merge it or apply it as a patch, and **MUST NOT** treat missing items as unchanged.

A repeated observation with the same revision and the same content **MUST NOT** change what the client shows. An older revision **MUST NOT** replace a newer one. A gap between revisions **MUST NOT** be treated as a count of missed updates.

Two observations with the same revision and different content or availability **MUST** make the client stop treating its view as current, and the client **MUST** report the inconsistency. It **MUST NOT** keep whichever copy arrived last. A newer valid revision can restore the view. Receiving one of the conflicting copies again does not.

### Available, Empty, Unavailable and Omitted

An unavailable observation **MUST** be distinguishable from an available empty value. A client **MAY** keep an earlier value as history, but **MUST NOT** show it as the current view.

A task message that carries no observation tells the client nothing new about the output. A client **MUST NOT** read it as an empty view, a deletion, or a sign that a cached view is still fresh.

### Size Bound

A server **MUST** declare and enforce a size bound for the view. If the output does not fit, the server **MUST NOT** present a truncated tail or a summary as the complete view. In this proposal it reports the view as unavailable while the task continues. How size is measured, declared and negotiated is open.

### Final Result, Late Output and Cancellation

The existing Tasks terminal statuses and results stay authoritative. A client **MUST NOT** build the final result by joining or merging views. A task that completes with `isError: true` is still a completed task with a tool-error result.

After a client accepts a terminal status, late non-terminal output **MUST NOT** overwrite that status or its result. Conflicting terminal messages are reported, and output revisions do not decide between them.

A `tasks/cancel` acknowledgement **MUST NOT** be treated as proof that the task was cancelled. Later output or a final result still follows the existing task lifecycle.

### Lost Visibility and Fresh Reads

A disconnect, a task TTL that has run out, a not-found response or a change in the caller's authorization **MUST** make the client stop treating its cached view as current. None of these means the task failed, and none is a reason to send the call again.

To treat a view as current again, the client **MUST** make a fresh authorized read through the chosen read path. Messages buffered from before the loss **MUST NOT** restore it on their own. A fresh read can confirm an unchanged revision, but does not by itself resolve a conflict.

### Non-Normative Example

A task checks five repositories and builds a report. The view is a list of finished checks.

| Step | Client receives | Client shows |
|---|---|---|
| 1 | Revision 1, available, `[]` | An empty view. Nothing is done yet |
| 2 | Revision 3, available, `["repo-a: ok"]` | `["repo-a: ok"]` |
| 3 | Revision 5, available, `["repo-a: ok", "repo-b: 2 issues"]` | Both lines. The value replaces the old view and is not appended to it |
| 4 | Revision 5 again, same value | No change. It is a duplicate |
| 5 | Revision 4, arriving late | No change. It is older than the current view |
| 6 | A task status update with no view | No change. It says nothing about the output |
| 7 | Revision 6, unavailable, because the output no longer fits the size bound | No current view. The old lines can stay as history, not as the current view |
| 8 | The task completes with its result | The final result, which is not built from the views |

### Delivery and Negotiation

The view **MUST** be optional and negotiated before a server relies on the client understanding it. A client that does not negotiate it keeps ordinary Tasks behavior.

The view **MUST** work with polling alone. Clients poll as Tasks already describes. Notifications **MAY** say that the view changed, but are not required. This proposal does not add a stream method, bring back `tasks/result`, or reuse progress or logging notifications, which are not supported on tasks.

### Carrier

The proposal needs one carrier. Two competing ways to carry the same view would defeat the point of a common contract.

| Option | What it reuses | What is open |
|---|---|---|
| **Task extension data**: optional view data carried with the `DetailedTask` that `tasks/get` returns and `notifications/tasks` carries | Task identity, authorization, polling advice and the terminal lifecycle | Where the data sits and what it is called; negotiation (see agents-wg#29); the value type; whether a view-only change should send `notifications/tasks`, since each one carries a complete `DetailedTask`; the TypeScript package in ext-tasks currently drops unknown fields from `tasks/get` results ([ext-tasks#32](https://github.com/modelcontextprotocol/ext-tasks/pull/32)) |
| **Advertised resource**: a read-only resource the server advertises for the task, such as a `tasks://` resource that could also expose other intermediate artifacts. This was suggested in the `#agents-wg` discussion | `resources/read` and resource update notifications | How the resource is tied to the task and its authorization; where the revision and availability live; how it stays separate from the final result; how content that can change is handled |

### Error Handling

Invalid view data is not a task failure. If the rest of a task message is valid, rejecting its view does not change the task's status or create a result. An invalid task message stays subject to the base protocol's handling. The chosen carrier needs to say how validation failures and revision conflicts are reported, and this draft allocates no error codes.

## Rationale

### Replacement Over Append

Whole replacement is the smallest model that lets a late reader, or a client that missed updates, catch up with one bounded read. The producer keeps the running output, so a generic client never has to guess between append and replace. The revision only orders views, so there is no cursor to keep and nothing to replay.

The cost is resending data, and the producer has to keep or rebuild the current view. Replacement is a poor fit for unbounded logs. If the main use case needs full history, the group should choose that explicitly rather than add cursors, retention and patches to this proposal.

### Application-Specific Tools

ext-tasks#26 would let a server offer a sibling tool that reads a running task, and that route works without this proposal. The question here is what a generic client can assume without knowing the tool. The same rules can describe what such a tool returns. The carrier decides whether a generic client can find and read the view on its own.

### Revisions Rather Than Timestamps

Tasks already carries `lastUpdatedAt`, and [ext-tasks#24](https://github.com/modelcontextprotocol/ext-tasks/issues/24) uses it to discard a stale snapshot. Timestamps can tie or drift across replicas, and two equal timestamps do not mean the same content. A revision does.

### Scope Boundaries

This proposal does not change progress notifications ([SEP-2632](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2632)) and does not add resumable event delivery ([SEP-2694](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2694)). A revision orders views of the output. It is not a transport or event sequence and does not promise delivery.

### Objections

Consensus is not established. A comment on agents-wg#26 prefers a lossy, best-effort event feed, and application-specific tools may be enough for many servers. Those are alternatives to weigh, not support for this proposal. The same comment asks for an upper bound on what servers buffer. The size bound here is one answer, at the cost that output larger than the bound becomes unavailable instead of truncated.

## Backward Compatibility

The view is optional. Clients that do not negotiate it keep ordinary Tasks behavior, and final results, cancellation and error responses do not change. Existing application-specific tools keep working.

Being additive is not enough on its own. Before choosing a carrier, the group should test a client without the capability, a peer that drops unknown extension data, and any relevant intermediary. The proposal cannot rely on a peer that does not support it passing a new field through. [ext-tasks#32](https://github.com/modelcontextprotocol/ext-tasks/pull/32) shows the risk today: the TypeScript package in ext-tasks keeps an unknown field on `notifications/tasks` but drops it from `tasks/get` and `CreateTaskResult`.

## Security Implications

- **Untrusted content.** Views are untrusted content, not instructions and not evidence that the work succeeded. A view gets no authority that the final result would not have. Hosts keep their normal approval and origin rules.
- **Privacy.** Servers apply the same redaction and filtering to views as to final results. A view can expose intermediate data that the final result would not.
- **Authorization.** Servers **MUST** apply the same authentication and authorization checks to a view read that they apply to `tasks/get` for that task. Cached views stay tied to the caller, so a change in permissions does not expose a previous caller's view.
- **Resource limits.** The carrier needs size and nesting limits that are enforced before a view is accepted, on top of normal transport and parser limits.
- **Conflicts.** Same-revision conflicts are reported, not hidden by last-write-wins. Invalid or conflicting views cannot make a task look completed.
- **References.** A resource reference inside a view does not grant permission to fetch its target, and normal approval, authorization and origin rules apply. A revision does not freeze the content behind a URI that can change.

## Reference Implementation

There is no implementation yet. After the carrier and wire shape are chosen, the plan is a small producer and client over existing MCP transports and Tasks support, including a client that does not negotiate the view, using synthetic data. A prototype is required before the proposal can be accepted, and a second, independent implementation is the evidence that the rules interoperate.

## Testing Plan

These cases are planned for when a carrier exists. None of them has run against an MCP implementation yet.

| Cases | What they check |
|---|---|
| Replacement, duplicate, older revision and skipped revision | Replacement and revision rules |
| Same revision with different content or availability | Conflict handling |
| Unavailable, empty and omitted view | Availability rules |
| A view that differs from the final result, an `isError: true` result, and late output after completion | Final result rules |
| A cancel acknowledgement followed by completion | Cancellation |
| Disconnect, task TTL run out, not-found, fresh read, and a changed caller or server | Identity and lost visibility |
| A declared size bound, oversized values, and malformed or deeply nested values | Size bound |
| Restart or replica change, and referenced content that can change | Revision continuity and references |
| A client without the capability, and a peer or intermediary that drops unknown data | Negotiation and compatibility |

Each requirement needs a concrete check or an explicit exclusion. Cases that are not run do not count as passing.

## Open Questions

1. Do real producers and generic clients need a common current view, or are a lossy feed and application-specific tools enough?
2. Which carrier fits better: task extension data, or an advertised resource such as `tasks://`?
3. What value type renders usefully without treating a view as a final `CallToolResult` or requiring it to match the tool's `outputSchema`?
4. How are revision identity, equality and continuity across restarts represented consistently across languages?
5. How is the size bound declared, measured and negotiated, and how is unavailability reported?
6. Should this be a new SEP, or a joint successor with the authors of SEP-2509 and SEP-2679?
