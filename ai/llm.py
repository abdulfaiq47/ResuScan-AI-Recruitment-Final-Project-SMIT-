from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

load_dotenv(override=False)

# ─────────────────────────────────────────────────────────────────────────────
#  Provider endpoints
# ─────────────────────────────────────────────────────────────────────────────
OPENROUTER_BASE = "https://openrouter.ai/api/v1"
NVIDIA_BASE = "https://integrate.api.nvidia.com/v1"
GEMINI_OPENAI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"

REQUEST_TIMEOUT = 90
DISCOVERY_TIMEOUT = 12


@dataclass
class ModelCandidate:
    """One usable (provider, model) pair, with a quality score used for ranking."""

    provider: str          # openrouter | nvidia | gemini
    model_id: str
    label: str
    rank: float            # higher = preferred
    context: int = 0
    notes: str = ""

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.model_id}"


# ─────────────────────────────────────────────────────────────────────────────
#  Ranking
#  Provider catalogues churn constantly — a hardcoded "best model" list goes
#  stale within months. So we score whatever the provider reports *right now*
#  from signals in the model id and metadata: parameter count, tier keyword,
#  context window, family, and instruction tuning.
# ─────────────────────────────────────────────────────────────────────────────

# Models that cannot do the job at all: embedders, rerankers, safety filters,
# image/audio/video models, code-completion-only and OCR/parsing models.
_EXCLUDE = (
    "embed", "rerank", "retriev", "bge-", "gte-", "e5-", "guard", "safety", "topic-control",
    "moderation", "content-safety", "gliner", "pii", "detector", "calibration",
    "whisper", "tts", "voice", "audio", "lyria", "imagen", "veo", "sora",
    "diffusion", "stable-", "flux", "dall-e", "clip-", "deplot", "kosmos",
    "fuyu", "ocr", "parse", "starcoder", "codegemma", "codellama", "codestral",
    "coder", "-code", "code-", "vision", "-vl", "-vlm", "chatqa",
    # scoring/judging heads — they emit a scalar, not a chat reply
    "reward", "-rm", "verifier", "critic", "judge",
)

# Family reputation — a nudge, never the deciding factor.
_FAMILY_BONUS = {
    "deepseek": 6, "kimi": 5, "minimax": 5, "qwen": 4, "nemotron": 4,
    "llama": 4, "mistral": 4, "gemma": 3, "gpt-oss": 3, "glm": 3,
    "gemini": 4, "phi": 1, "granite": 1, "yi": 1, "jamba": 1,
}

# Vendor tier keywords: how the vendor itself positions the model.
_TIER_BONUS = {
    "ultra": 12, "-pro": 12, "max": 11, "large": 10, "super": 8,
    "medium": 4, "flash": 4, "turbo": 3, "plus": 3,
}
_TIER_PENALTY = {
    "nano": 10, "mini": 8, "-xs": 8, "tiny": 10, "lite": 6, "small": 3,
    "-e2b": 8, "-e4b": 8, "preview": 2, "experimental": 2,
}

_PARAM_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b(?![a-z0-9])")


def _is_usable(model_id: str) -> bool:
    low = model_id.lower()
    return not any(bad in low for bad in _EXCLUDE)


def _param_billions(model_id: str) -> tuple[float, float]:
    """
    (total, active) parameter counts in billions, parsed from the id.

    Mixture-of-experts models name both: "nemotron-3-ultra-550b-a55b" is 550B
    total but only 55B active per token — which is what governs latency.
    Returns (0, 0) when the id says nothing.
    """
    sizes = []
    for raw in _PARAM_RE.findall(model_id.lower()):
        try:
            sizes.append(float(raw))
        except ValueError:
            continue
    if not sizes:
        return 0.0, 0.0
    return max(sizes), min(sizes)


