"""
KenyaA2A — A2A-compliant server for East African civic data.
Built on the official a2a-sdk (Linux Foundation / Apache 2.0).
"""
import os
import re
from pathlib import Path

import pandas as pd
import uvicorn
from a2a.helpers import new_text_message
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.routes import create_agent_card_routes, create_jsonrpc_routes
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentSkill,
)
from dotenv import load_dotenv
from starlette.applications import Starlette

load_dotenv()

DATA_DIR = Path(__file__).parent / "civic_data"

COUNTIES = [
    "Nairobi", "Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita Taveta",
    "Garissa", "Wajir", "Mandera", "Marsabit", "Isiolo", "Meru", "Tharaka Nithi",
    "Embu", "Kitui", "Machakos", "Makueni", "Nyandarua", "Nyeri", "Kirinyaga",
    "Murang'a", "Kiambu", "Turkana", "West Pokot", "Samburu", "Trans Nzoia",
    "Uasin Gishu", "Elgeyo Marakwet", "Nandi", "Baringo", "Laikipia", "Nakuru",
    "Narok", "Kajiado", "Kericho", "Bomet", "Kakamega", "Vihiga", "Bungoma",
    "Busia", "Siaya", "Kisumu", "Homa Bay", "Migori", "Kisii", "Nyamira",
]

RIGHTS_EN = {
    "land": "Article 40: Every person has the right, either individually or in association with others, to acquire and own property. Land shall not be arbitrarily deprived from any person.",
    "education": "Article 43: Every person has the right to education, including the right to free and compulsory basic education.",
    "water": "Article 43: Every person has the right to clean and safe water in adequate quantities.",
    "health": "Article 43: Every person has the right to the highest attainable standard of health, including the right to healthcare services.",
    "labour": "Article 41: Every person has the right to fair labour practices.",
    "assembly": "Article 37: Every person has the right, peaceably and unarmed, to assemble, to demonstrate, to picket, and to present petitions to public authorities.",
}

RIGHTS_SW = {
    "land": "Kifungu 40: Kila mtu ana haki, mmoja mmoja au kwa ushirikiano na wengine, kupata na kumiliki mali. Ardhi haitachukuliwa bila sababu ya msingi.",
    "elimu": "Kifungu 43: Kila mtu ana haki ya elimu, ikiwemo haki ya elimu ya msingi bure na ya lazima.",
    "maji": "Kifungu 43: Kila mtu ana haki ya maji safi na salama kwa kiasi cha kutosha.",
    "afya": "Kifungu 43: Kila mtu ana haki ya kiwango cha juu zaidi cha afya, ikiwemo huduma za afya.",
    "kazi": "Kifungu 41: Kila mtu ana haki ya mazoea ya haki ya kazi.",
}


# ── Routing ──────────────────────────────────────────────────────────────────
# Whole-word matching (the old substring matching sent "important" to the parliament skill and "answer" to Kiswahili) and
# specific topics before the generic word "county" (the old order sent "drought status in Turkana County" to the budget skill).
def _words(*ws: str) -> "re.Pattern[str]":
    return re.compile(r"\b(?:" + "|".join(re.escape(w) for w in ws) + r")\b", re.IGNORECASE)


_ROUTES = (
    ("drought", _words("drought", "ndma", "water stress", "rainfall", "wapimaji")),
    ("budget", _words("budget", "absorption", "development fund", "cob")),
    ("parliament", _words("mp", "mps", "parliament", "bill", "bills", "cdf", "constituency", "vote")),
    ("rights", _words("right", "rights", "haki", "constitution", "katiba", "article", "kifungu")),
    ("budget", _words("county", "counties")),
)
_SWAHILI = _words("kiswahili", "swahili", "katiba", "sw")
_TOPICS = ("land", "ardhi", "education", "elimu", "water", "maji", "health", "afya", "labour", "kazi", "assembly")


def route(message: str) -> str:
    """Return the skill name for a message: drought, budget, parliament, rights, or help."""
    for name, pattern in _ROUTES:
        if pattern.search(message):
            return name
    return "help"


