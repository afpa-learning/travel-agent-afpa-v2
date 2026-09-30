"""Serveur MCP local pour une base MongoDB de réservations de voyages.

Collections : flights, reservations, customers, destinations.

Lancement (stdio, pour un client MCP comme Claude Desktop) :
    python server.py

Prérequis : avoir peuplé la base au préalable avec load_data.py.
"""
import uuid
from datetime import date, datetime
from typing import Optional

from pymongo import MongoClient
from mcp.server.mcpserver import MCPServer

from config import MONGODB_URI, MONGODB_DB

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]

mcp = MCPServer("travel-booking")

VALID_STATUSES = {"pending", "confirmed", "completed", "cancelled"}


# --------------------------------------------------------------------------
# Helpers internes
# --------------------------------------------------------------------------
def _parse_date(value: str, field_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field_name} doit être au format AAAA-MM-JJ (reçu : {value!r})") from exc


def _next_reservation_id() -> str:
    """Génère le prochain id RES-XXXXX en se basant sur le plus grand id existant."""
    last = db.reservations.find_one(sort=[("_id", -1)])
    if last and last["_id"].startswith("RES-") and last["_id"][4:].isdigit():
        next_num = int(last["_id"][4:]) + 1
    else:
        next_num = 20001
    return f"RES-{next_num}"


# --------------------------------------------------------------------------
# Outils : vols (flights)
# --------------------------------------------------------------------------
@mcp.tool()
def search_flights(
    origin: Optional[str] = None,
    destination: Optional[str] = None,
    airline: Optional[str] = None,
    cabin: Optional[str] = None,
    max_fare: Optional[float] = None,
) -> list[dict]:
    """Recherche des vols. Tous les paramètres sont optionnels et combinables.

    origin / destination : codes aéroport IATA (ex: 'CDG', 'JFK').
    airline : recherche partielle insensible à la casse (ex: 'air france').
    cabin : 'economy' ou 'business'.
    max_fare : tarif de base maximum (EUR).
    """
    query: dict = {}
    if origin:
        query["origin"] = origin.upper()
    if destination:
        query["destination"] = destination.upper()
    if airline:
        query["airline"] = {"$regex": airline, "$options": "i"}
    if cabin:
        query["cabin"] = cabin.lower()
    if max_fare is not None:
        query["base_fare"] = {"$lte": max_fare}
    return list(db.flights.find(query))


@mcp.tool()
def get_flight(flight_id: str) -> Optional[dict]:
    """Récupère un vol par son identifiant (ex: 'FL-AF1080')."""
    return db.flights.find_one({"_id": flight_id})


# --------------------------------------------------------------------------
# Outils : destinations
# --------------------------------------------------------------------------
@mcp.tool()
def search_destinations(
    region: Optional[str] = None,
    category: Optional[str] = None,
    tag: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_nightly_rate: Optional[float] = None,
) -> list[dict]:
    """Recherche des destinations. Tous les paramètres sont optionnels et combinables.

    region : ex 'Europe', 'Asia', 'North America'...
    category : ex 'city-break', 'beach', 'resort', 'adventure'.
    tag : un tag présent dans la liste tags (ex: 'food', 'beach', 'luxury').
    min_rating : note minimale (0-5).
    max_nightly_rate : tarif moyen par nuit maximum (EUR).
    """
    query: dict = {}
    if region:
        query["region"] = {"$regex": f"^{region}$", "$options": "i"}
    if category:
        query["category"] = category.lower()
    if tag:
        query["tags"] = tag.lower()
    if min_rating is not None:
        query["rating"] = {"$gte": min_rating}
    if max_nightly_rate is not None:
        query.setdefault("avg_nightly_rate", {})["$lte"] = max_nightly_rate
    return list(db.destinations.find(query))


@mcp.tool()
def get_destination(destination_id: str) -> Optional[dict]:
    """Récupère une destination par son identifiant (ex: 'DEST-ROM')."""
    return db.destinations.find_one({"_id": destination_id})


