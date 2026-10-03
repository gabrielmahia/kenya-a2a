"""Agent Card tests. Added because CI had never run a test for this repository (there was no tests/ directory), and the
server could not import on any allowed SDK: an unused import of a name that does not exist, plus skills missing the
schema-required `tags`. These tests need no network and no API key."""
import importlib.metadata
import json
import os
import pathlib
import re

import pytest

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")
ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_supported_sdk_range():
    major = int(importlib.metadata.version("a2a-sdk").split(".")[0])
    assert major < 1, "kenya-a2a supports a2a-sdk >=0.3.26,<1.0 (see requirements.txt); 1.x removed a2a.server.apps and made AgentCard a protobuf type"


def test_card_builds_and_every_skill_has_tags():
    import server

    card = server.build_agent_card()
    assert card.name == "KenyaA2A" and card.skills
    assert all(s.tags for s in card.skills), "A2A requires non-empty tags on every skill"


def test_runtime_card_is_served_at_the_current_well_known_path_and_validates():
    from a2a.types import AgentCard
    from starlette.testclient import TestClient

    import server

    r = TestClient(server.create_app()).get("/.well-known/agent-card.json")
    assert r.status_code == 200
    card = AgentCard.model_validate(r.json())
    assert card.protocol_version.startswith("0.3")


def test_deprecated_path_is_still_served_by_the_sdk():
    from starlette.testclient import TestClient

    import server

    assert TestClient(server.create_app()).get("/.well-known/agent.json").status_code == 200


@pytest.mark.parametrize("name", ["agent-card.json", "agent.json"])
def test_static_cards_match_the_code(name):
    from scripts.export_card import render

    assert (ROOT / ".well-known" / name).read_text() == render(), "run: python scripts/export_card.py"


def test_descriptions_make_no_superlative_claims():
    import server

    card = server.build_agent_card()
    texts = [card.description] + [s.description for s in card.skills]
    assert not [t for t in texts if re.search(r"\b(first|only|best|leading|unique|pioneer)", t, re.IGNORECASE)], "describe what it does, not what it was first to do"


# ── behaviour added after an independent review found the card over-claimed ───────────────────────────────────────────
import asyncio


def _ask(message: str, data_dir=None) -> str:
    """Run the real executor on one message (no network) and return the response text."""
    import server

    events: list = []

    class Ctx:
        def get_user_input(self):
            return message

    class Queue:
        async def enqueue_event(self, e):
            events.append(e)

    if data_dir is not None:
        server.DATA_DIR = data_dir
    asyncio.run(server.KenyaCivicAgentExecutor().execute(Ctx(), Queue()))
    part = events[0].parts[0]
    return getattr(part, "root", part).text


@pytest.mark.parametrize("message,skill", [
    ("What is the drought status in Turkana County?", "drought"),   # the repo's own example; the old order sent it to budget
    ("budget absorption in Nakuru County", "budget"),
    ("county development fund", "budget"),
    ("Tell me about MPs and bills", "parliament"),
    ("What does the constitution say about land rights?", "rights"),
    ("this is an important simple temperature question", "help"),     # 'mp' inside words must not route to parliament
    ("hello", "help"),
])
def test_routing_prefers_specific_skills_and_matches_whole_words(message, skill):
    import server

    assert server.route(message) == skill


def test_swahili_is_chosen_only_by_whole_words():
    # 'land' exists in BOTH languages, so a wrong language choice changes the answer's header (a topic missing from the Swahili
    # table would return a not-found message that hides the mistake: the first version of this test could not fail).
    assert "[English" in _ask("please answer: what is the right to land?")        # 'sw' inside 'answer' must not switch language
    assert "[Kiswahili" in _ask("haki ya land kwa Kiswahili")
    assert "[Kiswahili" in _ask("land rights in sw")                              # 'sw' as a whole word does select Swahili


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


def test_end_to_end_message_send_over_jsonrpc_returns_the_answer():
    """The real protocol round trip (message/send), not a unit call: this is what a verifier or registry would exercise."""
    from starlette.testclient import TestClient

    import server

    req = {"jsonrpc": "2.0", "id": "1", "method": "message/send", "params": {"message": {
        "role": "user", "messageId": "m-1", "parts": [{"kind": "text", "text": "What does the constitution say about land rights?"}]}}}
    r = TestClient(server.create_app()).post("/", json=req)
    assert r.status_code == 200
    body = r.json()
    assert "error" not in body, body
    assert "Article 40" in json.dumps(body["result"])