def _quality_score(model_id: str, context: int = 0) -> float:
    """
    Heuristic 0-100ish quality estimate from the model id alone.

    Deliberately signal-based so it survives catalogue churn: a model released
    tomorrow still gets ranked sensibly from its size/tier/family.
    """
    low = model_id.lower()
    score = 45.0

    total, _active = _param_billions(low)
    if total:
        # 7B→+9, 31B→+16, 70B→+20, 253B→+26, 675B→+30 (capped)
        score += min(30.0, 11.0 * math.log10(total + 1.0))

    for token, bonus in _TIER_BONUS.items():
        if token in low:
            score += bonus
            break
    for token, penalty in _TIER_PENALTY.items():
        if token in low:
            score -= penalty

    for family, bonus in _FAMILY_BONUS.items():
        if family in low:
            score += bonus
            break

    if "instruct" in low or "-it" in low or "chat" in low:
        score += 2.0
    if context:
        score += min(6.0, context / 50_000.0)

    return round(score, 2)


def _speed_penalty(model_id: str) -> float:
    """
    How much this model is likely to cost you in wall-clock time.

    Latency tracks *active* parameters, not total — so a 550B MoE with 55B
    active is penalised like a 55B dense model. Reasoning models pay extra
    because they emit a long hidden chain before the answer.
    """
    low = model_id.lower()
    total, active = _param_billions(low)
    penalty = 0.0
    if total:
        # Active params dominate latency, but total size still costs queue time
        # on a shared free tier — so blend the two rather than ignoring total.
        effective = (active or total) + 0.15 * total
        penalty += max(0.0, (effective - 25.0) / 4.0)
    if any(t in low for t in ("reasoning", "-r1", "thinking", "-think")):
        penalty += 12.0
    if low.endswith(":free"):
        # Measured: OpenRouter's shared ":free" pool queues requests heavily —
        # the same 120B model answered in ~50s on NVIDIA NIM versus several
        # minutes here. Provider queueing dominates model size in practice.
        penalty += 10.0
    return min(30.0, penalty)


# Model-selection strategies exposed in the UI.
STRATEGIES = {
    "balanced": "Balanced — best quality that still answers quickly",
    "quality": "Best quality — largest model available, slower",
    "fastest": "Fastest — smallest capable model, for big batches",
}


def _strategy_rank(cand: ModelCandidate, strategy: str) -> float:
    """Re-weight a candidate's raw quality score for the chosen strategy."""
    if strategy == "quality":
        return cand.rank
    penalty = _speed_penalty(cand.model_id)
    if strategy == "fastest":
        return cand.rank - 2.2 * penalty
    return cand.rank - 0.75 * penalty          # balanced (default)


# ─────────────────────────────────────────────────────────────────────────────
#  Key helpers
# ─────────────────────────────────────────────────────────────────────────────
def _key(name: str) -> str:
    return (os.getenv(name) or "").strip()


def available_providers() -> Dict[str, bool]:
    return {
        "openrouter": bool(_key("OPENROUTER_API_KEY")),
        "nvidia": bool(_key("NVIDIA_API_KEY")),
        "gemini": bool(_key("GOOGLE_API_KEY")),
    }


def has_any_key() -> bool:
    return any(available_providers().values())


# ─────────────────────────────────────────────────────────────────────────────
#  Discovery — ask each provider what it actually offers right now
# ─────────────────────────────────────────────────────────────────────────────
def _discover_openrouter() -> List[ModelCandidate]:
    """Every zero-cost, text-in/text-out model OpenRouter currently serves."""
    api_key = _key("OPENROUTER_API_KEY")
    if not api_key:
        return []

    try:
        resp = requests.get(
            f"{OPENROUTER_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=DISCOVERY_TIMEOUT,
        )
        resp.raise_for_status()
        payload = resp.json().get("data", [])
    except Exception:
        return []   # offline / blocked — other providers still work

    found: List[ModelCandidate] = []
    for m in payload:
        mid = m.get("id", "")
        pricing = m.get("pricing") or {}
        try:
            free = (float(pricing.get("prompt", 1)) == 0.0
                    and float(pricing.get("completion", 1)) == 0.0)
        except (TypeError, ValueError):
            free = mid.endswith(":free")
        if not free or not _is_usable(mid):
            continue

        # Must actually be a text chat model — this filters out the music and
        # image models that also happen to be priced at zero.
        arch = m.get("architecture") or {}
        out_modes = [str(x).lower() for x in (arch.get("output_modalities") or ["text"])]
        in_modes = [str(x).lower() for x in (arch.get("input_modalities") or ["text"])]
        if "text" not in out_modes or "text" not in in_modes:
            continue
        if any(mode in out_modes for mode in ("audio", "image", "video")):
            continue

        ctx = int(m.get("context_length") or 0)
        found.append(
            ModelCandidate(
                provider="openrouter",
                model_id=mid,
                label=m.get("name") or mid,
                rank=_quality_score(mid, ctx),
                context=ctx,
                notes="free",
            )
        )
    return found


