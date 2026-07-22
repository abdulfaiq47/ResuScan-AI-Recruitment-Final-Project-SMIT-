from __future__ import annotations

import re
from typing import List

import streamlit as st

from utils.pdf_reader import ExtractedDoc, read_document

ACCEPTED = ["pdf", "txt", "docx"]


@st.cache_data(show_spinner=False, max_entries=64)
def _extract(file_name: str, data: bytes) -> dict:
    doc = read_document(file_name, data)
    return doc.__dict__


def _to_doc(payload: dict) -> ExtractedDoc:
    return ExtractedDoc(**payload)


def _guess_title(text: str) -> str:
    """First line that reads like a job title — shown on the report header."""
    for line in (text or "").splitlines():
        line = line.strip(" #*-•\t")
        if not (4 < len(line) < 90):
            continue
        if re.search(r"(?i)(engineer|developer|scientist|analyst|manager|designer|"
                     r"intern|architect|lead|specialist|consultant|administrator|officer)", line):
            return re.sub(r"(?i)^(job\s*title|position|role)\s*[:\-]\s*", "", line).strip()
    first = next((l.strip() for l in (text or "").splitlines() if l.strip()), "")
    return first[:70] or "Open Role"


# ─────────────────────────────────────────────────────────────────────────────
#  Job description
# ─────────────────────────────────────────────────────────────────────────────
def job_description_input() -> tuple[str, str]:
    mode = st.radio(
        "JD source", ["Upload file", "Paste text"],
        horizontal=True, label_visibility="collapsed", key="jd_mode",
    )

    text = ""
    if mode == "Upload file":
        jd_file = st.file_uploader(
            "Job description (PDF / DOCX / TXT)", type=ACCEPTED,
            key="jd_file", label_visibility="collapsed",
        )
        if jd_file is not None:
            doc = _to_doc(_extract(jd_file.name, jd_file.getvalue()))
            text = doc.text
            if doc.warning:
                st.warning(doc.warning, icon=":material/warning:")
            elif text:
                st.success(f"{doc.pages or 1} page(s) · {doc.chars:,} chars", icon=":material/check_circle:")
    else:
        text = st.text_area(
            "Paste the job description",
            key="jd_text", height=190, label_visibility="collapsed",
            placeholder="Paste the full job description here — responsibilities, "
                        "required skills, years of experience, education…",
        )
        if text.strip():
            st.caption(f"{len(text):,} characters")

    text = (text or "").strip()
    return text, _guess_title(text) if text else ""


# ─────────────────────────────────────────────────────────────────────────────
#  Resumes
# ─────────────────────────────────────────────────────────────────────────────
def resume_uploader() -> List[ExtractedDoc]:
    files = st.file_uploader(
        "Resumes (PDF / DOCX / TXT) — one or many", type=ACCEPTED,
        accept_multiple_files=True, key="resume_files", label_visibility="collapsed",
    )
    if not files:
        st.caption("Drop a single CV or a whole folder of them.")
        return []

    docs: List[ExtractedDoc] = []
    seen: set[str] = set()
    for f in files:
        if f.name in seen:          # Streamlit can hand back duplicates
            continue
        seen.add(f.name)
        docs.append(_to_doc(_extract(f.name, f.getvalue())))

    good = [d for d in docs if d.ok]
    bad = [d for d in docs if not d.ok]

    st.markdown(
        f'<div class="status-line" style="margin-top:8px;">'
        f'<span class="dot dot-live"></span>{len(good)} resume(s) ready'
        + (f' · {len(bad)} unreadable' if bad else "")
        + "</div>",
        unsafe_allow_html=True,
    )
    for d in bad:
        st.error(f"**{d.file_name}** — {d.warning or 'no text found'}", icon=":material/error:")

    return good
