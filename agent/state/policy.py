#!/usr/bin/env python3
"""Thebes validation policy — task characteristics in, validation route out.

THE SEPARATION THIS MODULE EXISTS TO ENFORCE

    TASK CHARACTERISTICS  are facts about the work.   Actors assert them.
    VALIDATION ROUTE      is a consequence.           Only this module derives it.

If an actor could write `validation_route` it would choose its own reviewer. If an
actor could freely assert the characteristics that *determine* the route, it would
choose its own reviewer indirectly — which is the same defect wearing a different
field name. So each characteristic carries an authority rule (see AUTHORITY below),
one of them is derived from paths and asserted by nobody, and none of them is a
free-form judgement.

WHY DETERMINISTIC AND NOT A MODEL CALL
  A route that a model picks is a route nobody can predict, reproduce or audit. Every
  rule here is lifted from an artifact that already exists — WORKFLOWS.md §3's review
  table, CONTRACT.md §4's contended/shared list, and the money-write-invariants table
  set — rather than invented. No `risk` or `execution_complexity` value is fabricated
  to feed it; the policy does not consume them, which is exactly why it can be
  deterministic in Wave 5 while those fields stay deferred to Wave 6.

Stdlib only.
"""

# ---------------------------------------------------------------- routes

SELF, PEER, QA = "self", "peer", "qa"

# Safety strictness. PEER outranks QA because PEER requires an authorised
# same-capability seat to take execution ownership on failure, whereas QA is
# black-box and cannot reach schema, RLS or money invariants at all — `qa` has no
# database access by design. A route may escalate; it may never silently drop.
STRICTNESS = {SELF: 0, QA: 1, PEER: 2}

CHARACTERISTICS = (
    "schema_change",
    "money_path",
    "security_sensitive",
    "shared_or_contended_surface",
    "user_visible_runtime",
)

# ---------------------------------------------------------------- authority
#
# who may assert a characteristic, and who may take it back down.
#
#   assert_true  — may set false -> true
#   downgrade    — may set true -> false, and ONLY before review_context exists
#
# A worker may always raise a characteristic it discovers mid-execution; a worker
# may never lower one. That asymmetry is the whole protection: escalation is
# available to whoever finds the danger, de-escalation is not available to whoever
# would benefit from an easier review.

AUTHORITY = {
    "schema_change":               {"assert_true": ("po", "worker", "cto"),
                                    "downgrade":   ("cto",)},
    "money_path":                  {"assert_true": ("po", "worker", "cto"),
                                    "downgrade":   ("cto",)},
    "security_sensitive":          {"assert_true": ("po", "worker", "cto", "analyst"),
                                    "downgrade":   ("cto",)},
    "shared_or_contended_surface": {"assert_true": (),          # system-derived only
                                    "downgrade":   ()},
    "user_visible_runtime":        {"assert_true": ("po", "worker"),
                                    "downgrade":   ("po",)},
}

# Characteristics whose truth is computed, never asserted. Where a fact can be
# derived it must be — a derived fact has no author to lean on it.
SYSTEM_DERIVED = ("shared_or_contended_surface",)

# A basis_ref is required with a true assertion, so the claim names its own evidence.
NEEDS_BASIS_REF = ("schema_change", "money_path", "security_sensitive")

# ---------------------------------------------------------------- fact tables
#
# CONTRACT.md §4 — the four contended files, plus the shared surfaces amended in
# 2026-09-05, plus profile_providers.dart which §3 directs to be treated as
# contended until Phase 1 splits it. Exhaustive by intent: "the shared surfaces"
# is not a grant, so each path is named.

CONTENDED_FILES = (
    "lib/app/app_router.dart",
    "lib/providers.dart",
    "lib/core/config/feature_flags.dart",
    "lib/core/config/supabase_config.dart",
    "lib/features/profile/presentation/providers/profile_providers.dart",
)

SHARED_PREFIXES = (
    "lib/core/",
    "lib/data/",
)

# money-write-invariants / DECISIONS.md T-049. A money_path assertion's basis_ref
# must name one of these, so the field cannot be asserted or denied freely — the
# list is system-owned even though the assertion is not.
MONEY_TABLES = (
    "wallet_ledger",
    "financial_ledger",
    "payment_intents",
    "wallets",
    "payouts",
    "game_settlements",
)


def normalise_path(p):
    """Strip a repository prefix so `Dabbler/dabbler-code/lib/x` and `lib/x` match."""
    p = str(p).strip().lstrip("./")
    for marker in ("dabbler-code/", "webapp/"):
        i = p.find(marker)
        if i != -1:
            p = p[i + len(marker):]
    return p