def find_county(message: str) -> str:
    """First county named in the message (longest names first), defaulting to Nairobi."""
    for c in sorted(COUNTIES, key=len, reverse=True):
        if re.search(r"(?<!\w)" + re.escape(c) + r"(?!\w)", message, re.IGNORECASE):
            return c
    return "Nairobi"


def find_topic(message: str) -> str:
    for topic in _TOPICS:
        if _words(topic).search(message):
            return topic
    return "land"


def query_budget(county: str) -> str | None:
    """Query COB budget data for a county."""
    fpath = DATA_DIR / "county_budgets_fy2223.csv"
    if not fpath.exists():
        return None  # the civic_data/ directory is not part of this repository
    df = pd.read_csv(fpath)
    county_clean = county.strip().title()
    matches = df[df.apply(
        lambda row: county_clean.lower() in " ".join(row.astype(str).str.lower()), axis=1
    )]
    if matches.empty:
        return f"No budget records found for {county_clean}. Valid counties: {COUNTIES[:5]}..."
    return matches.to_string(index=False)


def query_parliament(query: str) -> str | None:
    """Query MP and bills data."""
    results = []
    present = [f for f in ["mps_seed.csv", "bills_seed.csv", "cdf_seed.csv"] if (DATA_DIR / f).exists()]
    if not present:
        return None  # the civic_data/ directory is not part of this repository
    for fname in present:
        fpath = DATA_DIR / fname
        if fpath.exists():
            df = pd.read_csv(fpath)
            matches = df[df.apply(
                lambda row: any(
                    query.lower() in str(v).lower() for v in row
                ), axis=1
            )]
            if not matches.empty:
                results.append(f"From {fname}:\n{matches.head(5).to_string(index=False)}")
    return "\n\n".join(results) if results else "No parliamentary records matched your query."


def get_drought_status(county: str) -> dict:
    """Get NDMA drought phase for a county."""
    import hashlib
    county_clean = county.strip().title()
    if county_clean not in COUNTIES:
        return {"error": f"County not found: {county}"}
    h = int(hashlib.md5(county_clean.encode()).hexdigest()[:4], 16) % 4 + 1
    phases = {1: "Minimal", 2: "Stressed", 3: "Crisis", 4: "Emergency", 5: "Famine"}
    return {
        "county": county_clean,
        "phase": h,
        "phase_label": phases[h],
        "rainfall_deficit_pct": round((h - 1) * 15 + 5, 1),
        "source": "SYNTHETIC DEMO: derived from the county name; NOT NDMA data",
        "is_synthetic": True,
    }


def get_rights(topic: str, language: str = "en") -> str:
    """Query constitutional rights in English or Kiswahili."""
    topic_clean = topic.lower().strip()
    if language.lower() in ("sw", "swahili", "kiswahili"):
        for key, val in RIGHTS_SW.items():
            if key in topic_clean or topic_clean in key:
                return f"[Kiswahili — Constitution of Kenya 2010]\n{val}"
        return "Haki hii haikupatikana. Jaribu: ardhi, elimu, maji, afya, kazi."
    for key, val in RIGHTS_EN.items():
        if key in topic_clean or topic_clean in key:
            return f"[English — Constitution of Kenya 2010]\n{val}"
    return f"Right not found for '{topic}'. Try: land, education, water, health, labour, assembly."