# --------------------------------------------------------------------------
# Outils : clients (customers)
# --------------------------------------------------------------------------
@mcp.tool()
def search_customers(
    country: Optional[str] = None,
    loyalty_tier: Optional[str] = None,
    min_loyalty_points: Optional[int] = None,
) -> list[dict]:
    """Recherche des clients. Tous les paramètres sont optionnels et combinables.

    loyalty_tier : 'bronze', 'silver' ou 'gold'.
    """
    query: dict = {}
    if country:
        query["country"] = {"$regex": f"^{country}$", "$options": "i"}
    if loyalty_tier:
        query["loyalty_tier"] = loyalty_tier.lower()
    if min_loyalty_points is not None:
        query["loyalty_points"] = {"$gte": min_loyalty_points}
    return list(db.customers.find(query))


@mcp.tool()
def get_customer(customer_id: str) -> Optional[dict]:
    """Récupère un client par son identifiant (ex: 'CUST-1001')."""
    return db.customers.find_one({"_id": customer_id})


# --------------------------------------------------------------------------
# Outils : réservations (reservations) — lecture
# --------------------------------------------------------------------------
@mcp.tool()
def search_reservations(
    customer_id: Optional[str] = None,
    destination_id: Optional[str] = None,
    status: Optional[str] = None,
    paid: Optional[bool] = None,
    min_total_price: Optional[float] = None,
    max_total_price: Optional[float] = None,
) -> list[dict]:
    """Recherche des réservations. Tous les paramètres sont optionnels et combinables.

    status : 'pending', 'confirmed', 'completed' ou 'cancelled'.
    """
    query: dict = {}
    if customer_id:
        query["customer_id"] = customer_id
    if destination_id:
        query["destination_id"] = destination_id
    if status:
        if status.lower() not in VALID_STATUSES:
            raise ValueError(f"status invalide : {status!r}. Valeurs possibles : {sorted(VALID_STATUSES)}")
        query["status"] = status.lower()
    if paid is not None:
        query["payment.paid"] = paid
    if min_total_price is not None or max_total_price is not None:
        price_filter: dict = {}
        if min_total_price is not None:
            price_filter["$gte"] = min_total_price
        if max_total_price is not None:
            price_filter["$lte"] = max_total_price
        query["total_price"] = price_filter
    return list(db.reservations.find(query))


@mcp.tool()
def get_reservation(reservation_id: str) -> Optional[dict]:
    """Récupère une réservation par son identifiant (ex: 'RES-20001')."""
    return db.reservations.find_one({"_id": reservation_id})


# --------------------------------------------------------------------------
# Outils : réservations — écriture
# --------------------------------------------------------------------------
@mcp.tool()
def create_reservation(
    customer_id: str,
    destination_id: str,
    flight_id: str,
    check_in: str,
    check_out: str,
    travelers: int,
    payment_method: str,
) -> dict:
    """Crée une nouvelle réservation (statut initial : 'pending', non payée).

    check_in / check_out : dates au format AAAA-MM-JJ.
    Les totaux (room_total, flight_total, total_price) sont calculés
    automatiquement à partir du tarif du vol et du tarif moyen/nuit de la
    destination.
    """
    customer = db.customers.find_one({"_id": customer_id})
    if not customer:
        raise ValueError(f"Client inconnu : {customer_id!r}")

    destination = db.destinations.find_one({"_id": destination_id})
    if not destination:
        raise ValueError(f"Destination inconnue : {destination_id!r}")

    flight = db.flights.find_one({"_id": flight_id})
    if not flight:
        raise ValueError(f"Vol inconnu : {flight_id!r}")

    if travelers < 1:
        raise ValueError("travelers doit être >= 1")

    d_in = _parse_date(check_in, "check_in")
    d_out = _parse_date(check_out, "check_out")
    if d_out <= d_in:
        raise ValueError("check_out doit être postérieur à check_in")
    nights = (d_out - d_in).days

    room_total = destination["avg_nightly_rate"] * nights * travelers
    flight_total = flight["base_fare"] * travelers
    total_price = room_total + flight_total

    reservation = {
        "_id": _next_reservation_id(),
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "destination_id": destination_id,
        "destination_city": destination["city"],
        "flight_id": flight_id,
        "status": "pending",
        "booking_date": date.today().isoformat(),
        "check_in": check_in,
        "check_out": check_out,
        "nights": nights,
        "travelers": travelers,
        "room_total": room_total,
        "flight_total": flight_total,
        "total_price": total_price,
        "currency": "EUR",
        "payment": {"method": payment_method.lower(), "paid": False},
    }
    db.reservations.insert_one(reservation)
    return reservation


