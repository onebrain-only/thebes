"""Run selected layers by command. No model, no navigation, no judgement.

WHAT A RUN PRODUCES
    Full stdout+stderr on disk under an artifact reference; a bounded tail and
    the exit code in memory; one classification from `results.classify`. That
    is the whole token-efficiency argument in one function: the reviewer reads
    forty lines and a path, not a terminal session.

WHAT THE RUNNER REFUSES
    External layers. Routing may NAME TestSprite or BrowserStack; the runner
    records them as NOT_RUN with the reason `external-not-invoked`. Invoking an
    external QA service is an act with cost and credentials behind it, and it is
    requested explicitly by a seat under the existing authority model — never
    fired by a loop because a table said so.

TOOLCHAIN. The subprocess environment is the executor environment
(`agent.execution.claude.executor_environment`): `DEVELOPER_DIR` pinned per
process (D-025), never machine-wide. Without it `flutter` dies on the Xcode
licence on this machine, which would look like a Product failure and is not.
"""

import os
import shutil
import subprocess
import time

from agent.qa.layers import LAYERS
from agent.qa.results import (
    Classification, LayerRun, TAIL_LINES, TIMEOUT_EXIT, classify, now_iso,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_ARTIFACT_ROOT = os.path.join(ROOT, "agent", "qa", "runtime", "artifacts")


def _environment():
    try:
        from agent.execution.claude import executor_environment
        return executor_environment()
    except Exception:                                     # noqa: BLE001
        return dict(os.environ)


def _artifact_path(root, layer_id, started):
    os.makedirs(root, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(started))
    return os.path.join(root, "%s-%s.log" % (layer_id, stamp))


def run_layer(layer_id, workspace_path, artifact_root=None, run=subprocess.run,
              which=shutil.which, environ=None, clock=time.time):
    """Execute one layer in the workspace. Never raises for a failing command."""
    layer = LAYERS[layer_id]
    started = clock()
    command = " ".join(layer.argv) if layer.argv else "<external: %s>" % layer_id
    if layer.external:
        return LayerRun(layer_id, command, None, Classification.NOT_RUN, 0.0, None,
                        reason="external-not-invoked", started_at=now_iso())
    if layer.cwd_marker and not os.path.exists(os.path.join(workspace_path,
                                                            layer.cwd_marker)):
        return LayerRun(layer_id, command, None, Classification.NOT_RUN, 0.0, None,
                        reason="workspace has no %s" % layer.cwd_marker,
                        started_at=now_iso())
    if layer.tool and not which(layer.tool):
        return LayerRun(layer_id, command, None,
                        Classification.TEST_INFRASTRUCTURE_FAILURE, 0.0, None,
                        reason="tool missing on PATH: %s" % layer.tool,
                        started_at=now_iso())

    artifact = _artifact_path(artifact_root or DEFAULT_ARTIFACT_ROOT, layer_id, started)
    env = dict(environ if environ is not None else _environment())
    env.setdefault("CI", "1")           # deterministic: no watch mode, no prompts
    exit_code, output = None, ""
    try:
        completed = run(list(layer.argv), cwd=workspace_path, env=env,
                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        timeout=layer.timeout_seconds, check=False)
        exit_code = completed.returncode
        output = (completed.stdout or b"").decode("utf-8", "replace") \
            if isinstance(completed.stdout, bytes) else (completed.stdout or "")
    except subprocess.TimeoutExpired as exc:
        exit_code = TIMEOUT_EXIT
        partial = exc.stdout or b""
        output = (partial.decode("utf-8", "replace") if isinstance(partial, bytes)
                  else str(partial)) + "\n!!! TIMEOUT after %ss" % layer.timeout_seconds
    except OSError as exc:
        exit_code = 127
        output = "OSError: %s" % exc
    duration = clock() - started
    with open(artifact, "w", encoding="utf-8") as handle:
        handle.write("$ %s\n(cwd %s)\n\n" % (command, workspace_path))
        handle.write(output)
        handle.write("\n\nexit=%s duration=%.1fs\n" % (exit_code, duration))
    tail = tuple(output.splitlines()[-TAIL_LINES:])
    return LayerRun(layer_id, command, exit_code, classify(layer, exit_code, tail),
                    duration, artifact, tail=tail, started_at=now_iso())


def run_layers(decision, workspace_path, artifact_root=None, **kw):
    """Run every selected layer in decision order, cheapest first.

    IT DOES NOT STOP AT THE FIRST INFRASTRUCTURE FAILURE. It did until
    2026-09-16, on the reasoning that "later layers cannot say anything the
    broken toolchain has not already said." That reasoning assumed a failure is
    toolchain-WIDE. A single broken layer is the commoner case and the
    assumption cost real work: `flutter test` is broken on this machine by a
    native-asset link fault, so KAN-212 and KAN-208 were refused without ever
    running `flutter analyze` — the one gate that actually sees the barrel
    export lines those tickets change.

    The cost of being wrong in the other direction is bounded by each layer's
    own timeout, and `gate_outcome` reports the hole rather than papering over
    it. Paying minutes to learn something beats saving them to learn nothing.
    """
    return tuple(run_layer(selection.layer_id, workspace_path, artifact_root, **kw)
                 for selection in decision.selected)
