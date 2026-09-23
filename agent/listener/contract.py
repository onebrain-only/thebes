"""The Phase-3 Listener intent contract.

One small, transport-neutral envelope. It is deliberately NOT a command
language: `intent_type` is allow-listed, every payload is schema-checked field
by field, and there is no field anywhere that carries a shell command, a file
path, a provider, a seat, a workspace, or a lifecycle decision. A caller can
name work that already exists and answer a decision Thebes already asked for.
Nothing else crosses this boundary.

The envelope carries no authority of its own. `actor` records the claimed
employee answering a decision and is checked against the organization authority
registry by the Controller; it is not authentication, and Phase 3 is loopback-only
for exactly that reason.
"""

import hashlib
import json
import re


SCHEMA_VERSION = 1

# Allow-listed intent families. A type outside this set is rejected at intake
# and never reaches a dispatcher, so adding a family is a deliberate act.
EXECUTE_WORK_ITEM = "EXECUTE_WORK_ITEM"
DECISION_RESPONSE = "DECISION_RESPONSE"
# Dispatch an ALREADY-OPEN review context to its recorded owner. It names work
# that already exists and is already in review; it carries no reviewer, no
# route and no verdict — the Controller re-derives all of those from the store.
# Added 2026-09-21 (T-091): before it, a review opened by po and resolved to a
# CEO-named reviewer had no front door, because EXECUTE_WORK_ITEM refuses an
# item that is not Ready and never reaches the validator.
VALIDATE_WORK_ITEM = "VALIDATE_WORK_ITEM"
INTENT_TYPES = (EXECUTE_WORK_ITEM, DECISION_RESPONSE, VALIDATE_WORK_ITEM)

# Bounded intake. A body larger than this is refused before it is parsed.
MAX_BODY_BYTES = 64 * 1024
MAX_TEXT = 2000

WORK_ITEM_ID = re.compile(r"^[A-Z][A-Z0-9]{1,15}-\d{1,9}$")
# Deliberately narrow: no shell metacharacters, no whitespace, no wildcards.
# argv is built as an array regardless, but a token that cannot express an
# injection is a second, independent guarantee.
TOKEN = re.compile(r"^[A-Za-z0-9_.:@/-]{1,200}$")
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,200}$")

ENVELOPE_FIELDS = ("schema_version", "intent_type", "source", "actor",
                   "idempotency_key", "correlation_id", "payload")
OPTIONAL_ENVELOPE_FIELDS = ("responds_to",)

PAYLOAD_FIELDS = {
    EXECUTE_WORK_ITEM: (("work_item_id",), ()),
    VALIDATE_WORK_ITEM: (("work_item_id",), ()),
    DECISION_RESPONSE: (("work_item_id", "original_invocation_id", "decision",
                         "permission", "approval_scope"),
                        ("allowed_operation",)),
}

DECISIONS = ("approve",)


class IntentRejected(ValueError):
    """Intake refusal. Carries a stable machine reason, never a stack trace."""

    def __init__(self, reason, detail=None):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


def _text(value, field, pattern=None, maximum=MAX_TEXT):
    if not isinstance(value, str) or not value.strip():
        raise IntentRejected("invalid-field", "%s must be a non-empty string" % field)
    if len(value) > maximum:
        raise IntentRejected("field-too-long", "%s exceeds %d characters" % (field, maximum))
    if pattern is not None and not pattern.match(value):
        raise IntentRejected("invalid-field", "%s is not a permitted value" % field)
    return value


