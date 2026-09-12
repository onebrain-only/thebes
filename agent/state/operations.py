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


def derive_primary_target(reported_environment):
    """Derive where diagnosis starts; tools are separate from environments."""
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
        if runtime == "flutter_web" and platform == "chrome":
            target.update({"launch_method": "terminal",
                           "launch_command": "flutter run -d chrome"})
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
    changed = (diagnosis or {}).get("changed_surfaces") or []
    path_platforms = sorted({platform for path in changed for platform, prefix in
                             (("android", "android/"), ("ios", "ios/"), ("web", "web/"))
                             if path.startswith(prefix)})
    expected_specificity = "platform_specific" if path_platforms else "shared"
    if specificity != expected_specificity:
        raise ValueError("platform specificity %r contradicts changed surfaces; expected %r"
                         % (specificity, expected_specificity))
    if path_platforms and not set(path_platforms) <= set(affected):
        raise ValueError("affected_platforms must include changed-surface platforms %s"
                         % ", ".join(path_platforms))
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
