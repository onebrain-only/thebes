"""Operational-domain policy shared by Persistent State gates."""

SYSTEM_MAINTENANCE = "SYSTEM_MAINTENANCE"
PRODUCT_EXECUTION = "PRODUCT_EXECUTION"
OPERATING_MODES = {SYSTEM_MAINTENANCE, PRODUCT_EXECUTION}
CURRENT_MODE_ID = "current"
TASK_INTENTS = {"observed_condition", "reproduction_request", "implementation", "validation"}
LOCALITIES = {"local", "deployed", "unknown"}
PLATFORM_SPECIFICITY = {"shared", "platform_specific"}


def product_execution_reason(mode):
    if mode == SYSTEM_MAINTENANCE:
        return "system-maintenance-active"
    if mode == PRODUCT_EXECUTION:
        return None
    raise ValueError("unknown operating mode %r" % mode)


def initial_phase(intent):
    if intent == "observed_condition":
        return "investigation"
    if intent == "reproduction_request":
        return "reproduction"
    if intent == "implementation":
        return "implementation"
    if intent == "validation":
        return "validation"
    raise ValueError("unknown task intent %r" % intent)


DEFAULT_FLUTTER_WEB_LAUNCH = "flutter run -d chrome"


def derive_primary_target(reported_environment):
    """Derive where diagnosis starts; tools are separate from environments.

    A DECLARED LAUNCH COMMAND OUTRANKS THE DERIVED DEFAULT (2026-09-16).
    `launch_command` was derived from runtime+platform alone and could not be
    stated, so `flutter_web` + `chrome` always produced
    `flutter run -d chrome`. That default was right when a manual launch was
    the only way to start the app. It is now wrong often enough to cost real
    work: KAN-207's `environment_ref` had been rewritten to name the
    deterministic web layer, the derived `launch_command` still said
    `flutter run -d chrome`, the executor followed the command, asked for a
    tool to watch the startup, and stalled 30 minutes at a permission boundary
    that nothing needed to cross.

    Derivation exists so nobody INVENTS a launch. It does not exist to override
    a caller who knows which command actually starts this target — so a stated
    command is kept and the derived one fills the silence. `po` may state it
    from a fact (a runner that exists in the Product repository); it still may
    not invent one, and validate.py's reference bounds apply to it as before.
    """
    env = dict(reported_environment or {})
    locality = env.get("locality", "unknown")
    runtime = env.get("runtime")
    platform = env.get("platform")
    if locality not in LOCALITIES:
        raise ValueError("unknown reported-environment locality %r" % locality)
    if locality == "local":
        target = {"locality": "local", "runtime": runtime, "platform": platform,
                  "environment_ref": env.get("environment_ref"),
                  "browser_automation": False, "source": "reported_environment"}
        declared = env.get("launch_command")
        if declared:
            target.update({"launch_method": env.get("launch_method") or "terminal",
                           "launch_command": declared})
        elif runtime == "flutter_web" and platform == "chrome":
            target.update({"launch_method": "terminal",
                           "launch_command": DEFAULT_FLUTTER_WEB_LAUNCH})
        return target
    if locality == "deployed":
        return {"locality": "deployed", "runtime": runtime, "platform": platform,
                "environment_ref": env.get("environment_ref"),
                "browser_automation": False, "source": "reported_environment"}
    return {"locality": "unknown", "runtime": runtime, "platform": platform,
            "browser_automation": False, "source": "reported_environment"}


def derive_validation_plan(diagnosis, primary_target):
    """Derive required and optional targets from cause and changed surface."""
    specificity = (diagnosis or {}).get("platform_specificity")
    if specificity not in PLATFORM_SPECIFICITY:
        raise ValueError("unknown platform specificity %r" % specificity)
    affected = sorted(set((diagnosis or {}).get("affected_platforms") or []))
    causal_platforms = sorted(set((diagnosis or {}).get("causal_platforms") or []))
    changed = (diagnosis or {}).get("changed_surfaces") or []
    path_platforms = sorted({platform for path in changed for platform, prefix in
                             (("android", "android/"), ("ios", "ios/"), ("web", "web/"))
                             if path.startswith(prefix)})
    expected_specificity = "platform_specific" if path_platforms or causal_platforms else "shared"
    if specificity != expected_specificity:
        raise ValueError("platform specificity %r contradicts changed surfaces; expected %r"
                         % (specificity, expected_specificity))
    required_platforms = set(path_platforms) | set(causal_platforms)
    if required_platforms and not required_platforms <= set(affected):
        raise ValueError("affected_platforms must include causal/changed-surface platforms %s"
                         % ", ".join(sorted(required_platforms)))
    primary_platform = (primary_target or {}).get("platform")
    required, optional = [], []
    if specificity == "shared":
        required.append({"target_id": "shared-automated", "kind": "automated",
                         "surface": "shared"})
        if primary_platform:
            required.append({"target_id": "primary-%s" % primary_platform,
                             "kind": "runtime", "platform": primary_platform})
        for platform in affected:
            if platform != primary_platform:
                optional.append({"target_id": "confidence-%s" % platform,
                                 "kind": "runtime", "platform": platform})
    else:
        for platform in affected:
            required.append({"target_id": "required-%s" % platform,
                             "kind": "runtime", "platform": platform})
    return {"required": required, "optional": optional, "evidence": {}}


def validation_complete(plan):
    evidence = (plan or {}).get("evidence") or {}
    return all(target.get("target_id") in evidence
               for target in (plan or {}).get("required") or [])
