from __future__ import annotations

import os

import streamlit as st

# Resolved against this file, not the working directory — a bare "/images/..."
# would point at the drive root and the favicon would silently vanish.
_FAVICON = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "favicon.svg")

st.set_page_config(
    page_title="ResuScan — AI Resume Screening",
    page_icon=_FAVICON if os.path.exists(_FAVICON) else ":material/target:",
    layout="wide",
    initial_sidebar_state="expanded",
)

from ai.chains import ResumePipeline, analyze_batch, rank   # noqa: E402
from ai.llm import NoModelAvailable, get_llm        # noqa: E402
from components import ranking, results, sidebar, styles  # noqa: E402

styles.inject()


# ─────────────────────────────────────────────────────────────────────────────
#  Session state
# ─────────────────────────────────────────────────────────────────────────────
def _init_state() -> None:
    st.session_state.setdefault("results", [])
    st.session_state.setdefault("job_title", "")
    st.session_state.setdefault("last_run_model", "")


_init_state()


# ─────────────────────────────────────────────────────────────────────────────
#  Hero
# ─────────────────────────────────────────────────────────────────────────────
def hero(state: sidebar.SidebarState) -> None:
    engine = state.engine_label if state.engine_ready else "no model connected"
    st.markdown(
        f"""
        <div class="hero">
          <span class="hero-eyebrow">{styles.icon("pipeline", 14)} LangChain · 5-chain pipeline</span>
          <h1>Screen every resume<br/><span class="grad">in minutes, not days.</span></h1>
          <p>Upload a job description and a stack of CVs. The assistant reads each one,
             scores the fit, flags missing skills, drafts tailored interview questions
             and ranks the whole pool — all on free AI models.</p>
          <div class="hero-chips">
            <div class="hero-chip">{styles.icon("engine", 14)} Engine · <b>{styles.esc(engine)}</b></div>
            <div class="hero-chip">{styles.icon("job-description", 14)} JD · <b>{"ready" if state.job_description else "not set"}</b></div>
            <div class="hero-chip">{styles.icon("resumes", 14)} Resumes · <b>{len(state.resumes)} loaded</b></div>
            <div class="hero-chip">{styles.icon("failover", 14)} Failovers · <b>{len(state.backups)}</b></div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────────────────────────────────────
#  Analysis run
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(state: sidebar.SidebarState) -> None:
    try:
        bundle = get_llm(strategy=state.strategy, prefer=state.prefer)
    except NoModelAvailable as exc:
        st.error(str(exc), icon=":material/key:")
        return

    total = len(state.resumes)
    st.session_state["last_run_model"] = bundle.display

    progress = st.progress(0.0, text="Starting the pipeline…")
    log = st.empty()

    def say(msg: str) -> None:
        log.markdown(
            f'<div class="status-line"><span class="dot dot-live"></span>{styles.esc(msg)}</div>',
            unsafe_allow_html=True,
        )

    workers = min(state.workers, total)
    if workers > 1:
        # Concurrent path: progress is reported from the main thread as each
        # candidate finishes, so Streamlit is only ever touched from one thread.
        say(f"Analysing {total} resumes, {workers} at a time…")

        def on_progress(done: int, count: int, label: str) -> None:
            progress.progress(min(1.0, done / max(count, 1)),
                              text=f"{done} of {count} analysed")
            say(f"{done}/{count} done — {label}")

        collected = analyze_batch(
            [(doc.file_name, doc.text) for doc in state.resumes],
            state.job_description,
            bundle=bundle,
            workers=workers,
            on_progress=on_progress,
            skip_questions_for_rejects=state.skip_questions_for_rejects,
        )
    else:
        collected = []
        pipeline = ResumePipeline(bundle)
        for i, doc in enumerate(state.resumes):
            head = f"{doc.file_name} ({i + 1}/{total})"

            def step(msg: str, _head=head, _i=i) -> None:
                say(f"{_head} — {msg}")
                progress.progress(min(0.99, (_i + 0.5) / total), text=f"Analysing {_head}")

            collected.append(
                pipeline.analyze(
                    doc.text,
                    state.job_description,
                    file_name=doc.file_name,
                    on_step=step,
                    skip_questions_for_rejects=state.skip_questions_for_rejects,
                )
            )
            progress.progress((i + 1) / total, text=f"{i + 1} of {total} analysed")

    progress.empty()
    log.empty()

    st.session_state["results"] = rank(collected)
    st.session_state["job_title"] = state.job_title

    failed = [r for r in collected if r.error]
    if failed:
        st.warning(
            f"{len(failed)} of {total} resume(s) could not be analysed — "
            "usually a free-tier rate limit. Try again or pick another model.",
            icon=":material/warning:",
        )
    if len(failed) < total:
        st.success(f"Analysed {total - len(failed)} candidate(s) with {bundle.display}.", icon=":material/check_circle:")


# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────
def main() -> None:
    state = sidebar.render()
    hero(state)

    # ── Action bar ──────────────────────────────────────────────────────────
    left, right = st.columns([3, 1])
    with left:
        if not state.engine_ready:
            st.info("Connect a free AI model in the sidebar to begin.", icon=":material/key:")
        elif not state.job_description:
            st.info("Upload or paste the job description in the sidebar.", icon=":material/assignment:")
        elif not state.resumes:
            st.info("Upload one or more resumes in the sidebar.", icon=":material/description:")
        else:
            st.markdown(
                f'<div class="status-line"><span class="dot dot-live"></span>'
                f"Ready · {len(state.resumes)} resume(s) vs "
                f"<b style='margin-left:4px'>{styles.esc(state.job_title or 'the job description')}</b></div>",
                unsafe_allow_html=True,
            )
    with right:
        analyse = st.button(
            f"Analyse {len(state.resumes) or ''} resume{'s' if len(state.resumes) != 1 else ''}".replace("  ", " "),
            icon=":material/rocket_launch:",
            type="primary",
            width="stretch",
            disabled=not state.ready,
        )

    if analyse:
        run_analysis(state)

    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

    # ── Results ─────────────────────────────────────────────────────────────
    found = st.session_state["results"]
    job_title = st.session_state["job_title"]

    if not found:
        st.markdown(
            styles.empty_state(
                "empty",
                "No analysis yet",
                "Add a job description and at least one resume in the sidebar, then hit "
                "Analyse. Results, rankings and exports will appear right here.",
            ),
            unsafe_allow_html=True,
        )
        with st.expander("How the pipeline works", icon=":material/help:"):
            st.markdown(
                """
| Stage | What happens |
|---|---|
| **Extract** | Each PDF/DOCX/TXT is parsed and cleaned into plain text. |
| **Chain 1 · Summary** | Education, years of experience, key skills, highlights. |
| **Chain 2 · Skill match** | Splits skills into matching / missing / extra vs the JD. |
| **Chain 3 · Score** | Weighted 0-100 score — skills 55%, experience 30%, education 15%. |
| **Chain 4 · Recommendation** | Hire / Interview / Reject plus written justification. |
| **Chain 5 · Interview kit** | 6 technical + 5 HR questions, tailored per candidate. |
| **Rank & export** | Candidates ranked best-first, exportable as CSV, Word or JSON. |

Chains 1 and 2 run in parallel; the rest are sequential because each one
consumes the previous chain's structured output.
                """
            )
        return

    tab_rank, tab_detail, tab_export = st.tabs(
        [":material/leaderboard: Ranking dashboard",
         ":material/person: Candidate detail",
         ":material/download: Export"]
    )

    with tab_rank:
        df = ranking.render_ranking(found, job_title)
    with tab_detail:
        results.render_candidate_picker(found, job_title)
    with tab_export:
        ranking.render_exports(found, df, job_title)

    if st.session_state["last_run_model"]:
        st.markdown(
            f'<div class="tiny" style="text-align:center;margin-top:28px;">'
            f"Analysed with {styles.esc(st.session_state['last_run_model'])} · "
            "results are AI-generated decision support, not a hiring decision.</div>",
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
