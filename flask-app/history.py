import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient, ASCENDING

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "traveldb")

_client = MongoClient(MONGODB_URI)
_db = _client[MONGODB_DB]
qa_history = _db["qa_history"]

MAX_MESSAGES : int = int(os.environ.get("MCP_MAX_RESULTS", "20"))  # nombre de messages réinjectés dans le contexte du modèle


def new_conv_id() -> str:
    return uuid.uuid4().hex


def save_message(conv_id: str, role: str, content: str, trace: list | None = None):
    qa_history.insert_one({
        "conv_id": conv_id,
        "role": role,            # "user" ou "assistant"
        "content": content,
        "trace": trace,          # optionnel, uniquement pour role="assistant"
        "created_at": datetime.now(timezone.utc),
    })


def load_history(conv_id: str, limit: int = MAX_MESSAGES) -> list[dict]:
    """Retourne les derniers messages au format attendu par run_turn (role/content)."""
    docs = list(
        qa_history.find({"conv_id": conv_id}, {"role": 1, "content": 1, "_id": 0})
        .sort("created_at", ASCENDING)
        .limit(limit * 2)  # marge, filtré ci-dessous
    )
    # on ne garde que les MAX_MESSAGES derniers, tout en s'assurant que ça commence par "user"
    docs = docs[-limit:]
    while docs and docs[0]["role"] != "user":
        docs.pop(0)
    return docs


def load_full_history(conv_id: str) -> list[dict]:
    """Historique complet avec trace, pour affichage dans l'UI (pas pour Groq)."""
    return list(
        qa_history.find({"conv_id": conv_id}, {"_id": 0})
        .sort("created_at", ASCENDING)
    )


def clear_history(conv_id: str):
    qa_history.delete_many({"conv_id": conv_id})