def parse_body(raw):
    """Decode one intake body. Oversized or malformed input never becomes an intent."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if not isinstance(raw, (bytes, bytearray)):
        raise IntentRejected("malformed-body", "intake body must be bytes")
    if len(raw) > MAX_BODY_BYTES:
        raise IntentRejected("body-too-large",
                             "intake body exceeds %d bytes" % MAX_BODY_BYTES)
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise IntentRejected("malformed-json", "intake body is not valid JSON: %s" % exc)
    if not isinstance(payload, dict):
        raise IntentRejected("malformed-json", "intake body must be a JSON object")
    return payload


def normalize(submitted):
    """Validate one submitted envelope and return its canonical form.

    Unknown fields are refused rather than ignored: silently dropping a field a
    caller believed was meaningful is how a boundary starts lying about what it
    honoured.
    """
    if not isinstance(submitted, dict):
        raise IntentRejected("malformed-json", "intent must be a JSON object")
    unknown = sorted(set(submitted) - set(ENVELOPE_FIELDS) - set(OPTIONAL_ENVELOPE_FIELDS))
    if unknown:
        raise IntentRejected("unknown-field", "unknown envelope field(s): %s"
                             % ", ".join(unknown))
    version = submitted.get("schema_version", SCHEMA_VERSION)
    if version != SCHEMA_VERSION:
        raise IntentRejected("unsupported-schema-version",
                             "listener intent schema_version must be %d" % SCHEMA_VERSION)
    intent_type = submitted.get("intent_type")
    if intent_type not in INTENT_TYPES:
        raise IntentRejected("unknown-intent-type",
                             "intent_type must be one of: %s" % ", ".join(INTENT_TYPES))
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "intent_type": intent_type,
        "source": _text(submitted.get("source"), "source", TOKEN),
        "actor": _text(submitted.get("actor"), "actor", TOKEN),
        "idempotency_key": _text(submitted.get("idempotency_key"), "idempotency_key",
                                 IDENTIFIER),
        "correlation_id": _text(submitted.get("correlation_id"), "correlation_id",
                                IDENTIFIER),
        "payload": _payload(intent_type, submitted.get("payload")),
    }
    responds_to = submitted.get("responds_to")
    if intent_type == DECISION_RESPONSE:
        envelope["responds_to"] = _text(responds_to, "responds_to", IDENTIFIER)
    elif responds_to is not None:
        raise IntentRejected("unknown-field",
                             "responds_to is only valid on a %s" % DECISION_RESPONSE)
    envelope["intent_id"] = intent_id(envelope)
    return envelope


def _payload(intent_type, payload):
    if not isinstance(payload, dict):
        raise IntentRejected("invalid-field", "payload must be a JSON object")
    required, optional = PAYLOAD_FIELDS[intent_type]
    unknown = sorted(set(payload) - set(required) - set(optional))
    if unknown:
        raise IntentRejected("unknown-field", "unknown payload field(s): %s"
                             % ", ".join(unknown))
    missing = sorted(field for field in required if field not in payload)
    if missing:
        raise IntentRejected("missing-field", "payload is missing: %s" % ", ".join(missing))
    clean = {"work_item_id": _text(payload.get("work_item_id"), "work_item_id",
                                   WORK_ITEM_ID, 40)}
    if intent_type in (EXECUTE_WORK_ITEM, VALIDATE_WORK_ITEM):
        return clean
    decision = _text(payload.get("decision"), "decision", TOKEN, 40)
    if decision not in DECISIONS:
        raise IntentRejected("unsupported-decision",
                             "decision must be one of: %s" % ", ".join(DECISIONS))
    clean.update({
        "decision": decision,
        "original_invocation_id": _text(payload.get("original_invocation_id"),
                                        "original_invocation_id", IDENTIFIER),
        # The approval writer refuses a wildcard itself; refusing it here too
        # means a wildcard never becomes a durable listener record either.
        "permission": _text(payload.get("permission"), "permission", TOKEN, 120),
        "approval_scope": _text(payload.get("approval_scope"), "approval_scope"),
    })
    if payload.get("allowed_operation") is not None:
        clean["allowed_operation"] = _text(payload["allowed_operation"],
                                           "allowed_operation", maximum=MAX_TEXT)
        if "*" in clean["allowed_operation"]:
            raise IntentRejected("invalid-field", "allowed_operation cannot be wildcarded")
    if "*" in clean["permission"]:
        raise IntentRejected("invalid-field", "permission cannot be wildcarded")
    return clean


def intent_id(envelope):
    """Content-addressed identity.

    The id is derived from the caller's own idempotency key plus the intent
    family, so the SAME logical request submitted twice is literally the same
    record — duplicate suppression is an identity property, not a lookup that
    can race.
    """
    identity = "%s\0%s" % (envelope["intent_type"], envelope["idempotency_key"])
    return "intent-" + hashlib.sha256(identity.encode("utf-8")).hexdigest()


def conflicts(existing, envelope):
    """Fields a re-submission under the same idempotency key may not change."""
    return sorted(field for field in ("intent_type", "source", "actor",
                                      "correlation_id", "payload", "responds_to")
                  if existing.get(field) != envelope.get(field))
