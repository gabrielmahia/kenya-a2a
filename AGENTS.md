# AGENTS.md — KenyaA2A

A2A-protocol civic data agent.

## Main files
- `server.py` — FastAPI A2A server + all skill handlers
- `.well-known/agent.json` — static agent card for discovery
- `civic_data/` — Kenya civic CSVs (not in version control)

## Skills
budget_query, parliament_query, drought_status, rights_query

## Rules
- Never fabricate civic data
- Sandbox mode on by default
- Cite sources in every response
