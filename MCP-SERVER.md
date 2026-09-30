# Serveur MCP — Travel Booking

Serveur MCP (Model Context Protocol) écrit en Python, qui expose à un agent IA
la base MongoDB `traveldb` : **vols, destinations, clients et réservations**.

- Fichier : `serveur_mcp_local/server.py`
- Nom du serveur MCP : `travel-booking`
- Transport : **stdio** (JSON-RPC sur l'entrée/sortie standard)
- SDK : [`mcp`](https://pypi.org/project/mcp/) **2.x** (classe `MCPServer`)
- Outils : **14** (8 lecture, 3 écriture, 3 analyse)

Il est utilisé de deux façons :

1. **Par l'application Flask du projet** : elle démarre le serveur comme
   sous-processus et relaie les appels d'outils demandés par le LLM (Groq).
2. **Directement par un client MCP** (VS Code + GitHub Copilot, Claude Code,
   Cursor, Gemini CLI…), sans Flask.

## Installation

```bash
pip install -r serveur_mcp_local/requirements.txt
```

Contenu de `requirements.txt` :

| Paquet | Version | Rôle |
|---|---|---|
| `mcp` | `>=2,<3` | SDK MCP (serveur et client) |
| `pymongo[srv]` | `>=4.6` | Accès MongoDB / Azure DocumentDB (`mongodb+srv://`) |
| `python-dotenv` | `>=1.0` | Chargement de fichiers `.env` |

Prérequis : Python 3.10+ et une base MongoDB accessible, **déjà peuplée**.
Depuis la racine du dépôt :

```bash
docker compose up -d                    # MongoDB local (avec authentification)
python scripts/load_data.py --reset     # charge data/*.json
```

## Lancement autonome (test)

Le serveur importe `config` avec un import direct (`from config import ...`) :
il doit donc être lancé **comme un script**, et non avec `python -m`.

```bash
export MONGODB_URI="mongodb://admin:Test1234@localhost:27017/?authSource=admin"
export MONGODB_DB="traveldb"
python serveur_mcp_local/server.py
```

Sous PowerShell :

```powershell
$env:MONGODB_URI = "mongodb://admin:Test1234@localhost:27017/?authSource=admin"
$env:MONGODB_DB  = "traveldb"
python serveur_mcp_local\server.py
```

Le processus reste en attente de messages MCP sur stdin : il n'affiche rien,
c'est normal. Pour l'explorer de façon interactive, utilisez l'inspecteur MCP :

```bash
npx @modelcontextprotocol/inspector python serveur_mcp_local/server.py
```

> Le serveur ne charge **pas** de fichier `.env` par lui-même : il lit
> uniquement les variables d'environnement de son processus. C'est le client
> qui doit les lui fournir (bloc `env` de `mcp.json`, ou variables exportées).

## Configuration dans un client agent

Le fichier **`mcp.json`** de la racine sert de modèle :

```json
{
  "servers": {
    "serveur-mcp-local": {
      "type": "stdio",
      "command": "python",
      "args": ["project_root_path\\serveur_mcp_local\\server.py"],
      "env": {
        "MONGODB_URI": "mongodb://localhost:27017",
        "MONGODB_DB": "traveldb",
        "MCP_MAX_RESULTS": "20",
        "ENABLE_WRITE_TOOLS": "false",
        "ENABLE_MANAGEMENT_TOOLS": "false"
      }
    }
  },
  "inputs": []
}
```

À adapter :

1. Remplacer `project_root_path` par le **chemin absolu** du projet (sous
   Linux/macOS : `/chemin/vers/travel-agent-afpa-v2/serveur_mcp_local/server.py`).
2. Remplacer `MONGODB_URI` par la chaîne réelle. Avec le MongoDB du
   `docker-compose.yml`, l'authentification est activée : utiliser
   `mongodb://admin:Test1234@localhost:27017/?authSource=admin`.
3. Si besoin, remplacer `python` par le chemin complet de l'interpréteur de
   votre environnement virtuel (celui où `mcp` et `pymongo` sont installés).

Emplacement du fichier selon le client :

| Client | Fichier |
|---|---|
| VS Code (GitHub Copilot) | `.vscode/mcp.json` |
| Cursor | `.cursor/mcp.json` |
| Application Flask du projet | `.vscode/mcp.json` (premier serveur du fichier) |
| Autres clients | voir leur documentation |

Notes VS Code :

- une connexion à **GitHub Copilot** est nécessaire, même pour un serveur MCP local ;
- à la première utilisation, autoriser la session courante à démarrer le serveur
  (alerte de sécurité) ;
- les variables attendues s'appellent `MONGODB_URI` et `MONGODB_DB`
  (**pas** `MONGO_URI` / `MONGO_DB`) : sinon, le serveur retombe sur ses valeurs
  par défaut.

## Outils exposés

Tous les paramètres marqués `?` sont optionnels et **combinables** (logique ET).

### Vols — collection `flights`

| Outil | Paramètres | Description |
|---|---|---|
| `search_flights` | `origin?`, `destination?`, `airline?`, `cabin?`, `max_fare?` | Recherche de vols. `origin` / `destination` : codes IATA (`CDG`, `JFK`), mis en majuscules automatiquement. `airline` : recherche partielle insensible à la casse. `cabin` : `economy` ou `business`. `max_fare` : tarif de base maximum (EUR). |
| `get_flight` | `flight_id` | Un vol par identifiant (ex. `FL-AF1080`). Renvoie `null` si inconnu. |

### Destinations — collection `destinations`

| Outil | Paramètres | Description |
|---|---|---|
| `search_destinations` | `region?`, `category?`, `tag?`, `min_rating?`, `max_nightly_rate?` | `region` : correspondance exacte insensible à la casse (`Europe`, `Asia`…). `category` : `city-break`, `beach`, `resort`, `adventure`… `tag` : un tag de la liste `tags` (`food`, `luxury`…). `min_rating` : note minimale (0-5). `max_nightly_rate` : tarif moyen par nuit maximum (EUR). |
| `get_destination` | `destination_id` | Une destination par identifiant (ex. `DEST-ROM`). Renvoie `null` si inconnue. |

### Clients — collection `customers`

| Outil | Paramètres | Description |
|---|---|---|
| `search_customers` | `country?`, `loyalty_tier?`, `min_loyalty_points?` | `country` : correspondance exacte insensible à la casse. `loyalty_tier` : `bronze`, `silver` ou `gold`. |
| `get_customer` | `customer_id` | Un client par identifiant (ex. `CUST-1001`). Renvoie `null` si inconnu. |

### Réservations — lecture — collection `reservations`

| Outil | Paramètres | Description |
|---|---|---|
| `search_reservations` | `customer_id?`, `destination_id?`, `status?`, `paid?`, `min_total_price?`, `max_total_price?` | `status` : `pending`, `confirmed`, `completed` ou `cancelled` (valeur invalide → erreur). `paid` : booléen, filtre sur `payment.paid`. Les prix portent sur `total_price`. |
| `get_reservation` | `reservation_id` | Une réservation par identifiant (ex. `RES-20001`). Renvoie `null` si inconnue. |

### Réservations — écriture ⚠️

Ces outils **modifient la base**.

| Outil | Paramètres | Description |
|---|---|---|
| `create_reservation` | `customer_id`, `destination_id`, `flight_id`, `check_in`, `check_out`, `travelers`, `payment_method` | Crée une réservation au statut `pending`, non payée. Dates au format `AAAA-MM-JJ`. Calcule automatiquement `nights`, `room_total`, `flight_total` et `total_price` (voir ci-dessous). Renvoie le document créé. |
| `update_reservation_status` | `reservation_id`, `status` | Change le statut (`pending`, `confirmed`, `completed`, `cancelled`). Renvoie la réservation mise à jour. |
| `mark_reservation_paid` | `reservation_id`, `paid=True` | Positionne `payment.paid`. Renvoie la réservation mise à jour. |

Règles de calcul de `create_reservation` :

```
nights       = check_out - check_in                (en jours)
room_total   = avg_nightly_rate × nights × travelers
flight_total = base_fare × travelers
total_price  = room_total + flight_total           (devise : EUR)
```

Validations : le client, la destination et le vol doivent exister ;
`travelers >= 1` ; `check_out` strictement postérieur à `check_in`. Sinon, une
erreur explicite est levée. L'identifiant généré suit le format `RES-XXXXX`
(plus grand identifiant existant + 1, à partir de `RES-20001`).

### Analyses

| Outil | Paramètres | Description |
|---|---|---|
| `customer_spending_summary` | `customer_id` | Total dépensé (réservations annulées exclues), nombre de réservations par statut, destinations visitées, niveau de fidélité. |
| `destination_popularity` | `top_n=5` | Classement des destinations par nombre de réservations non annulées, avec le chiffre d'affaires cumulé. |
| `db_stats` | — | Nombre de documents par collection. Pratique pour vérifier la connexion et le chargement des données. |

### Exemple de réponse

`db_stats` sur la base de démonstration :

```json
{ "flights": 10, "reservations": 24, "customers": 12, "destinations": 10 }
```

Les identifiants métier (`FL-…`, `DEST-…`, `CUST-…`, `RES-…`) sont conservés
tels quels dans les `_id` : ils sont lisibles par le modèle et réutilisables
directement comme paramètres d'un outil suivant.

## Variables d'environnement

Définies dans `serveur_mcp_local/config.py`.

| Variable | Défaut | Rôle |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | Chaîne de connexion. Fixée côté serveur, jamais transmise par l'agent. |
| `MONGODB_DB` | `traveldb` | Base de données cible. |
| `MCP_MAX_RESULTS` | `20` | Plafond de résultats par outil — **défini mais pas encore appliqué** par `server.py`. |
| `ENABLE_WRITE_TOOLS` | `false` | **Défini mais pas encore appliqué** : les 3 outils d'écriture sont toujours exposés. |
| `ENABLE_MANAGEMENT_TOOLS` | `false` | Réservé à une évolution future (ex. création d'index). |
| `MCP_SERVER_SELECTION_TIMEOUT_MS` | `8000` | Délai de sélection du serveur MongoDB — défini dans `config.py`, pas encore utilisé lors de la connexion. |

Les variables `GROQ_API_KEY`, `GROQ_MODEL_AGENT` et `FLASK_SECRET_KEY` du
fichier `.env` concernent l'application Flask et l'agent, **pas** le serveur MCP
(voir `README.md`).

## Comment l'application Flask s'y connecte

1. `MCPClientManager` (`agent/mcp_client.py`) démarre une boucle asyncio dans un
   thread dédié.
2. `MCPSession.start()` (`agent/orchestrator.py`) lit `.vscode/mcp.json`,
   prend le **premier** serveur déclaré et le lance en sous-processus
   (`stdio_client`), avec le bloc `env` du fichier.
3. Après `initialize()`, la session récupère la liste des outils
   (`list_tools`) et les convertit au format « function calling » de Groq : le
   schéma JSON des paramètres est repris tel quel.
4. Quand le modèle demande un outil, `call_tool` l'envoie au serveur MCP et
   renvoie le résultat au modèle sous forme de message `tool`.

Le serveur MCP peut donc être enrichi (nouvel outil décoré avec `@mcp.tool()`)
sans toucher à l'agent : la liste des outils est redécouverte au démarrage.

## Ajouter un outil

```python
@mcp.tool()
def cancel_reservation(reservation_id: str) -> dict:
    """Annule une réservation (la docstring est envoyée au modèle : soyez précis)."""
    result = db.reservations.find_one_and_update(
        {"_id": reservation_id},
        {"$set": {"status": "cancelled"}},
        return_document=True,
    )
    if result is None:
        raise ValueError(f"Réservation inconnue : {reservation_id!r}")
    return result
```

La docstring et les annotations de type servent à générer la description et le
schéma de l'outil vus par le LLM. Redémarrez ensuite le serveur (ou l'application
Flask).

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `ModuleNotFoundError: No module named 'config'` | Lancement avec `python -m serveur_mcp_local.server` | Lancer `python serveur_mcp_local/server.py` |
| `ModuleNotFoundError: mcp.server.mcpserver` | SDK `mcp` en version 1.x | `pip install "mcp>=2,<3"` (voir ci-dessous) |
| `requires authentication` / `Unauthorized` | URI sans identifiants alors que MongoDB Docker est authentifié | Utiliser `mongodb://admin:Test1234@localhost:27017/?authSource=admin` |
| Le serveur semble ignorer `MONGODB_URI` | Variable nommée `MONGO_URI` dans le `mcp.json` | Renommer en `MONGODB_URI` |
| `ServerSelectionTimeoutError` | MongoDB non démarré | `docker compose up -d` |
| Les outils renvoient des listes vides ou `null` | Base non chargée, ou mauvaise base | `python scripts/load_data.py --reset`, puis appeler `db_stats` |
| `search_destinations` renvoie des réservations | Bug connu de `load_data.py` (`destinations` chargée depuis `reservations.json`) | Corriger le dictionnaire `COLLECTIONS` puis recharger avec `--reset` |
| Le client ne trouve pas `python` ou `mcp` | Mauvais interpréteur | Indiquer le chemin complet du `python` du `.venv` dans `command` |

## Compatibilité du SDK `mcp`

Ce serveur cible `mcp>=2,<3` : la classe s'appelle `MCPServer` et se trouve dans
`mcp.server.mcpserver`.

```python
from mcp.server.mcpserver import MCPServer
mcp = MCPServer("travel-booking")
```

Pour un environnement resté sur `mcp<2`, il suffit de remplacer l'import et
l'instanciation dans `server.py` ; le reste (décorateurs `@mcp.tool()`, outils)
est identique :

```python
from mcp.server.fastmcp import FastMCP
mcp = FastMCP("travel-booking")
```

> Le `README.md` de `serveur_mcp_local/` mentionne encore une version épinglée
> `mcp==1.9.4` : elle est obsolète, `requirements.txt` fait foi.

## Limites actuelles

- Les outils de recherche ne plafonnent pas le nombre de résultats (voir
  `MCP_MAX_RESULTS`) ; sur les volumes de démonstration, cela reste sans effet.
- Le drapeau `ENABLE_WRITE_TOOLS` n'est pas encore branché : pour un usage réel,
  conditionner l'enregistrement des outils d'écriture à cette variable.
- Les valeurs de `cabin`, `category` ou `region` sont saisies en texte libre par
  le modèle : une valeur inexistante renvoie simplement une liste vide.
- La génération de l'identifiant `RES-XXXXX` n'est pas atomique : en cas
  d'écritures concurrentes, prévoir un compteur atomique ou un UUID.
- Le serveur ne comporte pas de suite de tests automatisés.