class KenyaCivicAgentExecutor(AgentExecutor):
    """A2A executor for Kenya civic data skills."""

    async def execute(self, context: RequestContext, event_queue) -> None:
        user_message = context.get_user_input()
        if not user_message:
            await event_queue.enqueue_event(
                self._text_response("Please send a question about Kenya civic data.", context)
            )
            return

        skill = route(user_message)

        if skill == "budget":
            county = find_county(user_message)
            result = query_budget(county)
            if result is None:
                response = (
                    "Budget data is not included in this deployment (the civic_data/ directory is absent), "
                    "so no figures can be returned."
                )
            else:
                response = f"**County Budget Data — {county}**\n\n{result}\n\nSource: Controller of Budget (cob.go.ke)"

        elif skill == "parliament":
            result = query_parliament(user_message)
            if result is None:
                response = (
                    "Parliament data is not included in this deployment (the civic_data/ directory is absent), "
                    "so no records can be returned."
                )
            else:
                response = f"**Parliamentary Records**\n\n{result}\n\nSource: Parliament of Kenya / Mzalendo"

        elif skill == "drought":
            data = get_drought_status(find_county(user_message))
            if "error" in data:
                response = data["error"]
            else:
                response = (
                    "**DEMO: synthetic values, not NDMA data. Do not use for decisions.**\n"
                    f"**Drought Status — {data['county']}**\n"
                    f"Phase: {data['phase']} ({data['phase_label']})\n"
                    f"Rainfall deficit: {data['rainfall_deficit_pct']}%\n"
                    f"Source: {data['source']}"
                )

        elif skill == "rights":
            lang = "sw" if _SWAHILI.search(user_message) else "en"
            response = get_rights(find_topic(user_message), lang)

        else:
            response = (
                "**KenyaA2A — East African Civic Data Agent (demo)**\n\n"
                "Working: ⚖️ **Rights** — Constitution of Kenya 2010 in English and Kiswahili (a small set of articles).\n"
                "Needs data files that are not included in this deployment: 🏛 County budgets, 📋 Parliament.\n"
                "Synthetic demo output, not real data: 💧 Drought.\n\n"
                "Example: \'What does the constitution say about land rights?\'"
            )

        await event_queue.enqueue_event(self._text_response(response, context))

    def _text_response(self, text: str, context: RequestContext):
        # A plain agent message is the SDK's supported reply for a simple, single-turn skill. It must carry the
        # (possibly server-generated) contextId: the official TCK requirement CORE-MULTI-001a failed without it.
        return new_text_message(text, context_id=context.context_id)

    async def cancel(self, context: RequestContext, event_queue) -> None:
        raise NotImplementedError("Cancel not supported")


def build_agent_card(host: str = "http://localhost:8000") -> AgentCard:
    return AgentCard(
        name="KenyaA2A",
        description=(
            "East African civic data agent (demo). Working: constitutional rights lookup in English "
            "and Kiswahili (a small set of articles). County budget and parliament queries need data "
            "files that are not included in this deployment. Drought status returns synthetic demo "
            "values, not NDMA data."
        ),
        supported_interfaces=[AgentInterface(protocol_binding="JSONRPC", url=f"{host}/", protocol_version="1.0")],
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(id="budget_query", name="County Budget Query",
                       description="Query Controller of Budget county development fund absorption. Needs data files that are not included in this deployment.",
                       tags=["budget", "counties", "public-finance", "kenya"]),
            AgentSkill(id="parliament_query", name="Parliament Records Query",
                       description="Query MP records, parliamentary bills and CDF utilisation. Needs data files that are not included in this deployment.",
                       tags=["parliament", "bills", "mps", "kenya"]),
            AgentSkill(id="drought_status", name="Drought Status (DEMO, synthetic)",
                       description="DEMO: returns synthetic values derived from the county name, not NDMA data. Do not use for decisions.",
                       tags=["drought", "ndma", "climate", "kenya"]),
            AgentSkill(id="rights_query", name="Constitutional Rights (EN/SW)",
                       description="Query the Constitution of Kenya 2010 in English or Kiswahili",
                       tags=["constitution", "rights", "kiswahili", "kenya"]),
        ],
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
    )


def create_app(host: str = "http://localhost:8000"):
    card = build_agent_card(host)
    handler = DefaultRequestHandler(agent_executor=KenyaCivicAgentExecutor(), task_store=InMemoryTaskStore(), agent_card=card)
    # Cache-Control on the card: the official TCK's SHOULD-level agent-card caching requirement.
    routes = [*create_agent_card_routes(card, cache_control="public, max-age=3600"), *create_jsonrpc_routes(handler, "/")]
    return Starlette(routes=routes)


app = create_app(os.getenv("A2A_HOST_URL", "http://localhost:8000"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
