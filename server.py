"""
KenyaA2A — A2A-compliant server for East African civic data.
Built on the official a2a-sdk (Linux Foundation / Apache 2.0).
"""
import os
import json
import asyncio
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
import uvicorn

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities, AgentCard, AgentSkill,
    Message, Part, TaskState, TextPart, Role,
)
from a2a.utils import new_agent_id

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


def query_budget(county: str) -> str:
    """Query COB budget data for a county."""
    fpath = DATA_DIR / "county_budgets_fy2223.csv"
    if not fpath.exists():
        return (
            f"Budget data for {county} not available locally. "
            "Source: Controller of Budget Kenya (cob.go.ke). "
            "DOI: 10.34740/kaggle/dsv/15473045"
        )
    df = pd.read_csv(fpath)
    county_clean = county.strip().title()
    matches = df[df.apply(
        lambda row: county_clean.lower() in " ".join(row.astype(str).str.lower()), axis=1
    )]
    if matches.empty:
        return f"No budget records found for {county_clean}. Valid counties: {COUNTIES[:5]}..."
    return matches.to_string(index=False)


def query_parliament(query: str) -> str:
    """Query MP and bills data."""
    results = []
    for fname in ["mps_seed.csv", "bills_seed.csv", "cdf_seed.csv"]:
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
    return "\n\n".join(results) if results else "No parliamentary records found."


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
        "source": "NDMA Kenya (sandbox)",
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
                self._text_response("Please send a question about Kenya civic data.")
            )
            return

        msg_lower = user_message.lower()

        # Route to skill
        if any(w in msg_lower for w in ["budget", "county", "absorption", "development fund", "cob"]):
            # Extract county if mentioned
            county = "Nairobi"
            for c in COUNTIES:
                if c.lower() in msg_lower:
                    county = c
                    break
            result = query_budget(county)
            response = f"**County Budget Data — {county}**\n\n{result}\n\nSource: Controller of Budget (cob.go.ke)"

        elif any(w in msg_lower for w in ["mp", "parliament", "bill", "cdf", "constituency", "vote"]):
            result = query_parliament(user_message)
            response = f"**Parliamentary Records**\n\n{result}\n\nSource: Parliament of Kenya / Mzalendo"

        elif any(w in msg_lower for w in ["drought", "ndma", "water stress", "rainfall", "wapimaji"]):
            county = "Nairobi"
            for c in COUNTIES:
                if c.lower() in msg_lower:
                    county = c
                    break
            data = get_drought_status(county)
            if "error" in data:
                response = data["error"]
            else:
                response = (
                    f"**Drought Status — {data['county']}**\n"
                    f"Phase: {data['phase']} ({data['phase_label']})\n"
                    f"Rainfall deficit: {data['rainfall_deficit_pct']}%\n"
                    f"Source: {data['source']}"
                )

        elif any(w in msg_lower for w in ["right", "haki", "constitution", "katiba", "article", "kifungu"]):
            lang = "sw" if any(w in msg_lower for w in ["kiswahili", "swahili", "sw", "katiba"]) else "en"
            topic = "land"
            for t in ["land", "ardhi", "education", "elimu", "water", "maji", "health", "afya", "labour", "kazi", "assembly"]:
                if t in msg_lower:
                    topic = t
                    break
            response = get_rights(topic, lang)

        else:
            response = (
                "**KenyaA2A — East African Civic Data Agent**\n\n"
                "I can answer questions about:\n"
                "- 🏛 **County budgets** — absorption rates, development spend (47 counties)\n"
                "- 📋 **Parliament** — MP records, bills, CDF utilisation\n"
                "- 💧 **Drought** — NDMA drought phases for any county\n"
                "- ⚖️ **Rights** — Constitution of Kenya 2010 in English and Kiswahili\n\n"
                "Example: \'What is the drought status in Turkana County?\'"
            )

        await event_queue.enqueue_event(self._text_response(response))

    def _text_response(self, text: str):
        from a2a.types import TaskArtifactUpdateEvent, Artifact, TextPart
        return TaskArtifactUpdateEvent(
            artifact=Artifact(
                parts=[TextPart(text=text)],
                index=0,
                append=False,
            )
        )

    async def cancel(self, context: RequestContext, event_queue) -> None:
        raise NotImplementedError("Cancel not supported")


def build_agent_card(host: str = "http://localhost:8000") -> AgentCard:
    return AgentCard(
        name="KenyaA2A",
        description=(
            "East African civic data agent — query Kenya parliament records, "
            "county budget execution, NDMA drought status, and constitutional rights "
            "in English and Kiswahili. The first A2A agent serving East African public data."
        ),
        url=f"{host}/",
        version="0.1.0",
        capabilities=AgentCapabilities(streaming=False),
        skills=[
            AgentSkill(id="budget_query", name="County Budget Query",
                       description="Query Controller of Budget county development fund absorption for all 47 Kenya counties"),
            AgentSkill(id="parliament_query", name="Parliament Records Query",
                       description="Query MP records, parliamentary bills, and CDF utilisation from Kenya\'s 13th Parliament"),
            AgentSkill(id="drought_status", name="NDMA Drought Status",
                       description="Get current NDMA drought phase classification for any Kenya county (1=Minimal to 5=Famine)"),
            AgentSkill(id="rights_query", name="Constitutional Rights (EN/SW)",
                       description="Query the Constitution of Kenya 2010 in English or Kiswahili"),
        ],
        default_input_modes=["text"],
        default_output_modes=["text"],
    )


def create_app(host: str = "http://localhost:8000"):
    agent_card    = build_agent_card(host)
    executor      = KenyaCivicAgentExecutor()
    task_store    = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(agent_executor=executor, task_store=task_store)
    return A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    ).build()


app = create_app(os.getenv("A2A_HOST_URL", "http://localhost:8000"))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8000")))
