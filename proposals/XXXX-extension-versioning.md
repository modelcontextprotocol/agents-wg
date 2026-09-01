# SEP-XXXX: Extension Versioning

- **Status**: Draft
- **Type**: Standards Track
- **Created**: 2026-06-01
- **Author(s)**: Luca Chang (@LucaButBoring), Thierry Damiba (@thierrypdamiba); on behalf of the Agents Working Group
- **Sponsor**: Caitie McCaffrey (@CaitieM20)
- **PR**: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/XXXX

## Abstract

[SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions) establishes that extensions evolve independently of the core protocol and **SHOULD** be versioned, but it leaves the versioning approach unspecified and defers extension dependency declaration to future work. This proposal fills both gaps with a single mechanism. Each extension carries a [semantic version](https://semver.org/spec/v2.0.0.html) in its settings object, and **MAY** declare the core protocol version its behavior depends on. A difference in the major version means the two peers are incompatible; they negotiate a shared major version through inline retry, as they negotiate a protocol version (see [protocol version negotiation](https://modelcontextprotocol.io/seps/2575-stateless-mcp#version-negotiation-flow)). A difference in the minor version is not a conflict: each peer uses the features common to both, and neither rejects the other. A difference in the patch version changes nothing about how the peers interoperate. A new error code, `-32005` (Unsupported Extension Version), reports a major-version mismatch and tells the client which major versions the server supports, so it can retry against one of them.

The mechanism is described generically and applies to any extension. This proposal draws its examples from the Tasks extension ([SEP-2663](https://modelcontextprotocol.io/seps/2663-tasks-extension)).

## Motivation

[SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions) scoped itself narrowly: it defined how extensions are governed, identified, and negotiated, but excluded two compatibility concerns from its scope. Under _Not Specified_, it omits both extension dependencies on core protocol versions and a concrete versioning approach, recording only that "Extensions **SHOULD** be versioned, but exact versioning approach is not specified here." Three problems follow from those omissions, and each currently surfaces as a runtime failure rather than a negotiated outcome.

### An extension's protocol-version dependency is undiscoverable

Many extensions depend on base-protocol features introduced in a specific revision. Tasks depends on server-request association ([SEP-2260](https://modelcontextprotocol.io/seps/2260-Require-Server-requests-to-be-associated-with-Client-requests)), multi round-trip requests ([SEP-2322](https://modelcontextprotocol.io/seps/2322-MRTR)), sessionless operation ([SEP-2567](https://modelcontextprotocol.io/seps/2567-sessionless-mcp)), and the stateless model ([SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp)), all of which arrive in the `2026-06-30` specification. A peer on an older protocol version can advertise the extension and pass capability negotiation, then fail on the first request that relies on one of those features. The protocol provides no field in which the extension can state the protocol version it requires.

### An extension cannot roll out a breaking change of its own

Extensions and the core protocol release on independent schedules, so a maintainer who needs to make a breaking change to an extension — removing `tasks/cancel`, renaming a method — cannot defer it to the next core specification revision. SEP-2133 requires a new identifier for an extension's breaking changes. A new identifier is a poor fit for this case: it discards the identifier a client uses to recognize the extension, and it provides no period during which the old and new definitions coexist. A rollout instead requires publishing the new revision of the extension, advertising it alongside the old one for a migration window, and letting each pair of peers agree on a revision both implement.

### Optional, non-breaking features cannot be advertised

An additive change carries no such hazard, yet still cannot be communicated. SEP-2663 anticipates one — "This specification may be extended to support tasks over other request types in the future; implementations **SHOULD** be designed to accommodate additional request types in future revisions of this specification" — but defines no way to advertise which of those additions a peer implements. Two peers can both advertise `io.modelcontextprotocol/tasks` while disagreeing on every feature added since the first release. A client that needs a later feature can only issue the request and observe whether the server honors it, which is the trial-and-error handshake the SEP-2663 redesign removed from capability negotiation.

The mechanism below addresses all three problems generically. Tasks gives the work added urgency: it is slated to return to the core protocol in a future revision, so any breaking changes are best made beforehand, while it is still an extension and free to iterate.

## Specification

### Versioning Scheme

An extension version is a [semantic version](https://semver.org/spec/v2.0.0.html) of the form `MAJOR.MINOR.PATCH`. The components carry distinct compatibility meanings, and each addresses one of the problems in [Motivation](#motivation):

- **MAJOR** identifies a revision that makes a breaking change, as defined by [SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions#definition): removing or renaming fields, changing field types, altering the semantics of existing behavior, or adding new required fields. Peers **MUST** agree on a major version to interoperate.
- **MINOR** identifies an additive, backward-compatible revision, such as support for an additional task-augmented request type. Peers at differing minor versions remain interoperable by confining themselves to the surface shared at the lower of the two (see [Minor Version Resolution](#minor-version-resolution)).
- **PATCH** identifies a clarification or non-breaking correction. A difference in the patch version **MUST NOT** affect interoperability.

An extension's first published version is `1.0.0`. A version string that omits a component is malformed; peers **MUST** declare all three components.

### Declaring an Extension Version

A client declares the single extension version it targets for a request in the `version` field of that extension's settings object, within the [SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions) `extensions` map carried in its per-request capabilities ([SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp)):

```jsonc
// Client to server, in per-request capabilities
{
  "params": {
    "_meta": {
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": {
            "version": "2.1.0"
          }
        }
      }
    }
  }
}
```

A server advertises the extension versions it supports in its `server/discover` response. The `versions` field lists one entry per supported major version, each giving the highest minor and patch versions the server implements for that major version. A server **MUST NOT** list two entries that share a major version. A server **MAY** support multiple major versions simultaneously; this is what permits a breaking change to be rolled out across a migration window:

```jsonc
// Server to client, in response to server/discover
{
  "result": {
    "supportedVersions": ["2025-11-25", "2026-06-30"],
    "capabilities": {
      "extensions": {
        "io.modelcontextprotocol/tasks": {
          "versions": ["1.4.0", "2.3.0"],
          "requires": {
            "protocolVersion": "2026-06-30"
          }
        }
      }
    }
  }
}
```

A missing `version` (client) or `versions` (server) **MUST** be interpreted as the peer supporting only the extension's initial version, `1.0.0`. This preserves the meaning of the empty settings object `{}` that implementations published before this proposal already advertise.

The version numbers in this document are illustrative. They do not assert that any particular extension has reached a given revision; the Tasks extension's shipped revision under [SEP-2663](https://modelcontextprotocol.io/seps/2663-tasks-extension) is `1.0.0`.

The `version` and `versions` fields are mutually exclusive by role: a client declares the one version it targets per request, and a server enumerates the set it supports. The negotiation defined here governs the client-to-server direction. A server-originated request that itself carries an extension-versioned payload (for example, an elicitation surfaced through a task's `inputRequests`) inherits the extension version resolved when the task was created, and the server **MUST NOT** introduce a payload that exceeds that version. The effective version of a long-lived object is pinned at creation: the `version` a client declares on a later `tasks/get` or `tasks/update` does not retroactively widen or narrow the surface of an in-flight task, just as it does not for a subscription (see [Subscription Version Pinning](#subscription-version-pinning)). No separate version field travels on the embedded request.

### Protocol Version Dependencies

A server **MAY** declare the minimum core protocol version its extension behavior depends on in the `requires.protocolVersion` field of the extension's settings object in its `server/discover` response. The value is a protocol version identifier in the scheme the core specification uses (a `YYYY-MM-DD` revision string today):

```jsonc
// Server to client, in the extensions map of a server/discover response
{
  "io.modelcontextprotocol/tasks": {
    "versions": ["2.3.0"],
    "requires": {
      "protocolVersion": "2026-06-30"
    }
  }
}
```

A declared floor is **advisory**. A client **SHOULD** compare the negotiated protocol version against a server's advertised `requires.protocolVersion` and degrade gracefully — declining to exercise the extension — when the negotiated version is lower. A server **MUST NOT** reject a request solely because the negotiated protocol version is below a floor. A client that heeds the floor exercises the extension only on a protocol version that satisfies it, so no new error path is introduced: a floor is resolved by the client renegotiating a higher core protocol version through the existing `-32004` (Unsupported Protocol Version) flow, not by an extension-specific error. This is deliberately distinct from a major-version mismatch, which `-32005` reports because the client resolves it by changing the extension version it requests rather than the protocol version.

A server that declares no `requires.protocolVersion` makes no protocol-version assumption beyond what the negotiated version already guarantees.

### Major Version Negotiation

Major version negotiation mirrors [protocol version negotiation](https://modelcontextprotocol.io/seps/2575-stateless-mcp#version-negotiation-flow):

1. The client sends a request declaring its target version under `extensions.<id>.version`.
2. If the server supports the requested major version, it processes the request. The minor and patch versions the server uses are governed by [Minor Version Resolution](#minor-version-resolution).
3. If the server does not support the requested major version, it **MUST** return an [Unsupported Extension Version](#unsupported-extension-version) error (`-32005`) listing the versions it supports for that extension.
4. On receiving the error, the client **MUST** select a mutually supported major version and retry the request, or abort if it supports none the server offers.

A client **MAY** instead call `server/discover` before issuing any extension-targeted request, learning the server's supported versions in advance and avoiding the retry round-trip.

A server **SHOULD** process a request whose extension version it does not support when the request does not exercise the extension. Version negotiation gates only the behavior that depends on the disagreeing extension.

When a request fails both extension version negotiation and protocol version negotiation, the server **MUST** return `UnsupportedProtocolVersionError` (`-32004`). The protocol version error takes precedence because extension behavior is undefined under an unsupported protocol version.

#### Unsupported Extension Version

If servicing a request requires an extension major version the client did not declare, the server **MUST** return a JSON-RPC error enumerating the versions it supports. For HTTP, the response status code **MUST** be `400 Bad Request`.

```typescript
export const UNSUPPORTED_EXTENSION_VERSION = -32005;

export interface UnsupportedExtensionVersionError extends Omit<
  JSONRPCErrorResponse,
  "error"
> {
  error: Error & {
    code: typeof UNSUPPORTED_EXTENSION_VERSION;
    data: {
      /**
       * The versions the server supports, keyed by extension identifier.
       * Present only for extensions that failed version negotiation.
       */
      extensions: Record<string, {
        /** The version the client declared for this extension. */
        requested: string;
        /** The versions the server supports for this extension. */
        supported: string[];
      }>;
    };
  };
}
```

A single request **MAY** target functionality from more than one extension, each declaring its version independently. When several extensions fail negotiation at once, the server **SHOULD** report every failure in one response so the client can resolve them together:

```jsonc
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    // UNSUPPORTED_EXTENSION_VERSION
    "code": -32005,
    // Message provided for example purposes only. The content of this example message is non-normative.
    "message": "Unsupported extension version(s)",
    "data": {
      "extensions": {
        "io.modelcontextprotocol/tasks": {
          "requested": "3.0.0",
          "supported": ["1.4.0", "2.3.0"]
        },
        "io.modelcontextprotocol/ui": {
          "requested": "1.0.0",
          "supported": ["2.1.0"]
        }
      }
    }
  }
}
```

#### Rolling Out a Breaking Change

A maintainer rolls out a breaking change by publishing a new major version and having servers advertise it alongside the prior one for a migration window. Convergence then works in both directions.

Consider a server advertising `versions: ["1.4.0", "2.3.0"]` for an extension. A client that has adopted major version `2` declares `version: "2.1.0"`; the server supports that major version and processes the request at effective minor version `2.1`. A client still on major version `1` declares `version: "1.4.0"`; the server processes it at major version `1` unchanged. Neither client coordinates with the other, and the server honors both until it retires major version `1`.

When the two are not yet aligned, the client converges through the same `-32005` flow whichever side is ahead. A client that has adopted major version `2` but reaches a server still advertising only `versions: ["1.4.0"]` receives `-32005` with `supported: ["1.4.0"]`, selects major version `1`, and retries against the surface that server offers. A client still on major version `1` that reaches a server advertising only `versions: ["2.3.0"]` receives the same error with `supported: ["2.3.0"]`, and either adopts major version `2` or aborts if it cannot. The breaking change is thus gated on negotiation rather than imposed at a flag day, and the migration window is bounded only by how long servers choose to advertise the old major version.

### Minor Version Resolution

Within an agreed major version, the **effective minor version** of the session is the lower of the two peers' minor versions, written below in `MAJOR.MINOR` form. Each peer **MUST** confine itself to the additive surface available at the effective minor version: a client **MUST NOT** depend on a server honoring features introduced above it, and a server **MUST NOT** emit responses that rely on features above it.

Computing the effective minor version requires the client to know the server's minor version for the agreed major version, which it learns from the server's advertised `versions` — through `server/discover` or a prior response carrying that extension's settings. A client that has not obtained the server's `versions` **MUST** assume only the base minor version (`.0`) of the agreed major version, the lowest-common-denominator surface that the major version guarantees. A server learns the client's minor version directly from the `version` the client declares on each request.

A difference in the minor version is never grounds for rejection. A server **MUST NOT** return `-32005` because a client's declared minor version differs from its own; the error is reserved for major-version disagreement. A client that requires a feature introduced at a particular minor version degrades gracefully when the server's minor version for the agreed major version is lower, exactly as it would for any optional capability.

For a concrete case, suppose major version `2` of the Tasks extension adds task-augmented `prompts/get` at minor version `2.2`. A server that implements it advertises `versions: ["2.3.0"]`; a client that wants it declares `version: "2.3.0"`, observes from the server's advertised `versions` that the agreed effective minor version is at least `2.2`, and issues task-augmented `prompts/get`. The same client talking to a server advertising `versions: ["2.1.0"]` resolves an effective minor version of `2.1`, below `2.2`, so it confines itself to the surface available there and never issues the augmented request. No error is exchanged in either direction; the optional feature is present or absent purely by intersection.

### Subscription Version Pinning

When a client issues a `subscriptions/listen` request ([SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp)) that includes extension-scoped notification types — for the Tasks extension, `notifications/tasks` — the effective version resolved for that request, from the `version` it declares in the listen request's per-request capabilities as for any other request, is pinned for the lifetime of the subscription. The pinned version is the declared major version together with the effective minor version per [Minor Version Resolution](#minor-version-resolution). A notification can carry minor-gated additive fields, so freezing the minor version, not the major version alone, is what keeps the schema stable across the subscription.

The server **MUST NOT** send a notification that relies on a feature above the pinned effective version. If the server drops support for the pinned major version while the subscription is active, it **MUST** [close the subscription](https://modelcontextprotocol.io/seps/2575-stateless-mcp#stopping-a-subscription) rather than silently switch the client to another version.

### Error Handling

Servers **MUST** return the following JSON-RPC errors for extension version negotiation:

- One or more unsupported extension major versions in a request: `-32005` (Unsupported Extension Version).
- A request that fails both extension and protocol version negotiation: `-32004` (Unsupported Protocol Version), which takes precedence over `-32005` (see [Major Version Negotiation](#major-version-negotiation)).

Servers **SHOULD** provide informative error messages describing the cause of the error.

### Example Message Flows

The following flows illustrate how the mechanism addresses each of the three problems from [Motivation](#motivation), followed by a multi-extension case. They are non-normative; the extensions and version numbers are illustrative. For brevity, the requests elide per-request `_meta` fields that [SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp) requires but that are immaterial here, such as `io.modelcontextprotocol/clientInfo`.

#### A Client Honors an Unmet Protocol Floor

The server's Tasks behavior requires protocol `2026-06-30`. A client that has negotiated `2025-11-25` calls `server/discover` and reads the floor:

```jsonc
// server/discover result
{
  "supportedVersions": ["2025-11-25", "2026-06-30"],
  "capabilities": {
    "extensions": {
      "io.modelcontextprotocol/tasks": {
        "versions": ["2.3.0"],
        "requires": { "protocolVersion": "2026-06-30" }
      }
    }
  }
}
```

The negotiated `2025-11-25` is below the advertised floor, so the client declines to exercise Tasks. It issues an ordinary `tools/call` without declaring the extension, and the server returns a `CallToolResult` directly rather than a task:

```jsonc
// Client to server: no tasks capability declared
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "long_running_job",
    "arguments": {},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2025-11-25",
      "io.modelcontextprotocol/clientCapabilities": { "extensions": {} }
    }
  }
}
```

The floor binds entirely on the client; the server never rejects the request on protocol-version grounds. Had the client instead negotiated `2026-06-30`, the floor would be satisfied and the client would be free to declare the extension.

#### A Breaking Change Converges Through Retry

The Tasks extension has published a breaking major version `2`, but this server still implements only major version `1`. A client that has adopted major version `2` declares it:

```jsonc
// Client to server
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "long_running_job",
    "arguments": {},
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-06-30",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": { "version": "2.0.0" }
        }
      }
    }
  }
}
```

The server does not support major version `2`, so it returns `-32005` naming the version it does support:

```jsonc
// Server to client
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    // UNSUPPORTED_EXTENSION_VERSION
    "code": -32005,
    "message": "Unsupported extension version(s)",
    "data": {
      "extensions": {
        "io.modelcontextprotocol/tasks": {
          "requested": "2.0.0",
          "supported": ["1.4.0"]
        }
      }
    }
  }
}
```

The client retries against major version `1`, which the server honors. A client that supported only major version `1` against a major-`2`-only server would receive the symmetric error and either adopt major version `2` or abort.

#### An Optional Feature Resolves by Intersection

[Minor Version Resolution](#minor-version-resolution) walks the case where major version `2` adds task-augmented `prompts/get` at minor version `2.2`. Once the effective minor version permits the feature — the server advertises `versions: ["2.3.0"]`, so it resolves to at least `2.2` — the augmented request the client issues is:

```jsonc
// Client to server, declaring tasks 2.3.0
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "prompts/get",
  "params": {
    "name": "summarize",
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-06-30",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": { "version": "2.3.0" }
        }
      }
    }
  }
}
```

Against a server whose effective minor version falls below `2.2`, the client withholds this request entirely. Either way, no error is exchanged.

#### Two Extensions Negotiate Independently

A request can carry more than one extension, each versioned independently. One extension can also build on another: a hypothetical Events extension might let Tasks attach an event stream to a task, so a client that wants streamed intermediate results declares both Tasks and Events on the same `tools/call`. (The pairing is illustrative; it does not commit either extension to this design.)

```jsonc
// Client to server, declaring two extensions
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "run_ci",
    "arguments": { "branch": "feature/auth" },
    "_meta": {
      "io.modelcontextprotocol/protocolVersion": "2026-06-30",
      "io.modelcontextprotocol/clientCapabilities": {
        "extensions": {
          "io.modelcontextprotocol/tasks": { "version": "2.3.0" },
          "io.modelcontextprotocol/events": { "version": "1.1.0" }
        }
      }
    }
  }
}
```

The two negotiate separately. Suppose the server supports Tasks major version `2` but only Events major version `2`, having dropped major version `1`. Tasks succeeds; Events fails. The server reports only the extension that failed:

```jsonc
// Server to client
{
  "jsonrpc": "2.0",
  "id": 1,
  "error": {
    // UNSUPPORTED_EXTENSION_VERSION
    "code": -32005,
    "message": "Unsupported extension version(s)",
    "data": {
      "extensions": {
        "io.modelcontextprotocol/events": {
          "requested": "1.1.0",
          "supported": ["2.0.0"]
        }
      }
    }
  }
}
```

The client can either retry against Events major version `2`, or — because the event stream is an optional enhancement, not a precondition for the tool call — drop the Events capability and reissue with Tasks alone, accepting task creation without streamed results. That fallback exists because the failed Events negotiation gates only the streamed-results behavior Events governs; Tasks is untouched. Had the failing extension instead been one the request genuinely depends on, the client would have no such fallback and would abort.

- The keys `version`, `versions`, and `requires` within an extension's settings object are reserved by this proposal. An extension **MUST NOT** assign them an incompatible meaning.
- The error code `-32005` (Unsupported Extension Version) is reserved by this proposal.

## Rationale

### Semantic Versioning over a Date-Based Scheme

The core protocol identifies versions by date (`YYYY-MM-DD`) to mark the last backward-incompatible change. That convention works for a specification that ships infrequently and effectively recognizes only major versions: every dated revision is a checkpoint, with no separate notation for an additive change. Extensions evolve on a different cadence, iterating between protocol releases and accreting optional features continuously. A date string collapses "added an optional feature" and "removed a method" into the same kind of event, whereas a semantic version distinguishes them by construction — which is what lets a maintainer ship a minor revision without the ceremony of a major release, and lets a peer reason about compatibility from the version string alone.

### The Version Lives in the Settings Object, Not the Identifier

SEP-2133 states that breaking changes **MUST** use a new identifier, and one reading would encode every major version in the identifier itself (`io.modelcontextprotocol/tasks-v2`). This proposal carries the entire version, including the major version, in the settings object instead, and treats a gated breaking change as not requiring a new identifier.

The justification is that SEP-2133 defines a breaking change as one that would "cause existing compliant implementations to fail or behave incorrectly." A change negotiated through the mechanism defined here does not have that effect: a peer that does not support the new major version learns so during negotiation and continues against a version it does understand. The breaking change is therefore gated, not imposed, and the condition that compels a new identifier is not met. This reading is consistent with the published [extensions guidance](https://modelcontextprotocol.io/extensions/overview#evolution), which already advises maintainers to "prefer using capability flags or versioning within the extension settings object rather than creating a new extension identifier," reserving a new identifier for a breaking change that is otherwise unavoidable.

Encoding the major version in the identifier would also fragment the very identity that negotiation depends on. A client recognizes a feature by its identifier; if `io.modelcontextprotocol/tasks` and `io.modelcontextprotocol/tasks-v2` are distinct identifiers, a client must already know they denote the same extension to negotiate between them, and the server cannot report "I support these versions of the thing you asked for" in a single error. Keeping a stable identifier and a negotiated version separates identity from revision and lets a server advertise several major versions at once during a migration.

A new identifier remains the correct tool for a change that negotiation cannot express — for instance, a redefinition so fundamental that the extension is no longer recognizably the same feature. This proposal narrows when a new identifier is required; it does not remove the option.

This narrowing reinterprets a normative **MUST** in an accepted SEP: SEP-2133 states that "Breaking changes **MUST** use a new identifier." The reinterpretation rests on SEP-2133's own definition of a breaking change as one that makes existing implementations "fail or behave incorrectly," which a negotiated change does not. The published extensions guidance has since moved in the same direction. Because it touches accepted normative text, this position requires core-maintainer concurrence rather than working-group adoption alone, consistent with this proposal's framing of Tasks as a maintainer-preflighted proving ground.

### Minor Versions Do Not Gate Negotiation

If a minor version increment is genuinely additive, then rejecting a peer over a difference in the minor version would reject an interoperable peer. Treating the minor version as the ceiling of _available_ additive surface, resolved by intersection, is what lets a newer server and an older client interoperate without coordination: each confines itself to the shared surface, and neither has to enumerate the other's minor versions to find common ground. A dependency strong enough to justify refusing a peer is, by definition, not additive, and belongs at the major version boundary where negotiation can act on it.

### A Dedicated Error Code Identifies Version Mismatches

Reusing `-32003` (Missing Required Client Capability) was considered and rejected. Its payload names specific capabilities a client must add to proceed, but an extension version mismatch is resolved differently: the client switches to _any_ mutually supported version, not by acquiring a particular capability. A distinct code, `-32005`, lets a client disambiguate the two cases without inspecting the error payload, and carries the `requested`/`supported` shape that drives the retry. The code is modeled on `-32004` (Unsupported Protocol Version) from [SEP-2575](https://modelcontextprotocol.io/seps/2575-stateless-mcp); its data extends the same pattern to per-extension keys, since one request can fail negotiation for several extensions at once.

### The Protocol-Version Floor Is Advisory

A single minimum protocol version assumes every later protocol revision remains compatible with the extension. That assumption can fail: a future protocol revision could make a breaking change that invalidates the extension's behavior, and capturing this precisely would force a server to enumerate every protocol version it remains compatible with and to keep that list current as new revisions ship. That maintenance burden falls hardest on servers that are otherwise stable and unattended. Treating the floor as advisory client-side guidance keeps older, un-updated servers working: a server that never declares a floor, or whose floor predates a later breaking protocol change, is not summarily rejected. Clients carry the responsibility to check the floor and degrade, which is where the protocol already places graceful-degradation logic.

## Backward Compatibility

This proposal is additive to the extension framework and changes no wire behavior for implementations that do not adopt it.

- An implementation predating this convention advertises `{}`, or omits `version`/`versions`. A conforming peer **MUST** interpret an absent version as the extension's initial version, `1.0.0`. Such implementations remain fully interoperable and are never rejected on versioning grounds.
- A server that declares extension versions returns an explicit `-32005` error to a client requesting an unsupported major version, rather than a malformed response a client expecting a different major version cannot parse.
- This proposal does not supersede the backward-compatibility requirements of [SEP-2133](https://modelcontextprotocol.io/seps/2133-extensions#backward-compatibility). It interprets them: a breaking change between extension versions that is gated on the negotiation flow defined here does not require a new identifier, whereas a breaking change that cannot be so gated still does.
- The migration from the experimental `tasks` feature of the `2025-11-25` specification to the Tasks extension is governed by [SEP-2663 §Backward Compatibility](https://modelcontextprotocol.io/seps/2663-tasks-extension) and the [feature lifecycle](https://modelcontextprotocol.io/community/feature-lifecycle). This proposal does not redefine that transition and introduces no separate legacy identifier.

## Security Implications

- **Version metadata is untrusted input.** The `version`, `versions`, and `requires` fields are peer-supplied and **MUST** be validated as untrusted, consistent with [SEP-2133 §Security Implications](https://modelcontextprotocol.io/seps/2133-extensions#security-implications). A malformed or hostile value **MUST NOT** crash or hang a peer's negotiation.
- **No downgrade through an understated floor.** A server could understate `requires.protocolVersion` to coax a client into exercising an extension on an older protocol revision than it would otherwise accept. A client **MUST** treat the floor only as a lower bound below which it declines the extension, and **MUST NOT** treat a server's declared floor as a reason to downgrade an already-negotiated protocol version.
- **No new task or extension state surface.** This proposal adds only negotiation metadata and one error code. It introduces no new identifiers, methods, or result shapes, and therefore no new access-control boundary beyond those already defined by the extensions it versions. Security implications arising from behavioral differences between extension versions are owned by the individual extension.

## Open Questions

- **Scope graduation.** This proposal is written generically but is scoped to prove the convention on the Tasks extension first. Whether it should graduate into framework-wide guidance — the candidate answer to SEP-2133's deferred versioning and dependency questions for all data-plane extensions — is left open pending implementation experience on Tasks.
- **Inter-extension dependencies.** `requires.protocolVersion` covers an extension's dependency on the core protocol, but not one extension's dependency on another — the other half of what SEP-2133 leaves under _Not Specified_. This appears to need no new machinery. A request already carries each extension with its own version, the two negotiate independently, and the dependent extension's implementation enforces what it needs from the other; the Tasks-and-Events pairing [sketched above](#two-extensions-negotiate-independently) composes exactly this way, through an optional field and prose requirements rather than a declared dependency. A `requires.extensions` field would add only machine-readable validation for parties that do not implement the dependent extension, such as intermediaries — a benefit speculative enough to leave out of this trial.

## Reference Implementation

To be provided.
