"""The team (execution island) registry. Stdlib only; validate.py imports it.

A team is not a seat and not a Role: it is one persistent Claude session that
receives a request from the Codex Listener, runs the seats it needs as
subagents, and returns one report. Seats stay the shared pool; a team holds a
seat only while a dispatch is open (`seat_reservation` in Persistent State).

  read()        {team_id: {"number": n, "display_name": ...}}
  is_team(id)   True for a declared team id
"""
import json
import os
import re


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TEAMS_JSON = os.path.join(ROOT, "agent", "state", "registry", "teams.json")
_ID = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TeamRegistryError(ValueError):
    pass


def read(path=TEAMS_JSON):
    try:
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
    except (OSError, ValueError) as exc:
        raise TeamRegistryError("cannot read %s: %s" % (path, exc))
    if doc.get("record_type") != "team_registry" or not isinstance(doc.get("teams"), dict):
        raise TeamRegistryError("%s is not a team_registry document" % path)
    teams = {}
    for team_id, entry in doc["teams"].items():
        if not _ID.match(team_id) or not isinstance(entry, dict):
            raise TeamRegistryError("invalid team entry %r" % team_id)
        if not isinstance(entry.get("number"), int) or not entry.get("display_name"):
            raise TeamRegistryError("team %r needs an integer number and a display_name" % team_id)
        kind = entry.get("kind", "team")
        if kind not in ("team", "orchestrator"):
            raise TeamRegistryError("team %r has unknown kind %r" % (team_id, kind))
        teams[team_id] = {"number": entry["number"], "display_name": entry["display_name"],
                          "kind": kind}
    return teams


def is_team(team_id, path=TEAMS_JSON):
    """A declared island of either kind (delivery team or the orchestrator)."""
    try:
        return team_id in read(path)
    except TeamRegistryError:
        return False


def is_orchestrator(team_id, path=TEAMS_JSON):
    try:
        return read(path).get(team_id, {}).get("kind") == "orchestrator"
    except TeamRegistryError:
        return False


def delivery_teams(path=TEAMS_JSON):
    """The islands Codex may send WORK to — never the orchestrator."""
    return {t: e for t, e in read(path).items() if e["kind"] == "team"}


ORCHESTRATOR_ID = "orchestrator"
