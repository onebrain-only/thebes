#!/usr/bin/env python3
"""Automatic integration of verified work into staging (D-042, D-052). Fakes only."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store, teams, validate                       # noqa: E402
from agent.execution import integrate                                # noqa: E402
from agent.execution import conversation_dispatch as cd              # noqa: E402

ORCH = "0eeeeeee-9999-7000-8000-00000000000e"
LUXOR = "0bbbbbbb-9999-7000-8000-00000000000b"
MEMPHIS = "0ddddddd-9999-7000-8000-00000000000d"
HOME = "/stable/home"
SHA = "a" * 40
SHA2 = "b" * 40
# The recipe tests run past the patch ceiling (TH-075); the patch gate has its own tests.
LATER = __import__("time").time() + 2 * integrate.PATCH_CEILING_SECONDS


def _refuse(*a, **k):
    raise AssertionError("no process may be spawned here")


class Done:
    def __init__(self, out="", rc=0):
        self.stdout, self.returncode = out, rc


def fake_git(remote):
    """remote: {branch: sha} for ls-remote."""
    def run(argv, **kw):
        if "merge-base" in argv:                       # not on the base yet unless marked
            return Done("", 0 if argv[-2] in remote.get("_on_base", ()) else 1)
        if "ls-remote" in argv:
            return Done("".join("%s\trefs/heads/%s\n" % (v, k) for k, v in remote.items()
                                if not k.startswith("_")))
        return Done("")
    return run


class IntegrateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = (store.RUNTIME, store.LOCKS, validate.RUNTIME)
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        store.LOCKS = os.path.join(store.RUNTIME, ".locks")
        validate.RUNTIME = store.RUNTIME
        store.bind_role_session("orchestrator", "claude", ORCH, HOME, "ceo")
        store.bind_role_session("luxor", "claude", LUXOR, HOME, "ceo")
        store.bind_role_session("memphis", "claude", MEMPHIS, HOME, "ceo")
        self.patches = [mock.patch.object(subprocess, n, _refuse) for n in ("run", "Popen")]
        for p in self.patches:
            p.start()
        self.sent = []

    def tearDown(self):
        for p in self.patches:
            p.stop()
        store.RUNTIME, store.LOCKS, validate.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def root(self, key="KAN-1", branch="staging-luxor", sha=SHA, verdict="pass", **extra):
        did = store.new_id("conversation_dispatch")
        store.create("conversation_dispatch", dict({
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": LUXOR, "target_seat_id": "luxor",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "completed", "delivery_status": "DELIVERED", "outcome": "completed",
            "result_ref": "/x", "result_sha256": "0" * 64, "outcome_at": store.now(),
            "attested_delivery_id": did, "reported_session_id": LUXOR, "jira_key": key, "checks": [{"id": "C1", "kind": "run", "what": "x", "pass": "exit 0"}],
            "verification": {"verdict": verdict, "branch": branch, "sha": sha, "results": {}},
            "verified_at": store.now()}, **extra), rid=did)
        return did

    def send(self, text, sid, env, state_store, detach, ticket):
        self.sent.append({"text": text, "sid": sid, "ticket": ticket})
        did = state_store.new_id("conversation_dispatch")
        state_store.create("conversation_dispatch", {
            "dispatch_id": did, "origin_provider": "claude", "origin_thread_id": ORCH,
            "target_provider": "claude", "target_session_id": sid, "target_seat_id": "memphis",
            "delivery_id": did, "capability_sha256": "0" * 64, "prompt_ref": "/x",
            "status": "delivered", "delivery_status": "DELIVERED"}, rid=did)
        return {"dispatch_id": did}

    def run_dispatch(self, remote, allowed=True):
        import json
        rules = [integrate.push_rule(t) for t in
                 (integrate.base_for("staging-x"), integrate.base_for("staging-ds-x"))] if allowed else []
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"permissions": {"allow": rules}}, fh)
        return integrate.dispatch_for(state_store=store, dispatch=self.send,
                                      runner=fake_git(remote), settings_files=[path], now=LATER)

    def test_without_the_push_rule_nothing_is_sent_that_would_block_memphis(self):
        self.root("KAN-1", "staging-luxor", SHA)
        out = self.run_dispatch({"staging-luxor": SHA}, allowed=False)
        self.assertEqual(out[0]["action"], "waiting")
        self.assertIn("Bash(git -C * push origin integrate-staging:staging)", out[0]["reason"])
        self.assertEqual(self.sent, [])
        self.assertEqual(self.run_dispatch({"staging-luxor": SHA})[0]["action"], "dispatched",
                         "the moment the CEO adds the rule, it goes")

    def test_verified_pushed_work_is_sent_to_memphis_once_with_the_whole_recipe(self):
        a = self.root("KAN-1", "staging-luxor", SHA)
        out = self.run_dispatch({"staging-luxor": SHA})
        self.assertEqual((out[0]["action"], out[0]["tickets"]), ("dispatched", ["KAN-1"]))
        sent = self.sent[0]
        self.assertEqual((sent["sid"], sent["ticket"]), (MEMPHIS, None))
        for part in ("INTEGRATE", "staging-luxor @ aaaaaaaaaaaa  (tickets: KAN-1)", "OWN worktree",
                     "flutter analyze --no-pub --no-fatal-infos", "flutter test --no-pub",
                     "BY NAME, not by count", "fails only on the merged result",
                     "Never push or merge Alpha, Canary or main",
                     "INTEGRATED: <KEY> <branch> <merge-commit-sha>", "do not ask the CEO"):
            self.assertIn(part, sent["text"], part)
        self.assertIn("integrate-staging:staging", sent["text"])
        self.assertEqual(self.run_dispatch({"staging-luxor": SHA}), [], "never twice")
        self.assertTrue(store.read("conversation_dispatch", a)["integration_dispatch_id"])

    def test_review_passed_work_integrates_without_any_ceo_order_d046(self):
        from agent.execution import orders
        self.root("KAN-1", "staging-luxor", SHA)
        out = self.run_dispatch({"staging-luxor": SHA})
        self.assertEqual([(o["action"], o["tickets"]) for o in out], [("dispatched", ["KAN-1"])])
        last = orders.recent(1)[0]
        self.assertEqual((last["action"], last.get("rule")),
                         ("integration-dispatched", "review-passed"))

    def test_every_verified_item_is_allowed_d046(self):
        items = [{"key": "KAN-1", "branch": "b", "sha": SHA, "at": "1"},
                 {"key": "KAN-3", "branch": "c", "sha": "c" * 40, "at": "3"}]
        self.assertEqual(integrate.ordered_items(items), (items, []))

    def fast_runner(self, remote, files):
        base = fake_git(remote)

        def run(argv, **kw):
            if "diff" in argv:
                return Done("\n".join(files) + "\n")
            return base(argv, **kw)
        return run

    def fast(self, files):
        import json
        rules = [integrate.push_rule(integrate.base_for("staging-x"))]
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"permissions": {"allow": rules}}, fh)
        return integrate.dispatch_for(state_store=store, dispatch=self.send, settings_files=[path],
                                      runner=self.fast_runner({"staging-luxor": SHA}, files),
                                      now=LATER)

    def test_integration_goes_to_memphis_only_even_for_a_small_ticket(self):
        """2026-10-14: a code team may not work in the CEO's folders; the fast lane is off."""
        self.root("KAN-1", "staging-luxor", SHA)
        out = self.fast(["lib/a.dart", "test/a_test.dart"])
        self.assertEqual((out[0]["action"], out[0]["lane"]), ("dispatched", "ops"))
        self.assertEqual(self.sent[0]["sid"], MEMPHIS)

    def test_the_fast_lane_still_works_when_it_is_switched_on(self):
        self.root("KAN-1", "staging-luxor", SHA)
        with mock.patch.object(integrate, "FAST_LANE", True):
            out = self.fast(["lib/a.dart", "test/a_test.dart"])
        self.assertEqual((out[0]["action"], out[0]["lane"]), ("dispatched", "team"))
        self.assertEqual(self.sent[0]["sid"], LUXOR)

    def test_big_or_risky_tickets_stay_with_memphis(self):
        self.root("KAN-1", "staging-luxor", SHA)
        self.assertEqual(self.fast(["f%d.dart" % i for i in range(6)])[0]["lane"], "ops")
        self.assertEqual(self.sent[0]["sid"], MEMPHIS)

    def test_pubspec_database_and_unknown_are_never_small(self):
        self.assertFalse(integrate.is_small(["pubspec.yaml"]))
        self.assertFalse(integrate.is_small(["supabase/migrations/1.sql"]))
        self.assertFalse(integrate.is_small(None))
        self.assertFalse(integrate.is_small([]))
        self.assertTrue(integrate.is_small(["lib/a.dart"]))

    def test_a_tip_already_on_the_base_is_marked_integrated_not_sent_again(self):
        """B5: an automatic integration re-merged what the orchestrator had already merged."""
        a = self.root("KAN-1", "staging-luxor", SHA)
        out = self.run_dispatch({"staging-luxor": SHA, "_on_base": (SHA,)})
        self.assertEqual((out, self.sent), ([], []))
        self.assertTrue(store.read("conversation_dispatch", a)["integrated_at"])

    # -- 2026-10-13: false "not on its base yet" blockers ------------------------------
    def repo_runner(self, on_base=(), in_ds=()):
        """cat-file: the commit lives in the app repo unless it is listed in `in_ds`."""
        def run(argv, **kw):
            repo = "design-system" if "dabbler-design-system" in " ".join(argv) else "app"
            if "cat-file" in argv:
                sha = argv[-1].split("^")[0]
                return Done("", 0 if (sha in in_ds) == (repo == "design-system") else 1)
            if "merge-base" in argv:
                return Done("", 0 if (repo, argv[-2]) in on_base else 1)
            return Done("")
        return run

    def test_a_design_system_commit_on_an_app_named_branch_is_checked_against_staging_ds(self):
        """KAN-508: Alpha-deir-el-bahari lived in the design system (legacy name, still mapped)."""
        did = self.root("KAN-508", "Alpha-deir-el-bahari", SHA2)
        run = self.repo_runner(on_base={("design-system", SHA2)}, in_ds={SHA2})
        self.assertEqual(integrate.target_for("Alpha-deir-el-bahari", SHA2, run)["key"], "staging-ds")
        self.assertEqual(integrate.target_for("staging-deir-el-bahari", SHA2, run)["key"], "staging-ds")
        self.assertEqual(integrate.target_for("Alpha-deir-el-bahari", SHA, run)["key"], "staging")
        self.assertEqual(integrate.target_for("staging-deir-el-bahari", SHA, run)["base"], "staging")
        out = integrate.reconcile(state_store=store, runner=run, fetch=False)
        self.assertEqual([o["reconciled"] for o in out], ["KAN-508"])
        rec = store.read("conversation_dispatch", did)
        self.assertEqual((rec["integrated_sha"], rec["integrated_via"]), (SHA2, "ancestor-of-staging-ds"))

    def test_an_app_tip_that_is_an_ancestor_of_staging_is_integrated_whoever_merged_it(self):
        """KAN-497: merged by hand (3879a977), integrated_at stayed None for hours."""
        did = self.root("KAN-497", "staging-deir-el-bahari", SHA)
        out = integrate.reconcile(state_store=store, fetch=False,
                                  runner=self.repo_runner(on_base={("app", SHA)}))
        self.assertEqual([o["base"] for o in out], ["staging"])
        self.assertTrue(store.read("conversation_dispatch", did)["integrated_at"])
        self.assertEqual(integrate.reconcile(state_store=store, fetch=False,
                                             runner=self.repo_runner(on_base={("app", SHA)})), [],
                         "once")

    def test_not_yet_on_the_base_stays_pending_and_canary_is_never_touched(self):
        self.root("KAN-1", "staging-luxor", SHA)
        self.root("KAN-2", "canary-luxor", SHA)
        self.assertEqual(integrate.reconcile(state_store=store, fetch=False,
                                             runner=self.repo_runner()), [])

    def test_mark_integrated_needs_evidence_and_git_must_agree(self):
        did = self.root("KAN-497", "staging-deir-el-bahari", SHA)
        run = self.repo_runner(on_base={("app", SHA), ("app", SHA2)})
        for args in (("staging", SHA2, " "), ("nope", SHA2, "x"), ("Alpha", SHA2, "x"),
                     ("staging-ds", SHA2, "x")):
            with self.assertRaises(ValueError):
                integrate.mark_integrated(did[:14], args[0], args[1], args[2], state_store=store,
                                          runner=run, fetch=False, jira=mock.Mock())
        self.assertFalse(store.read("conversation_dispatch", did).get("integrated_at"))
        with self.assertRaises(ValueError):          # the --sha is not in the base
            integrate.mark_integrated(did, "staging", "c" * 40, "merge 3879a977", state_store=store,
                                      runner=run, fetch=False, jira=mock.Mock())
        out = integrate.mark_integrated(did[:14], "staging", SHA2, "merge 3879a977 on staging",
                                        state_store=store, runner=run, fetch=False, jira=mock.Mock())
        self.assertEqual(out["status"], "marked")
        rec = store.read("conversation_dispatch", did)
        self.assertEqual((rec["integrated_sha"], rec["integrated_via"]), (SHA2, "manual-mark"))
        self.assertIn("3879a977", rec["integration_evidence"])

    def test_a_branch_pushed_with_another_letter_case_is_found(self):
        """2026-10-16: Karnak pushes Staging-karnak, the verified name was staging-karnak."""
        self.root("KAN-561", "staging-karnak", SHA)
        out = self.run_dispatch({"Staging-karnak": SHA})
        self.assertEqual([o["action"] for o in out if "action" in o and o.get("integrate") != "skipped"],
                         ["dispatched"])

    def test_verified_work_that_is_skipped_says_why_instead_of_vanishing(self):
        self.root("KAN-562", "staging-luxor", SHA)
        out = self.run_dispatch({})
        self.assertEqual((out[0]["integrate"], out[0]["key"]), ("skipped", "KAN-562"))
        self.assertIn("branch-not-found-on-origin", out[0]["reason"])
        again = self.run_dispatch({})
        self.assertEqual([o for o in again if o.get("integrate") == "skipped"], [], "once per 6 hours")

    def cherry_runner(self, cherry, log):
        def run(argv, **kw):
            if "cherry" in argv:
                return Done(cherry)
            if "log" in argv:
                return Done(log)
            if "merge-base" in argv:
                return Done("", 1)
            if "ls-remote" in argv:
                return Done("")
            return Done("")
        return run

    def test_a_cherry_picked_ticket_counts_as_integrated(self):
        """2026-10-14, KAN-505: another ticket's commits stayed out, the ticket's own went in."""
        run = self.cherry_runner("- aaa111\n+ bbb222\n",
                                 "bbb222 KAN-506: other work\naaa111 KAN-505: the migration\n")
        self.assertTrue(integrate.ticket_commits_on_base("Dabbler/dabbler-code", "staging", SHA, "KAN-505", run))
        self.assertFalse(integrate.ticket_commits_on_base("Dabbler/dabbler-code", "staging", SHA, "KAN-506", run),
                         "its own commit is still missing")
        self.assertFalse(integrate.ticket_commits_on_base("Dabbler/dabbler-code", "staging", SHA, "KAN-999", run),
                         "no commit of that ticket at all")
        self.assertFalse(integrate.ticket_commits_on_base("Dabbler/dabbler-code", "staging", SHA, None, run))

    def test_mark_integrated_accepts_a_cherry_pick_with_evidence(self):
        did = self.root("KAN-505", "staging-deir-el-bahari", SHA)
        run = self.cherry_runner("- aaa111\n+ bbb222\n",
                                 "bbb222 KAN-506: other\naaa111 KAN-505: the migration\n")
        out = integrate.mark_integrated(did, "staging", SHA2, "cherry-picked as 5a2264a0 from 20db6a4e",
                                        state_store=store, runner=run, fetch=False, jira=mock.Mock())
        self.assertEqual(out["status"], "marked")

    def test_only_what_thebes_verified_and_the_team_pushed_is_integrated(self):
        self.root("KAN-1", "staging-luxor", SHA)
        acts = lambda out: [o for o in out if o.get("integrate") != "skipped"]
        self.assertEqual(acts(self.run_dispatch({})), [], "not pushed")
        self.assertEqual(acts(self.run_dispatch({"staging-luxor": SHA2})), [],
                         "the branch moved on past what was verified")
        self.root("KAN-2", "canary-luxor", SHA)
        self.root("KAN-3", "staging-luxor", SHA, verdict="exhausted")
        self.assertEqual(acts(self.run_dispatch({"canary-luxor": SHA, "staging-luxor": SHA2})), [],
                         "Canary and main are never auto-integrated; failed work is never merged")

    def test_the_design_system_goes_to_its_staging_and_each_base_has_its_own_integration(self):
        self.root("KAN-1", "staging-luxor", SHA)
        self.root("KAN-2", "staging-ds-luxor", SHA2)
        out = self.run_dispatch({"staging-luxor": SHA, "staging-ds-luxor": SHA2})
        self.assertEqual([o["action"] for o in out], ["dispatched", "waiting"],
                         "Memphis is one session: the second base waits")
        waiting_base = out[1]["integrate"]
        self.assertEqual(sorted(o["integrate"] for o in out), ["staging", "staging-ds"])
        out2 = self.run_dispatch({"staging-luxor": SHA, "staging-ds-luxor": SHA2})
        self.assertEqual(out2, [{"integrate": waiting_base, "action": "waiting",
                                 "reason": "ops-team-busy"}])
        ds_brief = integrate.brief({"target": integrate.base_for("staging-ds-x"), "items": [
            {"key": "KAN-9", "branch": "staging-ds-x", "sha": SHA}]})
        self.assertIn("integrate-staging-ds:staging", ds_brief)
        self.assertIn("Dabbler/dabbler-design-system", ds_brief)
        self.assertEqual(integrate.base_for("alpha-ds-x")["key"], "staging-ds",
                         "a legacy alpha-ds-<team> name integrates into staging too")

    def test_a_finished_integration_marks_tickets_and_comments_a_blocked_one_counts_an_attempt(self):
        a = self.root("KAN-1", "staging-luxor", SHA, verified_at="2026-10-09T05:00:00Z")
        b = self.root("KAN-2", "staging-luxor", SHA2, verified_at="2026-10-09T05:10:00Z")
        self.run_dispatch({"staging-luxor": SHA2})
        self.assertIn("(tickets: KAN-1, KAN-2)", self.sent[0]["text"])
        self.assertIn("staging-luxor @ bbbbbbbbbbbb", self.sent[0]["text"],
                      "one merge of the head covers the earlier ticket on the branch")
        did = self.sent[0] and [r for r in store.read_all("conversation_dispatch")
                                if r.get("integrates_base")][0]["dispatch_id"]
        ref = os.path.join(self.tmp, "result.txt")
        with open(ref, "w") as fh:
            fh.write("Done.\nINTEGRATED: KAN-1 staging-luxor 1234567890abcdef\nBASE_SHA: fedcba0987654321\n"
                     "Skipped KAN-2: conflict in venues_screen.dart\n")
        rec = store.read("conversation_dispatch", did)
        store.update("conversation_dispatch", did, rec["revision"],
                     {"status": "blocked", "outcome": "blocked", "result_ref": ref,
                      "outcome_at": store.now(), "reported_session_id": MEMPHIS,
                      "attested_delivery_id": did, "result_sha256": "0" * 64})
        comments = []

        class J:
            def add_comment(self, k, t):
                comments.append((k, t))
        out = integrate.settle(state_store=store, jira=J())
        self.assertIn({"integrated": "KAN-1", "branch": "staging-luxor", "base_sha": "fedcba0987654321"},
                      out)
        self.assertTrue(store.read("conversation_dispatch", a)["integrated_at"])
        self.assertIn("Integrated into staging", comments[0][1])
        self.assertIn("1234567890ab", comments[0][1])
        skipped = store.read("conversation_dispatch", b)
        self.assertEqual((skipped.get("integrated_at"), skipped["integration_attempts"]), (None, 1))
        self.assertIsNone(skipped["integration_dispatch_id"], "released for one more try")
        self.assertEqual(integrate.settle(state_store=store, jira=J()), [], "settled once")

    def test_a_ticket_is_left_alone_after_two_failed_attempts(self):
        self.root("KAN-1", "staging-luxor", SHA, integration_attempts=integrate.MAX_ATTEMPTS)
        self.assertEqual(self.run_dispatch({"staging-luxor": SHA}), [])

    def test_the_orchestrator_hears_a_blocked_integration_as_a_plain_result(self):
        from agent.execution import inbox
        self.root("KAN-1", "staging-luxor", SHA)
        self.run_dispatch({"staging-luxor": SHA})
        did = [r for r in store.read_all("conversation_dispatch") if r.get("integrates_base")][0]
        ref = os.path.join(self.tmp, "r.txt")
        open(ref, "w").write("Skipped KAN-1: conflict")
        store.update("conversation_dispatch", did["dispatch_id"], did["revision"],
                     {"status": "blocked", "outcome": "blocked", "result_ref": ref,
                      "outcome_at": store.now(), "reported_session_id": MEMPHIS,
                      "attested_delivery_id": did["dispatch_id"], "result_sha256": "0" * 64})
        items = inbox.pending(ORCH, state_store=store, now=__import__("time").time() + 60)
        self.assertEqual([i["kind"] for i in items if i.get("dispatch_id") == did["dispatch_id"]],
                         ["result"])


