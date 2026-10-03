# Official A2A TCK results (JSON-RPC, 2026-10-03)

**What was run:** `a2aproject/a2a-tck` at commit `263b9cf` against this server on `a2a-sdk` 1.2.1 (A2A protocol 1.0), JSON-RPC transport only (the only interface the card declares), levels `must`, `should`, `may`. Raw machine-readable report: `tck-compatibility-2026-10-03.json`.

```bash
# terminal 1
ANTHROPIC_API_KEY=unused A2A_HOST_URL=http://localhost:9997 PORT=9997 python server.py
# terminal 2 (in a checkout of a2a-tck, after `uv venv && uv pip install -e .`)
./run_tck.py --sut-host http://localhost:9997 --transport jsonrpc --level must   # then should, may
```
(The server must stay running for the whole TCK run; if it is not reachable every fixture errors with "Connection refused", which says nothing about the server.)

| Level | Passed | Failed | Skipped |
|---|---|---|---|
| MUST | 54 | 5 | 176 |
| SHOULD | 4 | 0 | 16 |
| MAY | 2 | 1 | 7 |

## What was fixed because the TCK exposed it
- `CORE-MULTI-001a` (MUST): replies carried no `contextId`. Fixed: every reply carries the request context's id (test: `test_every_reply_carries_a_context_id`).
- Agent-card caching (SHOULD): no `Cache-Control`. Fixed: `public, max-age=3600` (test: `test_agent_card_is_served_with_a_cache_control_max_age`).

## What still fails, and our reading of why (an interpretation, not a statement by the TCK)
- **5 MUST failures** (`test_task_has_text_artifact`, `..._file_artifact`, `..._file_url_artifact`, `..._data_artifact`, `test_returns_message_with_text_part`): they fail with "Response contains no artifacts" or expect the exact text `Direct message response`. In the TCK source, that text and the artifact outputs are produced by its own reference server (`sut/a2a-python/sut_agent.py`) in response to scripted inputs defined in `scenarios/core_operations.feature`. A general-purpose agent has no reason to answer those inputs that way, so we have **not** changed the product to pass them. If the A2A maintainers regard any of these as requirements for every server, that is a question for them, not something this repository can settle.
- **1 MAY failure**: `Last-Modified` on the card. Optional.

## Upstream corroboration (added 2026-10-03; these are open issues by other reporters, not maintainer rulings)
- **The 5 MUST failures:** [a2a-tck#229](https://github.com/a2aproject/a2a-tck/issues/229), "Add applicability for prompt-dependent artifact/message scenarios", reports the *same five tests* failing against an unrelated, conformant narrow A2A 1.0 agent, for the same reason: the tests send the generic text `TCK artifact test` and encode the requested scenario only in the `messageId` prefix (`artifact-text`, `artifact-file`, `artifact-file-url`, `artifact-data`, `message-response`). The TCK's own reference server routes on those prefixes. So the question "do these apply to every server?" is already open upstream, and there is no need for us to ask it separately.
- **The 1 MAY failure:** [a2a-tck#236](https://github.com/a2aproject/a2a-tck/issues/236) reports that `CARD-CACHE-003` (`Last-Modified`) is a MAY-level requirement whose test nonetheless hard-fails when the header is absent. That is a TCK classification bug, not a defect here.
- Both issues were open when checked (2026-10-03). Until maintainers respond, "the failures are fixture artifacts" remains a well-supported reading, not an established fact.

## What this does and does not show
Shows: the server speaks A2A 1.0 over JSON-RPC well enough to pass 54 of the 59 MUST tests that ran, all executed SHOULD tests, and serves a card that parses strictly.
Does **not** show: streaming, push notifications, task lifecycle, the REST and gRPC transports (not declared, so skipped), authentication or authorization (the card declares none), identity verification, or that any skill returns real data (drought is synthetic; budget and parliament data are absent). 176 MUST-level tests were skipped because the corresponding capabilities are not declared.
