import json
from functools import lru_cache

from ..config import settings
from .business_loan import BusinessLoanAgent
from .engine import FlowAgent, Session, get_session
from .localized import IndonesiaReminderAgent, PhilippinesLifeAgent

AGENT_CLASSES: dict[str, type[FlowAgent]] = {
    "business_loan": BusinessLoanAgent,
    "ph_life_insurance": PhilippinesLifeAgent,
    "id_consumer_finance": IndonesiaReminderAgent,
}


def load_config(key: str) -> dict:
    return json.loads((settings.configs_dir / "assistants" / f"{key}.json").read_text(encoding="utf-8"))


@lru_cache
def get_agent(key: str) -> FlowAgent:
    if key not in AGENT_CLASSES:
        raise KeyError(key)
    return AGENT_CLASSES[key](load_config(key))


def start_session(key: str, today: str | None = None, lang: str | None = None) -> tuple[Session, dict]:
    agent = get_agent(key)
    session = Session(agent_key=key)
    if today:
        session.today = today
    if lang:
        session.lang = lang
    return session, agent.start(session)


def continue_session(session_id: str, text: str) -> dict:
    session = get_session(session_id)
    if session is None:
        raise KeyError(session_id)
    return get_agent(session.agent_key).handle(session, text)