class Board:
    """A fake Jira: `parents` maps ticket -> Epic, `done` lists tickets in a done status."""
    def __init__(self, parents, done=()):
        self.parents, self.done, self.calls = parents, set(done), 0

    def get_issue(self, key, fields=None):
        self.calls += 1
        return {"key": key, "parent": self.parents.get(key)}

    def search_issues(self, jql, fields=None, limit=50):
        self.calls += 1
        epic = jql.split("=")[1].strip()
        return [{"key": k, "status_category": "done" if k in self.done else "indeterminate"}
                for k, e in sorted(self.parents.items()) if e == epic]


class PatchTests(unittest.TestCase):
    """TH-075 (CEO 2026-11-11): a base integrates when a patch closes, not when one ticket passes."""
    tearDown, root, send = IntegrateTests.tearDown, IntegrateTests.root, IntegrateTests.send

    def setUp(self):
        IntegrateTests.setUp(self)
        integrate._JIRA_CACHE.clear()

    def patch(self, remote, jira, now=None):
        import json
        path = os.path.join(self.tmp, "settings.json")
        with open(path, "w") as fh:
            json.dump({"permissions": {"allow": [integrate.push_rule(
                integrate.base_for("staging-x"))]}}, fh)
        return integrate.dispatch_for(state_store=store, dispatch=self.send, jira=jira,
                                      runner=fake_git(remote), settings_files=[path], now=now)

    def test_one_verified_ticket_of_an_open_epic_waits_on_its_team_branch(self):
        self.root("KAN-1", "staging-luxor", SHA)
        out = self.patch({"staging-luxor": SHA}, Board({"KAN-1": "KAN-100", "KAN-2": "KAN-100"}))
        self.assertEqual(self.sent, [])
        self.assertEqual(out[0]["integrate"], "skipped")
        self.assertIn("KAN-100 waits for KAN-2", out[0]["reason"])

    def test_the_epic_merges_once_its_last_ticket_is_verified(self):
        self.root("KAN-1", "staging-luxor", SHA)
        self.root("KAN-2", "staging-karnak", SHA2)
        board = Board({"KAN-1": "KAN-100", "KAN-2": "KAN-100", "KAN-3": "KAN-100"}, done={"KAN-3"})
        out = self.patch({"staging-luxor": SHA, "staging-karnak": SHA2}, board)
        self.assertEqual([o.get("action") for o in out], ["dispatched"])
        self.assertEqual(sorted(out[0]["tickets"]), ["KAN-1", "KAN-2"],
                         "both teams' branches go in one merge")
        self.assertIn("Why now: patch: every ticket of KAN-100 is verified or Done.",
                      self.sent[0]["text"])

    def test_work_with_no_epic_waits_for_the_ceiling_then_goes(self):
        self.root("KAN-1", "staging-luxor", SHA)
        self.assertEqual(self.patch({"staging-luxor": SHA}, Board({})), [
            {"integrate": "skipped", "key": "staging",
             "reason": "patch-open: no Epic behind the waiting work"}])
        out = self.patch({"staging-luxor": SHA}, Board({}), now=LATER)
        self.assertEqual(out[0]["action"], "dispatched")
        self.assertIn("ceiling", out[0]["why"])

    def test_without_jira_only_the_ceiling_opens_a_patch(self):
        due, why = integrate.patch_due([{"key": "KAN-1", "at": store.now()}], set(), None)
        self.assertEqual((due, why.split(":")[0]), (False, "patch-open"))
        self.assertTrue(integrate.patch_due([{"key": "KAN-1", "at": "2026-01-01T00:00:00Z"}],
                                            set(), None)[0])

    def test_a_jira_error_waits_instead_of_merging(self):
        class Broken:
            def get_issue(self, *a, **k):
                raise RuntimeError("503")
        due, why = integrate.patch_due([{"key": "KAN-1", "at": store.now()}], set(), Broken())
        self.assertFalse(due)
        self.assertIn("Jira error", why)

    def test_the_brief_drops_only_the_breaking_branch_and_follows_th071(self):
        text = integrate.brief({"target": integrate.base_for("staging-x"), "items": [
            {"key": "KAN-1", "branch": "staging-luxor", "sha": SHA}]})
        for part in ("Drop only that branch", "the rest of the patch still goes",
                     "staging-memphis", "gh run watch", "analyze-and-test",
                     "every branch you dropped"):
            self.assertIn(part, text, part)


if __name__ == "__main__":
    unittest.main()
