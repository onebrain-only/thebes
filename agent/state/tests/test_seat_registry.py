#!/usr/bin/env python3
"""Migration Slice 2 — provider-neutral Seat registry."""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, section, summary, repo_root, state_path  # noqa: E402

ROOT = repo_root()
sys.path.insert(0, state_path())
import roster, store, validate, view  # noqa: E402


def write_registry(root, seats):
    path = os.path.join(root, "seats.json")
    with open(path, "w") as fh:
        json.dump({"record_type": "seat_registry", "schema_version": 1,
                   "seats": {seat: {"role": role}
                             for seat, role in seats.items()}}, fh)
    return path


section("NEUTRAL REGISTRY — CANONICAL PARITY")
entries = roster.read()
fixture_path = os.path.join(ROOT, "agent", "execution", "tests", "fixtures",
                            "current_claude.json")
fixture = json.load(open(fixture_path, encoding="utf-8"))
expected_roles = {seat: row["role"] for seat, row in fixture["seats"].items()}
actual_roles = {seat: row["role"] for seat, row in entries.items()}
ok("exact 28-seat roster (content-2 added 2026-09-21, ux-engineer-2 added 2026-09-25, both within ceiling)",
   len(entries) == 28 and set(entries) == set(expected_roles))
ok("exact Seat to Role mapping", actual_roles == expected_roles)
ok("registry contains provider-neutral fields only",
   all(set(row) == {"seat_id", "role", "capability"} for row in entries.values()))
by_capability = roster.seats_by_capability()
ok("frontend and backend capacity inputs remain eight each",
   len(by_capability["frontend"]) == 8 and len(by_capability["backend"]) == 8)
ok("all other active capabilities retain one defined Seat, except content and ux-engineer at two",
   all(len(seats) == (2 if cap in ("content", "ux-engineer") else 1)
       for cap, seats in by_capability.items()
       if cap not in ("frontend", "backend")))
topology = json.load(open(os.path.join(ROOT, "agent", "state", "registry",
                                      "topology.json"), encoding="utf-8"))["capabilities"]
ok("topology defined-seat counts match the neutral registry",
   all(row["defined_seats"] == len(by_capability.get(capability, ()))
       for capability, row in topology.items()))
section("NEGATIVE — NO CLAUDE SOURCE REQUIRED")
tmp = tempfile.mkdtemp()
neutral = {"payments-3": "backend", "quality-specialist": "qa"}
registry_path = write_registry(tmp, neutral)
missing_bindings = os.path.join(tmp, "no-claude-bindings")
isolated = roster.read(registry_path)
ok("neutral registry reads with no .claude/bindings directory",
   set(isolated) == set(neutral))
ok("absence of a provider directory is not a universal registry error",
   not hasattr(roster, "CLAUDE_BINDINGS_DIR")
   and not hasattr(roster, "claude_compatibility"))

runtime = os.path.join(tmp, "runtime")
for kind in ("tasks", "dependencies", "interventions", "policies", "events",
             "learning", "coverage", "corrections"):
    os.makedirs(os.path.join(runtime, kind), exist_ok=True)
topology_path = os.path.join(tmp, "topology.json")
with open(topology_path, "w") as fh:
    json.dump({"record_type": "topology", "schema_version": 3,
               "capabilities": {"backend": {"defined_seats": 1},
                                "qa": {"defined_seats": 1}}}, fh)
store.RUNTIME = runtime
store.LOCKS = os.path.join(runtime, ".locks")
validate.RUNTIME = runtime
validate.SEATS_JSON = registry_path
view.SEATS_JSON = registry_path
view.CLAUDE_BINDINGS_DIR = missing_bindings
view.AGENTS_DIR = os.path.join(tmp, "no-generated-agents")
view.STATUS_DIR = os.path.join(tmp, "no-status")
view.NAMING_CSV = os.path.join(tmp, "no-naming.csv")
view.TELEMETRY_JSONL = os.path.join(tmp, "no-events.jsonl")
view.TOPOLOGY_JSON = topology_path
payload = view.build()
ok("Persistent State validation discovers Seats from the neutral registry",
   validate.seats() == set(neutral)
   and validate.seats_by_capability()["backend"] == ["payments-3"])
ok("Agent View discovers Seat identity and Role without Claude bindings",
   {row["seat_id"]: row["capability"] for row in payload["seats"]} == neutral)
ok("missing Claude display settings stay optional provider metadata",
   all(row["model"] is None and row["effort"] is None for row in payload["seats"]))


shutil.rmtree(tmp, ignore_errors=True)
sys.exit(summary())