def _discover_nvidia() -> List[ModelCandidate]:
    """
    Every chat model on NVIDIA NIM. The catalogue is free to use with the
    build.nvidia.com trial credits, and /models exposes only ids — so ranking
    leans entirely on the id heuristics.
    """
    api_key = _key("NVIDIA_API_KEY")
    if not api_key:
        return []

    try:
        resp = requests.get(
            f"{NVIDIA_BASE}/models",
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=DISCOVERY_TIMEOUT,
        )
        resp.raise_for_status()
        live_ids = [m.get("id", "") for m in resp.json().get("data", [])]
    except Exception:
        return []

    return [
        ModelCandidate(
            provider="nvidia",
            model_id=mid,
            label=mid,
            rank=_quality_score(mid),
            notes="NIM free credits",
        )
        for mid in sorted(live_ids)
        if mid and _is_usable(mid)
    ]


def _discover_gemini() -> List[ModelCandidate]:
    """Gemini's free-tier chat models, as reported by the ListModels endpoint."""
    api_key = _key("GOOGLE_API_KEY")
    if not api_key:
        return []

    try:
        resp = requests.get(
            "https://generativelanguage.googleapis.com/v1beta/models",
            params={"key": api_key},
            timeout=DISCOVERY_TIMEOUT,
        )
        resp.raise_for_status()
        models = resp.json().get("models", [])
    except Exception:
        return []

    found: List[ModelCandidate] = []
    for m in models:
        mid = (m.get("name") or "").replace("models/", "")
        if not mid or not _is_usable(mid):
            continue
        if "generateContent" not in (m.get("supportedGenerationMethods") or []):
            continue
        ctx = int(m.get("inputTokenLimit") or 0)
        found.append(
            ModelCandidate(
                provider="gemini",
                model_id=mid,
                label=m.get("displayName") or mid,
                rank=_quality_score(mid, ctx),
                context=ctx,
                notes="Google free tier",
            )
        )
    return found


def discover_models(strategy: str = "balanced") -> List[ModelCandidate]:
    """All usable free models across every configured provider, best first."""
    strategy = strategy if strategy in STRATEGIES else "balanced"
    cands = _discover_openrouter() + _discover_nvidia() + _discover_gemini()

    forced_provider = _key("FORCE_PROVIDER").lower()
    if forced_provider:
        cands = [c for c in cands if c.provider == forced_provider]

    cands.sort(key=lambda c: _strategy_rank(c, strategy), reverse=True)

    # An explicit pin always wins, whatever the strategy says.
    forced_model = _key("FORCE_MODEL")
    if forced_model:
        pinned = [c for c in cands if c.model_id == forced_model]
        rest = [c for c in cands if c.model_id != forced_model]
        if not pinned:  # user pinned something we didn't discover — trust them
            prov = forced_provider or ("openrouter" if _key("OPENROUTER_API_KEY") else
                                       "nvidia" if _key("NVIDIA_API_KEY") else "gemini")
            pinned = [ModelCandidate(prov, forced_model, forced_model, 999, notes="pinned")]
        else:
            pinned[0].notes = "pinned"
        cands = pinned[:1] + rest

    return cands


# ─────────────────────────────────────────────────────────────────────────────
#  Building LangChain chat models
# ─────────────────────────────────────────────────────────────────────────────
def _temperature() -> float:
    try:
        return float(_key("LLM_TEMPERATURE") or 0.1)
    except ValueError:
        return 0.1


