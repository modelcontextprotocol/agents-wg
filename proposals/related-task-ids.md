# SEP-{NUMBER}: Related Task IDs

- **Status**: Draft
- **Type**: Extensions Track
- **Created**: 2026-09-16
- **Author(s)**: @vinoo999
- **Sponsor**: None (seeking sponsor)
- **Extension Identifier**: `io.modelcontextprotocol/tasks`
- **Issue**: https://github.com/modelcontextprotocol/agents-wg/issues/27
- **PR**: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/{NUMBER}

## Abstract

This SEP adds a structured mechanic to allow task supporting operations to accept related task identifiers.

The proposal adds one reserved `_meta` key as part of the [Tasks extension](https://modelcontextprotocol.io/seps/2663-tasks-extension): `io.modelcontextprotocol/relatedTaskIds`, an optional array of task IDs that a client may attach to task supporting operations (for the scope of the current task specification, a `tools/call` request) to indicate that the new request relates to one or more tasks the server has already created.

The field is client-to-server only. There is no obligation on the server to read, act on, or acknowledge it. A server that ignores the key remains conformant with the specification. The key provides a defined, interoperable place to express a relationship that clients currently cannot express.

Today a cancelled task and its replacement are unrelated. A server that may reuse cancelled task's partial work has no way to know the two are connected, so cancel-and-restart discards state that the server holds. This SEP does not force servers to reuse that state. It makes the relationship expressible so that servers which want to can, at their own discretion and without any change to the request/response contract.

## Motivation

Tasks give server operations a durable lifecycle, but that lifecycle is strictly per-task. Nothing in the extension provides mechanics for [steering](https://github.com/modelcontextprotocol/agents-wg/issues/27) or for clients to use stateful interactions beyond server directed elicitations.

While there are a lot of potential problems (and solutions) to navigate steering, there is a clearer sub-problem that may be solved in the core Task extension surrounding cancellation and retry operations. `tasks/cancel` per the specification is explicit that "a server is not obligated to actually stop the work" and that "eventual transition to `cancelled` is not guaranteed"; however, regardless if the task is cancelled by the server or not, the client possesses a clear identifier issued by the server that holds stateful information about a particular task. There is no way today of the client to supply such stateful information as a hint for the server to re-use or restart from as appropriate.

### Examples

Consider three cases: a non-agentic tool, an agentic tool, and a pair of tools in one toolset.

**`run_ci(repo, ref, testFilter?)`.** A client calls a continuous integration tool that runs tests with labels with no filter, so the server begins the full matrix and returns a task. Ten minutes in, the client decides it only needs one package's tests. It cancels and calls `run_ci` again with a `testFilter`.

By that point the server may have performed operations like cloning the repository, installing dependencies, and building the package. The server may still have the prepared workspace in some state. It has no way to learn that the second call is the same work narrowed, so it repeats all of it.

**`stateful_agent(query)`.** A client sends a broad query. The agent runs, makes tool calls, and accumulates findings. Partway through, the client determines the premise was wrong and re-issues a corrected query.

The agent's accumulated context, the LLM + tool calls already made, are discarded. The server may well still hold that state. The client cannot say the second query continues the first.

**`get_ci_logs(tail?)` next to `run_ci`.** The CI task is still `working`, and when it finishes its result will be a pass/fail verdict. The client wants the log lines produced so far, which the verdict will never carry. The same server exposes a second tool that reads the current state of a run, and the client names the running task on the call:

```json
{
  "name": "get_ci_logs",
  "arguments": { "tail": 200 },
  "_meta": {
    "io.modelcontextprotocol/relatedTaskIds": ["task_1234"]
  }
}
```

The server resolves `task_1234`, reads the log buffer it already holds, and returns it as an ordinary `CallToolResult`. `task_1234` is untouched: it keeps running, its status does not change, and its eventual result is the same verdict it was always going to produce.

This is intermediary results without a streaming channel and without any change to the task lifecycle. The read is a normal tool call that happens to be scoped to a task the client names, so the server decides what is worth exposing mid-flight and advertises it as a tool like any other. It does not replace a general intermediary-results mechanism, and it only works where the server chose to offer the reader tool, but it is reachable with the key alone.

### Relationship to steering

The Agents WG is scoping steering, defined in [agents-wg#27](https://github.com/modelcontextprotocol/agents-wg/issues/27) as input delivered to an ongoing task that may change what it does next. Several of the motivating cases there are where the client already knows what it wants and only needs the server to not start over.

Two of the cases above stand on their own even if steering is never specified: cancel-and-retry that does not throw away server-held state, and reading the current state of a running task through a sibling tool. Neither delivers input into a running task, and both leave the task lifecycle exactly as specified today. Both do require a host that knows which task the new call relates to, since the host, not the model, populates the key. That is the same bookkeeping a host already does to poll or cancel a task it created.

Steering in its totality is contentious. It requires deciding where the input is carried, what the server is obliged to do with it, how it interleaves with output already in flight, and whether it belongs in the elicitation machinery. Those questions will take time.

This SEP addresses where there is little ambiguity. Naming prior tasks on a new request adds advisory metadata and the hope would be it can land in the Tasks extension on its own schedule while steering and intermediary results continue as separate, slower work.

One consequence of this SEP that you will find is that nothing here restricts a related task to be in a terminal state, so a client may name a task that is still `working`. A server that chose to act on that could let the new call influence work already in flight, which is steering in effect (think: custom steering tool to send a message with a `taskId` of a server's task on a different `tools/call` tool). However structuring semantics for that is out of scope here and would be imposing too strict of restrictions on the server.

The server remains free to ignore the key, task creation stays server-directed, and the referenced task's own lifecycle and its `tasks/get` and `tasks/cancel` surface are untouched. The point is only that the identifier makes the capability reachable, which the WG should weigh when it decides where steering belongs.

Prior art: A2A carries `reference_task_ids` on `Message` for the same purpose.

## Specification

### The `_meta` key

This SEP reserves one key under the `io.modelcontextprotocol/` prefix:

| Key | Type | Direction | Required |
|---|---|---|---|
| `io.modelcontextprotocol/relatedTaskIds` | `string[]` | Client to server | No |

```ts
/**
 * Task IDs that the client considers related to this request. Advisory.
 *
 * A server MAY use these to carry forward context from earlier work, and is
 * under no obligation to do so or to report whether it did.
 */
export type RelatedTaskIds = string[];
```

The key is defined on requests to operations that support task augmentation. `tools/call` is the only such operation in this revision of the Tasks extension, so in this revision the key is only valid on `tools/call` requests.

The Tasks specification anticipates additional task-supporting request types and advises implementations to accommodate them in future revisions. If a later revision makes another operation task-supporting, this key applies to that operation's requests on the same terms, without a further SEP.

Non-normative example, narrowing a cancelled CI run. The client previously called `run_ci` with no filter, received `task_1234`, and cancelled it:

```json
{
  "jsonrpc": "2.0",
  "id": 7,
  "method": "tools/call",
  "params": {
    "name": "run_ci",
    "arguments": {
      "repo": "example/widgets",
      "ref": "main",
      "testFilter": "packages/parser"
    },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": { "io.modelcontextprotocol/tasks": {} }
      },
      "io.modelcontextprotocol/relatedTaskIds": ["task_1234"]
    }
  }
}
```

A server holding the prepared workspace from `task_1234` may reuse state from the related task and run only the filtered tests. A server may discard the key at its discretion and start afresh. The request is identical in both cases, and the client cannot tell which happened. A fuller exchange is in the [Appendix](#appendix-example-message-flow).

### Semantics

A client **MAY** include `io.modelcontextprotocol/relatedTaskIds` in the `_meta` of a `tools/call` request. A client **SHOULD** populate each element with a task ID previously returned by the same server in a `CreateTaskResult`. Clients **SHOULD NOT** include task IDs obtained from a different server, and **SHOULD NOT** include task IDs obtained under a different authorization context, since a server cannot be expected to resolve either.

Clients **MAY** send an empty array or omit the key to indicate no related tasks. The array carries no defined ordering semantics, and clients **SHOULD NOT** assume a server interprets position as priority or recency.

Clients **SHOULD NOT** allow a language model to populate this field directly. A model that can emit arbitrary task IDs into a request is a path for prompt injection to reference work the caller did not intend. The field is intended to be populated by the host or client from its own record of tasks it created.

A server **MAY** ignore `io.modelcontextprotocol/relatedTaskIds` entirely. Ignoring it is conformant behaviour and requires no signalling. A server **SHOULD** treat an empty array as equivalent to the key being absent, and **SHOULD** ignore duplicate entries. A server **MAY** impose an implementation-defined limit on the number of entries it will process but **SHOULD** ignore entries beyond that limit rather than reject the request.

A server **MUST** apply the same authentication and authorization checks to each referenced task that it would apply to a `tasks/get` for that task, before using it for any purpose. The Tasks specification already requires servers to "perform authentication and authorization checks on each task-related request to ensure that the client has permission to access a task"; a reference in `relatedTaskIds` is such an access and is subject to the same rule.

A server **MAY** treat a reference it does not recognise as if it had not been supplied. A server **SHOULD NOT** use response data models to indicate which task IDs exist or were unauthorized.

A server **MUST NOT** treat the presence of the key as a request to create a task. Task creation remains server-directed and is unaffected by this SEP. A server **SHOULD** issue a new task ID in a `CreateTaskResult` if a new task is created in response to the `tools/call`.

This SEP defines no response field and no mechanism by which a server reports whether it used a referenced task.

### Error handling

This SEP defines no new error codes and no new error conditions.

A server **MAY** return an error code if it attempts to fetch a related task that the client is unauthorized to access. This is the permitted exception to the requirement above that a server not use responses to indicate which task IDs exist, and a server taking it should read the disclosure note in Security Implications first.

## Rationale

### Why `_meta` rather than a request parameter?

Tool arguments belong to the tool's own input schema and are model-facing; a protocol-level relationship between tasks is neither. Putting it in `_meta` keeps it out of the tool's schema and makes it structurally ignorable by servers and protocol versions that do not know about it. It also means that if Tasks later supports operations beyond `tools/call`, the key carries over unchanged, since `_meta` is present on every request while a tool-argument field would have to be reinvented per operation. It also matches how the specification already carries per-request protocol concerns such as `logLevel` and `clientCapabilities`.

### Why client-only, with no acknowledgement?

A client cannot tell whether the hint was used. That is deliberate, for two reasons: scope and security.

On scope, an acknowledgement implies a contract about what it means. That the server read the IDs, or resolved them, or actually reused the work are three different promises, and specifying any of them drags in the obligation questions that make steering hard.

On security, the absence of an acknowledgement means that in the ordinary case nothing differs between a resolvable and an unresolvable reference, so the extension's anti-enumeration property holds without each implementer having to reason about it. Error handling permits a deliberate exception for unauthorized access, and Security Implications sets out what that exception discloses.

### Why an array rather than a single task ID?

A single ID would cover the simple retry case, and it is the smaller field. This limits extensibility for chained operation while simultaneously not prescribing the semantics.

### Why not a new method?

A method implies a request/response contract and an expectation of effect. This is a hint attached to work the client was going to request anyway, and is operationally the same.

### Why `relatedTaskIds` rather than `referenceTaskIds`?

"Reference" implies a pointer the server is expected to dereference, and a field named that way invites implementers to read a resolution step into it and clients to assume one happened. Neither is required here. "Related" says only that the client believes a connection exists, which is the whole of the contract: the server decides whether the relationship means anything, and may conclude it means nothing.

A2A's field is `reference_task_ids`. The divergence is in spelling and connotation rather than semantics, and the two remain close enough to bridge.

### Why this does not prejudge steering

Nothing defined here carries instructions or changes any task's state. The key names prior tasks on a *new* request, and the new request follows the ordinary path.

A referenced task may still be `working`, and Motivation notes that a server could use that to influence work in flight. This SEP neither sanctions nor prevents it.

## Backward Compatibility

There are no backward incompatibilities.

The key is optional. `_meta` is an open map, so a server that does not implement this key simply does not read it, and adding the key changes nothing structurally about the request. Clients that do not send it are unaffected.

Note that the specification does not state a general rule that unrecognised `_meta` keys must be ignored; it requires only that implementations "**MUST NOT** make assumptions about values at" reserved keys. The safety of this key therefore rests on the explicit requirements in the Specification rather than on a blanket ignore-unknown-metadata rule. If the WG would prefer such a general rule, that is a broader change than this SEP and should be proposed separately.

A client cannot detect support and does not need to: sending the key to a server that ignores it produces exactly the behaviour the client would have got without it.

## Security Implications

**Task-existence disclosure.** The Tasks extension deliberately omits `tasks/list` so that, in the specification's words, "a server cannot inadvertently leak the existence of one caller's tasks to another". It also permits servers to use task IDs as bearer tokens, requiring only that they be generated "with sufficient entropy that a third party cannot enumerate or guess them".

`relatedTaskIds` adds a channel where a caller supplies task IDs of its choosing, so a server that responds differently to a known ID than to an unknown one reveals which IDs exist. That is why the Semantics ask for the same response in both cases. The same question is already open against the extension in [ext-tasks#20](https://github.com/modelcontextprotocol/ext-tasks/issues/20), which observes that `-32602` currently collapses "unknown task" and "not authorized" and argues the collapse is probably deliberate but undocumented. A server that chooses to error on an unauthorized reference should understand it is making that distinction observable.

**Task IDs are untrusted input.** The Semantics ask that the host populate this field from its own record of tasks it created, rather than letting a model emit IDs into it, since a model under prompt injection can name work the caller did not intend.

That is a request to clients, and a server has no way to verify it was honored. Servers therefore treat every ID in this field as untrusted caller input, authorized on the server's own terms exactly as a `taskId` arriving on `tasks/get` would be. Servers should not assume a host-populated field on the strength of this SEP saying so.

## Reference Implementation

_No reference implementation yet._

## Open Questions

**Should the array carry typed relations?** A richer element form, `{ taskId, relation }` with a vocabulary such as continues, supersedes, or context, would let a client say what the relationship is rather than only that one exists. It is not proposed here because the vocabulary would be guesswork before implementations exist, and a wrong enumeration is harder to remove than a missing one. A bare array stays forward-compatible, since a later revision could accept either a string or an object per element. If early implementations converge on a small set of distinct meanings, that is the evidence for adding structure.

**Should servers be able to advertise that they honor the field?** A capability flag would let clients avoid a pointless cancel-and-re-issue against a server that will ignore the hint. It is omitted here because it reintroduces a signal about server behaviour, and because the cost of sending an ignored key is zero. This may be worth revisiting if implementations show clients making different decisions based on support.

**Does this belong in Tasks or alongside it?** This SEP assumes Tasks, since it references task IDs. The WG may prefer to add it directly to the Tasks extension before that extension graduates.

## Appendix: Example Message Flow

A complete cancel-and-retry exchange using `run_ci`. Protocol `_meta` fields are elided after the first message for brevity.

**1. Client calls the tool with no filter.**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_ci",
    "arguments": { "repo": "example/widgets", "ref": "main" },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-07-28",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": { "io.modelcontextprotocol/tasks": {} }
      }
    }
  }
}
```

**2. Server materializes a task instead of returning a `CallToolResult`.**

```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "resultType": "task",
    "taskId": "task_1234",
    "status": "working",
    "createdAt": "2026-09-16T14:02:11Z",
    "lastUpdatedAt": "2026-09-16T14:02:11Z",
    "ttlMs": 3600000,
    "pollIntervalMs": 5000
  }
}
```

**3. Ten minutes later the client narrows its intent and cancels.**

```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tasks/cancel",
  "params": { "taskId": "task_1234" }
}
```

**4. Server acknowledges. Cancellation is cooperative, so the task may not stop immediately and may not reach `cancelled` at all.**

```json
{ "jsonrpc": "2.0", "id": 2, "result": { "resultType": "complete" } }
```

**5. Client re-issues the narrowed call, naming the cancelled task.**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "tools/call",
  "params": {
    "name": "run_ci",
    "arguments": {
      "repo": "example/widgets",
      "ref": "main",
      "testFilter": "packages/parser"
    },
    "_meta": {
      "io.modelcontextprotocol/relatedTaskIds": ["task_1234"]
    }
  }
}
```

**6. Server materializes a new task. The response is the same whether or not the server used `task_1234`.**

```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "resultType": "task",
    "taskId": "task_5678",
    "status": "working",
    "createdAt": "2026-09-16T14:12:40Z",
    "lastUpdatedAt": "2026-09-16T14:12:40Z",
    "ttlMs": 3600000,
    "pollIntervalMs": 5000
  }
}
```

A server that still holds the prepared workspace from `task_1234` may skip cloning, dependency installation, and the build, and run only the filtered tests. A server that discarded it, or that does not implement this key, performs the full preparation. Nothing in the exchange tells the client which happened.

**7. Client polls the new task to completion.**

```json
{
  "jsonrpc": "2.0",
  "id": 4,
  "method": "tasks/get",
  "params": { "taskId": "task_5678" }
}
```
