"""Agent Card and behaviour tests for the A2A 1.0 port. No network and no API key: the server is driven in memory with the SDK's own
client over an ASGI transport, so every behaviour test is a real protocol round trip."""
import asyncio
import importlib.metadata
import json
import os
import pathlib
import re

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def _ask(message: str, data_dir=None) -> str:
    """Send one message through the SDK client to the in-memory server; return the response as JSON text."""
    import httpx
    from a2a.client import ClientConfig, create_client
    from a2a.helpers import new_text_message
    from a2a.types import Role, SendMessageRequest
    from google.protobuf.json_format import MessageToDict

    import server

    if data_dir is not None:
        server.DATA_DIR = data_dir

    async def go():
        app = server.create_app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://localhost:8000") as http:
            client = await create_client(agent=server.build_agent_card(), client_config=ClientConfig(streaming=False, httpx_client=http))
            request = SendMessageRequest(message=new_text_message(message, role=Role.ROLE_USER))
            return [MessageToDict(chunk) async for chunk in client.send_message(request)]

    # A broken reply must FAIL the test, not hang it (an invalid event once left the client waiting forever).
    return json.dumps(asyncio.run(asyncio.wait_for(go(), timeout=10)))


def test_supported_sdk_range():
    major = int(importlib.metadata.version("a2a-sdk").split(".")[0])
    assert major == 1, "kenya-a2a targets a2a-sdk >=1.0,<2.0 (A2A protocol 1.0); see requirements.txt"


def test_card_builds_and_every_skill_has_tags():
    import server

    card = server.build_agent_card()
    assert card.name == "KenyaA2A" and card.skills
    assert all(list(s.tags) for s in card.skills), "A2A requires non-empty tags on every skill"


def test_card_declares_a_1_0_jsonrpc_interface():
    import server

    ifaces = list(server.build_agent_card().supported_interfaces)
    assert [(i.protocol_binding, i.protocol_version) for i in ifaces] == [("JSONRPC", "1.0")]


def test_runtime_card_is_served_at_the_well_known_path_and_parses_strictly():
    from a2a.types import AgentCard
    from google.protobuf.json_format import ParseDict
    from starlette.testclient import TestClient

    import server

    r = TestClient(server.create_app()).get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = ParseDict(r.json(), AgentCard())          # raises on unknown or malformed fields
    assert card.name == "KenyaA2A"


def test_static_card_matches_the_code():
    from scripts.export_card import render

    assert (ROOT / ".well-known" / "agent-card.json").read_text() == render(), "run: python scripts/export_card.py"


def test_descriptions_make_no_superlative_claims():
    import server

    card = server.build_agent_card()
    texts = [card.description] + [s.description for s in card.skills]
    assert not [t for t in texts if re.search(r"\b(first|only|best|leading|unique|pioneer)", t, re.IGNORECASE)], "describe what it does, not what it was first to do"


@pytest.mark.parametrize("message,skill", [
    ("What is the drought status in Turkana County?", "drought"),
    ("budget absorption in Nakuru County", "budget"),
    ("county development fund", "budget"),
    ("Tell me about MPs and bills", "parliament"),
    ("What does the constitution say about land rights?", "rights"),
    ("this is an important simple temperature question", "help"),
    ("hello", "help"),
])
def test_routing_prefers_specific_skills_and_matches_whole_words(message, skill):
    import server

    assert server.route(message) == skill


def test_end_to_end_the_rights_skill_answers_over_the_protocol():
    assert "Article 40" in _ask("What does the constitution say about land rights?")


def test_swahili_is_chosen_only_by_whole_words():
    # 'land' exists in BOTH languages, so a wrong language choice changes the visible header.
    assert "[English" in _ask("please answer: what is the right to land?")
    assert "[Kiswahili" in _ask("haki ya land kwa Kiswahili")
    assert "[Kiswahili" in _ask("land rights in sw")


def test_drought_output_is_labelled_synthetic_everywhere():
    import server

    data = server.get_drought_status("Turkana")
    assert data["is_synthetic"] is True and "NOT NDMA" in data["source"]
    assert "synthetic" in _ask("drought status in Turkana County").lower()


def test_missing_data_is_reported_without_a_source_attribution(tmp_path):
    import server

    old = server.DATA_DIR
    try:
        for msg in ("budget absorption in Nakuru", "list the MPs and bills"):
            out = _ask(msg, data_dir=tmp_path)
            assert "not included" in out and "Source:" not in out
    finally:
        server.DATA_DIR = old


def test_card_discloses_demo_and_missing_data():
    import server

    card = server.build_agent_card()
    skills = {s.id: s for s in card.skills}
    assert "DEMO" in skills["drought_status"].name and "not NDMA" in skills["drought_status"].description
    assert "data files" in skills["budget_query"].description and "data files" in skills["parliament_query"].description
    assert "NDMA drought status" not in card.description and "demo" in card.description.lower()


def test_every_reply_carries_a_context_id():
    # Official TCK requirement CORE-MULTI-001a: a generated contextId must be included in the response.
    out = json.loads(_ask("What does the constitution say about land rights?"))
    message = out[0].get("message") or out[0]
    assert message.get("contextId"), out


def test_agent_card_is_served_with_a_cache_control_max_age():
    # Official TCK SHOULD-level requirement (agent-card caching): Cache-Control present, with max-age.
    from starlette.testclient import TestClient

    import server

    header = TestClient(server.create_app()).get("/.well-known/agent-card.json").headers.get("cache-control", "")
    assert "max-age=" in header, header
