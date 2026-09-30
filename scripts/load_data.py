"""Charge les fichiers data/*.json dans MongoDB.

Usage :
    python scripts/load_data.py            # peuple la base
    python scripts/load_data.py --reset    # peuple la base (vide chaque collection avant)
    python scripts/load_data.py --uri "mongodb://localhost:27017" --db traveldb

"""
import argparse
import json
import sys
import os
from pathlib import Path

from pymongo import MongoClient, ASCENDING

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

COLLECTIONS = {
    "flights": "flights.json", 
    "reservations": "reservations.json", 
    "customers": "customers.json", 
    "destinations": "reservations.json"
}

# Index utiles pour accélérer les requêtes les plus fréquentes du serveur MCP.
INDEXES = {
    "flights": [("origin", ASCENDING), ("destination", ASCENDING)],
    "reservations": [("customer_id", ASCENDING)],
    "customers": [("country", ASCENDING)],
    "destinations": [("region", ASCENDING), ("category", ASCENDING)],
}


def load_json(name: str) -> list[dict]:
    path = DATA_DIR / f"{name}"
    if not path.exists():
        print(f"[!] Fichier introuvable : {path}", file=sys.stderr)
        sys.exit(1)
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Charge la base de données exemple de l'agent de voyage")
    parser.add_argument(
        "--uri",
        default=os.environ.get("MONGODB_URI", "mongodb://localhost:27017"),
        help="Chaîne de connexion MongoDB/DocumentDB (défaut : variable MONGODB_URI ou mongodb://localhost:27017)",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("MONGODB_DB", "traveldb"),
        help="Nom de la base de données (défaut : traveldb)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Vide les collections avant de les recharger",
    )
    args = parser.parse_args()

    print(f"Connexion à {args.uri} ...")
    client = MongoClient(args.uri, serverSelectionTimeoutMS=8000)
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"Impossible de joindre le serveur MongoDB/DocumentDB : {exc}")
        sys.exit(1)

    db = client[args.db]
    print(f"Base cible : {args.db}\n")

    for coll_name, filename in COLLECTIONS.items():
        docs = load_json(filename)
        collection = db[coll_name]

        if args.reset:
            deleted = collection.delete_many({}).deleted_count
            if deleted:
                print(f"  - {coll_name}: {deleted} document(s) supprimé(s) avant rechargement")

        if not docs:
            continue

        result = collection.insert_many(docs)

        for field, direction in INDEXES.get(coll_name, []):
            collection.create_index([(field, direction)])

        print(f"  - {coll_name}: {len(result.inserted_ids)} document(s) inséré(s)")

    # Création de l'historique de conversation
    qa_history = db["qa_history"]

    # Index pour trier/filtrer efficacement par conversation
    qa_history.create_index([("conv_id", ASCENDING), ("created_at", ASCENDING)])

    print("\nDécompte final des documents :")
    for coll_name in COLLECTIONS:
        count = db[coll_name].count_documents({})
        print(f"  {coll_name}: {count}")

    print("\nTerminé.")


if __name__ == "__main__":
    main()
