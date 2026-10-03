"""Agent Card tests. Added because CI had never run a test for this repository (there was no tests/ directory), and the
server could not import on any allowed SDK: an unused import of a name that does not exist, plus skills missing the
schema-required `tags`. These tests need no network and no API key."""
import importlib.metadata
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
