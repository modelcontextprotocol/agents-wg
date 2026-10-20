# SEP-0000: Tasks Extension Split-Negotiation

- **Status**: Draft
- **Type**: Standards Track
- **Created**: 2026-09-17
- **Author(s)**: @LucaButBoring
- **Sponsor**: None
- **PR**: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/{NUMBER}

## Abstract

With the Tasks extension specification [planned](https://blog.modelcontextprotocol.io/posts/mcp-roadmap/) to eventually move back into the core protocol while continuing to incubate new additions to it as extensions, clients and servers need to be able to communicate whether they support the Tasks extension on the `2026-07-28` protocol specification or the core-ified version of it in the stablized specification version after that in a consistent manner, while also continuing to negotiate additions to Tasks on top of that. This proposal introduces that updated negotiation behavior through a new extension identifier that coexists with the existing one, and describes how backwards-compatible clients should behave on the old and new protocol version combinations.

## Motivation

The Tasks extension is [planned](https://blog.modelcontextprotocol.io/posts/mcp-roadmap/) to be moved back into the core protocol in its current form, while we are also looking to potentially extend it further via [steering](https://github.com/modelcontextprotocol/agents-wg/issues/27) and [intermediate results](https://github.com/modelcontextprotocol/agents-wg/issues/26). The working group does not intend to simultaneously stabilize the extension while also modifying it, as this would be functionally equivalent to claiming to stabilize untested functionality.

To navigate this design space, the new and old functionality need to simultaneously interoperate and be distinct enough to be negotiated and used separately, introducing complexity for `2026-07-28` clients/servers determining how specification-conformant implementations adopt the new features and for clients/servers on the version of the protocol that stabilizes Tasks and looking to interoperate with `2026-07-28` peers.

The key point of ambiguity under consideration is how to make divergent breaking changes to the specification (making extension-gated functionality not-so; and separately, introducing new extension-gated functionality) while simultaneously reusing the current `io.modelcontextprotocol/tasks` extension identifier used for negotiation under the `2026-07-28` specification for seamless backwards-compatibility with existing implementations.

## Specification

All behavior under the `2026-07-28` Tasks extension, currently identified as `io.modelcontextprotocol/tasks`, will be adopted into the core protocol in a future specification release, referred to here as the **stabilizing release**. Stabilization is adopt-as-is, with no wire-level changes. The identifier is **frozen** from that point: it permanently identifies Tasks as specified by the `2026-07-28` extension, and no new behavior will be negotiated under it.

Implementations conforming to the stabilizing release ("stabilized implementations") interoperate with `2026-07-28` implementations ("extension-era implementations") as follows:

- Stabilized servers **MUST** support Tasks in its `2026-07-28` form for requests made at the stabilizing release's protocol version or later, whether or not either party declares `io.modelcontextprotocol/tasks`.
- Stabilized servers **SHOULD** still declare `io.modelcontextprotocol/tasks` in their [`server/discover`](https://modelcontextprotocol.io/specification/2026-07-28/server/discover) capabilities so that extension-era clients recognize them as supporting Tasks.
- For requests made at protocol version `2026-07-28`, that specification's negotiation rules apply unchanged: the client **MUST** declare `io.modelcontextprotocol/tasks` for task augmentation to apply, and the server **MUST NOT** return task-augmented results otherwise.

All new Tasks behavior will be negotiated under a new `io.modelcontextprotocol/tasks-v2` identifier, defined under both the `2026-07-28` specification and the stabilizing release. The new identifier gates only the behavior added on top of base Tasks, and supporting it is optional: implementations on either specification **MAY** support base Tasks alone, declaring only `io.modelcontextprotocol/tasks`. Where `io.modelcontextprotocol/tasks-v2` is supported:

- Under `2026-07-28`, `io.modelcontextprotocol/tasks-v2` **MUST** be declared alongside `io.modelcontextprotocol/tasks`; peers **MUST** treat a lone `io.modelcontextprotocol/tasks-v2` declaration as though neither identifier were declared.
- On or after the stabilizing release, `io.modelcontextprotocol/tasks-v2` **MAY** be declared on its own or in addition to `io.modelcontextprotocol/tasks`.
- Standard [extension negotiation](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning#extension-negotiation) applies: if only one party declares `io.modelcontextprotocol/tasks-v2`, the declaring party reverts to base Tasks behavior.

The settings schema for `io.modelcontextprotocol/tasks-v2` will be defined by the behaviors negotiated under it.

### Compatibility Matrix

[Protocol version negotiation](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning#protocol-version-negotiation) settles mixed-era pairs on `2026-07-28`.

| Client                            | Server                            | Outcome                                                                                                                                                                                                                                                     |
| --------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Extension-era, declares `tasks`   | Extension-era, declares `tasks`   | Tasks per the `2026-07-28` extension. Unchanged by this proposal.                                                                                                                                                                                             |
| Extension-era, declares `tasks`   | Stabilized                        | Works. The client's per-request declaration gates augmentation per the `2026-07-28` extension.                                                                                                                                                                |
| Extension-era, no declaration     | Stabilized                        | No Tasks. The server **MUST NOT** return task-augmented results on a `2026-07-28` request that does not opt in.                                                                                                                                               |
| Stabilized                        | Extension-era, declares `tasks`   | Works. The client declares `io.modelcontextprotocol/tasks` per the `2026-07-28` specification and proceeds under the extension.                                                                                                                               |
| Stabilized                        | Extension-era, no declaration     | No Tasks. The client reverts to core protocol behavior.                                                                                                                                                                                                       |
| Stabilized                        | Stabilized                        | Tasks as core protocol, regardless of extension declarations.                                                                                                                                                                                                 |

`io.modelcontextprotocol/tasks-v2` layers on uniformly: wherever the matrix yields active Tasks, its behaviors are additionally in effect if and only if both parties declare it.

## Rationale

### Split Identifiers vs. Reusing `io.modelcontextprotocol/tasks`

The main alternative was keeping a single identifier: silently move the existing behavior into the core specification at stabilization, and reuse `io.modelcontextprotocol/tasks` to gate whichever new behaviors incubate next. This changes what the declaration promises: an extension-era peer declaring it promises exactly the `2026-07-28` behavior, while a stabilized peer would read it as a promise of the new behaviors. [SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions) prohibits this ("Breaking changes **MUST** use a new identifier"), and it defeats the fallback in [extension negotiation](https://modelcontextprotocol.io/specification/2026-07-28/basic/versioning#extension-negotiation): both parties declare the same string while meaning different feature sets, so negotiation succeeds spuriously and the mismatch surfaces as runtime errors rather than clean degradation.

Scoping the identifier's meaning by protocol version instead would avoid the wire-level mismatch, but would make the `extensions` capability map uninterpretable without out-of-band context: the same key would name different feature sets and settings schemas depending on the protocol version of the request carrying it.

### Making `io.modelcontextprotocol/tasks-v2` Available Under `2026-07-28`

Defining `io.modelcontextprotocol/tasks-v2` only from the stabilizing release onward would couple the incubation of prospective new features such as [steering](https://github.com/modelcontextprotocol/agents-wg/issues/27) and [intermediate results](https://github.com/modelcontextprotocol/agents-wg/issues/26) to the core release cadence. If stabilization slipped, the working group would face pressure to land new behavior under the existing identifier in the meantime. Decoupling the two allows incubation to proceed against the existing `2026-07-28` install base immediately.

## Backward Compatibility

This proposal introduces no breaking changes; it in fact describes how to avoid making true breaking changes.

## Security Implications

TBD

## Reference Implementation

TBD
