"""
Configuration du serveur MCP, entièrement pilotée par variables d'environnement
(voir .env.example). La chaîne de connexion n'est JAMAIS transmise par l'agent
à l'exécution : elle est fixée ici, côté serveur, conformément à la section 4.4
du cahier des charges.
"""

import os

# Connexion MongoDB / Azure DocumentDB
MONGODB_URI: str = os.environ.get("MONGODB_URI", "mongodb://localhost:27017")
MONGODB_DB: str = os.environ.get("MONGODB_DB", "traveldb")

# Nombre maximum de documents retournés par un outil, quelle que soit la
# limite demandée par l'agent (section 4.4 : "limitation du nombre de
# résultats retournés par requête, ex. max 20 vols").
MAX_RESULTS: int = int(os.environ.get("MCP_MAX_RESULTS", "20"))

# Outils d'écriture/administration : désactivés par défaut. Non utilisés par
# le serveur v1 (100% lecture seule) — réservés pour une évolution future
# (ex. create_index), conservés ici pour rester alignés avec le cahier des
# charges et le principe observé dans documentdb-agent-kit.
ENABLE_WRITE_TOOLS: bool = os.environ.get("ENABLE_WRITE_TOOLS", "false").lower() == "true"
ENABLE_MANAGEMENT_TOOLS: bool = os.environ.get("ENABLE_MANAGEMENT_TOOLS", "false").lower() == "true"

# Délai de sélection du serveur MongoDB (ms)
SERVER_SELECTION_TIMEOUT_MS: int = int(os.environ.get("MCP_SERVER_SELECTION_TIMEOUT_MS", "8000"))
