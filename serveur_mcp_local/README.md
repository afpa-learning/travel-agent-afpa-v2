# Travel Booking — Serveur MCP local (Python + MongoDB)

Serveur MCP local exposant 4 collections MongoDB :
- **flights** (vols)
- **reservations** (réservations)
- **customers** (clients)
- **destinations** (destinations)

## Structure

```
serveur_mcp_local/
  config.py       # URI Mongo / nom de la base (surchargeable par variables d'env)
  load_data.py       # charge data/*.json dans MongoDB
  server.py        # le serveur MCP (outils exposés)
  data/
    flights.json
    reservations.json
    customers.json
    destinations.json
  requirements.txt
```

## Installation

1. **MongoDB doit tourner localement** (ou accessible via une URI). Sur la plupart des systèmes :
   ```bash
   # macOS (Homebrew)
   brew tap mongodb/brew && brew install mongodb-community && brew services start mongodb-community

   # Linux (Debian/Ubuntu) — suivre la doc officielle MongoDB pour le dépôt apt
   # https://www.mongodb.com/docs/manual/administration/install-on-linux/
   ```
   Vérifie que `mongod` écoute bien sur `localhost:27017` (par défaut).

2. **Dépendances Python** :
   ```bash
   cd serveur_mcp_local
   pip install -r requirements.txt
   ```

   > Le fichier pin `mcp==1.9.4` intentionnellement : les versions `mcp>=2.0`
   > renomment `FastMCP` en `MCPServer` et changent l'API. Si tu veux utiliser
   > `mcp 2.x`, il faudra adapter `server.py` en conséquence.

3. **Peupler la base** :
   ```bash
   python load_data.py
   ```
   Ce script charge chaque collection à partir de `data/*.json` —
   

## Configuration

Variables d'environnement (ou fichier `.env` à la racine du projet) :

| Variable | Défaut | Description |
|---|---|---|
| `MONGO_URI` | `mongodb://localhost:27017` | URI de connexion MongoDB |
| `MONGO_DB` | `travel_booking` | Nom de la base de données |
| `MCP_MAX_RESULTS` | `20` | Plafond de résultats par outil |
| `ENABLE_WRITE_TOOLS` | `false` | Activer outils en écriture |
| `ENABLE_MANAGEMENT_TOOLS` | `false` | Réservé à une évolution future (ex. création d'index) |

## Lancer le serveur

En autonome (mode stdio, pour tester ou déboguer) :
```bash
python server.py
```

### Configuration dans un client agent

Utiliser le fichier `mcp.json` fourni à la racine (à adapter selon le client :
certains attendent ce fichier sous un autre nom ou dans un autre emplacement,
par ex. `.cursor/mcp.json` pour Cursor ou `.vscode/mcp.json` pour VS Code).

Modifier dans ce fichier le chemin du projet en lieu et place de "project_root_path"

## Outils exposés

### Lecture
- `search_flights(origin?, destination?, airline?, cabin?, max_fare?)`
- `get_flight(flight_id)`
- `search_destinations(region?, category?, tag?, min_rating?, max_nightly_rate?)`
- `get_destination(destination_id)`
- `search_customers(country?, loyalty_tier?, min_loyalty_points?)`
- `get_customer(customer_id)`
- `search_reservations(customer_id?, destination_id?, status?, paid?, min_total_price?, max_total_price?)`
- `get_reservation(reservation_id)`

### Écriture
- `create_reservation(customer_id, destination_id, flight_id, check_in, check_out, travelers, payment_method)`
  — calcule automatiquement `nights`, `room_total`, `flight_total`, `total_price` ;
  statut initial `pending`, non payée.
- `update_reservation_status(reservation_id, status)` — `pending` / `confirmed` / `completed` / `cancelled`
- `mark_reservation_paid(reservation_id, paid=True)`

### Analyses
- `customer_spending_summary(customer_id)` — total dépensé, réservations par statut, destinations visitées
- `destination_popularity(top_n=5)` — classement des destinations par nombre de réservations (hors annulées)
- `db_stats()` — nombre de documents par collection (utile pour vérifier la connexion)

## Notes de conception

- Les `_id` restent les identifiants métier d'origine (`FL-AF1080`, `CUST-1001`,
  `DEST-ROM`, `RES-20001`) plutôt que des `ObjectId` Mongo générés — cohérent
  avec les fichiers JSON fournis, et plus lisible dans les réponses des outils.
- `create_reservation` génère le prochain id `RES-XXXXX` en se basant sur le
  plus grand id existant en base ; en environnement concurrent, il faudrait
  remplacer ça par un compteur atomique ou un `ObjectId`/UUID.
- Des index sont créés par `seed_db.py` sur les champs les plus filtrés
  (`origin`/`destination` sur flights, `customer_id` sur reservations, etc.)
  pour garder les recherches rapides même si les collections grossissent.
