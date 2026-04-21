# 🌍 KenyaA2A — East African Civic Agent (A2A)

> The first [Agent-to-Agent (A2A) protocol](https://github.com/a2aproject/A2A) server for East African civic data. Any A2A-compatible AI agent — Claude, GPT, Gemini, or your own — can discover and query Kenya's parliament records, county budgets, drought status, and constitutional rights.

[![License: CC BY-NC-ND 4.0](https://img.shields.io/badge/License-CC%20BY--NC--ND%204.0-lightgrey.svg)](LICENSE)
[![A2A Protocol](https://img.shields.io/badge/A2A-Protocol%200.3-blue)](https://github.com/a2aproject/A2A)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-green)](https://modelcontextprotocol.io)
[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)

## Why A2A + Kenya

The [A2A protocol](https://github.com/a2aproject/A2A) (Linux Foundation, Apache 2.0) is the emerging standard for agent-to-agent communication — complementing MCP (agent-to-tool). This is the first A2A implementation serving East African civic data, making Kenya's public information queryable by any AI agent in any framework.

**A2A complements [mpesa-mcp](https://github.com/gabrielmahia/mpesa-mcp):**
- `mpesa-mcp` = agent-to-tool (MCP) — gives agents M-Pesa and SMS tools
- `kenya-a2a` = agent-to-agent (A2A) — makes Kenya civic data agents discoverable by other agents

## Agent Card

The agent self-describes at `/.well-known/agent.json`:

```json
{
  "name": "KenyaA2A",
  "description": "East African civic data agent — parliament, budgets, drought, rights",
  "url": "https://kenya-a2a.onrender.com",
  "version": "0.1.0",
  "skills": [
    {"id": "budget_query", "name": "County Budget Query"},
    {"id": "parliament_query", "name": "Parliament Records Query"},
    {"id": "drought_status", "name": "NDMA Drought Status"},
    {"id": "rights_query", "name": "Constitutional Rights (EN/SW)"}
  ]
}
```

## Quickstart

```bash
pip install kenya-a2a
# or from source:
git clone https://github.com/gabrielmahia/kenya-a2a
cd kenya-a2a
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

**Agent card:** `GET http://localhost:8000/.well-known/agent.json`

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
| `budget_query` | County budget absorption FY 2022/23 | *"Which counties spent less than 50% of their development budget?"* |
| `parliament_query` | MP records, bills, CDF utilisation | *"How many bills were enacted in the 13th Parliament?"* |
| `drought_status` | NDMA drought phase for any county | *"Is Marsabit County in drought emergency?"* |
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
License: CC BY-NC-ND 4.0
Protocol: A2A (Linux Foundation / Apache 2.0)
Not affiliated with Parliament of Kenya, Controller of Budget, or NDMA.