@mcp.tool()
def update_reservation_status(reservation_id: str, status: str) -> dict:
    """Change le statut d'une réservation existante.

    status : 'pending', 'confirmed', 'completed' ou 'cancelled'.
    """
    status = status.lower()
    if status not in VALID_STATUSES:
        raise ValueError(f"status invalide : {status!r}. Valeurs possibles : {sorted(VALID_STATUSES)}")

    result = db.reservations.find_one_and_update(
        {"_id": reservation_id},
        {"$set": {"status": status}},
        return_document=True,
    )
    if result is None:
        raise ValueError(f"Réservation inconnue : {reservation_id!r}")
    return result


@mcp.tool()
def mark_reservation_paid(reservation_id: str, paid: bool = True) -> dict:
    """Marque une réservation comme payée (ou non payée)."""
    result = db.reservations.find_one_and_update(
        {"_id": reservation_id},
        {"$set": {"payment.paid": paid}},
        return_document=True,
    )
    if result is None:
        raise ValueError(f"Réservation inconnue : {reservation_id!r}")
    return result


# --------------------------------------------------------------------------
# Outils : analyses / agrégations
# --------------------------------------------------------------------------
@mcp.tool()
def customer_spending_summary(customer_id: str) -> dict:
    """Résumé des dépenses d'un client : total dépensé (hors annulées),
    nombre de réservations par statut, et destinations visitées.
    """
    customer = db.customers.find_one({"_id": customer_id})
    if not customer:
        raise ValueError(f"Client inconnu : {customer_id!r}")

    reservations = list(db.reservations.find({"customer_id": customer_id}))

    total_spent = sum(r["total_price"] for r in reservations if r["status"] != "cancelled")
    by_status: dict[str, int] = {}
    for r in reservations:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
    destinations = sorted({r["destination_city"] for r in reservations})

    return {
        "customer_id": customer_id,
        "customer_name": customer["name"],
        "loyalty_tier": customer["loyalty_tier"],
        "total_reservations": len(reservations),
        "reservations_by_status": by_status,
        "total_spent_eur": total_spent,
        "destinations_visited": destinations,
    }


@mcp.tool()
def destination_popularity(top_n: int = 5) -> list[dict]:
    """Classement des destinations par nombre de réservations non annulées."""
    pipeline = [
        {"$match": {"status": {"$ne": "cancelled"}}},
        {"$group": {
            "_id": "$destination_city",
            "reservation_count": {"$sum": 1},
            "total_revenue_eur": {"$sum": "$total_price"},
        }},
        {"$sort": {"reservation_count": -1}},
        {"$limit": top_n},
    ]
    results = list(db.reservations.aggregate(pipeline))
    return [
        {
            "destination_city": r["_id"],
            "reservation_count": r["reservation_count"],
            "total_revenue_eur": r["total_revenue_eur"],
        }
        for r in results
    ]


@mcp.tool()
def db_stats() -> dict:
    """Nombre de documents dans chaque collection (utile pour vérifier la connexion)."""
    return {
        "flights": db.flights.count_documents({}),
        "reservations": db.reservations.count_documents({}),
        "customers": db.customers.count_documents({}),
        "destinations": db.destinations.count_documents({}),
    }


if __name__ == "__main__":
    mcp.run()
