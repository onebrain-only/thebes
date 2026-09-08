#!/usr/bin/env python3
"""Jira REST connector — every test runs against a MOCKED transport.

Not one test in this file opens a socket. `jira._open` is the single seam the
connector calls to reach the network, and every test replaces it; the environment
is replaced too, with an obviously fake token, so a test that accidentally escaped
the seam would authenticate with nothing and fail loudly rather than mutate the
live board.

What these tests defend is the module's one load-bearing promise: A JIRA FAILURE
IS NEVER AN EMPTY RESULT. Each HTTP failure mode gets its own assertion that it
raises its own exception type, because the defect being prevented is a caller
reading `[]` and concluding there is no work, or `None` and concluding Done.

Stdlib only, like the rest of the suite.
"""
import io
import json
import os
import sys
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import ok, raises, section, summary, repo_root      # noqa: E402

sys.path.insert(0, os.path.join(repo_root(), "agent", "integrations"))
import jira                                                       # noqa: E402

FAKE_TOKEN = "fake-token-not-a-real-credential-0123456789"

os.environ["JIRA_API_TOKEN"] = FAKE_TOKEN
os.environ["JIRA_ACCOUNT_EMAIL"] = "nobody@example.invalid"
os.environ["JIRA_API_BASE"] = "https://jira.example.invalid/ex/jira/FAKECLOUD"
os.environ.pop("JIRA_CLOUD_ID", None)


# ---------------------------------------------------------------- transport doubles

class FakeResponse(io.BytesIO):
    def __init__(self, payload, status=200):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        io.BytesIO.__init__(self, body)
        self.status = status

    def getcode(self):
        return self.status