def derive_contended(paths):
    """shared_or_contended_surface, computed from the paths the work names.

    Asserted by no actor. Recomputed whenever the path set changes.
    """
    for raw in paths or ():
        p = normalise_path(raw)
        if p in CONTENDED_FILES:
            return True
        for pre in SHARED_PREFIXES:
            if p.startswith(pre):
                return True
    return False


def names_money_table(basis_ref):
    return any(t in str(basis_ref or "") for t in MONEY_TABLES)


# ---------------------------------------------------------------- the policy

def validation_route(ch):
    """The whole policy. First match wins.

    `ch` is a mapping of the five characteristics to booleans. Absent means false —
    a characteristic nobody asserted and nothing derived is not true.
    """
    unknown = set(ch or {}) - set(CHARACTERISTICS)
    if unknown:
        raise ValueError("unknown task characteristic(s): %s" % ", ".join(sorted(unknown)))
    g = lambda k: bool((ch or {}).get(k))
    if (g("schema_change") or g("money_path") or g("security_sensitive")
            or g("shared_or_contended_surface")):
        return PEER
    if g("user_visible_runtime"):
        return QA
    return SELF


def escalate(current, recomputed, execution_started):
    """Monotonic route movement.

    Before development starts the route simply follows the facts. Once execution has
    started the route may only move up. A developer who discovers mid-execution that
    ordinary work needs an RLS migration escalates SELF -> PEER by recording the
    characteristic; nobody walks it back by removing it afterwards.
    """
    if current is None:
        return recomputed
    if not execution_started:
        return recomputed
    return recomputed if STRICTNESS[recomputed] > STRICTNESS[current] else current


# ---------------------------------------------------------------- peer eligibility

def peer_eligible(required_capability, seats_by_capability, exclude=()):
    """Seats that could own a PEER review of work of this capability.

    A PEER reviewer must be able to FIX, because PEER FAIL transfers execution
    ownership to the reviewer. So the reviewer needs execution authority for the
    work, and capability is the only structured proxy the system has for that.

    There is no cross-capability exception list, because no architecture rule grants
    one. In particular a frontend-N/backend-N pair is a CONSULTATION relationship:
    pairing conveys no execution authority across the boundary, and using the pair as
    a default peer would reintroduce cross-capability review through the back door.

    Returning [] is a real answer. It does NOT license a downgrade — see
    resolve_owner_or_wait().
    """
    return sorted(s for s in seats_by_capability.get(required_capability, ())
                  if s not in set(exclude))


def resolve_owner_or_wait(route, required_capability, seats_by_capability,
                          evidenced_reviewer=None, executor_seats=()):
    """(review_owner, route) — and the route NEVER comes back weaker.

    The absence of a validator does not make the work less dangerous, so a PEER route
    with no available peer waits in `Peer-review` with review_owner null rather
    than becoming QA or SELF. Waiting is visible on the board and a CEO can resolve
    it; a silent downgrade is invisible and nobody resolves it.
    """
    if route == SELF:
        ev = list(executor_seats)
        # Exactly one evidenced executor is required. Zero means nobody to review;
        # two or more is conflicting evidence, and routing must refuse rather than pick.
        return (ev[0] if len(ev) == 1 else None), SELF
    if route == QA:
        qa_seats = seats_by_capability.get("qa", ())
        return ("qa" if "qa" in qa_seats else None), QA
    # PEER: both conditions, independently.
    if evidenced_reviewer is None:
        return None, PEER
    if evidenced_reviewer not in peer_eligible(required_capability, seats_by_capability,
                                               exclude=executor_seats):
        # Condition A held, condition B failed. Not a reviewer. May consult.
        return None, PEER
    return evidenced_reviewer, PEER


def peer_possible(required_capability, seats_by_capability):
    """Whether a PEER route could ever be owned for this capability today.

    Reported, never acted on: a capability with no possible peer does not get an
    easier route, it gets work that waits until one is authorised.
    """
    return len(seats_by_capability.get(required_capability, ())) >= 2


if __name__ == "__main__":
    print(__doc__.strip().split("\n")[0])
    for name, ch in (
        ("plain frontend copy tweak", {}),
        ("visible screen change",     {"user_visible_runtime": True}),
        ("RLS migration",             {"schema_change": True}),
        ("router edit",               {"shared_or_contended_surface": True}),
    ):
        print("  %-26s -> %s" % (name, validation_route(ch)))
