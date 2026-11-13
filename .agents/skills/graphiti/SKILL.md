---
name: graphiti
description: "Retrieve project decisions and their temporal history with Graphiti MCP, or record an authorized durable episode. Use for graphiti, memory facts, episodes and decision history."
---

# Graphiti MCP

Use Graphiti for durable decisions, their rationale and changes over time.
Documentation and code graphs remain the sources for current implementation.

## Workflow

1. Read the [canonical rule](../../../.cursor/rules/mcp/graphiti.mdc) and
   [server document](docs/mcp/graphiti.md) for arguments, storage and history.
2. Resolve the current project's `GRAPHITI_GROUP_ID` from its configuration
   without exposing secret values. Call `get_status` before using the graph.
3. Search `search_memory_facts` with `group_ids` restricted to that project.
   Use `search_nodes` for entities and `get_episodes` for provenance and dates.
4. For an authorized durable record, search for duplicates first, then call
   `add_memory` with a short episode, the explicit `group_id` and its source.
   Supply `reference_time` when the event occurred in the past.
5. Retain the returned episode UUID and use `get_episode_entities` to inspect
   extraction. Recording is asynchronous; an accepted episode is not proof that
   extraction or subsequent search has completed.
6. Report facts with provenance and dates, distinguishing current and superseded
   decisions. Report queued or unavailable extraction without inventing facts.

## Isolation And Safety

- Use one configured `group_id` per project for all reads and writes; never use
  `main`, an empty group or another project's graph.
- Do not record secrets, tokens or customer personal data.
- `delete_episode`, `delete_entity_edge` and `clear_graph` require explicit user
  authorization and the exact project group. Do not clear data to fix a search.
- Keep the unauthenticated endpoint local. Do not publish it to an external network.
- If the service is unavailable, report the limitation and consult project
  documents; an empty search alone does not establish that no decision exists.
