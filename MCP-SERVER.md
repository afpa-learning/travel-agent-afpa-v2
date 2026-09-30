# Serveur MCP — Agent de Voyage IA

Serveur MCP Python, **100 % lecture seule**, qui expose la base d'exemple
`travel_agent_db` (voir `data/` et `README.md`) à un agent IA, conformément à
la section 4 du cahier des charges.

## Installation

```bash
pip install -r serveur_mcp_local/requirements.txt
```

Prérequis : une base MongoDB/DocumentDB accessible (voir la racine du dépôt
pour lancer une instance locale via `docker compose up -d` et charger les
données avec `scripts/load_data.py`).

## Lancement autonome (pour test)

```bash
export MONGODB_URI="mongodb://admin:Test1234@localhost:27017/?authSource=admin"
export MONGODB_DB="traveldb"
python -m serveur_mcp_local.server
```

Le serveur communique en stdio, comme attendu par la plupart des clients
agents (Claude Code, Cursor, VS Code/Copilot, Gemini CLI...).

## Configuration dans un client agent

Utiliser le fichier `mcp.json` fourni à la racine (à adapter selon le client :
certains attendent ce fichier sous un autre nom ou dans un autre emplacement,
par ex. `.cursor/mcp.json` pour Cursor ou `.vscode/mcp.json` pour VS Code).

Modifier dans ce fichier le chemin du projet en lieu et place de "project_root_path"

## Outils exposés

| Outil | Paramètres | Description |
|---|---|---|
| `search_flights` | `origin`, `destination`, `date_from?`, `date_to?`, `max_price?`, `max_stops?`, `limit?` | Recherche de vols filtrée, triée par prix croissant |
| `get_flight_details` | `flight_id?`, `flight_number?`, `date?` | Détail d'un vol ; désambiguïsation par date si le numéro de vol existe à plusieurs dates |
| `compare_flights` | `flights` (liste de 2 à 6 identifiants) | Comparaison prix/durée/escales, indique le moins cher et le plus rapide |
| `list_airports` | `query`, `limit?` | Recherche d'aéroports par ville, pays ou code IATA |
| `cheapest_flights` | `origin`, `destination`, `date_from?`, `date_to?`, `limit?` | Les N vols les moins chers sur une route, dates flexibles |

Tous les outils :
- valident strictement leurs paramètres (codes IATA à 3 lettres, dates
  `AAAA-MM-JJ`, nombres positifs) et lèvent une erreur explicite sinon ;
- limitent leurs résultats à `MCP_MAX_RESULTS` (20 par défaut) ;
- ne modifient jamais la base (aucune opération d'écriture) ;
- retournent du JSON sérialisable (les `ObjectId` Mongo sont convertis en
  chaîne `flight_id`).

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | Chaîne de connexion (jamais transmise par l'agent) |
| `MONGODB_DB` | `travel_agent_db` | Base de données cible |
| `MCP_MAX_RESULTS` | `20` | Plafond de résultats par outil |
| `ENABLE_WRITE_TOOLS` | `false` | Réservé à une évolution future (aucun outil d'écriture en v1) |
| `ENABLE_MANAGEMENT_TOOLS` | `false` | Réservé à une évolution future (ex. création d'index) |
| `GROQ_API_KEY` | `false` | Clé API GROQ |
| `GROQ_MODEL_AGENT` | `qwen/qwen3.8-27b` | Modèle utilisé par GROQ |
| `FLASK_SECRET_KEY` | `MySuperSecretPhrase123!` | Clé secrète de l'application Flask pour l'utilisation de la session de l'application Flask (obligatoire) |

## Tests

```bash
pip install pytest mongomock
python -m pytest tests/ -v
```

Les tests (`tests/test_tools.py`) valident chaque outil indépendamment du
SDK MCP, contre une base `mongomock` pré-chargée avec le jeu de données
`data/*.json` (voir `tests/conftest.py`).

## Notes de compatibilité

Le SDK officiel `mcp` a introduit en version 2.0 (juillet 2026) un
renommage de `FastMCP` en `MCPServer` (module `mcp.server.mcpserver`), avec
un décorateur `@mcp.tool()` inchangé. Ce serveur cible `mcp>=2,<3`. Pour un
environnement encore sur `mcp<2`, il suffit de remplacer dans
`mcp_server/server.py` :

```python
from mcp.server.mcpserver import MCPServer
mcp = MCPServer(...)
```

par :

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP(...)
```

Le reste du code (outils, décorateurs) est strictement identique dans les
deux cas.
