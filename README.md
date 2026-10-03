# 🌍 KenyaA2A — East African Civic Agent (A2A)

> [Agent-to-Agent (A2A) protocol](https://github.com/a2aproject/A2A) server for East African civic data. Any A2A-compatible AI agent — Claude, GPT, Gemini, or your own — can discover and query Kenya's parliament records, county budgets, drought status, and constitutional rights.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol%201.0-blue)](https://github.com/a2aproject/A2A)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)

## Why A2A + Kenya

The [A2A protocol](https://github.com/a2aproject/A2A) (Linux Foundation, Apache 2.0) is the emerging standard for agent-to-agent communication — complementing MCP (agent-to-tool). It serves East African civic data over A2A, making Kenya's public information queryable by any AI agent in any framework.

**A2A complements [mpesa-mcp](https://github.com/gabrielmahia/mpesa-mcp):**
- `mpesa-mcp` = agent-to-tool (MCP) — gives agents M-Pesa and SMS tools
- `kenya-a2a` = agent-to-agent (A2A) — makes Kenya civic data agents discoverable by other agents

## Agent Card

The agent describes itself at `/.well-known/agent-card.json` (A2A 1.0). The complete card is in `.well-known/agent-card.json`; it is **generated from the code** by `scripts/export_card.py`, and a test fails if the two drift. Abbreviated:

```json
{
  "name": "KenyaA2A",
  "version": "0.1.0",
  "supportedInterfaces": [
    {
      "protocolBinding": "JSONRPC",
      "protocolVersion": "1.0",
      "url": "http://localhost:8000/"
    }
  ],
  "skills": [
    {
      "id": "budget_query",
      "name": "County Budget Query",
      "tags": [
        "budget",
        "counties",
        "public-finance",
        "kenya"
      ]
    },
    {
      "id": "parliament_query",
      "name": "Parliament Records Query",
      "tags": [
        "parliament",
        "bills",
        "mps",
        "kenya"
      ]
    },
    {
      "id": "drought_status",
      "name": "Drought Status (DEMO, synthetic)",
      "tags": [
        "drought",
        "ndma",
        "climate",
        "kenya"
      ]
    },
    {
      "id": "rights_query",
      "name": "Constitutional Rights (EN/SW)",
      "tags": [
        "constitution",
        "rights",
        "kiswahili",
        "kenya"
      ]
    }
  ]
}
```

## Status

Runs locally on `a2a-sdk>=1.0,<2.0` (A2A protocol 1.0, JSON-RPC). **No public instance is deployed** (an earlier hosted instance no longer exists).

- **Official compatibility kit** (`a2a-tck`, JSON-RPC): MUST 54 passed / 5 failed, SHOULD 4 / 0, MAY 2 / 1. The 5 MUST failures appear to be the TCK's own scripted fixture behaviour; details, command and limits in [`docs/TCK.md`](docs/TCK.md).
- **What works end to end** (tested through the SDK's own client): the constitutional-rights skill (a small set of articles, English and Kiswahili). **Budget and parliament** need data files (`civic_data/`) that are not in this repository; they say so plainly instead of returning anything. **Drought returns synthetic demo values derived from the county name, not NDMA data**, and is labelled as such in the card and in every answer.
- **Not covered:** streaming, push notifications, task lifecycle, authentication or authorization (the card declares none), REST and gRPC transports.

## Quickstart

```bash
# from source (the package is not published to PyPI):
git clone https://github.com/gabrielmahia/kenya-a2a
cd kenya-a2a
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Agent card:** `GET http://localhost:8000/.well-known/agent-card.json`

**Send a task:**
```bash
curl -X POST http://localhost:8000/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tasks/send",
    "id": "1",
    "params": {
      "id": "task-001",
      "message": {
        "role": "user",
        "parts": [{"type": "text", "text": "What is the drought status in Turkana County?"}]
      }
    }
  }'
```

## Skills

| Skill ID | Description | Example query |
|----------|-------------|---------------|
| `budget_query` | County budget absorption FY 2022/23 (needs data files not in this repository) | *"Which counties spent less than 50% of their development budget?"* |
| `parliament_query` | MP records, bills, CDF utilisation (needs data files not in this repository) | *"How many bills were enacted in the 13th Parliament?"* |
| `drought_status` | **DEMO: synthetic values, not NDMA data** | *"What is the drought status in Turkana County?"* |
| `rights_query` | Constitution of Kenya 2010, in English and Kiswahili | *"What does the Constitution say about land rights in Kiswahili?"* |

## A2A + MCP ecosystem

```
Your AI Agent
    ├── MCP tools (via mpesa-mcp)
    │     ├── mpesa_stk_push
    │     ├── sms_send
    │     └── airtime_send
    │
    └── A2A agents (via kenya-a2a)
          ├── budget_query
          ├── parliament_query
          ├── drought_status
          └── rights_query
```

## Data

Built on [Kenya Civic Datasets](https://kaggle.com/datasets/gmahia/kenya-civic-data-parliament-budget-saccos):
- DOI: `10.34740/kaggle/dsv/15473045` (Kaggle)
- DOI: `10.57967/hf/8223` (HuggingFace)

## Related

- [mpesa-mcp](https://github.com/gabrielmahia/mpesa-mcp) — M-Pesa + AT MCP server (3,000+ PyPI downloads)
- [kenya-rag](https://github.com/gabrielmahia/kenya-rag) — LlamaIndex RAG over Kenya civic data
- [hesabu-agent](https://github.com/gabrielmahia/hesabu-agent) — CrewAI budget analysis agent
- [gabrielmahia.github.io](https://gabrielmahia.github.io) — Full portfolio

## IP & Collaboration

© 2026 Gabriel Mahia · [contact@aikungfu.dev](mailto:contact@aikungfu.dev)
License: MIT
Protocol: A2A (Linux Foundation / Apache 2.0)
Not affiliated with Parliament of Kenya, Controller of Budget, or NDMA.