class Recorder(object):
    """Replaces `_open`, serves a scripted list of outcomes, records the requests."""
    def __init__(self, *outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def __call__(self, req, timeout):
        self.requests.append(req)
        out = self.outcomes.pop(0) if len(self.outcomes) > 1 else self.outcomes[0]
        if isinstance(out, Exception):
            raise out
        return out


def install(*outcomes):
    rec = Recorder(*outcomes)
    jira._open = rec
    return rec


def http_error(code, payload=None, headers=None):
    body = json.dumps(payload if payload is not None else
                      {"errorMessages": ["boom"], "errors": {}}).encode()
    return urllib.error.HTTPError("https://jira.example.invalid/x", code, "err",
                                  headers or {}, io.BytesIO(body))


ISSUE = {
    "id": "10500", "key": "KAN-153",
    "fields": {
        "summary": "Fix false comment",
        "status": {"id": 10044, "name": "Self-review",
                   "statusCategory": {"key": "indeterminate"}},
        "duedate": "2026-09-08",
        "updated": "2026-09-08T10:00:00.000+0000",
        "created": "2026-09-01T10:00:00.000+0000",
        "issuetype": {"name": "Task"},
        "labels": ["frontend"],
        "assignee": None,
        "description": {"type": "doc", "version": 1, "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}]},
    },
}


# ---------------------------------------------------------------- config & secret

section("configuration and the secret")

cfg = jira.config()
ok("config resolves the base URL", cfg["base"].endswith("/ex/jira/FAKECLOUD"))
ok("config resolves the account email", cfg["email"] == "nobody@example.invalid")
ok("config NEVER returns the token",
   not any(FAKE_TOKEN in str(v) for v in cfg.values()))

os.environ["JIRA_API_BASE"] = ""
os.environ["JIRA_CLOUD_ID"] = "FAKECLOUD"
ok("base URL is derived from cloud id when JIRA_API_BASE is absent",
   jira.config()["base"] == "https://api.atlassian.com/ex/jira/FAKECLOUD")
os.environ["JIRA_API_BASE"] = "https://jira.example.invalid/ex/jira/FAKECLOUD"

_saved = os.environ.pop("JIRA_API_TOKEN")
raises("missing token fails with the agreed sentinel",
       lambda: jira.get_issue("KAN-1"), "JIRA_API_TOKEN_NOT_AVAILABLE")
try:
    jira.config()
except jira.JiraNotConfigured as e:
    ok("JiraNotConfigured is a JiraError subclass", isinstance(e, jira.JiraError))
os.environ["JIRA_API_TOKEN"] = _saved

_saved_email = os.environ.pop("JIRA_ACCOUNT_EMAIL")
raises("missing email is reported distinctly, not as a token failure",
       jira.config, "JIRA_ACCOUNT_EMAIL_NOT_AVAILABLE")
os.environ["JIRA_ACCOUNT_EMAIL"] = _saved_email

rec = install(FakeResponse(ISSUE))
jira.get_issue("KAN-153")
sent = rec.requests[0]
ok("request carries an Authorization header", sent.has_header("Authorization"))
ok("Authorization is Basic", sent.get_header("Authorization").startswith("Basic "))
ok("the raw token is NOT the header value",
   FAKE_TOKEN not in sent.get_header("Authorization"))
ok("_scrub removes the raw token", FAKE_TOKEN not in jira._scrub("x " + FAKE_TOKEN + " y"))
ok("_scrub removes the base64 Authorization value",
   sent.get_header("Authorization").split(" ", 1)[1]
   not in jira._scrub("leak " + sent.get_header("Authorization")))
ok("_scrub leaves ordinary text alone", jira._scrub("plain text") == "plain text")


# ---------------------------------------------------------------- read: issue

section("read operations")

install(FakeResponse(ISSUE))
i = jira.get_issue("KAN-153")
ok("get_issue returns the key", i["key"] == "KAN-153")
ok("get_issue returns the status name", i["status"] == "Self-review")
ok("status_id is a STRING (board.py keys on strings)", i["status_id"] == "10044")
ok("get_issue returns the due date", i["due_date"] == "2026-09-08")
ok("get_issue flattens the ADF description", i["description"] == "hello")
ok("get_issue returns labels", i["labels"] == ["frontend"])
ok("an absent assignee is None, not a crash", i["assignee"] is None)

install(FakeResponse(ISSUE))
ok("raw=True returns the untouched Jira payload",
   jira.get_issue("KAN-153", raw=True)["fields"]["summary"] == "Fix false comment")

install(FakeResponse(ISSUE))
jira.get_issue("KAN-153", fields=["summary"])
ok("explicit fields reach the query string",
   "fields=summary" in jira._open.requests[0].full_url)

raises("get_issue refuses an empty key", lambda: jira.get_issue(""), "required")

install(FakeResponse({"nope": 1}))
raises("a 200 that is not an issue raises JiraProtocolError",
       lambda: jira.get_issue("KAN-1"), "not an issue")


# ---------------------------------------------------------------- read: search

section("search and pagination")

page1 = {"issues": [ISSUE, ISSUE], "nextPageToken": "TOK1"}
page2 = {"issues": [ISSUE], "nextPageToken": None}
rec = install(FakeResponse(page1), FakeResponse(page2))
res = jira.search_issues("project = KAN", limit=10, page_size=2)
ok("search follows nextPageToken across pages", len(res) == 3)
ok("search made exactly two requests", len(rec.requests) == 2)
ok("the second request carries the page token", "nextPageToken=TOK1" in rec.requests[1].full_url)
ok("search normalizes each issue", res[0]["status_id"] == "10044")

rec = install(FakeResponse({"issues": [ISSUE] * 5, "nextPageToken": "MORE"}))
res = jira.search_issues("project = KAN", limit=3, page_size=5)
ok("search honours the caller's limit", len(res) == 3)

rec = install(FakeResponse({"issues": [], "nextPageToken": None}))
ok("an empty page is an empty list — a SUCCESSFUL read of nothing",
   jira.search_issues("project = NOPE") == [])

install(FakeResponse({"maxResults": 50}))
raises("a search response with no `issues` key raises rather than returning []",
       lambda: jira.search_issues("project = KAN"), "no `issues` key")

install(FakeResponse([1, 2, 3]))
raises("a search response of the wrong type raises",
       lambda: jira.search_issues("project = KAN"), "not an object")

raises("search refuses empty JQL", lambda: jira.search_issues(""), "required")


# ---------------------------------------------------------------- read: transitions/comments

section("transitions and comments")

install(FakeResponse({"transitions": [
    {"id": 6, "name": "Self-review", "to": {"id": 10044, "name": "Self-review"}},
    {"id": 41, "name": "Done", "to": {"id": 10007, "name": "Done"}}]}))
tr = jira.get_transitions("KAN-153")
ok("get_transitions returns every transition", len(tr) == 2)
ok("transition ids are strings", tr[0]["id"] == "6")
ok("target status ids are strings", tr[0]["to_status_id"] == "10044")
ok("target status names survive", tr[1]["to_status"] == "Done")

install(FakeResponse({"nope": []}))
raises("a malformed transitions response raises rather than returning []",
       lambda: jira.get_transitions("KAN-1"), "no `transitions` key")


def comment(n):
    return {"id": n, "author": {"displayName": "Horemheb"},
            "created": "2026-09-08T00:00:00.000+0000",
            "updated": "2026-09-08T00:00:00.000+0000",
            "body": {"type": "doc", "content": [
                {"type": "paragraph", "content": [{"type": "text", "text": "c%s" % n}]}]}}


rec = install(FakeResponse({"comments": [comment(1), comment(2)], "total": 3},),
              FakeResponse({"comments": [comment(3)], "total": 3}))
cs = jira.get_comments("KAN-153", limit=10, page_size=2)
ok("get_comments follows startAt paging to `total`", len(cs) == 3)
ok("comment paging sent startAt on the second call", "startAt=2" in rec.requests[1].full_url)
ok("comment bodies are flattened from ADF", cs[0]["body"] == "c1")
ok("comment authors survive", cs[0]["author"] == "Horemheb")
ok("comment ids are strings", cs[2]["id"] == "3")

install(FakeResponse({"total": 0}))
raises("a malformed comment response raises rather than returning []",
       lambda: jira.get_comments("KAN-1"), "no `comments` key")


# ---------------------------------------------------------------- write primitives

section("write primitives")

rec = install(FakeResponse(b"", status=204))
ok("transition_issue returns None on 204", jira.transition_issue("KAN-153", "41") is None)
ok("transition_issue POSTs", rec.requests[0].get_method() == "POST")
ok("transition_issue hits the transitions endpoint",
   rec.requests[0].full_url.endswith("/issue/KAN-153/transitions"))
ok("transition id is sent as a string in the body",
   json.loads(rec.requests[0].data)["transition"]["id"] == "41")
raises("transition_issue refuses an empty transition id",
       lambda: jira.transition_issue("KAN-1", ""), "required")

rec = install(FakeResponse({"id": 900, "created": "2026-09-09T00:00:00.000+0000"}))
c = jira.add_comment("KAN-153", "line one\nline two")
ok("add_comment returns the new comment id as a string", c["id"] == "900")
body = json.loads(rec.requests[0].data)["body"]
ok("add_comment sends ADF, not a bare string", body["type"] == "doc")
ok("add_comment preserves both lines as paragraphs", len(body["content"]) == 2)
ok("add_comment text survives the ADF wrap",
   body["content"][0]["content"][0]["text"] == "line one")
raises("add_comment refuses an empty body", lambda: jira.add_comment("KAN-1", ""), "required")

rec = install(FakeResponse(b"", status=204))
ok("update_issue returns None on 204",
   jira.update_issue("KAN-153", {"duedate": "2026-09-10"}) is None)
ok("update_issue PUTs", rec.requests[0].get_method() == "PUT")
ok("update_issue wraps the fields",
   json.loads(rec.requests[0].data)["fields"]["duedate"] == "2026-09-10")
raises("update_issue refuses empty fields", lambda: jira.update_issue("KAN-1", {}), "required")

ok("no write primitive consults Persistent State",
   "store" not in dir(jira) and "observe_lifecycle" not in dir(jira))


# ---------------------------------------------------------------- error model

section("error model — a failure is never an empty result")

install(http_error(401))
raises("401 raises JiraAuthError", lambda: jira.get_issue("KAN-1"), "rejected the credential")
install(http_error(403))
raises("403 raises JiraPermissionError", lambda: jira.get_issue("KAN-1"), "forbade")
install(http_error(404))
raises("404 raises JiraNotFound", lambda: jira.get_issue("KAN-1"), "no such resource")
install(http_error(429, headers={"Retry-After": "42"}))
raises("429 raises JiraRateLimited", lambda: jira.get_issue("KAN-1"), "rate-limited")
install(http_error(500))
raises("500 raises JiraUnavailable", lambda: jira.get_issue("KAN-1"), "unavailable")
install(http_error(503))
raises("503 raises JiraUnavailable", lambda: jira.get_issue("KAN-1"), "unavailable")
install(http_error(400, {"errorMessages": [], "errors": {"transition": "bad id"}}))
raises("400 raises JiraInvalidRequest", lambda: jira.transition_issue("KAN-1", "999"),
       "refused the request")


def caught(fn):
    try:
        fn()
    except Exception as e:
        return e
    return None


install(http_error(401))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("401 is typed JiraAuthError", isinstance(e, jira.JiraAuthError))
ok("401 is NOT confused with not-found", not isinstance(e, jira.JiraNotFound))
ok("401 carries the status code", e.status == 401)

install(http_error(404))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("404 is typed JiraNotFound", isinstance(e, jira.JiraNotFound))
ok("404 does NOT return None", e is not None)

install(http_error(429, headers={"Retry-After": "42"}))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("429 exposes Retry-After as an int", e.retry_after == 42)

install(http_error(429))
ok("a 429 with no Retry-After leaves it None",
   caught(lambda: jira.get_issue("KAN-1")).retry_after is None)

install(http_error(400, {"errorMessages": [], "errors": {"transition": "bad id"}}))
e = caught(lambda: jira.transition_issue("KAN-1", "999"))
ok("an invalid transition names the offending field", "transition" in e.errors)
ok("an invalid transition is JiraInvalidRequest", isinstance(e, jira.JiraInvalidRequest))
ok("an invalid transition is NOT JiraUnavailable", not isinstance(e, jira.JiraUnavailable))

install(http_error(418))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("an unexpected status raises the base JiraError", type(e) is jira.JiraError)
ok("an unexpected status still carries its code", e.status == 418)

install(FakeResponse(b"<html>not json</html>"))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("malformed JSON raises JiraProtocolError", isinstance(e, jira.JiraProtocolError))
ok("malformed JSON is NOT reported as unavailable — the server answered",
   not isinstance(e, jira.JiraUnavailable))

install(urllib.error.URLError("connection refused"))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("a network failure raises JiraUnavailable", isinstance(e, jira.JiraUnavailable))
ok("a network failure does NOT return an empty result", e is not None)

install(TimeoutError("timed out"))
ok("a timeout raises JiraUnavailable",
   isinstance(caught(lambda: jira.get_issue("KAN-1")), jira.JiraUnavailable))

install(urllib.error.URLError("connection refused"))
ok("a network failure on SEARCH raises rather than yielding []",
   isinstance(caught(lambda: jira.search_issues("project = KAN")), jira.JiraUnavailable))

install(http_error(500))
ok("a 5xx on SEARCH raises rather than yielding []",
   isinstance(caught(lambda: jira.search_issues("project = KAN")), jira.JiraUnavailable))

ok("every connector exception is a JiraError",
   all(issubclass(c, jira.JiraError) for c in (
       jira.JiraNotConfigured, jira.JiraAuthError, jira.JiraPermissionError,
       jira.JiraNotFound, jira.JiraInvalidRequest, jira.JiraRateLimited,
       jira.JiraUnavailable, jira.JiraProtocolError)))


# ---------------------------------------------------------------- secret containment

section("the secret never appears in a failure representation")

leaky = {"errorMessages": ["token was " + FAKE_TOKEN], "errors": {}}
for code in (400, 401, 403, 404, 429, 500, 418):
    install(http_error(code, leaky))
    e = caught(lambda: jira.get_issue("KAN-1"))
    ok("a %s that echoes the token is scrubbed in str(e)" % code, FAKE_TOKEN not in str(e))
    ok("a %s that echoes the token is scrubbed in .body" % code,
       FAKE_TOKEN not in str(getattr(e, "body", "")))
    ok("a %s that echoes the token is scrubbed in repr(e)" % code, FAKE_TOKEN not in repr(e))

install(FakeResponse(("<html>" + FAKE_TOKEN + "</html>").encode()))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("a malformed body containing the token is scrubbed", FAKE_TOKEN not in str(e))
ok("a malformed body containing the token is scrubbed in .body",
   FAKE_TOKEN not in str(e.body))

install(urllib.error.URLError("bad handshake for " + FAKE_TOKEN))
ok("a network error mentioning the token is scrubbed",
   FAKE_TOKEN not in str(caught(lambda: jira.get_issue("KAN-1"))))

install(http_error(401))
e = caught(lambda: jira.get_issue("KAN-1"))
ok("no exception message carries an Authorization header",
   "Basic " not in str(e) and "Authorization" not in str(e))


# ---------------------------------------------------------------- boundary

section("the adapter is a boundary, not an authority")

src = open(os.path.join(repo_root(), "agent", "integrations", "jira.py")).read()
ok("the connector imports no third-party package",
   not any(("import " + p) in src for p in ("requests", "aiohttp", "httpx", "atlassian")))
ok("the connector imports nothing from the state layer",
   "import store" not in src and "from store" not in src)
code = "\n".join(l for l in src.split("\n") if not l.strip().startswith("#"))
ok("the connector never CALLS observe_lifecycle — it only supplies the fact",
   "observe_lifecycle(" not in code)
ok("the connector defines no Persistent State writer",
   not any(n in dir(jira) for n in ("store", "update", "claim", "observe_lifecycle")))
ok("the connector never prints", "print(" not in src)
ok("the connector never logs", "logging" not in src)

sys.exit(summary())
