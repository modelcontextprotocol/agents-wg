# Approaches Being Explored

> These are not mutually exclusive solutions.

## Design Principles

- **Inference ownership is the central axis.** Where inference lives and where the agent loop runs — server, client, or split — drives every other design choice.
- **Separate definition from runtime.** The spec-time artifact (what an agent *is*) and the runtime artifact (what an agent *does*, i.e. a task or task graph) are distinct.

All outlined approaches using MCP Tasks are assumed to be based on some form of the revised tasks specification ([SEP-2557](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2557)) under consideration for the `2026-06-30` specification.

## Who Owns Inference and the Agent Loop?

The approaches below span a spectrum. At one end, the server runs inference and the agent loop. At the other, the server publishes an agent definition and the client runs the loop on its own inference. The cooperative middle has the server orchestrating while sampling delegates inference to the client.

Different deployment environments will land different ways on this decision. Many server authors are unlikely to want to own the agent execution end-to-end. Consider the GitHub MCP server: It is stateless, offered at no cost to its users, and serves many connections simultaneously. Hosting an agent for every user would come at considerable additional expense and operational complexity. In principle, it could leverage sampling to offload inference to the client, but this choice would represent a significant increase in traffic as each turn requires a separate server-to-client request. Approaches requiring server-owned inference tend to be simpler, but will likely see lower public adoption - however, private enterprise deployments or servers that charge the user for invocations may prefer this approach. It is possible that approaches that only require a server-owned agent loop could be realistic at scale, but require that the client supports sampling (few clients support sampling today, and [SEP-2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577) deprecates it and is being considered by Core Maintainers for the `2026-06-30` specification release).

## 1. Agent Hosted Behind a Tool Call

The server exposes an agent as a tool and runs the full loop internally. The client sees only the final tool result, potentially via a long-running task. As there are no client responsibilities in this approach, there is no agent definition, either (the definition is arguably the tool itself). Details such as the model choice, context management, and rate-limiting are encapsulated entirely within the server, eliminating client variance in agent construction present in several alternative approaches.

This works today with no protocol changes and is the baseline every other approach is compared against. It is the simplest approach from a protocol standpoint, but forces all associated costs on the server provider and leaves the client with no visibility into the agent's internal work. Some frameworks such as `fast-agent` [support this](https://fast-agent.ai/mcp/mcp-server/) out of the box today.

Under this approach, agent work could be represented by a [task](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks); we assume no feature additions to tasks under this approach (unlike *Agent as a Task Graph*).

All protocol-level approaches are expected to offer some sort of advantage over this baseline.

## 2. Agent-to-Agent (A2A) Protocol

