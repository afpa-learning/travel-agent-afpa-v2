# Travel Agent AFPA v2 — Agent de voyage IA (MCP + Groq + Flask)

Application web permettant d'interroger en langage naturel une base de
réservations de voyages (vols, destinations, clients, réservations).

Un agent IA (LLM hébergé chez **Groq**) choisit et appelle les outils d'un
**serveur MCP** Python, qui lit et écrit dans **MongoDB** (ou Azure DocumentDB).
L'interface est une application **Flask** avec deux écrans : un chat et un
générateur de rapports d'analyse.

> Le cahier des charges du projet se trouve dans
> `cahier-des-charges-agent-voyage-version-2.pdf`.

## Sommaire

- [Architecture](#architecture)
- [Structure du dépôt](#structure-du-dépôt)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Lancement](#lancement)
- [Fonctionnalités](#fonctionnalités)
- [API Flask](#api-flask)
- [Modèle de données](#modèle-de-données)
- [Utiliser le serveur MCP depuis VS Code / Copilot](#utiliser-le-serveur-mcp-depuis-vs-code--copilot)
- [Points d'attention connus](#points-dattention-connus)
- [État d'avancement par rapport au cahier des charges](#état-davancement-par-rapport-au-cahier-des-charges)

## Architecture

```
┌──────────────┐   HTTP    ┌───────────────────────────────┐
│  Navigateur  │──────────▶│  Flask  (flask-app/app.py)    │
│  chat/analyse│◀──────────│  + historique (qa_history)    │
└──────────────┘           └──────────────┬────────────────┘
                                          │ MCPClientManager
                                          │ (boucle asyncio dédiée)
                           ┌──────────────▼────────────────┐        ┌──────────┐
                           │  Agent (agent/orchestrator.py)│◀──────▶│  Groq    │
                           │  boucle "tool calling"        │  API   │  (LLM)   │
                           └──────────────┬────────────────┘        └──────────┘
                                          │ MCP / JSON-RPC sur stdio
                                          │ (sous-processus)
                           ┌──────────────▼────────────────┐
                           │  Serveur MCP                  │
                           │  serveur_mcp_local/server.py  │
                           └──────────────┬────────────────┘
                                          │ pymongo
                           ┌──────────────▼────────────────┐
                           │  MongoDB / Azure DocumentDB   │
                           │  base « traveldb »            │
                           └───────────────────────────────┘
```

Déroulé d'une question :

1. Le navigateur envoie la question à `POST /api/ask`.
2. Flask recharge l'historique de la conversation depuis MongoDB (collection
   `qa_history`) et appelle `run_turn`.
3. `run_turn` envoie la conversation et la liste des outils MCP à Groq. Tant que
   le modèle demande un outil, l'appel est transmis au serveur MCP (maximum
   8 tours), puis le résultat est renvoyé au modèle.
4. La réponse finale et la trace des appels d'outils sont renvoyées à
   l'interface et sauvegardées dans l'historique.

Le serveur MCP est lancé automatiquement par l'application Flask comme
sous-processus : il n'y a **pas** de second serveur à démarrer à la main.
La commande de lancement est lue dans `.vscode/mcp.json` (premier serveur déclaré).

## Structure du dépôt

```
travel-agent-afpa-v2/
├── agent/
│   ├── mcp_client.py        # MCPClientManager : boucle asyncio en thread, session MCP + client Groq
│   └── orchestrator.py      # MCPSession, run_turn (chat), run_analysis (rapport)
├── data/                    # Jeu de données de démonstration (JSON)
│   ├── flights.json         #   10 vols
│   ├── destinations.json    #   10 destinations
│   ├── customers.json       #   12 clients
│   └── reservations.json    #   24 réservations
├── flask-app/
│   ├── app.py               # Routes Flask + intégration de l'agent
│   ├── history.py           # Historique de conversation (collection qa_history)
│   ├── requirements.txt
│   ├── static/              # CSS / JS / logo
│   └── templates/           # index.html (chat), analysis.html (rapport)
├── scripts/
│   └── load_data.py         # Chargement de data/*.json dans MongoDB + index
├── serveur_mcp_local/
│   ├── server.py            # Serveur MCP (14 outils)
│   ├── config.py            # Configuration par variables d'environnement
│   └── requirements.txt
├── docker-compose.yml       # MongoDB 7 local (avec authentification)
├── mcp.json                 # Modèle de configuration client MCP
├── .env.example             # Modèle de variables d'environnement
├── MCP-SERVER.md            # Documentation détaillée du serveur MCP
└── cahier-des-charges-agent-voyage-version-2.pdf
```

## Prérequis

- **Python 3.10+** (le SDK `mcp` 2.x l'exige ; les dépendances figées du projet
  ont été générées avec Python 3.14)
- **Docker** (pour lancer MongoDB en local) — ou une instance MongoDB / Azure
  DocumentDB déjà accessible
- Une **clé API Groq** : <https://console.groq.com/keys>

## Installation

```bash
# 1. Cloner le dépôt
git clone https://github.com/afpa-learning/travel-agent-afpa-v2.git
cd travel-agent-afpa-v2

# 2. Environnement virtuel
python -m venv .venv
source .venv/bin/activate          # Windows : .venv\Scripts\activate

# 3. Dépendances
pip install -r serveur_mcp_local/requirements.txt
pip install flask groq
```

> **Important — `groq` :** le paquet `groq`, utilisé par `agent/`, n'est **pas**
> listé dans `flask-app/requirements.txt`. Il faut donc l'installer
> séparément (commande ci-dessus).
>
> Le fichier `flask-app/requirements.txt` est un `pip freeze` complet (~150
> paquets, encodé en UTF-16) ; les dépendances réellement utilisées sont
> `flask`, `groq`, `mcp>=2,<3`, `pymongo` et `python-dotenv`.

## Configuration

### 1. Variables d'environnement (`.env`)

```bash
cp .env.example .env               # Windows : copy .env.example .env
```

| Variable | Exemple / défaut | Rôle |
|---|---|---|
| `MONGO_ROOT_USER` | `admin` | Utilisateur root du MongoDB Docker |
| `MONGO_ROOT_PASSWORD` | `Test1234` | Mot de passe root du MongoDB Docker |
| `MONGODB_URI` | `mongodb://admin:Test1234@localhost:27017/?authSource=admin` | Chaîne de connexion (scripts, historique, serveur MCP) |
| `MONGODB_DB` | `traveldb` | Base de données cible |
| `MCP_MAX_RESULTS` | `20` | Taille de la fenêtre d'historique réinjectée dans le modèle (voir [points d'attention](#points-dattention-connus)) |
| `ENABLE_WRITE_TOOLS` | `false` | Réservé (non appliqué pour l'instant) |
| `ENABLE_MANAGEMENT_TOOLS` | `false` | Réservé (non appliqué pour l'instant) |
| `GROQ_API_KEY` | *(à renseigner)* | Clé API Groq |
| `GROQ_MODEL_AGENT` | `openai/gpt-oss-120b` | Modèle Groq utilisé par l'agent |
| `FLASK_SECRET_KEY` | *(à personnaliser)* | Clé de signature des sessions Flask |

Le fichier `.env` est ignoré par git : ne le publiez jamais (il contient votre
clé Groq et vos mots de passe).

### 2. Configuration du serveur MCP pour l'application

L'application Flask lit le fichier **`.vscode/mcp.json`** (ignoré par git) pour
savoir comment démarrer le serveur MCP. Créez-le à partir du modèle `mcp.json` :

```bash
mkdir -p .vscode
cp mcp.json .vscode/mcp.json       # Windows : copy mcp.json .vscode\mcp.json
```

Puis éditez `.vscode/mcp.json` :

1. remplacez `project_root_path` par le chemin absolu du projet ;
2. renseignez `MONGODB_URI` avec **la même chaîne que dans `.env`**, identifiants
   compris (`mongodb://admin:Test1234@localhost:27017/?authSource=admin`).

Exemple (Windows) :

```json
{
  "servers": {
    "travel-booking": {
      "type": "stdio",
      "command": "python",
      "args": ["C:\\Users\\moi\\projets\\travel-agent-afpa-v2\\serveur_mcp_local\\server.py"],
      "env": {
        "MONGODB_URI": "mongodb://admin:Test1234@localhost:27017/?authSource=admin",
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

> Les noms de variables attendus par le serveur sont `MONGODB_URI` et
> `MONGODB_DB` (et non `MONGO_URI` / `MONGO_DB`). Sous Linux/macOS, remplacez les
> `\\` du chemin par des `/`. Si `command` vaut `python`, l'interpréteur utilisé
> est celui du `PATH` : activez votre environnement virtuel avant de lancer Flask,
> ou indiquez le chemin complet de son `python`.

## Lancement

```bash
# 1. Démarrer MongoDB (port 27017, données persistées dans un volume Docker)
docker compose up -d

# 2. Charger les données de démonstration
python scripts/load_data.py --reset
```

Le script doit afficher le décompte final : **flights 10, reservations 24,
customers 12, destinations 10** (voir le [point d'attention n° 2](#points-dattention-connus)
si `destinations` affiche 24).

```bash
# 3. Exporter les variables d'environnement dans le terminal (voir point n° 4)
export MONGODB_URI="mongodb://admin:Test1234@localhost:27017/?authSource=admin"
export MONGODB_DB="traveldb"
# PowerShell : $env:MONGODB_URI="mongodb://admin:Test1234@localhost:27017/?authSource=admin"

# 4. Lancer l'application
cd flask-app
python app.py
```

L'application est disponible sur <http://127.0.0.1:5000> :

| URL | Écran |
|---|---|
| `/` | Chat (questions en langage naturel) |
| `/analysis` | Analyse agentique (rapport Markdown) |

## Fonctionnalités

### Chat (`/`)

- Questions en langage naturel, ex. « Top 3 des villes de destination par
  revenu total », « Qui sont mes 5 meilleurs clients par dépense ? ».
- Suggestions de questions prêtes à l'emploi dans la barre latérale.
- Liste des outils MCP disponibles, chargée dynamiquement depuis le serveur.
- Voyants d'état **MCP** et **LLM**.
- Historique de conversation persistant (MongoDB, lié à la session du
  navigateur) et bouton « Nouvelle conversation ».
- Trace des appels d'outils (nom, arguments, résultat) conservée avec chaque
  réponse.

### Analyse agentique (`/analysis`)

Le modèle enchaîne jusqu'à 20 appels d'outils pour rassembler les données d'un
sujet libre (ex. « Taux d'annulation par compagnie aérienne »), puis rédige un
**rapport Markdown structuré** affiché dans la page.

## API Flask

| Méthode | Route | Description |
|---|---|---|
| `GET` | `/` | Page de chat |
| `GET` | `/analysis` | Page d'analyse |
| `GET` | `/api/status` | État MCP / LLM et liste des outils (nom, description, schéma) |
| `POST` | `/api/ask` | Corps `{"question": "..."}` → `{"reply": "...", "trace": [...]}` |
| `POST` | `/api/call` | Corps `{"tool_name": "...", "arguments": {...}}` → appel direct d'un outil MCP |
| `POST` | `/api/analyze` | Corps `{"topic": "..."}` → `{"report": "<markdown>"}` |
| `GET` | `/api/history` | Historique complet de la conversation courante |
| `GET` | `/api/history/reset` | Supprime l'historique et démarre une nouvelle conversation |

Exemple :

```bash
curl -X POST http://127.0.0.1:5000/api/call \
  -H "Content-Type: application/json" \
  -d '{"tool_name": "db_stats", "arguments": {}}'
```

## Modèle de données

Base **`traveldb`** — quatre collections métier + une collection technique.
Les `_id` sont des identifiants métier lisibles (et non des `ObjectId`).

| Collection | Documents | Exemple d'`_id` | Champs principaux |
|---|---|---|---|
| `flights` | 10 | `FL-AF1080` | `airline`, `origin`, `destination`, `dest_city`, `duration_min`, `cabin`, `base_fare` |
| `destinations` | 10 | `DEST-PAR` | `city`, `country`, `region`, `category`, `avg_nightly_rate`, `rating`, `tags[]` |
| `customers` | 12 | `CUST-1001` | `name`, `email`, `country`, `loyalty_tier`, `loyalty_points`, `joined` |
| `reservations` | 24 | `RES-20001` | `customer_id`, `destination_id`, `flight_id`, `status`, `check_in`, `check_out`, `nights`, `travelers`, `room_total`, `flight_total`, `total_price`, `payment{method, paid}` |
| `qa_history` | — | *(auto)* | `conv_id`, `role`, `content`, `trace`, `created_at` |

Relations : `reservations.customer_id → customers`, `reservations.destination_id
→ destinations`, `reservations.flight_id → flights`. Les dates sont des chaînes
`AAAA-MM-JJ`. Statuts de réservation : `pending`, `confirmed`, `completed`,
`cancelled`.

Index créés par `load_data.py` : `flights(origin, destination)`,
`reservations(customer_id)`, `customers(country)`, `destinations(region)`,
`destinations(category)`, `qa_history(conv_id, created_at)`.

## Utiliser le serveur MCP depuis VS Code / Copilot

Le serveur MCP est aussi utilisable seul, depuis un client compatible (VS Code
avec GitHub Copilot, Claude Code, Cursor…), sans passer par Flask. Détails et
liste des outils dans **[MCP-SERVER.md](MCP-SERVER.md)**.

Dans VS Code :

- le fichier `.vscode/mcp.json` décrit le serveur (voir plus haut) ;
- une connexion à **GitHub Copilot** est obligatoire, même pour utiliser un
  serveur MCP local ;
- à la première utilisation, autorisez la session courante à démarrer le
  serveur local (alerte de sécurité).

Ressources utiles :

- <https://dev-ai.fr/news-ai/mcp-serveur-python-tutoriel>
- <https://realpython.com/widgets/mcp-function-calling-relay/1784301949/>

## Points d'attention connus

Ces points ont été relevés en relisant le code. Ils ne bloquent pas le projet,
mais il vaut mieux les connaître.

1. **`groq` absent de `flask-app/requirements.txt`** — à installer à part
   (`pip install groq`).
2. **`scripts/load_data.py` charge la mauvaise source pour `destinations`** : le
   dictionnaire `COLLECTIONS` associe `"destinations"` à `"reservations.json"`.
   Résultat : la collection `destinations` contient les 24 réservations au lieu
   des 10 destinations. Correction (ligne `"destinations"` du dictionnaire) :
   ```python
   "destinations": "destinations.json"
   ```
3. **`load_data.py` sans `--reset` échoue au second lancement** (clés `_id`
   déjà présentes). Utilisez `--reset` pour recharger.
4. **`MONGODB_URI` pour l'historique** : `flask-app/app.py` appelle
   `load_dotenv()` *après* avoir importé `history.py`, qui crée sa connexion
   MongoDB dès l'import. Sans variable exportée dans le terminal, l'historique
   se connecte donc à `mongodb://localhost:27017` **sans identifiants** et échoue
   avec le MongoDB Docker authentifié. Contournement : exporter `MONGODB_URI` et
   `MONGODB_DB` dans le terminal avant `python app.py` (voir [Lancement](#lancement)).
5. **`.vscode/mcp.json` du dépôt** : il utilise les variables `MONGO_URI` /
   `MONGO_DB` (inconnues du serveur) et un chemin absolu propre à un poste. Le
   modèle `mcp.json` de la racine est correct : partez de celui-ci.
6. **Outils d'écriture toujours actifs** : `create_reservation`,
   `update_reservation_status` et `mark_reservation_paid` sont exposés quelle que
   soit la valeur de `ENABLE_WRITE_TOOLS` (le drapeau est lu par `config.py` mais
   pas encore utilisé par `server.py`). De même, `MCP_MAX_RESULTS` ne plafonne pas
   encore les résultats des outils : il sert uniquement à dimensionner la fenêtre
   d'historique côté Flask.
7. **Secrets** : `.env` est ignoré par git, mais reste présent dans une archive
   `.zip` du dossier. Ne partagez pas l'archive telle quelle, et changez
   `FLASK_SECRET_KEY` (la valeur par défaut est publique dans le code).
8. **Mode debug** : `app.run(debug=True)` est destiné au développement
   uniquement ; ne pas l'utiliser en production.
9. Le fichier `data/lo` (2 octets) est un résidu sans utilité et peut être supprimé.

## État d'avancement par rapport au cahier des charges

| Objectif | État |
|---|---|
| Interroger la base en langage naturel | ✅ Fait (chat + outils MCP) |
| Interface Flask avec chatbot | ✅ Fait (`/`, `/analysis`) |
| Fonctionnement local (Docker) ou Azure DocumentDB par simple changement de `MONGODB_URI` | ✅ Prévu par la configuration |
| Historique des conversations (`qa_history`) | ✅ Fait |
| Serveur MCP officiel `microsoft/documentdb-mcp` | ⚠️ Remplacé par un serveur MCP **métier sur mesure** (`serveur_mcp_local`) |
| Cache exact + cache par similarité vectorielle (seuil 0.97, embeddings, métriques de tokens) | ❌ Non implémenté — l'indicateur « Seuil de cache » de l'interface représente uniquement le remplissage de la fenêtre d'historique |
| Skills `documentdb-agent-kit` (indexation ESR, etc.) | ❌ Non mobilisées dans le code |
| Affichage de la requête MongoDB générée | ⚠️ Partiel : la trace des appels d'outils est stockée et disponible |

## Licence

Projet pédagogique AFPA.
