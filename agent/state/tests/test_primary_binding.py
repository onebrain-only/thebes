#!/usr/bin/env python3
"""Primary bindings and wake evidence, against a real store in a temp runtime.

Covers: a binding persists and reloads; a bind can never write ACTIVE; the
single-ACTIVE guard demotes the previous ACTIVE in the same locked section;
generation is monotonic; a rebind is CAS'd and keeps history; a second ACTIVE
record on disk is refused by the validator sweep; and a primary_wake is
immutable evidence with a structured error when not delivered.
"""
import os, shutil, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from _harness import ok, raises, section, summary, state_path, repo_root  # noqa: E402

sys.path.insert(0, repo_root())
sys.path.insert(0, state_path())
import store      # noqa: E402
import validate   # noqa: E402

CLAUDE_A = "9dd2598a-556e-402c-b452-29a5456794d6"
CLAUDE_B = "11111111-1111-4111-8111-111111111111"
CODEX_T = "01a0e382-98e9-70b2-84df-c757e3c6c517"
HOME = "/stable/home"

TMP = tempfile.mkdtemp()
OLD = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
store.RUNTIME = os.path.join(TMP, "runtime")
store.LOCKS = os.path.join(store.RUNTIME, ".locks")
validate.RUNTIME = store.RUNTIME

try:
    section("1. bind persists, reloads, and never writes ACTIVE directly")
    c = store.bind_primary("claude", CLAUDE_A, "STANDBY", "ceo", "ref:proof-04", HOME)
    ok("created at revision 1, STANDBY, generation 0",
       c["revision"] == 1 and c["status"] == "STANDBY" and c["generation"] == 0)
    ok("reloads from disk", store.read("primary_binding", "claude")["session_ref"] == CLAUDE_A)
    ok("no ACTIVE primary yet", store.active_primary() is None)
    raises("binding ACTIVE directly is refused",
           lambda: store.bind_primary("codex", CODEX_T, "ACTIVE", "ceo", "ref:x", HOME),
           "primary-active-requires-transition")
    raises("unknown provider refused",
           lambda: store.bind_primary("gpt", CODEX_T, "STANDBY", "ceo", "ref:x", HOME),
           "unknown provider")
    raises("a name is not an identity",
           lambda: store.bind_primary("codex", "my-thread", "STANDBY", "ceo", "ref:x", HOME),
           "UUID")

    section("2. single-ACTIVE guard and monotonic generation")
    a1 = store.set_primary_active("claude", "ceo", "ref:activate-claude")
    ok("claude becomes ACTIVE at generation 1", a1["status"] == "ACTIVE" and a1["generation"] == 1)
    ok("active_primary returns claude", store.active_primary()["provider"] == "claude")
    ok("re-activating the ACTIVE one is a no-op", store.set_primary_active("claude", "ceo", "ref:again")["generation"] == 1)
    x = store.bind_primary("codex", CODEX_T, "STANDBY", "ceo", "ref:standby-codex", HOME)
    ok("codex bound STANDBY beside the ACTIVE claude", x["status"] == "STANDBY")
    ok("still exactly one ACTIVE", store.active_primary()["provider"] == "claude")
    a2 = store.set_primary_active("codex", "ceo", "ref:test-cutover")
    ok("codex ACTIVE at generation 2", a2["status"] == "ACTIVE" and a2["generation"] == 2)
    ok("claude demoted to STANDBY in the same transition",
       store.read("primary_binding", "claude")["status"] == "STANDBY")
    a3 = store.set_primary_active("claude", "ceo", "ref:back")
    ok("generation keeps climbing across providers", a3["generation"] == 3)
    ok("codex demoted again", store.read("primary_binding", "codex")["status"] == "STANDBY")

    section("3. rebind is CAS'd and keeps history")
    cur = store.read("primary_binding", "claude")
    raises("rebind without expected_revision refused",
           lambda: store.bind_primary("claude", CLAUDE_B, "STANDBY", "ceo", "ref:x", HOME),
           "expected_revision")
    raises("stale rebind refused",
           lambda: store.bind_primary("claude", CLAUDE_B, "STANDBY", "ceo", "ref:x", HOME,
                                      expected_revision=99), "stale write")
    ok("ACTIVE provider may rebind its ref as ACTIVE via CAS",
       store.bind_primary("claude", CLAUDE_B, "ACTIVE", "ceo", "ref:rebind", HOME,
                          expected_revision=cur["revision"])["previous_session_refs"] == [CLAUDE_A])
    rt = store.bind_primary("codex", CODEX_T, "RETIRED", "ceo", "ref:retire", HOME,
                            expected_revision=store.read("primary_binding", "codex")["revision"])
    ok("codex can be retired", rt["status"] == "RETIRED")
    raises("a RETIRED primary cannot be activated",
           lambda: store.set_primary_active("codex", "ceo", "ref:x"), "primary-not-standby-or-active")

    section("4. validator sweep refuses a second ACTIVE on disk")
    ok("clean sweep on primary-bindings",
       [e for e in validate.check(store.RUNTIME) if "primary" in e] == [])
    forged = dict(store.read("primary_binding", "codex"), status="ACTIVE", generation=9)
    store._atomic_write(store.path_for("primary_binding", "codex"), forged)
    errs = [e for e in validate.check(store.RUNTIME) if "ACTIVE Primaries" in e]
    ok("two ACTIVE bindings are reported by the sweep", len(errs) == 1)
    raises("active_primary refuses to pick between two", store.active_primary, "corrupt primary state")
    bad = dict(forged, generation=0)
    ok("an ACTIVE binding with generation 0 is rejected",
       any("generation" in e for e in validate.validate_record("primary_binding", bad)))

    section("5. primary_wake is immutable evidence")
    w = store.record_primary_wake({"provider": "codex", "session_ref": CODEX_T, "generation": 3,
                                   "event_kind": "platform_test", "payload_ref": "/tmp/x.jsonl",
                                   "status": "delivered", "turn_ref": "01a0e738-7d60",
                                   "response_summary": "STANDBY", "error": None,
                                   "started_at": store.now()})
    ok("wake id has the pwake prefix", w["primary_wake_id"].startswith("pwake-"))
    ok("completed_at defaulted", bool(w["completed_at"]))
    raises("a delivered wake needs a turn_ref",
           lambda: store.record_primary_wake(dict(w, primary_wake_id=None, turn_ref=None)), "turn")
    raises("a busy wake needs a structured error",
           lambda: store.record_primary_wake({"provider": "codex", "session_ref": CODEX_T,
                                              "generation": 3, "event_kind": "platform_test",
                                              "status": "busy", "error": None,
                                              "started_at": store.now()}), "error")
    raises("a wake is never updated",
           lambda: store.update("primary_wake", w["primary_wake_id"], 1, {"status": "failed"}),
           "error")
finally:
    store.RUNTIME, store.LOCKS, validate.RUNTIME = OLD
    shutil.rmtree(TMP, ignore_errors=True)

sys.exit(summary())
