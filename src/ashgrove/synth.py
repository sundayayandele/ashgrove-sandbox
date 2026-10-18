"""Deterministic synthetic data. Every person, order and token here is invented.

All emails use the reserved example.test domain and all phone numbers use
ranges reserved for fiction, so nothing can reach a real person.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

# The sandbox clock: data is generated relative to this date so every run is identical.
ANCHOR = datetime(2026, 9, 30, 12, 0, tzinfo=timezone.utc)

NAMES = {
    "NL": (
        ["Daan", "Sanne", "Lars", "Femke", "Bram", "Noor", "Joris", "Lotte"],
        ["de Vries", "Jansen", "Bakker", "Visser", "Smit", "Mulder"],
    ),
    "NG": (
        ["Chinedu", "Amaka", "Tunde", "Ngozi", "Emeka", "Funmi", "Ifeoma", "Segun"],
        ["Okafor", "Adeyemi", "Balogun", "Eze", "Nwosu", "Ogunleye"],
    ),
    "ZA": (
        ["Thabo", "Lerato", "Sipho", "Naledi", "Pieter", "Anele", "Zanele", "Johan"],
        ["Nkosi", "Dlamini", "van der Merwe", "Mokoena", "Botha", "Khumalo"],
    ),
    "GB": (
        ["Oliver", "Amelia", "Harry", "Isla", "Jack", "Grace", "Leo", "Freya"],
        ["Smith", "Patel", "Jones", "Taylor", "Brown", "Khan"],
    ),
    "DE": (
        ["Lukas", "Mia", "Felix", "Hannah", "Jonas", "Lea", "Paul", "Emma"],
        ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Wagner"],
    ),
}
COUNTRIES = list(NAMES)

PRODUCTS = [
    ("SKU-1001", "Wireless headset", 79.00),
    ("SKU-1002", "Standing desk", 420.00),
    ("SKU-1003", "USB-C hub", 35.50),
    ("SKU-1004", "27-inch monitor", 289.00),
    ("SKU-1005", "Ergonomic chair", 349.00),
    ("SKU-1006", "Mechanical keyboard", 119.00),
    ("SKU-1007", "Webcam HD", 64.90),
    ("SKU-1008", "Desk lamp", 42.00),
    ("SKU-1009", "Laptop stand", 39.95),
    ("SKU-1010", "Noise-cancelling earbuds", 159.00),
]


def person(rng: random.Random, n: int) -> dict:
    country = rng.choice(COUNTRIES)
    first, last = rng.choice(NAMES[country][0]), rng.choice(NAMES[country][1])
    slug = f"{first}.{last}".lower().replace(" ", "").replace("ü", "ue")
    return {
        "name": f"{first} {last}",
        "email": f"{slug}.{n}@example.test",
        "phone": f"+31 6 9999 {n:04d}",  # fictional range, never dialled
        "country": country,
    }


def days_ago(rng: random.Random, lo: int, hi: int) -> datetime:
    return ANCHOR - timedelta(days=rng.randint(lo, hi), minutes=rng.randint(0, 1439))


def iso(dt: datetime | None) -> str | None:
    return dt.replace(microsecond=0).isoformat() if dt else None
