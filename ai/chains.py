from __future__ import annotations

import concurrent.futures as futures
from typing import Callable, List, Optional

from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableParallel

from ai.llm import LLMBundle, get_llm
from ai.schemas import (
    CandidateAnalysis,
    HRRecommendation,
    InterviewQuestions,
    MatchScore,
    ResumeSummary,
    SkillMatch,
)
from utils.parser import as_bullets, dedupe, parse_into
from utils.pdf_reader import guess_name_from_filename
from utils.prompts import (
    INTERVIEW_PROMPT,
    RECOMMENDATION_PROMPT,
    SCORE_PROMPT,
    SKILLS_PROMPT,
    SUMMARY_PROMPT,
)

# Free models have modest context windows; a resume never needs more than this.
MAX_RESUME_CHARS = 14_000
MAX_JD_CHARS = 8_000


def _truncate(text: str, limit: int) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit] + "\n…[truncated]"


def _tidy_name(name: str) -> str:
    """
    'ALI RAZA' → 'Ali Raza'. Resume headers are usually set in caps, and the
    model echoes them verbatim; shouting the name in every table cell reads
    badly. Mixed-case names are left exactly as the candidate wrote them.
    """
    name = (name or "").strip()
    if name and name == name.upper():
        return " ".join(part.capitalize() for part in name.split())
    return name


def _reconcile(score: int, recommendation: str) -> tuple[str, str]:
    """
    Keep the verdict coherent with the score.

    Models occasionally return "96% match — Reject" by treating a missing
    *preferred* skill as disqualifying. An HR user cannot act on a
    self-contradictory result, so the score band — which is the objective,
    reproducible number — wins, and the adjustment is disclosed.

    Returns (recommendation, note) where note is "" when nothing changed.
    """
    if score >= 80 and recommendation == "Reject":
        return "Interview", (
            f"Verdict raised to Interview: a {score}% match is not consistent with a "
            "reject, and the gaps cited are preferred rather than required skills."
        )
    if 60 <= score < 80 and recommendation == "Reject":
        return "Interview", (
            f"Verdict raised to Interview: {score}% falls in the 60-79 band, where the "
            "candidate warrants a conversation."
        )
    if score < 60 and recommendation == "Hire":
        return "Interview", (
            f"Verdict lowered to Interview: {score}% is below the 60% bar for a "
            "straight hire."
        )
    return recommendation, ""


# ─────────────────────────────────────────────────────────────────────────────
#  Chain builders — each is  prompt | llm | StrOutputParser
#  (parsing to Pydantic happens in utils.parser so a malformed JSON response
#   degrades gracefully instead of blowing up the whole run)
# ─────────────────────────────────────────────────────────────────────────────
class ResumePipeline:
    def __init__(self, bundle: Optional[LLMBundle] = None):
        self.bundle = bundle or get_llm()
        llm = self.bundle.llm
        out = StrOutputParser()

        self.summary_chain = SUMMARY_PROMPT | llm | out            # Chain 1
        self.skills_chain = SKILLS_PROMPT | llm | out              # Chain 2
        self.score_chain = SCORE_PROMPT | llm | out                # Chain 3
        self.recommendation_chain = RECOMMENDATION_PROMPT | llm | out   # Chain 4
        self.interview_chain = INTERVIEW_PROMPT | llm | out        # Chain 5

        # Chains 1 + 2 fan out in parallel from the same input dict.
        self.profile_stage = RunnableParallel(
            summary=self.summary_chain,
            skills=self.skills_chain,
        )

    # ── the full 5-chain run for ONE resume ─────────────────────────────────
    def analyze(
        self,
        resume_text: str,
        job_description: str,
        file_name: str = "",
        on_step: Optional[Callable[[str], None]] = None,
        skip_questions_for_rejects: bool = True,
    ) -> CandidateAnalysis:
        step = on_step or (lambda _msg: None)
        resume_text = _truncate(resume_text, MAX_RESUME_CHARS)
        job_description = _truncate(job_description, MAX_JD_CHARS)

        result = CandidateAnalysis(
            file_name=file_name,
            model_used=self.bundle.display,
            resume_text=resume_text,
        )

        try:
            # ── Stage A · Chains 1 & 2 in parallel ──────────────────────────
            step("Reading the resume & matching skills…")
            stage_a = self.profile_stage.invoke(
                {
                    "resume_text": resume_text,
                    "job_description": job_description,
                    "candidate_skills": "(extracted in parallel — read the resume text)",
                }
            )
            summary = parse_into(stage_a["summary"], ResumeSummary)
            skills = parse_into(stage_a["skills"], SkillMatch)

            # Chain 2 ran without chain 1's skill list. If it came back thin but
            # chain 1 found skills, re-run it now with the proper input.
            if summary.key_skills and len(skills.matching_skills) + len(skills.missing_skills) < 3:
                step("Refining the skill comparison…")
                skills = parse_into(
                    self.skills_chain.invoke(
                        {
                            "resume_text": resume_text,
                            "job_description": job_description,
                            "candidate_skills": as_bullets(summary.key_skills),
                        }
                    ),
                    SkillMatch,
                )

            result.candidate_name = _tidy_name(summary.candidate_name)
            if result.candidate_name.lower() in {"unknown candidate", "unknown", "n/a", ""}:
                result.candidate_name = guess_name_from_filename(file_name)
            result.email = summary.email
            result.phone = summary.phone
            result.education = dedupe(summary.education)
            result.experience_years = summary.experience_years
            result.current_role = summary.current_role
            result.key_skills = dedupe(summary.key_skills)
            result.highlights = dedupe(summary.highlights)
            result.summary = summary.summary
            result.matching_skills = dedupe(skills.matching_skills)
            result.missing_skills = dedupe(skills.missing_skills)
            result.extra_skills = dedupe(skills.extra_skills)

            # ── Stage B · Chain 3 — score ───────────────────────────────────
            step("Scoring the match…")
            score = parse_into(
                self.score_chain.invoke(
                    {
                        "job_description": job_description,
                        "current_role": result.current_role or "Not stated",
                        "experience_years": result.experience_years,
                        "education": as_bullets(result.education, "Not stated"),
                        "matching_skills": as_bullets(result.matching_skills),
                        "missing_skills": as_bullets(result.missing_skills),
                        "extra_skills": as_bullets(result.extra_skills),
                        "summary": result.summary or "Not available",
                    }
                ),
                MatchScore,
            )
            result.score = score.score
            result.skills_score = score.skills_score
            result.experience_score = score.experience_score
            result.education_score = score.education_score
            result.score_reason = score.score_reason

            # ── Stage C · Chain 4 — recommendation ──────────────────────────
            step("Forming the HR recommendation…")
            rec = parse_into(
                self.recommendation_chain.invoke(
                    {
                        "job_description": job_description,
                        "score": result.score,
                        "score_reason": result.score_reason or "n/a",
                        "matching_skills": as_bullets(result.matching_skills),
                        "missing_skills": as_bullets(result.missing_skills),
                        "experience_years": result.experience_years,
                        "summary": result.summary or "Not available",
                        "highlights": as_bullets(result.highlights),
                    }
                ),
                HRRecommendation,
            )
            result.recommendation, note = _reconcile(result.score, rec.recommendation)
            result.justification = dedupe(rec.justification)
            result.strengths = dedupe(rec.strengths)
            result.concerns = dedupe(rec.concerns)
            if note:
                result.justification.append(note)

            # ── Stage D · Chain 5 — interview kit (shortlisted only) ────────
            if result.recommendation == "Reject" and skip_questions_for_rejects:
                step("Rejected — skipping the interview kit.")
            else:
                step("Writing tailored interview questions…")
                questions = parse_into(
                    self.interview_chain.invoke(
                        {
                            "job_description": job_description,
                            "summary": result.summary or "Not available",
                            "matching_skills": as_bullets(result.matching_skills),
                            "missing_skills": as_bullets(result.missing_skills),
                            "highlights": as_bullets(result.highlights),
                            "experience_years": result.experience_years,
                        }
                    ),
                    InterviewQuestions,
                )
                result.interview_questions = InterviewQuestions(
                    technical=dedupe(questions.technical),
                    hr=dedupe(questions.hr),
                )

            step("Done.")

        except Exception as exc:  # noqa: BLE001 — one bad resume must not stop the batch
            result.error = f"{type(exc).__name__}: {exc}"
            step(f"Failed: {result.error[:120]}")
            if not result.candidate_name or result.candidate_name == "Unknown Candidate":
                result.candidate_name = guess_name_from_filename(file_name)

        return result