Rather than using MCP at all for agent interop, the server exposes an agent over [A2A](https://a2a-protocol.org) and the client uses it. Potentially follows the same pattern as Gemini CLI's [Remote Subagents](https://geminicli.com/docs/core/remote-agents/). Functionally similar to an agent-as-tool approach, but with the benefit of having access to the message history and artifacts directly from the [A2A task resource](https://a2a-protocol.org/latest/specification/#411-task). The agent card becomes the agent definition under this approach. Like agents-as-tools, this works today with no protocol changes (MCP isn't in the picture at all), but this also forces all associated costs on the server provider and leaves the client with no visibility into the agent's internal work.

## 3. Agent Definition Exposed by Server; Client Runs the Loop

The server exposes a declarative description of an agent — system prompt, tools, model hints, subagent usage patterns — and the client instantiates it in its own agent loop and inference. This agent definition could include references to the server's existing tools, resources, and prompts — potentially using MCP primitives directly when defining the agent itself. Many existing coding agents already define sub-agents as Markdown documents with a system prompt and allowed tools, and MCP primitives could map to something that looks very similar (e.g. using an MCP Prompt as the declared system prompt).

Projects such as the [Agent Definition Protocol](https://github.com/casabre/agent-definition-protocol) and [Agent Definition Language](https://github.com/nextmoca/adl) expand this concept much further than most coding agents offer and aim to standardize it across the ecosystem, and may be worth considering as prior art or external specifications to leverage directly. This would follow the pattern of external specification integration being used by [SEP-2640: Skills Extension](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2640), which formalizes a convention over [resources](https://modelcontextprotocol.io/specification/2025-11-25/server/resources) for integrating with [Agent Skills](https://agentskills.io/) rather than introducing a new primitive.

Open questions:

- How granular should agent definitions be (prompt-only vs. prompt + tools + model hints + compaction strategy + subagent policy)?
- How much of the agent definition is the client obligated to honor? Does the protocol only expect best-effort compliance, or does it impose strict handling requirements?
- Should clients executing agents include context from the caller's message history (similar to sampling's [includeContext](https://modelcontextprotocol.io/specification/2025-06-18/schema#createmessagerequest))?

This would likely introduce a protocol extension to formalize this concept and define the format and behavior requirements tied to the agent definition itself.

## 4. Sampling with Tools

The server exposes an agent as a tool and owns the agent loop, but the client performs inference via [sampling-with-tools](https://modelcontextprotocol.io/specification/2025-11-25/client/sampling#sampling-with-tools).

This would require no protocol changes, but sampling support is [limited](https://modelcontextprotocol.io/clients) across the ecosystem, and support for sampling-with-tools is an unknown subset of that. Sampling is also a stateless completion request and cannot accept mid-loop messages from the client's main agent, so inter-agent messaging must happen elsewhere, and we need to decide if agents should be able to message each other directly or if all messages need to route through the main agent (see *Caller-directed messaging*). Each agent turn requires a separate request to the client, so a server that adopts this approach will see a significant increase in traffic (at least one additional request per tool call).

Furthermore, [SEP-2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577) would deprecate sampling, and is being considered by the Core Maintainers for inclusion in the `2026-06-30` specification release. Note that sampling is being potentially-deprecated because of low adoption and implementation complexity (human-in-the-loop, model selection, security concerns), which could make this approach difficult to implement regardless of if SEP-2577 is approved.

## 5. Agent as a Task Graph

**Proposal:** [SEP-2268: Subtasks](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2268)

An agent invocation would be an instance of a non-deterministic [task](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks). Tasks would be extended to support sub-structure (subtask tree or DAG) and agents fall out of that execution model — the distinction between "agent" and "task" reduces to runtime non-determinism, which is already an out-of-scope concern for the spec. Each subtask would have its own result, allowing the caller to introspect work (note that SEP-2268 currently requires subtasks to share a result shape with their parent). Elicitation and sampling requests raised by a subtask propagate to the client directly.

Tree-shaped tasks are likely too limiting, but a DAG is harder to represent and scale. Task semantics currently assume one result per task, so a graph needs either no-result tasks or per-subtask results that can somehow be chained together.

Possibly benefits from ideas from the Triggers & Events WG (see [notes](https://github.com/modelcontextprotocol/experimental-ext-triggers-events/pull/1)) and/or adopting a similar approach to [A2A tasks](https://a2a-protocol.org/latest/specification/#411-task) as alternatives for inspecting a remote agent's in-flight work.

Open questions:

- Are subtasks **visibility-only** (exposing work that was happening anyway, deferrable) or **load-bearing** (client participates via sampling, elicitation, cancellation, and must precede agent work)?

## 6. Distinct Agent and Task Primitives

Variant of *Agent Definition Exposed by Server*/*Agent as a Task Graph* where agents and tasks explicitly stay separate. A task is a representation of an agent's work (budget, input/output, start/end state). The agent itself is the executor of the work (tools, loop policy, sub-agent roster, context-sharing rules). A server-side planner — possibly itself an agent if desired by the server implementor — turns the input into a task graph, selects agents, and orchestrates. Subagents could be parallel processes (isolated context) or threads (shared session log). May require *Caller-directed messaging* for orchestration.

This would introduce a formal "agent" primitive as a protocol concept.

## Additional Considerations

### Caller-directed messaging

Sampling and elicitation do not necessarily cover everything subagents need. Elicitation targets the user, and sampling is both potentially being deprecated (see [SEP-2577](https://github.com/modelcontextprotocol/modelcontextprotocol/pull/2577)) and is a stateless operation that cannot receive mid-loop messages from the calling agent. There is currently no primitive that enables generic inter-agent messaging. Current workarounds would require the subagent to exit its loop so the parent can send a follow-up message.

A caller-directed agent messaging primitive — parallel to sampling and elicitation — would benefit most approaches above. This could follow a similar pattern to how [MCP Apps](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx#mcp-apps-specific-messages) multi-turn UI interactions work.
