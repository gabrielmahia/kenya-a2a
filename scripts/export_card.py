"""Regenerate the static Agent Card files from the code, so they cannot drift from what the server serves.

    python scripts/export_card.py           # rewrite .well-known/agent-card.json and .well-known/agent.json
    python scripts/export_card.py --check   # exit 1 if either file differs from the code (use in CI)

agent-card.json is the current well-known path; agent.json is the pre-0.3 path, still served by a2a-sdk 0.3.x but deprecated.
"""
import json
import os
import pathlib
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "unused")  # importing the server must not need a real key
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FILES = [ROOT / ".well-known" / "agent-card.json", ROOT / ".well-known" / "agent.json"]


def render() -> str:
    import server

    card = server.build_agent_card()
    return json.dumps(card.model_dump(mode="json", by_alias=True, exclude_none=True), indent=2, sort_keys=True) + "\n"


def main(argv: list[str]) -> int:
    want = render()
    if "--check" in argv:
        stale = [f.name for f in FILES if not f.exists() or f.read_text() != want]
        print("static cards match the code" if not stale else f"STALE static card(s): {stale}; run scripts/export_card.py")
        return 1 if stale else 0
    for f in FILES:
        f.write_text(want)
    print("wrote", ", ".join(f.name for f in FILES))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
