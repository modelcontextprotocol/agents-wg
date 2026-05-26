# SEP-XXXX: Versioning and Compatibility for the Tasks Extension

- **Status**: Draft
- **Type**: Extensions Track
- **Created**: 2026-05-26
- **Author(s)**: Thierry Damiba (@thierrypdamiba)
- **Sponsor**: _(seeking sponsor)_
- **Extension Identifier**: `io.modelcontextprotocol/tasks`
- **Working Group**: Agents Working Group

## Abstract

This proposal defines how the [Tasks extension][sep-2663] expresses two compatibility
relationships that it currently leaves implicit: the minimum core protocol version its behavior
depends on, and its own version. It introduces no new negotiation mechanism. The **major**
component of the extension version is carried by the extension identifier, exactly as
[SEP-2133][sep-2133] already mandates for breaking changes; the **minor** and **patch**
components, and the minimum required spec version, are carried as two reserved keys
(`version`, `requires`) in the extension's settings object. The proposal is scoped to Tasks as
a trial, with the explicit intent that a convention proven here inform the framework-wide
guidance SEP-2133 §"Not Specified" defers, rather than that guidance being designed in the
abstract.

## Motivation

The Tasks extension is moving toward real SDK implementations, but two compatibility facts that
an implementation needs at negotiation time are currently undiscoverable, so both surface as
runtime failures instead.

1. **The implemented version is unobservable.** Two implementations that both advertise
   `io.modelcontextprotocol/tasks` cannot tell whether they implement the same revision of it.
   SEP-2663 explicitly anticipates additive growth — "This specification may be extended to
   support tasks over other request types in the future; implementations **SHOULD** be designed
   to accommodate additional request types" — but provides no way to advertise *which* additions
   a peer has made. A client that depends on a newer additive surface has no signal short of
   issuing a request and observing whether it is honored. This is the same trial-and-error trap
   the SEP-2663 redesign removed from the original handshake, reintroduced one layer up.

2. **The spec dependency is implicit.** Tasks behavior assumes base-protocol features introduced
   in recent revisions — server-request association ([SEP-2260][sep-2260]), multi round-trip
   requests ([SEP-2322][sep-2322]), and the stateless model ([SEP-2575][sep-2575]) — all of
   which land in the `2026-06-30` specification. An implementation that has negotiated an older
   `protocolVersion` can still advertise the extension and then fail at first use, because
   nothing lets it declare the floor its behavior requires. The mismatch is detectable in
   principle at negotiation, but the protocol gives it nowhere to be stated.

This is not hypothetical. The Agents WG's own survey of production agent-backed tools
([`mcp-agent-tools.md`][agent-tools]) documents that real servers already diverge on exactly the
axes Tasks grows along — mid-flight steering, cancellation, and `input_required` handling — and
[SEP-2669][sep-2669] is actively adding task steer/pause/resume. As Tasks accretes these additive
surfaces, an implementation needs a way to advertise *which* of them it supports; today it
cannot, so a client either assumes the lowest common denominator or learns by trial and error.

