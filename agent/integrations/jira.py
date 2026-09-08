#!/usr/bin/env python3
"""The ONE Jira REST boundary for Thebes.

Jira is the Work Lifecycle authority. This module is how Thebes asks it, and the
only place that speaks HTTP to Atlassian: no agent, workflow or skill issues its
own `curl`, because a second caller is a second set of error semantics and the
first thing that gets lost is the difference between "Jira said no work" and
"Jira did not answer".

WHAT THIS MODULE IS NOT
  It is a set of PRIMITIVES. It executes an operation that has ALREADY been
  authorised elsewhere. It does not decide when to transition, which transition is
  valid, whether work is complete, who owns work, or which validation route
  applies — those live in the orchestration layer and in `agent/state/`. Nothing
  here imports the state layer, and nothing here writes Persistent State: the
  caller feeds a factual Jira response to `store.observe_lifecycle`.

FAILURE IS NEVER AN EMPTY RESULT
  Every failure mode raises a distinct exception. A caller that catches `JiraError`
  learns that Jira did not answer; it never receives `[]` and concludes there is no
  work, and never receives `None` and concludes Done. That collapse is the single
  defect this error model exists to prevent.

THE SECRET
  `JIRA_API_TOKEN` is read from the environment at request time and used only to
  build an `Authorization` header inside `_request`. It is never returned, never
  logged, never placed in an exception, and never written anywhere. `_scrub`
  guarantees the last of those even if Atlassian were to echo it back.

Python stdlib only — urllib, json, base64. Same constitution as the state layer:
a fresh clone can run this with nothing installed.
"""
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

DEFAULT_TIMEOUT = 30
API = "/rest/api/3"


# --------------------------------------------------------------- error model

class JiraError(Exception):
    """Base: Jira did not give us the answer we asked for."""
    def __init__(self, message, status=None, url=None, body=None):
        super().__init__(message)
        self.status = status
        self.url = url
        self.body = body


class JiraNotConfigured(JiraError):
    """A required environment variable is absent. Message is the agreed sentinel."""


class JiraAuthError(JiraError):
    """401 — the credential was rejected."""


class JiraPermissionError(JiraError):
    """403 — authenticated, but not allowed to do this."""


class JiraNotFound(JiraError):
    """404 — no such issue, or it is invisible to this account."""


class JiraInvalidRequest(JiraError):
    """400 — Jira refused the request itself (an invalid transition id, a field
    that is not on the screen). Carries `errors` when Jira names the fields."""
    def __init__(self, message, status=None, url=None, body=None, errors=None):
        super().__init__(message, status=status, url=url, body=body)
        self.errors = errors or {}


class JiraRateLimited(JiraError):
    """429 — back off. `retry_after` is seconds when Jira supplied it."""
    def __init__(self, message, status=None, url=None, body=None, retry_after=None):
        super().__init__(message, status=status, url=url, body=body)
        self.retry_after = retry_after


class JiraUnavailable(JiraError):
    """5xx, or the request never completed (DNS, TLS, timeout, reset)."""


class JiraProtocolError(JiraError):
    """A 2xx that was not the shape we asked for — malformed JSON, or JSON of
    the wrong type. Distinct from JiraUnavailable: the server answered."""


# --------------------------------------------------------------- credentials

def _env(name):
    v = os.environ.get(name)
    return v.strip() if v else None


def config():
    """Resolve non-secret configuration. Raises JiraNotConfigured if incomplete.

    The token is deliberately NOT returned. Nothing outside `_request` needs it,
    and a config dict is exactly the object that ends up in a debug print.
    """
    if not _env("JIRA_API_TOKEN"):
        raise JiraNotConfigured("JIRA_API_TOKEN_NOT_AVAILABLE")
    email = _env("JIRA_ACCOUNT_EMAIL")
    if not email:
        raise JiraNotConfigured("JIRA_ACCOUNT_EMAIL_NOT_AVAILABLE")
    base = _env("JIRA_API_BASE")
    if not base:
        cloud = _env("JIRA_CLOUD_ID")
        if not cloud:
            raise JiraNotConfigured("JIRA_API_BASE_NOT_AVAILABLE")
        base = "https://api.atlassian.com/ex/jira/" + cloud
    return {"base": base.rstrip("/"), "email": email, "cloud_id": _env("JIRA_CLOUD_ID")}