# ─────────────────────────────────────────────────────────────────────────────
#  Batch helper — Module 10 feeds off this
# ─────────────────────────────────────────────────────────────────────────────
def analyze_batch(
    documents: List[tuple[str, str]],          # [(file_name, resume_text), …]
    job_description: str,
    bundle: Optional[LLMBundle] = None,
    workers: int = 1,
    on_progress: Optional[Callable[[int, int, str], None]] = None,
    skip_questions_for_rejects: bool = True,
) -> List[CandidateAnalysis]:
    """
    Run the 5-chain pipeline over every uploaded resume.

    `workers > 1` analyses several candidates concurrently — much faster for a
    stack of CVs, but free tiers rate-limit, so the UI defaults to 2.

    `on_progress(done, total, label)` is only ever called from the calling
    thread, which keeps it safe to touch Streamlit from inside it.
    """
    pipeline = ResumePipeline(bundle)
    total = len(documents)
    results: List[Optional[CandidateAnalysis]] = [None] * total
    done = 0

    def _one(name: str, text: str, on_step=None) -> CandidateAnalysis:
        return pipeline.analyze(
            text,
            job_description,
            file_name=name,
            on_step=on_step,
            skip_questions_for_rejects=skip_questions_for_rejects,
        )

    if workers <= 1:
        for idx, (name, text) in enumerate(documents):
            if on_progress:
                on_progress(done, total, name)
            results[idx] = _one(
                name, text,
                on_step=lambda msg, n=name, d=done: on_progress and on_progress(d, total, f"{n} — {msg}"),
            )
            done += 1
    else:
        with futures.ThreadPoolExecutor(max_workers=min(workers, total or 1)) as pool:
            jobs = {
                pool.submit(_one, name, text): idx
                for idx, (name, text) in enumerate(documents)
            }
            for fut in futures.as_completed(jobs):
                idx = jobs[fut]
                try:
                    results[idx] = fut.result()
                except Exception as exc:  # noqa: BLE001 — keep the batch alive
                    name = documents[idx][0]
                    results[idx] = CandidateAnalysis(
                        file_name=name,
                        candidate_name=guess_name_from_filename(name),
                        error=f"{type(exc).__name__}: {exc}",
                    )
                done += 1
                if on_progress:
                    on_progress(done, total, results[idx].candidate_name)

    if on_progress:
        on_progress(total, total, "Analysis complete")
    return [r for r in results if r is not None]


def rank(results: List[CandidateAnalysis]) -> List[CandidateAnalysis]:
    """Sort candidates best-first: score, then recommendation, then experience."""
    weight = {"Hire": 2, "Interview": 1, "Reject": 0}
    return sorted(
        results,
        key=lambda r: (r.score, weight.get(r.recommendation, 0), r.experience_years),
        reverse=True,
    )