Neither gap is unique to Tasks, but Tasks feels both acutely and first. SEP-2133 deliberately
deferred extension versioning ("Extensions **SHOULD** be versioned, but exact versioning
approach is not specified here") and dependency declaration (§"Not Specified", items 1–2). This
proposal fills those two gaps for Tasks without pre-empting the broader question.

## Specification

The key words "MUST", "MUST NOT", "SHOULD", "SHOULD NOT", and "MAY" in this document are to be
interpreted as described in [BCP 14][bcp14].

### Relationship to the extension identifier

Per [SEP-2133 §Definition][sep-2133-def], a breaking change to an extension MUST be expressed as
a new extension identifier. This proposal does not alter that rule; it layers on top of it. The
**major** version of Tasks is carried by the identifier:

- `io.modelcontextprotocol/tasks` denotes major version `1`.
- A future breaking revision MUST use a new identifier — `io.modelcontextprotocol/tasks-v2`,
  denoting major version `2` — and is, for negotiation purposes, a distinct extension.

The identifier is authoritative for compatibility gating. The version metadata defined below
exists for legibility and for reasoning about additive surface; it MUST NOT be the basis on
which a peer is rejected.

### Extension version metadata

The settings object for the Tasks extension is defined as:

```typescript
/**
 * Settings object carried as the value of the
 * `io.modelcontextprotocol/tasks` entry in the `extensions` capability map.
 * All fields are OPTIONAL; an empty object {} remains a valid declaration of
 * support, identical in meaning to the SEP-2663 baseline.
 */
interface TasksExtensionSettings {
  /**
   * The full MAJOR.MINOR.PATCH version of the Tasks extension this peer
   * implements. The MAJOR component MUST equal the major version implied by
   * the extension identifier (1 for `io.modelcontextprotocol/tasks`). If
   * omitted, the peer MUST be treated as implementing MAJOR.0.0, where MAJOR
   * is the value implied by the identifier.
   */
  version?: string;

  /** Compatibility requirements this peer places on the session. */
  requires?: TasksRequirements;
}

interface TasksRequirements {
  /** Requirement on the negotiated core protocol version. */
  spec?: {
    /**
     * Minimum core protocol version this peer's Tasks behavior depends on,
     * in the identifier scheme the core specification uses (a YYYY-MM-DD
     * revision string today; a semantic version if SEP-1400 is adopted).
     */
    min: string;
  };
}
```

#### `version`

- A peer MAY include `version`. If present, its MAJOR component MUST equal the major implied by
  the identifier; a peer that receives a `version` whose MAJOR disagrees with the identifier
  MUST disregard the `version` field and treat the identifier as authoritative.
- A **minor** increment denotes additive, backward-compatible change (for example, a newly
  supported task-augmentable request type). A peer at a lower minor than its counterpart MUST
  remain interoperable; it simply does not exercise the newer surface.
- A **patch** increment denotes clarification or a non-breaking fix and MUST NOT affect
  interoperability.
- Omission MUST be treated as `MAJOR.0.0`. This preserves the meaning of the empty settings
  object `{}` that SEP-2663 implementations already advertise.

#### `requires.spec.min`

- A peer MAY declare `requires.spec.min`. The receiver compares it against the `protocolVersion`
  negotiated during the [initialization handshake][lifecycle] (or, under stateless operation,
  carried per-request per SEP-2663).
- If the negotiated `protocolVersion` is lower than a peer's own `requires.spec.min`, that peer
  MUST treat the Tasks extension as inactive for the session: it MUST NOT exercise Tasks
  behavior. Where it cannot service a request without Tasks, it MUST return error `-32003`
  (Missing Required Client Capability) per [SEP-2663][sep-2663-error] rather than failing
  opaquely.
- Omission means the peer makes no spec-version assumption beyond what the negotiated
  `protocolVersion` already guarantees.

### Compatibility evaluation

After negotiation, each side determines Tasks activation as follows. The Tasks extension is
**active** for the session if and only if all hold:

1. **Major agreement.** Both sides advertise the same `io.modelcontextprotocol/tasks`
   identifier. A differing identifier means the majors differ, and Tasks is inactive — silently,
   per [SEP-2133 §Graceful Degradation][sep-2133-degrade].
2. **Spec floor.** The negotiated `protocolVersion` satisfies each side's `requires.spec.min`
   (or the side declared none).

When active, the **effective minor** is the lower of the two advertised minors; each side MUST
confine itself to the additive surface available at that minor. The minor is never a rejection
criterion — see Rationale.

### Reservations

- The keys `version` and `requires` within the `io.modelcontextprotocol/tasks` settings object
  are reserved by this proposal. Future keys added to that settings object MUST NOT collide with
  them.

## Rationale

### Major in the identifier, minor and patch in metadata

SEP-2133 already makes the identifier the unit of breaking change, so the major version lives
there whether this proposal acts or not. Putting minor and patch — the components that are by
definition non-breaking — in the settings object keeps the one value that gates hard
compatibility (the major) in exactly one place, the identifier, while still letting peers reason
about additive surface.

The cost is that the major appears in two forms once a peer includes `version`: implied by the
identifier and stated in the string. We accept this and pin it with a MUST-agree rule (the
identifier wins) rather than carry a bare `MINOR.PATCH` string, because a bare string reads
ambiguously next to the identifier — `io.modelcontextprotocol/tasks` advertising `"2.0"` invites
a reader to think "version 2" — and tooling that surfaces "what version of Tasks is this" would
otherwise have to reconstruct the full version from two sources. An explicit, validated full
version is cheaper to reason about than an implicit one.

### Minor versions do not gate

If minor increments are genuinely additive, a check that rejects a peer on a minor difference
would reject interoperable implementations. Treating the minor as the floor of *available*
additive surface — never as grounds for refusal — is what lets "newer server, older client" just
work, and it directly answers the objection [raised on #1849][issue-1849] that enumerating minor
versions for negotiation is tedious and wrong. There is nothing to enumerate: a peer states the
one minor it implements, and the effective behavior is the intersection.

The cost is that this proposal gives a peer no way to *insist* on a minimum minor of its
counterpart. We judge that correct: a dependency strong enough to refuse a peer over is not
additive and therefore belongs at the major (identifier) boundary, not the minor.

### Dependency in the settings object, not a new field

SEP-2133 defines the per-extension settings object as the extension point and resists
replicating the capability structure elsewhere. Declaring the spec-version dependency inside it
keeps this proposal within the framework's existing shape and lets extensions that operate
outside the data plane — transport, auth — opt out simply by not using the block, as
[pja-ant noted][issue-1849] when arguing that one negotiation mechanism cannot fit every kind of
extension.

The cost is that `requires` is a per-extension convention rather than a framework guarantee:
another extension could choose a different key for the same purpose. We accept this for the
trial; convergence is exactly the framework-wide question this proposal feeds, not one it should
settle unilaterally.

### Silent inactivity by default, explicit error on demand

When a requirement is unmet, the default is silent inactivity, matching the graceful-degradation
contract every MCP capability already follows. A peer that genuinely *requires* Tasks is not
left guessing, though: it learns at first use through the `-32003` path SEP-2663 already defines,
with the missing capability named in `data.requiredCapabilities`.

The cost is that a hard requirement surfaces one round-trip after negotiation rather than at
negotiation itself. We accept this because the alternative — a negotiation-time rejection path
specific to extensions — is exactly the broader mechanism SEP-2133 declined to specify, and
reusing the existing `-32003` signal keeps this proposal additive.

## Backward Compatibility

This proposal is additive to the Tasks extension and changes no wire behavior.

- An implementation that predates this convention advertises the settings object `{}` (or omits
  `version`/`requires`). A conforming peer MUST interpret absent `version` as `MAJOR.0.0` and
  absent `requires.spec.min` as "no floor." This is the status quo; such implementations remain
  fully interoperable and are never rejected on versioning grounds.
- A peer that receives a `version` string whose MAJOR disagrees with the identifier MUST
  disregard `version` (identifier authoritative) and MUST NOT terminate the session for this
  reason alone.
- The migration from the experimental `tasks` feature of spec revision `2025-11-25` to the
  extension is governed by [SEP-2663 §Backward Compatibility][sep-2663] and the core feature
  lifecycle of [SEP-2596][sep-2596]. This proposal does not redefine it and introduces no
  `tasks_legacy` identifier; the experimental feature's removal and the extension's identifier
  together already express the transition.

## Security Implications

- **Version and requirement metadata are untrusted.** `version` and `requires` are peer-supplied
  fields and MUST be validated as untrusted input, per [SEP-2133 §Security
  Implications][sep-2133-sec]. A malformed or hostile value MUST NOT crash or hang a peer's
  negotiation.
- **No downgrade via understated floor.** A peer could understate `requires.spec.min` to coax a
  counterpart into activating Tasks on an older protocol revision than it would otherwise accept.
  An implementation MUST evaluate `requires` only as a gate on *its own* activation, and MUST NOT
  treat a peer's `requires` as a reason to downgrade an already-negotiated `protocolVersion`.
- **No new task-state surface.** This proposal adds only negotiation metadata; it introduces no
  new task identifiers, methods, or result shapes, and therefore no new task-access trust
  boundary beyond those in [SEP-2663 §Security Implications][sep-2663].

## Reference Implementation

To be provided in [experimental-ext-tasks][exp-tasks] as a settings-object schema plus the
activation check in the Compatibility evaluation section. A reference implementation is required
before this SEP can advance to review, per [SEP-2133 §Creation][sep-2133].

## Open Questions

1. **Scope graduation.** Should this remain Tasks-local, or be framed as the candidate answer to
   SEP-2133 §"Not Specified" items 1–2 for all data-plane extensions? This proposal assumes
   Tasks-local-first and feeds, rather than settles, the broader question.
2. **Inter-extension dependencies.** A `requires.extensions[]` array (one extension depending on
   another at a minimum version) is the obvious sibling to `requires.spec`. It is omitted here to
   keep the trial narrow; it is sketched in [#1849][issue-1849].
3. **Relationship to #1848.** [#1848][issue-1848] proposes encoding the version in the identifier
   path (`io.mcp/tasks/2.0`) rather than a suffix plus metadata. If that lands, the `version`
   field here becomes redundant and SHOULD be dropped in favor of the identifier form. The two
   are reconcilable; this proposal should track #1848, not pre-empt it. **These two issues and
   this proposal do not appear to be cross-referenced today; aligning them is itself a goal of
   filing this.**

<!-- References -->
[sep-2133]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md
[sep-2133-def]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#definition
[sep-2133-degrade]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#graceful-degradation
[sep-2133-sec]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2133-extensions.md#security-implications
[sep-2663]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2663-tasks-extension.md
[sep-2663-error]: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2756
[sep-2596]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2596-spec-feature-lifecycle-and-deprecation.md
[sep-1400]: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1400
[sep-2260]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2260-Require-Server-requests-to-be-associated-with-Client-requests.md
[sep-2322]: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/seps/2322-MRTR.md
[sep-2575]: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2575
[issue-1848]: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1848
[issue-1849]: https://github.com/modelcontextprotocol/modelcontextprotocol/issues/1849
[exp-tasks]: https://github.com/modelcontextprotocol/experimental-ext-tasks
[agent-tools]: https://github.com/modelcontextprotocol/agents-wg/blob/main/docs/research/mcp-agent-tools.md
[sep-2669]: https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2669
[lifecycle]: https://modelcontextprotocol.io/specification/2025-06-18/basic/lifecycle
[bcp14]: https://www.rfc-editor.org/info/bcp14
