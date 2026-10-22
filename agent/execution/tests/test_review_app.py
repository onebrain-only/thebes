#!/usr/bin/env python3
"""The local review app: one release build per sha, served statically, and fail closed when the app
never drew (live 2026-10-22: blank canvas, six tickets parked). Fakes only; no Flutter, no browser."""
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, ROOT)

from agent.state import store                                          # noqa: E402
from agent.execution import review_app as ra                           # noqa: E402

SHA = "a" * 40


class ReviewAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.old = store.RUNTIME
        store.RUNTIME = os.path.join(self.tmp, "runtime")
        self.wt = os.path.join(self.tmp, "wt")
        os.makedirs(self.wt)
        self.builds = []

    def tearDown(self):
        store.RUNTIME = self.old
        shutil.rmtree(self.tmp, ignore_errors=True)

    def flutter(self, ok=True):
        """A fake `flutter build web --release`: writes build/web/index.html and counts the calls."""
        def run(cmd, **kw):
            self.builds.append(cmd)
            if ok:
                out = os.path.join(kw["cwd"], "build", "web")
                os.makedirs(out, exist_ok=True)
                open(os.path.join(out, "index.html"), "w").write("<html></html>")
            return SimpleNamespace(returncode=0 if ok else 1)
        return run

    # ------------------------------------------------------------------- the sha cache
    def test_the_same_sha_builds_once_and_the_second_start_reuses_it(self):
        log = os.path.join(self.tmp, "log")
        first, cached1 = ra.build_web(self.wt, SHA, [], log, runner=self.flutter())
        second, cached2 = ra.build_web(self.wt, SHA, [], log, runner=self.flutter())
        self.assertEqual((cached1, cached2), (False, True))
        self.assertEqual(first, second)
        self.assertEqual(len(self.builds), 1, "flutter build ran once for two starts of one sha")
        self.assertEqual(self.builds[0][:4], ["flutter", "build", "web", "--release"])
        self.assertTrue(os.path.exists(os.path.join(first, "index.html")))

    def test_another_sha_builds_again(self):
        log = os.path.join(self.tmp, "log")
        ra.build_web(self.wt, SHA, [], log, runner=self.flutter())
        ra.build_web(self.wt, "b" * 40, [], log, runner=self.flutter())
        self.assertEqual(len(self.builds), 2)

    def test_a_failed_build_is_never_cached_or_served(self):
        log = os.path.join(self.tmp, "log")
        with self.assertRaises(RuntimeError) as ctx:
            ra.build_web(self.wt, SHA, [], log, runner=self.flutter(ok=False))
        self.assertIn("build not ready", str(ctx.exception))
        self.assertIsNone(ra.cached_build(SHA))

    def test_a_half_copied_build_without_the_complete_marker_is_not_a_hit(self):
        os.makedirs(os.path.join(ra._sha_dir(SHA), "web"))
        open(os.path.join(ra._sha_dir(SHA), "web", "index.html"), "w").close()
        self.assertIsNone(ra.cached_build(SHA))

    # ------------------------------------------------------------------- fail closed
    def test_no_semantics_placeholder_means_build_not_ready(self):
        seen = []
        ok, why = ra.wait_rendered("http://localhost:8124", 60, probe=lambda url, s: seen.append((url, s)) or False)
        self.assertFalse(ok)
        self.assertIn("build not ready", why)
        self.assertIn("flt-semantics-placeholder", why)
        self.assertEqual(seen, [("http://localhost:8124", 60)], "the probe is given the 60 s")

    def test_a_probe_that_cannot_run_fails_closed(self):
        def boom(url, seconds):
            raise OSError("no browser")
        ok, why = ra.wait_rendered("http://x", 60, probe=boom)
        self.assertFalse(ok)
        self.assertIn("build not ready", why)

    def test_the_default_is_sixty_seconds_and_the_marker_is_the_semantics_placeholder(self):
        self.assertEqual(ra.RENDER_SECONDS, 60)
        self.assertEqual(ra.RENDER_MARKER, "flt-semantics-placeholder")
        self.assertFalse(hasattr(ra, "WEB_READY"), "the early log marker is gone")

    def test_a_drawn_app_is_ready(self):
        self.assertEqual(ra.wait_rendered("http://x", 60, probe=lambda u, s: True), (True, ""))

    # ------------------------------------------------------------------- which browser
    def test_browser_lookup_order(self):
        pw = "/pw/Chromium"
        everything = {pw, ra.BRAVE, ra.CHROME}
        find = lambda env, have: ra.find_browser(env, exists=lambda p: p in have, globber=lambda pat: [pw])
        self.assertEqual(find({"THEBES_REVIEW_BROWSER": "/mine"}, everything), "/mine")
        self.assertEqual(find({}, everything), pw)
        self.assertEqual(find({}, {ra.BRAVE, ra.CHROME}), ra.BRAVE)
        self.assertEqual(find({}, {ra.CHROME}), ra.CHROME)
        self.assertIsNone(find({}, set()))

    def test_the_build_gets_the_messaging_worker_defines(self):
        env = os.path.join(self.tmp, ".env")
        open(env, "w").close()
        defines = ra.app_defines(env)
        self.assertEqual(defines, [
            "--dart-define-from-file=%s" % env,
            "--dart-define=MESSAGING_API_BASE_URL=https://dabbler-messaging-staging.dabbler-sport.workers.dev",
            "--dart-define=MESSAGING_ACCESS_MODE=all"])
        self.assertEqual(ra.app_defines(os.path.join(self.tmp, "none"))[0:1],
                         ["--dart-define=MESSAGING_API_BASE_URL=%s" % ra.MESSAGING_API_BASE_URL])

    def test_a_wrong_browser_path_is_not_replaced_and_fails_closed(self):
        with mock.patch.dict(os.environ, {"THEBES_REVIEW_BROWSER": "/no/such/browser"}):
            self.assertEqual(ra.find_browser(), "/no/such/browser")
            ok, why = ra.wait_rendered("http://127.0.0.1:9", 3)
        self.assertFalse(ok)
        self.assertIn("build not ready", why)

    def test_no_browser_at_all_fails_closed(self):
        with mock.patch.object(ra, "find_browser", return_value=None):
            self.assertFalse(ra._browser_probe("http://x", 1))

    # ------------------------------------------------------------------- start(), end to end with fakes
    def start(self, rendered, builder=None):
        item = {"ticket": "KAN-622", "sha": SHA, "branch": "alpha-ramesseum"}
        proc = mock.Mock(pid=4242)
        with mock.patch.object(ra, "_worktree", return_value=self.wt), \
                mock.patch.object(ra, "build_web", side_effect=builder or (lambda *a, **k: (os.path.join(self.tmp, "web"), False))), \
                mock.patch.object(ra, "_free_port", return_value=8124), \
                mock.patch.object(ra, "_wait_port", return_value=True), \
                mock.patch.object(ra.subprocess, "Popen", return_value=proc), \
                mock.patch.object(ra, "wait_rendered", return_value=(rendered, "" if rendered else "build not ready: blank")), \
                mock.patch.object(ra.os, "killpg"), \
                mock.patch.object(ra, "_git", return_value=SimpleNamespace(returncode=0, stdout="", stderr="")):
            return ra.start(item)

    def test_start_on_a_blank_canvas_raises_build_not_ready_and_records_it(self):
        with self.assertRaises(RuntimeError) as ctx:
            self.start(False)
        self.assertIn("build not ready", str(ctx.exception))
        rec = ra.render_record("KAN-622")
        self.assertEqual((rec["rendered"], rec["sha"]), (False, SHA))
        self.assertIsNone(ra.running("KAN-622"), "the half-started server is stopped")

    def test_start_prints_the_url_only_after_the_app_drew(self):
        out = self.start(True)
        self.assertEqual((out["status"], out["url"], out["rendered"]), ("running", "http://localhost:8124", True))
        self.assertTrue(ra.render_record("KAN-622")["rendered"])

    def test_a_failed_build_is_recorded_as_not_rendered(self):
        def bad(*a, **k):
            raise RuntimeError("build not ready: flutter build failed")
        with self.assertRaises(RuntimeError):
            self.start(True, builder=bad)
        self.assertFalse(ra.render_record("KAN-622")["rendered"])


if __name__ == "__main__":
    unittest.main()