def build_chat_model(cand: ModelCandidate, temperature: Optional[float] = None):
    """Turn a ModelCandidate into a LangChain BaseChatModel."""
    temp = _temperature() if temperature is None else temperature

    if cand.provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI

            return ChatGoogleGenerativeAI(
                model=cand.model_id,
                google_api_key=_key("GOOGLE_API_KEY"),
                temperature=temp,
                timeout=REQUEST_TIMEOUT,
                max_retries=1,
            )
        except ImportError:
            # Gemini also exposes an OpenAI-compatible endpoint.
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=cand.model_id,
                api_key=_key("GOOGLE_API_KEY"),
                base_url=GEMINI_OPENAI_BASE,
                temperature=temp,
                timeout=REQUEST_TIMEOUT,
                max_retries=1,
            )

    from langchain_openai import ChatOpenAI

    if cand.provider == "nvidia":
        return ChatOpenAI(
            model=cand.model_id,
            api_key=_key("NVIDIA_API_KEY"),
            base_url=NVIDIA_BASE,
            temperature=temp,
            timeout=REQUEST_TIMEOUT,
            max_retries=1,
        )

    # default: openrouter
    return ChatOpenAI(
        model=cand.model_id,
        api_key=_key("OPENROUTER_API_KEY"),
        base_url=OPENROUTER_BASE,
        temperature=temp,
        timeout=REQUEST_TIMEOUT,
        max_retries=1,
        default_headers={
            "HTTP-Referer": "https://github.com/ai-recruitment-assistant",
            "X-Title": "ResuScan",
        },
    )


@dataclass
class LLMBundle:
    """What the rest of the app consumes."""

    llm: Any                                   # LangChain runnable w/ fallbacks
    primary: ModelCandidate
    backups: List[ModelCandidate] = field(default_factory=list)

    @property
    def display(self) -> str:
        return f"{self.primary.provider} · {self.primary.model_id}"


class NoModelAvailable(RuntimeError):
    """Raised when no provider key is configured."""


def get_llm(
    max_fallbacks: int = 3,
    temperature: Optional[float] = None,
    strategy: str = "balanced",
    prefer: Optional[str] = None,
) -> LLMBundle:
    """
    Auto-select the best free model available and attach failovers.

    `prefer` is a "provider:model_id" key that jumps to the front — that's how
    the sidebar's manual model picker overrides auto-selection. Everything else
    stays in the list as a failover.

    Fallbacks deliberately prefer a *different provider* where possible, so a
    provider-wide rate limit doesn't take the whole chain down.
    """
    candidates = discover_models(strategy)
    if not candidates:
        raise NoModelAvailable(
            "No API key found. Add OPENROUTER_API_KEY, NVIDIA_API_KEY or "
            "GOOGLE_API_KEY to your .env file (or paste one in the sidebar)."
        )

    if prefer:
        chosen = [c for c in candidates if c.key == prefer]
        if chosen:
            candidates = chosen[:1] + [c for c in candidates if c.key != prefer]

    primary, pool = candidates[0], candidates[1:]

    backups: List[ModelCandidate] = []
    seen_providers = {primary.provider}
    # First pass: one strong model per *other* provider.
    for c in pool:
        if c.provider not in seen_providers:
            backups.append(c)
            seen_providers.add(c.provider)
    # Second pass: top-up with same-provider alternatives.
    for c in pool:
        if len(backups) >= max_fallbacks:
            break
        if c not in backups:
            backups.append(c)
    backups = backups[:max_fallbacks]

    chat = build_chat_model(primary, temperature)
    if backups:
        chat = chat.with_fallbacks(
            [build_chat_model(b, temperature) for b in backups]
        )
    return LLMBundle(llm=chat, primary=primary, backups=backups)


def ping(cand: ModelCandidate) -> tuple[bool, str]:
    """Cheap liveness check used by the sidebar 'Test connection' button."""
    try:
        model = build_chat_model(cand, temperature=0)
        out = model.invoke("Reply with the single word: OK")
        text = getattr(out, "content", str(out))
        return True, str(text).strip()[:80] or "OK"
    except Exception as exc:  # noqa: BLE001 — surfaced verbatim to the user
        return False, f"{type(exc).__name__}: {exc}"[:220]