def _auth_header():
    """Build the Authorization value. The ONLY place the token is touched."""
    token = _env("JIRA_API_TOKEN")
    if not token:
        raise JiraNotConfigured("JIRA_API_TOKEN_NOT_AVAILABLE")
    raw = ("%s:%s" % (_env("JIRA_ACCOUNT_EMAIL"), token)).encode("utf-8")
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _scrub(text):
    """Remove the secret from anything that could be shown to a human.

    Belt and braces: no Jira response should contain the token, but an exception
    message is the last place we want to find out we were wrong.
    """
    if not text:
        return text
    token = os.environ.get("JIRA_API_TOKEN")
    out = str(text)
    if token:
        out = out.replace(token, "[REDACTED]")
        try:
            b64 = base64.b64encode(
                ("%s:%s" % (os.environ.get("JIRA_ACCOUNT_EMAIL", ""), token)).encode()
            ).decode("ascii")
            out = out.replace(b64, "[REDACTED]")
        except Exception:                                   # pragma: no cover
            pass
    return out


# --------------------------------------------------------------- transport

def _open(req, timeout):
    """Seam for tests. Never called with a live URL by the test suite."""
    return urllib.request.urlopen(req, timeout=timeout)


def _decode(raw, url, status):
    if raw is None or raw == b"" or raw == "":
        return None
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    try:
        return json.loads(raw)
    except ValueError as e:
        raise JiraProtocolError(
            "Jira returned a %s that is not JSON: %s" % (status, _scrub(str(e))),
            status=status, url=url, body=_scrub(raw[:400]))


def _raise_for_http(e, url):
    try:
        raw = e.read()
    except Exception:                                       # pragma: no cover
        raw = b""
    text = _scrub(raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw))
    detail = text[:400]
    errors = {}
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            msgs = parsed.get("errorMessages") or []
            errors = parsed.get("errors") or {}
            if msgs or errors:
                detail = _scrub("; ".join(list(msgs) + [
                    "%s: %s" % (k, v) for k, v in sorted(errors.items())]))[:400]
    except ValueError:
        pass

    code = e.code
    where = "%s %s" % (code, url)
    if code == 401:
        raise JiraAuthError("Jira rejected the credential (%s): %s" % (where, detail),
                            status=code, url=url, body=detail)
    if code == 403:
        raise JiraPermissionError("Jira forbade this operation (%s): %s" % (where, detail),
                                  status=code, url=url, body=detail)
    if code == 404:
        raise JiraNotFound("Jira has no such resource, or it is invisible to this "
                           "account (%s): %s" % (where, detail),
                           status=code, url=url, body=detail)
    if code == 429:
        retry = None
        try:
            retry = int(e.headers.get("Retry-After"))
        except (TypeError, ValueError):
            pass
        raise JiraRateLimited("Jira rate-limited this client (%s): %s" % (where, detail),
                              status=code, url=url, body=detail, retry_after=retry)
    if 500 <= code < 600:
        raise JiraUnavailable("Jira is unavailable (%s): %s" % (where, detail),
                              status=code, url=url, body=detail)
    if code == 400:
        raise JiraInvalidRequest("Jira refused the request (%s): %s" % (where, detail),
                                 status=code, url=url, body=detail, errors=errors)
    raise JiraError("Unexpected Jira response (%s): %s" % (where, detail),
                    status=code, url=url, body=detail)


