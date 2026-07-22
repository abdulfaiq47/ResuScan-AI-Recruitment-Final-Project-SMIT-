from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List, Optional

import streamlit as st

from ai import llm as llm_mod
from components.styles import brand_mark, esc, icon
from components.uploader import job_description_input, resume_uploader
from utils.pdf_reader import ExtractedDoc


@dataclass
class SidebarState:
    job_description: str = ""
    job_title: str = ""
    resumes: List[ExtractedDoc] = field(default_factory=list)
    workers: int = 2
    skip_questions_for_rejects: bool = True
    engine_ready: bool = False
    engine_label: str = "Not configured"
    backups: List[str] = field(default_factory=list)
    strategy: str = "balanced"
    prefer: Optional[str] = None

    @property
    def ready(self) -> bool:
        return bool(self.job_description.strip()) and bool(self.resumes) and self.engine_ready


@st.cache_data(show_spinner=False, ttl=900)
def _cached_models(strategy: str, _bust: int = 0) -> List[dict]:
    """Discovery hits the network — cache it for 15 min so reruns stay instant."""
    return [
        {"provider": c.provider, "model_id": c.model_id, "label": c.label,
         "rank": c.rank, "notes": c.notes}
        for c in llm_mod.discover_models(strategy)
    ]


def _engine_panel() -> tuple[bool, str, List[str], str]:
    """AI engine status + manual key entry. Returns (ready, label, backups, strategy)."""
    st.markdown(
        f'<h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;'
        f'font-weight:800;margin:0 0 .5rem;">{icon("engine", 17)}AI Engine</h3>',
        unsafe_allow_html=True,
    )

    providers = llm_mod.available_providers()
    if not any(providers.values()):
        st.markdown(
            '<div class="status-line"><span class="dot dot-off"></span>'
            "No API key found</div>",
            unsafe_allow_html=True,
        )
        st.caption("Paste a free key below, or add one to `.env` and restart.")
        with st.form("key_form", clear_on_submit=False):
            choice = st.selectbox(
                "Provider",
                ["OpenRouter (free models)", "NVIDIA NIM (free credits)", "Google Gemini (free tier)"],
                label_visibility="collapsed",
            )
            key = st.text_input("API key", type="password", placeholder="paste key…",
                                label_visibility="collapsed")
            if st.form_submit_button("Connect", width="stretch", type="primary") and key.strip():
                env_var = {
                    "OpenRouter (free models)": "OPENROUTER_API_KEY",
                    "NVIDIA NIM (free credits)": "NVIDIA_API_KEY",
                    "Google Gemini (free tier)": "GOOGLE_API_KEY",
                }[choice]
                os.environ[env_var] = key.strip()
                _cached_models.clear()
                st.rerun()
        st.caption(
            "Free keys → [openrouter.ai/keys](https://openrouter.ai/keys) · "
            "[build.nvidia.com](https://build.nvidia.com/) · "
            "[aistudio.google.com](https://aistudio.google.com/apikey)"
        )
        return False, "Not configured", [], "balanced", None

    strategy_labels = list(llm_mod.STRATEGIES.values())
    strategy_keys = list(llm_mod.STRATEGIES.keys())
    strategy = strategy_keys[
        strategy_labels.index(
            st.selectbox(
                "Selection strategy", strategy_labels,
                help="Free models range from 8B to 675B. Balanced avoids the giant "
                     "ones that take minutes per resume; Best quality accepts the wait.",
            )
        )
    ]

    models = _cached_models(strategy, st.session_state.get("model_cache_bust", 0))
    if not models:
        st.warning("Keys found, but no free model could be listed. Check your connection.")
        return False, "No model available", [], strategy, None

    connected = ", ".join(p for p, ok in providers.items() if ok)
    st.markdown(
        f'<div class="status-line"><span class="dot dot-live"></span>'
        f"Connected · {esc(connected)}</div>",
        unsafe_allow_html=True,
    )

    # Auto-selected model, overridable without touching the environment.
    auto_label = f"Auto — {models[0]['provider']} · {models[0]['model_id']}"
    options = [f"{m['provider']} · {m['model_id']}" for m in models]
    picked = st.selectbox(
        "Model", [auto_label] + options,
        help="Auto picks the highest-ranked free model for the chosen strategy. "
             "Every other model stays on as an automatic failover for rate limits.",
    )

    if picked == auto_label:
        chosen, prefer = models[0], None
    else:
        provider, model_id = picked.split(" · ", 1)
        chosen = next(
            (m for m in models if m["provider"] == provider and m["model_id"] == model_id),
            models[0],
        )
        prefer = f"{provider}:{model_id}"

    backups = [
        f"{m['provider']} · {m['model_id']}"
        for m in models
        if not (m["provider"] == chosen["provider"] and m["model_id"] == chosen["model_id"])
    ][:3]

    st.caption(
        f"**{len(models)} free models** reachable · "
        + (f"{len(backups)} kept as automatic failover" if backups else "no failover available")
        + (f" · pinned in .env" if chosen.get("notes") == "pinned" else "")
    )

    if st.button("Test connection", width="stretch"):
        with st.spinner("Pinging the model…"):
            ok, msg = llm_mod.ping(
                llm_mod.ModelCandidate(
                    provider=chosen["provider"], model_id=chosen["model_id"],
                    label=chosen["label"], rank=chosen["rank"],
                )
            )
        (st.success if ok else st.error)(msg)

    return True, f"{chosen['provider']} · {chosen['model_id']}", backups, strategy, prefer


def render() -> SidebarState:
    state = SidebarState()

    with st.sidebar:
        st.markdown(
            '<div style="display:flex;align-items:center;gap:11px;margin-bottom:18px;">'
            + brand_mark(38)
            + '<div><div style="font-weight:800;font-size:15px;letter-spacing:-.02em;">ResuScan</div>'
            '<div style="font-size:11px;color:#9CA3AF;font-weight:600;">HR SCREENING CONSOLE</div></div></div>',
            unsafe_allow_html=True,
        )

        (
            state.engine_ready,
            state.engine_label,
            state.backups,
            state.strategy,
            state.prefer,
        ) = _engine_panel()

        st.divider()
        st.markdown(
            f'<h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;'
            f'font-weight:800;margin:0 0 .5rem;">{icon("job-description", 17)}'
            "Job Description</h3>",
            unsafe_allow_html=True,
        )
        state.job_description, state.job_title = job_description_input()

        st.divider()
        st.markdown(
            f'<h3 style="display:flex;align-items:center;gap:8px;font-size:1rem;'
            f'font-weight:800;margin:0 0 .5rem;">{icon("resumes", 17)}Resumes</h3>',
            unsafe_allow_html=True,
        )
        state.resumes = resume_uploader()

        st.divider()
        with st.expander("Analysis settings", icon=":material/tune:"):
            state.workers = st.slider(
                "Parallel analyses", 1, 5, 2,
                help="Analyse several candidates at once. Higher is faster but free "
                     "tiers rate-limit — 2 is a safe default.",
            )
            state.skip_questions_for_rejects = st.checkbox(
                "Skip interview questions for rejected candidates", value=True,
                help="Saves tokens and time. Module 8 only targets shortlisted candidates.",
            )

        st.markdown(
            '<div class="tiny" style="margin-top:22px;text-align:center;">'
            "LangChain · 5-chain pipeline<br/>Free models, auto-selected </div>",
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="tiny" style="margin-top:22px;text-align:center;">'
            f'Built with {icon("heart", 12)} by Abdul Faiq</div>',
            unsafe_allow_html=True,
        )
       

    return state
