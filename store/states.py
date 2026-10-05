"""
Storage for event-based states and comparisons.

Layout (relative to data/clients/):
    <client>/states/<state_id>.json
    <client>/comparisons/<comparison_id>.json
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import uuid

from store.backend import read_json, write_json, list_dir, delete_file
from engine.events import State, state_to_dict, state_from_dict, example_higher_edtech


@dataclass
class Comparison:
    title: str
    state_ids: list[str] = field(default_factory=list)
    description: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:10])
    compare_day: int = 1100
    intervention_label: str = ""  # e.g. "QA AI"; used in the claim sentence
    target_label: str = ""  # e.g. "higher education companies"
    created: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))


# ── States ────────────────────────────────────────────────────────────

def list_states(client: str) -> list[State]:
    out = []
    for name in list_dir(f"{client}/states"):
        if name.endswith(".json"):
            d = read_json(f"{client}/states/{name}")
            if d:
                out.append(state_from_dict(d))
    out.sort(key=lambda s: s.created)
    return out


def load_state(client: str, state_id: str) -> State | None:
    d = read_json(f"{client}/states/{state_id}.json")
    return state_from_dict(d) if d else None


def save_state(client: str, s: State) -> None:
    write_json(f"{client}/states/{s.id}.json", state_to_dict(s), message=f"Save state {s.title}")


def delete_state(client: str, state_id: str) -> None:
    delete_file(f"{client}/states/{state_id}.json", message=f"Delete state {state_id}")


# ── Comparisons ───────────────────────────────────────────────────────

def list_comparisons(client: str) -> list[Comparison]:
    out = []
    for name in list_dir(f"{client}/comparisons"):
        if name.endswith(".json"):
            d = read_json(f"{client}/comparisons/{name}")
            if d:
                out.append(Comparison(**{k: v for k, v in d.items() if k in Comparison.__dataclass_fields__}))
    out.sort(key=lambda c: c.created)
    return out


def load_comparison(client: str, cid: str) -> Comparison | None:
    d = read_json(f"{client}/comparisons/{cid}.json")
    if not d:
        return None
    return Comparison(**{k: v for k, v in d.items() if k in Comparison.__dataclass_fields__})


def save_comparison(client: str, c: Comparison) -> None:
    write_json(f"{client}/comparisons/{c.id}.json", asdict(c), message=f"Save comparison {c.title}")


def delete_comparison(client: str, cid: str) -> None:
    delete_file(f"{client}/comparisons/{cid}.json", message=f"Delete comparison {cid}")


# ── Seeding ───────────────────────────────────────────────────────────

def seed_example(client: str) -> Comparison:
    before, after = example_higher_edtech()
    save_state(client, before)
    save_state(client, after)
    c = Comparison(
        title="Higher EdTech - Comparison",
        state_ids=[before.id, after.id],
        description="QA AI lowers bug count; fewer bugs lower churn and CPM after 180 days.",
        compare_day=1100,
        intervention_label="QA AI",
        target_label="higher education companies",
    )
    save_comparison(client, c)
    return c
