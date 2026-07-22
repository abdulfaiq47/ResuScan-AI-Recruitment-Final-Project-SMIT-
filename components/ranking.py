from __future__ import annotations

from typing import List

import pandas as pd
import streamlit as st

from ai.schemas import CandidateAnalysis
from components.styles import badge, esc, section_heading, stat, stat_row
from utils.exporter import (
    batch_report_docx,
    dataframe_to_csv_bytes,
    results_to_dataframe,
    results_to_json_bytes,
    safe_filename,
)

MEDAL = {1: "", 2: " silver", 3: " bronze"}


def _summary_tiles(results: List[CandidateAnalysis]) -> str:
    total = len(results)
    hires = sum(1 for r in results if r.recommendation == "Hire")
    interviews = sum(1 for r in results if r.recommendation == "Interview")
    rejects = sum(1 for r in results if r.recommendation == "Reject")
    avg = round(sum(r.score for r in results) / total) if total else 0
    best = max((r.score for r in results), default=0)

    return stat_row([
        stat("Candidates", total, "screened this run"),
        stat("Shortlisted", hires + interviews, f"{hires} hire · {interviews} interview"),
        stat("Rejected", rejects, "below the bar"),
        stat("Average score", f"{avg}%", "across the pool"),
        stat("Top score", f"{best}%", results[0].candidate_name if results else "—"),
    ])


def _rank_rows(results: List[CandidateAnalysis]) -> str:
    rows = []
    for i, r in enumerate(results, start=1):
        medal_cls = MEDAL.get(i, " plain")
        top_cls = " top" if i == 1 else ""
        meta_bits = [
            f"{r.experience_years:g} yrs" if r.experience_years else "exp. n/a",
            r.current_role or "role n/a",
            f"{len(r.matching_skills)} matched",
            f"{len(r.missing_skills)} missing",
        ]
        rows.append(
            f'<div class="rank-row{top_cls}">'
            f'<div class="rank-medal{medal_cls}">{i}</div>'
            f'<div><div class="rank-name">{esc(r.candidate_name)}</div>'
            f'<div class="rank-meta">{esc(" · ".join(meta_bits))}</div></div>'
            f"<div>{badge(r.recommendation)}</div>"
            f'<div><div class="rank-score">{r.score}%</div>'
            f'<div class="rank-bar"><i style="width:{max(2, r.score)}%"></i></div></div>'
            "</div>"
        )
    return "".join(rows)


def render_ranking(results: List[CandidateAnalysis], job_title: str = "") -> pd.DataFrame:
    """Draw the full ranking dashboard and return the comparison DataFrame."""
    st.markdown(_summary_tiles(results), unsafe_allow_html=True)

    st.markdown(section_heading("ranking", "Candidate ranking"), unsafe_allow_html=True)
    st.markdown(_rank_rows(results), unsafe_allow_html=True)

    df = results_to_dataframe(results)

    st.markdown(section_heading("comparison", "Candidate comparison"), unsafe_allow_html=True)
    filt_col, sort_col = st.columns([2, 1])
    with filt_col:
        wanted = st.multiselect(
            "Show recommendations",
            ["Hire", "Interview", "Reject"],
            default=["Hire", "Interview", "Reject"],
            label_visibility="collapsed",
        )
    with sort_col:
        min_score = st.slider("Minimum score", 0, 100, 0, label_visibility="collapsed")

    view = df[df["Recommendation"].isin(wanted) & (df["Score"] >= min_score)] if not df.empty else df

    st.dataframe(
        view[
            ["Rank", "Candidate", "Score", "Recommendation", "Experience (yrs)",
             "Matching Skills", "Missing Skills", "Summary"]
        ],
        width="stretch",
        hide_index=True,
        column_config={
            "Rank": st.column_config.NumberColumn("#", width="small"),
            "Candidate": st.column_config.TextColumn("Candidate", width="medium"),
            "Score": st.column_config.ProgressColumn(
                "Match", format="%d%%", min_value=0, max_value=100, width="medium"
            ),
            "Recommendation": st.column_config.TextColumn("Verdict", width="small"),
            "Experience (yrs)": st.column_config.NumberColumn("Yrs", format="%g", width="small"),
            "Matching Skills": st.column_config.TextColumn("Matching skills", width="large"),
            "Missing Skills": st.column_config.TextColumn("Missing skills", width="medium"),
            "Summary": st.column_config.TextColumn("Summary", width="large"),
        },
    )
    if len(view) < len(df):
        st.caption(f"Showing {len(view)} of {len(df)} candidates — filters applied. Exports use the full set.")

    # Score distribution — a quick visual of how the pool clusters.
    if len(results) > 1:
        chart_df = pd.DataFrame(
            {"Match %": [r.score for r in results]},
            index=[r.candidate_name for r in results],
        )
        st.bar_chart(chart_df, height=260, color="#4F46E5")

    return df


def render_exports(results: List[CandidateAnalysis], df: pd.DataFrame, job_title: str = "") -> None:
    """Module 11 — download the whole run."""
    st.markdown(section_heading("export", "Export results"), unsafe_allow_html=True)
    st.caption("Every export contains all analysed candidates, ranked best-first.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.download_button(
            "Download CSV",
            icon=":material/table_view:",
            data=dataframe_to_csv_bytes(df),
            file_name=safe_filename(job_title or "candidate_ranking", ".csv"),
            mime="text/csv",
            width="stretch",
            type="primary",
        )
        st.caption("Ranking table — opens in Excel.")
    with c2:
        st.download_button(
            "Download Word report",
            icon=":material/description:",
            data=batch_report_docx(results, job_title),
            file_name=safe_filename(job_title or "screening_report", ".docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
        )
        st.caption("Full write-up, one page per candidate.")
    with c3:
        st.download_button(
            "Download JSON",
            icon=":material/data_object:",
            data=results_to_json_bytes(results),
            file_name=safe_filename(job_title or "analysis", ".json"),
            mime="application/json",
            width="stretch",
        )
        st.caption("Structured output for downstream systems.")
