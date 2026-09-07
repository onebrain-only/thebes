#!/usr/bin/env python3
"""The live KAN board model — the ONE place Thebes describes Jira's shape.

Read from the live board on 2026-09-08 (CEO configuration override). Every id and
every spelling here was taken from `getTransitionsForJiraIssue`, not from prose:
the review statuses really are `Self-review` and `Peer-review` with a lowercase r,
and there is no status named "Backlog" — the *column* is called Backlog and the
status inside it is still `To Do` (10004).

A COLUMN IS NOT A STATUS
  The board deliberately groups several statuses into one column. `Operations`
  holds three execution lanes and `Review` holds three validation routes. So a
  lifecycle observation carries all three of jira_column, jira_status_id and
  canonical — they answer different questions and none derives the other two.

      jira_column   = "Review"        <- what the board shows
      jira_status   = "Peer-review"   <- which route is active
      canonical     = "review"        <- which lifecycle state Thebes reasons in

NEITHER GROUPED COLUMN IS A SEQUENCE
  Design/Content/Operations are ALTERNATIVE execution lanes; a work item enters
  exactly one, chosen by its single required_capability. QA-Test/Self-review/
  Peer-review are ALTERNATIVE validation routes; a work item enters exactly one,
  chosen by system policy. Nothing flows Design -> Content, and nothing flows
  Self-review -> Peer-review.

LEGACY STATUSES STILL EXIST
  `In Progress` (10005), `Development` (10010) and `In Review` (10006) were not
  deleted when the new statuses were added. They are NOT valid targets for new
  work, but they must stay mapped: every historical changelog entry names them,
  and Sprint reconstruction replays that history.

Stdlib only. No imports from the rest of the state layer, so anything may import it.
"""

READY, DEVELOPMENT, REVIEW, DONE = "ready", "development", "review", "done"
CANONICAL_STATES = (READY, DEVELOPMENT, REVIEW, DONE)

# Board columns, left to right as configured.
COLUMNS = ("Backlog", "Ready", "Operations", "Frontend Development",
           "Backend Development", "Review", "Done")

# status id -> (name, column, canonical, transition id)
# `column` is None for a legacy status that is no longer a board target.
STATUSES = {
    "10004": ("To Do",       "Backlog",              READY,       "11"),
    "10008": ("Ready",       "Ready",                READY,       "2"),
    "10047": ("Design",      "Operations",           DEVELOPMENT, "9"),
    "10048": ("Content",     "Operations",           DEVELOPMENT, "10"),
    "10049": ("Operations",  "Operations",           DEVELOPMENT, "12"),
    "10046": ("Front-end",   "Frontend Development", DEVELOPMENT, "8"),
    "10043": ("Back-end",    "Backend Development",  DEVELOPMENT, "5"),
    "10009": ("QA-Test",     "Review",               REVIEW,      "3"),
    "10044": ("Self-review", "Review",               REVIEW,      "6"),
    "10045": ("Peer-review", "Review",               REVIEW,      "7"),
    "10007": ("Done",        "Done",                 DONE,        "41"),
    # ---- legacy: historical only, never a target for new work ----
    "10005": ("In Progress", None,                   DEVELOPMENT, "21"),
    "10010": ("Development", None,                   DEVELOPMENT, "4"),
    "10006": ("In Review",   None,                   REVIEW,      "31"),
}

LEGACY_STATUS_IDS = tuple(sid for sid, v in STATUSES.items() if v[1] is None)
LIVE_STATUS_IDS = tuple(sid for sid, v in STATUSES.items() if v[1] is not None)

DONE_STATUS_ID = "10007"

# ---------------------------------------------------------------- execution
#
# ONE EXECUTABLE WORK ITEM = ONE required_capability, and that capability picks
# exactly one execution status. The board now names the specialist lanes
# separately, so content/design/devops work is NOT collapsed into one generic
# status the way an earlier plan would have done.

