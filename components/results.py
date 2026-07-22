from __future__ import annotations

import json
from typing import List

import streamlit as st

from ai.schemas import CandidateAnalysis
from components.styles import (
    badge,
    bar,
    bullet_list,
    esc,
    icon,
    pills,
    question_list,
    ring,
    stat,
    stat_row,
)
from utils.exporter import candidate_summary_docx, safe_filename


def _header(a: CandidateAnalysis) -> None:
    contact = " · ".join(x for x in [a.current_role, a.email, a.phone] if x) or "Contact details not found"
    st.markdown(
        f'<div class="card"><div style="display:flex;gap:26px;align-items:center;flex-wrap:wrap;">'
        f"{ring(a.score)}"
        f'<div style="flex:1;min-width:260px;">'
        f'<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap;">'
        f'<span style="font-size:25px;font-weight:800;letter-spacing:-.03em;">{esc(a.candidate_name)}</span>'
        f"{badge(a.recommendation)}</div>"
        f'<div class="muted" style="margin-top:6px;">{esc(contact)}</div>'
        f'<div style="margin-top:14px;">'
        f'{bar("Skills fit", a.skills_score)}{bar("Experience fit", a.experience_score)}'
        f'{bar("Education fit", a.education_score)}</div>'
        + (f'<div class="tiny" style="margin-top:6px;">{icon("scale", 13)} '
           f"{esc(a.score_reason)}</div>" if a.score_reason else "")
        + "</div></div></div>",
        unsafe_allow_html=True,
    )


def render_candidate(a: CandidateAnalysis, job_title: str = "", key_prefix: str = "") -> None:
    if a.error:
        st.error(f"Analysis failed for **{a.file_name}** — {a.error}", icon=":material/error:")

    _header(a)

    # ── Module 4 · Candidate summary ────────────────────────────────────────
    st.markdown(
        '<div class="card"><div class="card-title"><span class="dot"></span>'
        "Candidate summary · chain 1</div>"
        + (f'<p style="font-size:15px;line-height:1.65;margin:0 0 16px;">{esc(a.summary)}</p>'
           if a.summary else '<p class="muted">No summary produced.</p>')
        + stat_row([
            stat("Experience", f"{a.experience_years:g} yrs", a.current_role or "role not stated"),
            stat("Skills found", len(a.key_skills), "extracted from the CV"),
            stat("Education", len(a.education), a.education[0][:34] if a.education else "not stated"),
        ])
        + '<div style="margin-top:6px;"><div class="card-title" style="margin-bottom:8px;">'
          "<span class='dot'></span>Education</div>"
        + bullet_list(a.education)
        + '<div class="card-title" style="margin:16px 0 8px;"><span class="dot"></span>'
          "Highlights &amp; projects</div>"
        + bullet_list(a.highlights, "good")
        + '<div class="card-title" style="margin:16px 0 8px;"><span class="dot"></span>'
          "Key skills</div>"
        + pills(a.key_skills, "neutral")
        + "</div></div>",
        unsafe_allow_html=True,
    )

    dl1, dl2, _ = st.columns([1, 1, 2])
    with dl1:
        st.download_button(
            "Download Word summary",
            icon=":material/description:",
            data=candidate_summary_docx(a, job_title),
            file_name=safe_filename(a.candidate_name, ".docx"),
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            width="stretch",
            key=f"{key_prefix}docx",
        )
    with dl2:
        st.download_button(
            "Download JSON",
            icon=":material/data_object:",
            data=json.dumps(a.to_public_json(), indent=2, ensure_ascii=False).encode("utf-8"),
            file_name=safe_filename(a.candidate_name, ".json"),
            mime="application/json",
            width="stretch",
            key=f"{key_prefix}json",
        )

    # ── Module 5 · Skill match ──────────────────────────────────────────────
    st.markdown(
        '<div class="card"><div class="card-title"><span class="dot"></span>'
        "Skill match · chain 2</div>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:22px;">'
        f'<div><div class="card-title" style="margin-bottom:9px;color:#047857;">'
        f'{icon("check", 14)}<span style="margin-left:2px">Matching</span> '
        f"({len(a.matching_skills)})</div>{pills(a.matching_skills, 'ok', 'No overlap found.')}</div>"
        f'<div><div class="card-title" style="margin-bottom:9px;color:#BE123C;">'
        f'{icon("cross", 14)}<span style="margin-left:2px">Missing</span> '
        f"({len(a.missing_skills)})</div>{pills(a.missing_skills, 'miss', 'Nothing missing — full coverage.')}</div>"
        f'<div><div class="card-title" style="margin-bottom:9px;color:#4338CA;">'
        f'{icon("plus", 14)}<span style="margin-left:2px">Extra</span> '
        f"({len(a.extra_skills)})</div>{pills(a.extra_skills, 'extra', 'No extras.')}</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ── Module 7 · HR recommendation ────────────────────────────────────────
    st.markdown(
        '<div class="card"><div class="card-title"><span class="dot"></span>'
        "HR recommendation · chain 4</div>"
        f'<div style="margin-bottom:14px;">{badge(a.recommendation)}</div>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:22px;">'
        f'<div><div class="card-title" style="margin-bottom:8px;">Justification</div>'
        f"{bullet_list(a.justification)}</div>"
        f'<div><div class="card-title" style="margin-bottom:8px;color:#047857;">Strengths</div>'
        f"{bullet_list(a.strengths, 'good')}</div>"
        f'<div><div class="card-title" style="margin-bottom:8px;color:#B45309;">Concerns to probe</div>'
        f"{bullet_list(a.concerns, 'warn')}</div>"
        "</div></div>",
        unsafe_allow_html=True,
    )

    # ── Module 8 · Interview kit ────────────────────────────────────────────
    q = a.interview_questions
    if q.technical or q.hr:
        st.markdown(
            '<div class="card"><div class="card-title"><span class="dot"></span>'
            "Interview kit · chain 5</div>"
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:24px;">'
            f'<div><div class="card-title" style="margin-bottom:10px;">{icon("technical", 15)}'
            f"<span>Technical</span></div>"
            f"{question_list(q.technical)}</div>"
            f'<div><div class="card-title" style="margin-bottom:10px;">{icon("hr", 15)}'
            f"<span>HR / behavioural</span></div>"
            f"{question_list(q.hr)}</div>"
            "</div></div>",
            unsafe_allow_html=True,
        )
    elif a.recommendation == "Reject":
        st.info("Interview questions are generated only for shortlisted candidates.",
                icon=":material/info:")

    # ── Module 9 · Raw structured output ────────────────────────────────────
    with st.expander("Structured JSON output (Module 9)", icon=":material/data_object:"):
        st.json(a.to_public_json())

    with st.expander("Extracted resume text (Module 2)", icon=":material/description:"):
        st.text_area(
            "Cleaned text", a.resume_text or "No text extracted.",
            height=320, label_visibility="collapsed", key=f"{key_prefix}text",
        )


def render_candidate_picker(results: List[CandidateAnalysis], job_title: str = "") -> None:
    """Dropdown + detail view for the whole batch."""
    if not results:
        return
    labels = [
        f"{i}. {r.candidate_name} — {r.score}% · {r.recommendation}"
        for i, r in enumerate(results, start=1)
    ]
    picked = st.selectbox("Candidate", labels, label_visibility="collapsed")
    idx = labels.index(picked)
    render_candidate(results[idx], job_title, key_prefix=f"c{idx}_")
