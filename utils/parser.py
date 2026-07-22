from __future__ import annotations

import json
import re
from typing import Any, Type, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)
_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")


def _strip_noise(text: str) -> str:
    text = _THINK_RE.sub(" ", text or "")
    fenced = _FENCE_RE.findall(text)
    if fenced:
        # Prefer the longest fenced block — that's the payload, not an example.
        text = max(fenced, key=len)
    return text.strip()


def _balanced_object(text: str) -> str | None:
    """Return the first complete top-level {...} block, ignoring braces in strings."""
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, escape = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]

    # Unterminated — the model hit its token limit mid-object. Close whatever is
    # still open so the fields it *did* finish can still be recovered.
    if depth <= 0:
        return None
    salvage = text[start:]
    if in_str:
        salvage = salvage.rstrip("\\") + '"'
    # Drop a dangling "key": with no value, which json.loads would choke on.
    salvage = re.sub(r',\s*"[^"]*"\s*:\s*$', "", salvage)
    return salvage + "}" * depth


def _repair(blob: str) -> str:
    blob = _TRAILING_COMMA_RE.sub(r"\1", blob)          # {"a": 1,}  → {"a": 1}
    blob = blob.replace("“", '"').replace("”", '"')   # smart quotes
    blob = blob.replace("‘", "'").replace("’", "'")
    blob = re.sub(r"\bNaN\b|\bInfinity\b", "0", blob)
    blob = re.sub(r"\bTrue\b", "true", blob)
    blob = re.sub(r"\bFalse\b", "false", blob)
    blob = re.sub(r"\bNone\b", "null", blob)
    return blob


def extract_json(raw: Any) -> dict:
    """Best-effort dict from any LLM response object/string. {} if hopeless."""
    if isinstance(raw, dict):
        return raw
    text = getattr(raw, "content", raw)
    if not isinstance(text, str):
        text = str(text)

    text = _strip_noise(text)
    for candidate in (text, _balanced_object(text) or ""):
        if not candidate:
            continue
        for attempt in (candidate, _repair(candidate)):
            try:
                parsed = json.loads(attempt)
                if isinstance(parsed, dict):
                    return parsed
                if isinstance(parsed, list) and parsed and isinstance(parsed[0], dict):
                    return parsed[0]
            except json.JSONDecodeError:
                continue
    return {}


def parse_into(raw: Any, model: Type[T]) -> T:
    """
    Parse an LLM response into `model`. Unknown keys are dropped, missing keys
    fall back to the schema default, so the UI always gets a complete object.
    """
    data = extract_json(raw)
    if not data:
        return model()

    # Some models nest everything under a wrapper key such as {"result": {...}}.
    if len(data) == 1:
        only = next(iter(data.values()))
        if isinstance(only, dict) and set(only) & set(model.model_fields):
            data = only

    clean = {k: v for k, v in data.items() if k in model.model_fields}
    try:
        return model(**clean)
    except Exception:
        # Field-by-field salvage: keep whatever validates.
        safe = {}
        for k, v in clean.items():
            try:
                model(**{k: v})
                safe[k] = v
            except Exception:
                continue
        try:
            return model(**safe)
        except Exception:
            return model()


# ── small formatting helpers shared by prompts + UI ─────────────────────────
def as_bullets(items: list[str] | None, empty: str = "None") -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    return ", ".join(items) if items else empty


def dedupe(items: list[str] | None) -> list[str]:
    """Case-insensitive de-duplication that preserves the original order/casing."""
    seen, out = set(), []
    for item in items or []:
        if item is None:
            continue                       # str(None) would leak "None" into the UI
        text = str(item).strip()
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out