CAPABILITY_TO_STATUS_ID = {
    "frontend":         "10046",   # Front-end
    "backend":          "10043",   # Back-end
    "content":          "10048",   # Content
    "product-designer": "10047",   # Design
    "ux-engineer":      "10047",   # Design
    "devops":           "10049",   # Operations
    "analyst":          "10049",   # Operations — when the work is a tracked deliverable
}

# Any other executable shared-specialist capability lands in Operations.
DEFAULT_EXECUTION_STATUS_ID = "10049"

# `qa` holds no execution status: QA is a validation route, not a lane.
NO_EXECUTION_CAPABILITIES = ("qa",)

# ---------------------------------------------------------------- review
#
# The Jira review status now expresses the validation route directly, so the two
# must never drift. Policy still CHOOSES the route before the transition; once the
# transition succeeds, the Jira status is authoritative evidence of which route is
# active, and Persistent State is reconciled to it — not the other way round.

ROUTE_TO_STATUS_ID = {
    "self": "10044",   # Self-review
    "peer": "10045",   # Peer-review
    "qa":   "10009",   # QA-Test
}
STATUS_ID_TO_ROUTE = {v: k for k, v in ROUTE_TO_STATUS_ID.items()}


# ---------------------------------------------------------------- accessors

def canonical_for(status_id):
    row = STATUSES.get(str(status_id))
    return row[2] if row else None


def column_for(status_id):
    row = STATUSES.get(str(status_id))
    return row[1] if row else None


def name_for(status_id):
    row = STATUSES.get(str(status_id))
    return row[0] if row else None


def transition_for(status_id):
    row = STATUSES.get(str(status_id))
    return row[3] if row else None


def is_legacy(status_id):
    return str(status_id) in LEGACY_STATUS_IDS


def execution_status_for(capability):
    if capability in NO_EXECUTION_CAPABILITIES:
        return None
    return CAPABILITY_TO_STATUS_ID.get(capability, DEFAULT_EXECUTION_STATUS_ID)


def review_status_for(route):
    return ROUTE_TO_STATUS_ID.get(route)


def route_for_status(status_id):
    """The validation route a review status expresses, or None if not a review status."""
    return STATUS_ID_TO_ROUTE.get(str(status_id))


def is_valid_transition_target(status_id):
    """Whether this status may be a CURRENT transition destination."""
    sid = str(status_id)
    return sid in STATUSES and not is_legacy(sid)


def assert_transition_target(status_id):
    """Guard every intentional transition. Raises on a legacy or unknown target.

    HISTORICAL READABILITY IS NOT CURRENT TRANSITION AUTHORITY, and the two are
    deliberately separated:

      - `canonical_for()` accepts a legacy id, because every historical changelog
        entry names one and Sprint reconstruction has to replay that history.
      - THIS function rejects it, because moving live work into a status with no
        board column would hide the work. That is not hypothetical: seven executable
        issues were found parked in `Development` and `In Review` after the board was
        reconfigured, invisible on the board until they were moved out.

    Every transition on this board is global and unconditional, so Jira itself will
    happily accept a legacy target. Nothing but this guard stops it.
    """
    sid = str(status_id)
    if sid not in STATUSES:
        raise ValueError("unknown Jira status id %r — not on the live KAN board" % sid)
    if is_legacy(sid):
        raise ValueError(
            "status %s (%s) is a LEGACY status with no board column and is NOT a valid "
            "transition target — it is retained only so historical changelog entries stay "
            "readable. Live targets: %s"
            % (sid, name_for(sid),
               ", ".join("%s (%s)" % (name_for(i), i) for i in LIVE_STATUS_IDS)))
    return sid


def statuses_in_column(column):
    return tuple(sid for sid, v in STATUSES.items() if v[1] == column)


if __name__ == "__main__":
    for col in COLUMNS:
        ids = statuses_in_column(col)
        print("%-22s %s" % (col, ", ".join("%s (%s)" % (name_for(i), i) for i in ids)))
    print("%-22s %s" % ("legacy (unmapped)",
                        ", ".join("%s (%s)" % (name_for(i), i) for i in LEGACY_STATUS_IDS)))