def _request(method, path, params=None, body=None, timeout=DEFAULT_TIMEOUT):
    """Issue one authenticated request and return decoded JSON (or None on 204).

    Every non-2xx outcome leaves through a typed exception; there is no path that
    swallows a failure into an empty value.
    """
    cfg = config()
    url = cfg["base"] + path
    if params:
        clean = {k: v for k, v in params.items() if v is not None}
        if clean:
            url += "?" + urllib.parse.urlencode(clean, doseq=True)

    payload = None
    if body is not None:
        payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Authorization", _auth_header())
    req.add_header("Accept", "application/json")
    if payload is not None:
        req.add_header("Content-Type", "application/json")

    try:
        resp = _open(req, timeout)
    except urllib.error.HTTPError as e:
        _raise_for_http(e, url)
    except urllib.error.URLError as e:
        raise JiraUnavailable("Jira could not be reached (%s): %s"
                              % (url, _scrub(getattr(e, "reason", e))), url=url)
    except (OSError, TimeoutError) as e:
        raise JiraUnavailable("Jira request failed (%s): %s" % (url, _scrub(e)), url=url)

    try:
        status = getattr(resp, "status", None) or resp.getcode()
        raw = resp.read()
    finally:
        try:
            resp.close()
        except Exception:                                   # pragma: no cover
            pass
    return _decode(raw, url, status)


# --------------------------------------------------------------- normalising

def _adf_text(node):
    """Flatten an Atlassian Document Format body to plain text.

    Comment bodies are ADF trees, not strings. We keep only the text so that a
    caller reading a comment cannot accidentally re-post rich content it did not
    author. Formatting is not preserved and is not claimed to be.
    """
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_adf_text(n) for n in node)
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    inner = _adf_text(node.get("content"))
    if node.get("type") in ("paragraph", "heading", "listItem", "blockquote"):
        return inner + "\n"
    return inner


def to_adf(text):
    """Wrap plain text as a minimal ADF document, for comment bodies."""
    lines = str(text).split("\n")
    return {"type": "doc", "version": 1,
            "content": [{"type": "paragraph",
                         "content": ([{"type": "text", "text": ln}] if ln else [])}
                        for ln in lines]}


def normalize_issue(raw):
    """Reduce a Jira issue to the facts Thebes reasons about.

    `status_id` is a string on purpose: `agent/state/board.py` keys on strings,
    and an int here would silently miss every lookup.
    """
    if not isinstance(raw, dict) or "key" not in raw:
        raise JiraProtocolError("Jira response is not an issue: %s"
                                % _scrub(str(raw)[:200]))
    f = raw.get("fields") or {}
    status = f.get("status") or {}
    assignee = f.get("assignee") or None
    return {
        "key": raw.get("key"),
        "id": raw.get("id"),
        "summary": f.get("summary"),
        "status": status.get("name"),
        "status_id": str(status["id"]) if status.get("id") is not None else None,
        "status_category": ((status.get("statusCategory") or {}).get("key")),
        "due_date": f.get("duedate"),
        "updated": f.get("updated"),
        "created": f.get("created"),
        "issue_type": ((f.get("issuetype") or {}).get("name")),
        "parent": ((f.get("parent") or {}).get("key")),
        "labels": list(f.get("labels") or []),
        "assignee": (assignee or {}).get("displayName"),
        "description": _adf_text(f.get("description")).strip() or None,
    }


DEFAULT_FIELDS = ("summary", "status", "duedate", "updated", "created",
                  "issuetype", "parent", "labels", "assignee")


# --------------------------------------------------------------- read ops

def get_issue(issue_key, fields=None, raw=False):
    """Read one issue. Raises JiraNotFound rather than returning None."""
    if not issue_key:
        raise ValueError("issue_key is required")
    flds = list(fields) if fields is not None else list(DEFAULT_FIELDS)
    if fields is None:
        flds.append("description")
    data = _request("GET", "%s/issue/%s" % (API, urllib.parse.quote(str(issue_key))),
                    params={"fields": ",".join(flds)})
    return data if raw else normalize_issue(data)


