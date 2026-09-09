#!/usr/bin/env python3
"""Repository-aware branch protection for `git push`.

WHY THIS EXISTS, AND WHAT IT IS NOT

The rule "never push main" is Product-specific: `dabblersport/webapp`'s `main`
deploys straight to app.dabbler.pro, so pushing it ships to real users. The
canonical Thebes repository `onebrain-only/thebes` also has a branch called `main`,
and there it is the ordinary authorised release branch. Until now the distinction
lived only in prose, so the two were indistinguishable to anything mechanical — the
command string `git push origin main` is byte-identical in both.

That is why an authorised Thebes release push was refused: nothing available to the
refusing layer could tell which repository the command was aimed at.

THIS GUARD DENIES. IT NEVER GRANTS.

A hook can veto a tool call; it cannot hand out a permission the operator has not
given. So this module's answer is exactly one of:

    DENY   — a protected-branch push, refused with the reason
    PASS   — no opinion; whatever permission policy applies still applies

`PASS` on a Thebes release push is NOT the guard authorising it. It means the guard
has nothing to say and the normal permission layer decides. Anything else would be
this file granting itself access, which is the shape of every permission bug worth
having a guard for.

IT IS REPOSITORY-AWARE, NOT STRING-AWARE. The repository is resolved by running
`git rev-parse` in the directory the command will actually run in — following `-C`
and a leading `cd` — and then reading its `origin` remote. Matching on the command
text alone is defeated by a `cd` and would give a false sense of protection.

Stdlib only.
"""
import os
import re
import shlex
import subprocess

# Identity comes from the remote, not from a local path or a directory name: a
# clone can live anywhere and be called anything.
PRODUCT_REMOTES = ("dabblersport/webapp",)
THEBES_REMOTES = ("onebrain-only/thebes",)

# Protected on the PRODUCT repository only.
PRODUCT_PROTECTED = ("main", "master")
# The Product repository's ordinary integration target.
PRODUCT_INTEGRATION = "Canary"

DENY, PASS = "DENY", "PASS"


def _run(cwd, *args):
    try:
        p = subprocess.run(["git"] + list(args), cwd=cwd, capture_output=True,
                           text=True, timeout=10)
        return p.stdout.strip() if p.returncode == 0 else ""
    except Exception:                                    # noqa: BLE001
        return ""


def classify_repo(cwd):
    """'product', 'thebes', or 'other' — from the origin remote of the repo at cwd."""
    if not cwd or not os.path.isdir(cwd):
        return "other"
    url = _run(cwd, "remote", "get-url", "origin")
    if not url:
        return "other"
    norm = url.rstrip("/")
    if norm.endswith(".git"):
        norm = norm[:-4]
    norm = norm.replace(":", "/")
    for r in PRODUCT_REMOTES:
        if norm.endswith(r):
            return "product"
    for r in THEBES_REMOTES:
        if norm.endswith(r):
            return "thebes"
    return "other"


def effective_cwd(command, cwd):
    """Where this command actually runs: `git -C X`, or a leading `cd X &&`.

    Resolved rather than pattern-matched, because a guard that reads only the
    command text is bypassed by the first `cd` anybody writes.
    """
    base = cwd or os.getcwd()
    m = re.match(r"\s*cd\s+(?:--\s+)?(\S+)\s*(?:&&|;)", command)
    if m:
        cand = os.path.expanduser(m.group(1).strip("'\""))
        base = cand if os.path.isabs(cand) else os.path.join(base, cand)
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for i, tok in enumerate(parts):
        if tok == "-C" and i + 1 < len(parts):
            cand = os.path.expanduser(parts[i + 1])
            base = cand if os.path.isabs(cand) else os.path.join(base, cand)
            break
    return os.path.normpath(base)


def push_targets(command):
    """Branch names a `git push` would write. [] when it is not a push.

    Handles `push origin main`, `push origin HEAD:main`, `push --force origin main`
    and a bare `push` (which writes the current branch — resolved by the caller).
    """
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    if "git" not in parts:
        return []
    g = parts.index("git")
    rest = parts[g + 1:]
    args, skip = [], False
    for tok in rest:
        if skip:
            skip = False
            continue
        if tok == "-C":
            skip = True
            continue
        if tok.startswith("-"):
            continue
        args.append(tok)
    if not args or args[0] != "push":
        return []
    refspecs = args[2:] if len(args) > 2 else []
    out = []
    for r in refspecs:
        dst = r.split(":")[-1] if ":" in r else r
        out.append(dst.replace("refs/heads/", "").lstrip("+"))
    return out or ["<current-branch>"]


def current_branch(cwd):
    return _run(cwd, "rev-parse", "--abbrev-ref", "HEAD")


def decide(command, cwd=None):
    """(verdict, reason). DENY refuses the call; PASS expresses no opinion."""
    targets = push_targets(command)
    if not targets:
        return PASS, ""
    where = effective_cwd(command, cwd)
    repo = classify_repo(where)
    if targets == ["<current-branch>"]:
        targets = [current_branch(where) or "<unknown>"]

    if repo == "product":
        hit = [t for t in targets if t in PRODUCT_PROTECTED]
        if hit:
            return DENY, (
                "PRODUCT MAIN IS PROTECTED. %s targets %s in dabblersport/webapp, "
                "whose main deploys straight to app.dabbler.pro — pushing it ships "
                "to real users. main is reached only by PR from %s, and under the "
                "standing freeze (P-030) that PR is not merged without the CEO's "
                "explicit go-ahead in the moment."
                % (" ".join(targets and ["this push"]), ", ".join(hit),
                   PRODUCT_INTEGRATION))
        return PASS, "product push to %s — the ordinary integration target" % (
            ", ".join(targets))

    if repo == "thebes":
        return PASS, (
            "canonical Thebes repository: main is its authorised release branch, not "
            "a production deploy. The guard has no objection; the normal permission "
            "layer still decides — this is not the guard granting access.")

    return PASS, "unrecognised repository — repository policy applies unchanged"


def main(argv=None):
    import json
    import sys
    argv = sys.argv[1:] if argv is None else argv
    try:
        payload = json.load(sys.stdin)
    except Exception:                                    # noqa: BLE001
        return 0
    if payload.get("tool_name") not in ("Bash", None):
        return 0
    cmd = (payload.get("tool_input") or {}).get("command") or ""
    verdict, reason = decide(cmd, payload.get("cwd"))
    if verdict == DENY:
        sys.stderr.write("BLOCKED by branch guard: " + reason + "\n")
        return 2                                         # 2 = deny, per hook contract
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
