#!/usr/bin/env python3
"""Wave 8 — advisory role learning.

A learning record is a RECOMMENDATION WITH EVIDENCE. It is not authority, and it
does not become authority by existing.

  telemetry -> retrospective -> learning candidate -> explicit authorised decision
  -> possible future system change

Never `learning -> automatic change`. This module has no write path into task
records, prompts, bindings or governance, and that is asserted by tests rather than
promised here: it imports `store` for its own record kind and nothing else.

THE SUBJECT MAY BE AN EMPLOYEE OR A DOMAIN
  Learning is a professional record, not a score. It may describe an employee's
  own adaptation or a recurring capability/project/product/workflow pattern. It
  never ranks or compares employees.

RUNTIME MAY ONLY PROPOSE
  Automatic analysis creates `candidate` records and nothing else. Moving one to
  accepted, rejected, superseded or contradicted requires `decide()`, an explicitly
  authorised act by the accountable domain owner. Nothing in Agent View can call it.

HISTORY IS NEVER OVERWRITTEN
  Superseding or contradicting a record leaves it, its evidence and its status in
  place, and links the newer record back to it. No knowledge graph — one pointer.

Stdlib only.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import store                                            # noqa: E402

SCOPE_TYPES = ("employee", "capability", "project", "product", "workflow", "organization")
STATUSES = ("candidate", "accepted", "rejected", "superseded", "contradicted")
# Runtime analysis may create only this. Everything else needs a human decision.
RUNTIME_STATUS = "candidate"


def propose(scope_type, scope_id, pattern, evidence_refs, occurrences,
            strength, recommendation, first_observed=None, last_observed=None):
    """Create a CANDIDATE learning record. The only status runtime may produce.

    Refuses without evidence: a recommendation nobody can trace is not actionable,
    and an unactionable recommendation in a durable store is just noise that later
    reads as fact.
    """
    if scope_type not in SCOPE_TYPES:
        raise store.StateError("unknown learning scope_type %r" % scope_type)
    refs = [r for r in (evidence_refs or []) if r]
    if not refs:
        raise store.StateError("a learning record requires evidence_refs — an "
                               "untraceable recommendation is not advice, it is noise")
    if not recommendation:
        raise store.StateError("a learning record requires a recommendation")
    if not isinstance(occurrences, int) or occurrences < 1:
        raise store.StateError("occurrences must be a positive integer")
    rec = {
        "record_type": "learning", "scope_type": scope_type, "scope_id": scope_id,
        "pattern": pattern, "evidence_refs": sorted(set(refs)),
        "occurrences": occurrences, "strength": strength,
        "recommendation": recommendation, "status": RUNTIME_STATUS,
        "first_observed": first_observed or store.now(),
        "last_observed": last_observed or store.now(),
        "supersedes": None, "decided_by": None, "decided_at": None,
        "advisory": True,
        "authority": "NONE — advisory until an authorised decision adopts it",
    }
    return store.create("learning", rec)


def _scope_owner(record):
    scope_type, scope_id = record.get("scope_type"), record.get("scope_id")
    return {
        "employee": scope_id,
        "capability": scope_id,
        "project": "po",
        "product": "cpo",
        "workflow": "analyst",
        "organization": "ceo",
    }.get(scope_type)


def _actor_owns(record, actor):
    owner = _scope_owner(record)
    if actor == owner:
        return True
    try:
        from agent.organization.registry import employee_profile
        return employee_profile(actor)["role"] == owner
    except (ValueError, KeyError):
        return False


def decide(learning_id, expected_revision, status, actor, reason_ref,
           supersedes=None, implementation_hook=None, classification=None):
    """Move a candidate to a decided status. AUTHORISED ACT ONLY.

    Runtime analysis cannot reach this: `propose` hard-codes `candidate`, and every
    other status arrives only through here, only from the accountable domain owner,
    and only with a reason. History is preserved — the superseded record keeps its own status,
    evidence and text, and the new record points back at it.
    """
    if status not in STATUSES or status == RUNTIME_STATUS:
        raise store.StateError("decide() sets a DECIDED status (%s), not %r"
                               % ("/".join(s for s in STATUSES if s != RUNTIME_STATUS),
                                  status))
    record = store.read("learning", learning_id)
    if record is None:
        raise store.StateError("learning %s does not exist" % learning_id)
    if not _actor_owns(record, actor):
        raise store.StateError("unauthorised-learning-decision: %r is not the owner "
                               "of %s/%s learning"
                               % (actor, record.get("scope_type"), record.get("scope_id")))
    if not reason_ref:
        raise store.StateError("reason_ref is required — a decision records why")
    if status == "accepted" and not implementation_hook and classification != "informational":
        raise store.StateError("accepted learning requires an implementation_hook or "
                               "classification='informational'")
    changes = {"status": status, "decided_by": actor, "decided_at": store.now(),
               "reason_ref": reason_ref, "implementation_hook": implementation_hook,
               "classification": classification}
    if supersedes:
        changes["supersedes"] = supersedes
    return store.update("learning", learning_id, expected_revision, changes)


def candidates(scope_type=None, scope_id=None):
    out = [r for r in store.read_all("learning")
           if (scope_type is None or r.get("scope_type") == scope_type)
           and (scope_id is None or r.get("scope_id") == scope_id)]
    return sorted(out, key=lambda r: (r.get("scope_id") or "", r.get("learning_id") or ""))


def from_retrospective(retro, scope_type="capability"):
    """Turn retrospective PATTERNS into candidates. Patterns only — never facts.

    A single observation cannot arrive here, because `retrospective.pattern` refuses
    to construct below two distinct occurrences. So the threshold is enforced once,
    where the evidence is, rather than repeated as a rule everyone must remember.
    """
    made = []
    for p in (retro or {}).get("patterns") or []:
        scope_id = p.get("group") or retro.get("scope_id")
        made.append(propose(
            scope_type=scope_type if scope_type in SCOPE_TYPES else "workflow",
            scope_id=str(scope_id), pattern=p.get("statement"),
            evidence_refs=p.get("evidence_refs"), occurrences=p.get("occurrences"),
            strength=p.get("strength"),
            recommendation="Review this recurring pattern before the next Sprint"))
    return made
