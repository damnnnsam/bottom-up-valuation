"""
Client folder management.

Each client is a folder under data/clients/ with:
  meta.json      name, industry, notes, created date
  states/        one JSON per state
  comparisons/   one JSON per comparison
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date

from store.backend import read_json, write_json, list_dir


@dataclass
class ClientMeta:
    name: str
    industry: str = ""
    notes: str = ""
    created: str = ""


def list_clients() -> list[tuple[str, ClientMeta]]:
    """Return list of (slug, ClientMeta) for all clients."""
    clients = []
    for slug in list_dir(""):
        meta = load_client_meta(slug)
        if meta is not None:
            clients.append((slug, meta))
    return clients


def load_client_meta(slug: str) -> ClientMeta | None:
    """Load meta.json for a client. Returns None if not found."""
    data = read_json(f"{slug}/meta.json")
    if data is None:
        return None
    return ClientMeta(
        name=data.get("name", slug),
        industry=data.get("industry", ""),
        notes=data.get("notes", ""),
        created=data.get("created", ""),
    )


def save_client_meta(slug: str, meta: ClientMeta) -> None:
    """Write meta.json for a client."""
    write_json(f"{slug}/meta.json", asdict(meta),
               message=f"Update client metadata: {meta.name}")


def create_client(slug: str, name: str, industry: str = "", notes: str = "") -> ClientMeta:
    meta = ClientMeta(name=name, industry=industry, notes=notes, created=str(date.today()))
    write_json(f"{slug}/meta.json", asdict(meta), message=f"Create client: {name}")
    return meta


def delete_client(slug: str) -> None:
    """Delete a client with all its states and comparisons."""
    from store.backend import delete_file
    for sub in ("states", "comparisons"):
        for name in list_dir(f"{slug}/{sub}"):
            delete_file(f"{slug}/{sub}/{name}", message=f"Delete {sub[:-1]} {name}")
    delete_file(f"{slug}/meta.json", message=f"Delete client {slug}")
