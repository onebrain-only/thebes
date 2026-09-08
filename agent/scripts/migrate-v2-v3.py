#!/usr/bin/env python3
"""One narrow, idempotent v2 -> v3 runtime migration. Not a framework.

Wave 6 adds two task fields — `ownership` and `surfaces` — and bumps the schema. The
real runtime holds seven task records and one dependency edge, so a generic migration
engine would be more machinery than the thing it migrates.

WHAT IT WILL NOT DO

  It invents nothing. Ownership starts null on every record, including records that
  carry executor_evidence: Wave 5 evidence says a seat DID work, not that a seat
  currently OWNS the slot, and quietly promoting one into the other would manufacture
  ownership nobody claimed. Surfaces start NULL — meaning "not assessed" — because a
  v2 record proves nothing about whether anyone looked; writing [] would assert an
  assessment that never happened. Work Effort, characteristics, reviewers and routes are copied untouched.

Idempotent: re-running is a no-op on records already at v3.

    python3 agent/scripts/migrate-v2-v3.py [--dry-run]
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "agent", "state"))
import store, validate                                  # noqa: E402

DRY = "--dry-run" in sys.argv
TARGET = 3


def migrate():
    changed, skipped, errors = [], [], []
    for kind in ("task", "dependency", "routing", "exception", "intervention"):
        for rec in store.read_all(kind):
            rid = rec.get(store._id_field(kind))
            if rec.get("schema_version") == TARGET:
                skipped.append("%s/%s" % (kind, rid)); continue
            new = dict(rec)
            new["schema_version"] = TARGET
            if kind == "task":
                # setdefault, never overwrite: a field that already exists is a fact.
                new.setdefault("ownership", None)
                # surfaces defaults to NULL, not []. A v2 record carries no evidence
                # that surface scope was ever assessed, and [] would claim it was —
                # which is how unassessed work came to look like "collides with
                # nothing". setdefault leaves a legitimate v3 [] untouched.
                new.setdefault("surfaces", None)
                if new.get("record_type") == "container":
                    new["ownership"] = None
            errs = [e for e in validate.validate_record(kind, new) if " WARN " not in e]
            if errs:
                errors.append("%s/%s: %s" % (kind, rid, "; ".join(errs))); continue
            if not DRY:
                store._atomic_write(store.path_for(kind, rid), new)
            changed.append("%s/%s" % (kind, rid))
    return changed, skipped, errors


if __name__ == "__main__":
    ch, sk, er = migrate()
    print(("DRY RUN — " if DRY else "") + "migrated: %d   already v%d: %d   errors: %d"
          % (len(ch), TARGET, len(sk), len(er)))
    for c in ch: print("  ->", c)
    for s in sk: print("  ==", s, "(already v%d)" % TARGET)
    for e in er: print("  !!", e)
    sys.exit(1 if er else 0)