def search_issues(jql, fields=None, limit=50, page_size=50, raw=False):
    """Run a JQL search, following `nextPageToken` until `limit` is reached.

    Jira Cloud's current search endpoint pages by opaque token, not by offset, and
    returns no total. `limit` is a hard stop the CALLER sets: an unbounded search
    against a live board is how a read turns into an outage.
    """
    if not jql:
        raise ValueError("jql is required")
    flds = list(fields) if fields is not None else list(DEFAULT_FIELDS)
    out, token, guard = [], None, 0
    while len(out) < limit:
        guard += 1
        if guard > 100:
            raise JiraProtocolError("Jira search did not terminate: 100 pages "
                                    "without exhausting results")
        page = _request("GET", "%s/search/jql" % API, params={
            "jql": jql,
            "fields": ",".join(flds),
            "maxResults": min(page_size, limit - len(out)),
            "nextPageToken": token,
        })
        if not isinstance(page, dict):
            raise JiraProtocolError("Jira search returned %s, not an object"
                                    % type(page).__name__)
        issues = page.get("issues")
        if issues is None:
            raise JiraProtocolError("Jira search response carries no `issues` key")
        out.extend(issues if raw else [normalize_issue(i) for i in issues])
        token = page.get("nextPageToken")
        if not token or not issues:
            break
    return out[:limit]


def get_transitions(issue_key):
    """The transitions Jira will accept for this issue RIGHT NOW.

    Returned so a caller can VERIFY an already-authorised target exists. Reading
    them is not permission to choose one.
    """
    data = _request("GET", "%s/issue/%s/transitions"
                    % (API, urllib.parse.quote(str(issue_key))))
    if not isinstance(data, dict) or "transitions" not in data:
        raise JiraProtocolError("Jira transitions response has no `transitions` key")
    return [{"id": str(t.get("id")),
             "name": t.get("name"),
             "to_status": ((t.get("to") or {}).get("name")),
             "to_status_id": (str((t.get("to") or {}).get("id"))
                              if (t.get("to") or {}).get("id") is not None else None)}
            for t in data["transitions"]]


def get_comments(issue_key, limit=50, page_size=50):
    """Read comments, following Jira's startAt/total paging."""
    key = urllib.parse.quote(str(issue_key))
    out, start, guard = [], 0, 0
    while len(out) < limit:
        guard += 1
        if guard > 100:
            raise JiraProtocolError("Jira comment paging did not terminate")
        page = _request("GET", "%s/issue/%s/comment" % (API, key), params={
            "startAt": start, "maxResults": min(page_size, limit - len(out)),
            "orderBy": "created"})
        if not isinstance(page, dict) or "comments" not in page:
            raise JiraProtocolError("Jira comment response has no `comments` key")
        batch = page["comments"]
        out.extend({"id": str(c.get("id")),
                    "author": ((c.get("author") or {}).get("displayName")),
                    "created": c.get("created"),
                    "updated": c.get("updated"),
                    "body": _adf_text(c.get("body")).strip()} for c in batch)
        start += len(batch)
        total = page.get("total")
        if not batch or (isinstance(total, int) and start >= total):
            break
    return out[:limit]


# --------------------------------------------------------------- write ops
#
# Primitives. Each executes a decision made elsewhere. None of them consults
# Persistent State, chooses a target, or judges whether the move is correct.

def transition_issue(issue_key, transition_id):
    """Apply an ALREADY-CHOSEN transition. Returns None (Jira answers 204)."""
    if not transition_id:
        raise ValueError("transition_id is required")
    return _request("POST", "%s/issue/%s/transitions"
                    % (API, urllib.parse.quote(str(issue_key))),
                    body={"transition": {"id": str(transition_id)}})


def add_comment(issue_key, body):
    """Post a comment. Plain text in, ADF on the wire."""
    if not body:
        raise ValueError("comment body is required")
    data = _request("POST", "%s/issue/%s/comment"
                    % (API, urllib.parse.quote(str(issue_key))),
                    body={"body": to_adf(body)})
    return {"id": str((data or {}).get("id")), "created": (data or {}).get("created")}


def update_issue(issue_key, fields):
    """Set fields on an issue. Returns None (Jira answers 204)."""
    if not fields:
        raise ValueError("fields is required")
    return _request("PUT", "%s/issue/%s" % (API, urllib.parse.quote(str(issue_key))),
                    body={"fields": dict(fields)})
