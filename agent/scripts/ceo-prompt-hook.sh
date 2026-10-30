#!/bin/sh
# CEO prompt hook — UserPromptSubmit + PreCompact entry point (D-044). See ceo_prompt_hook.py.
SELF=$(cd "$(dirname "$0")" 2>/dev/null && pwd) || exit 0
exec python3 "$SELF/ceo_prompt_hook.py"
