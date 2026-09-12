"""Resolve Desktop creation destinations for the single-checkout guard."""
import os
import shlex

PASS = "PASS"
DENY = "DENY"


def _tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    return list(lexer)


def _resolve(path, cwd, home):
    if path.startswith("~/"):
        path = os.path.join(home, path[2:])
    return os.path.normpath(path if os.path.isabs(path) else os.path.join(cwd, path))


def _outside_canonical_desktop(path, desktop, canonical):
    return (os.path.dirname(path) == desktop and path != canonical)


def decide(command, root, home=None):
    home = home or os.path.expanduser("~")
    desktop = os.path.join(home, "Desktop")
    canonical = os.path.normpath(root)
    cwd = canonical
    try:
        tokens = _tokens(command)
    except ValueError:
        return PASS
    segments, current = [], []
    for token in tokens + [";"]:
        if token in (";", "&&", "||", "|", "&"):
            if current:
                segments.append(current)
            current = []
        else:
            current.append(token)
    for segment in segments:
        if segment[0] == "cd" and len(segment) > 1:
            cwd = _resolve(segment[1], cwd, home)
            continue
        command_cwd = cwd
        executable = segment[0]
        args = segment[1:]
        if executable == "git" and len(args) >= 2 and args[0] == "-C":
            command_cwd = _resolve(args[1], cwd, home)
            args = args[2:]
        if executable == "git" and args and args[0] == "clone":
            positional = [arg for arg in args[1:] if not arg.startswith("-")]
            destination = positional[-1] if len(positional) > 1 else None
            if destination is None:
                if command_cwd == desktop:
                    return DENY
            elif _outside_canonical_desktop(
                    _resolve(destination, command_cwd, home), desktop, canonical):
                return DENY
        elif executable == "mkdir":
            for destination in (arg for arg in args if not arg.startswith("-")):
                if _outside_canonical_desktop(
                        _resolve(destination, command_cwd, home), desktop, canonical):
                    return DENY
        elif executable == "cp" and "-r" in args:
            positional = [arg for arg in args if not arg.startswith("-")]
            if positional and _outside_canonical_desktop(
                    _resolve(positional[-1], command_cwd, home), desktop, canonical):
                return DENY
        elif executable == "rsync":
            positional = [arg for arg in args if not arg.startswith("-")]
            if positional and _outside_canonical_desktop(
                    _resolve(positional[-1], command_cwd, home), desktop, canonical):
                return DENY
    return PASS
