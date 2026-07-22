from __future__ import annotations

import re
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


# ── Chain 1 · Resume Summary ────────────────────────────────────────────────
class ResumeSummary(BaseModel):
    candidate_name: str = Field(default="Unknown Candidate")
    email: str = Field(default="")
    phone: str = Field(default="")
    education: List[str] = Field(default_factory=list)
    experience_years: float = Field(default=0)
    current_role: str = Field(default="")
    key_skills: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list, description="Notable projects / achievements")
    summary: str = Field(default="")

    @field_validator("experience_years", mode="before")
    @classmethod
    def _num(cls, v):
        """Accept 5, "5", "5 years", "about 4", "3-4 years" → a plain number."""
        if isinstance(v, (int, float)):
            return max(0.0, float(v))
        match = re.search(r"\d+(?:\.\d+)?", str(v or ""))
        return max(0.0, float(match.group())) if match else 0.0


# ── Chain 2 · Skill Match ───────────────────────────────────────────────────
class SkillMatch(BaseModel):
    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    extra_skills: List[str] = Field(default_factory=list)


# ── Chain 3 · Match Score ───────────────────────────────────────────────────
class MatchScore(BaseModel):
    score: int = Field(default=0, ge=0, le=100)
    skills_score: int = Field(default=0, ge=0, le=100)
    experience_score: int = Field(default=0, ge=0, le=100)
    education_score: int = Field(default=0, ge=0, le=100)
    score_reason: str = Field(default="")

    @field_validator("score", "skills_score", "experience_score", "education_score", mode="before")
    @classmethod
    def _clamp(cls, v):
        try:
            n = int(round(float(str(v).replace("%", "").strip())))
        except Exception:
            n = 0
        return max(0, min(100, n))


# ── Chain 4 · HR Recommendation ─────────────────────────────────────────────
class HRRecommendation(BaseModel):
    recommendation: str = Field(default="Reject")   # Hire | Interview | Reject
    justification: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)

    @field_validator("recommendation", mode="before")
    @classmethod
    def _norm(cls, v):
        text = str(v or "").strip().lower()
        if "hire" in text and "not" not in text and "no " not in text:
            return "Hire"
        if "interview" in text or "maybe" in text or "consider" in text or "shortlist" in text:
            return "Interview"
        return "Reject"


# ── Chain 5 · Interview Questions ───────────────────────────────────────────
class InterviewQuestions(BaseModel):
    technical: List[str] = Field(default_factory=list)
    hr: List[str] = Field(default_factory=list)


# ── Final merged record (Module 9 schema) ───────────────────────────────────
class CandidateAnalysis(BaseModel):
    file_name: str = ""
    candidate_name: str = "Unknown Candidate"
    email: str = ""
    phone: str = ""
    education: List[str] = Field(default_factory=list)
    experience_years: float = 0
    current_role: str = ""
    key_skills: List[str] = Field(default_factory=list)
    highlights: List[str] = Field(default_factory=list)
    summary: str = ""

    matching_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    extra_skills: List[str] = Field(default_factory=list)

    score: int = 0
    skills_score: int = 0
    experience_score: int = 0
    education_score: int = 0
    score_reason: str = ""

    recommendation: str = "Reject"
    justification: List[str] = Field(default_factory=list)
    strengths: List[str] = Field(default_factory=list)
    concerns: List[str] = Field(default_factory=list)

    interview_questions: InterviewQuestions = Field(default_factory=InterviewQuestions)

    model_used: str = ""
    error: Optional[str] = None
    resume_text: str = ""

    # ── helpers used by the UI / exports ────────────────────────────────────
    def to_row(self) -> dict:
        return {
            "Candidate": self.candidate_name,
            "File": self.file_name,
            "Score": self.score,
            "Recommendation": self.recommendation,
            "Experience (yrs)": self.experience_years,
            "Summary": self.summary,
            "Matching Skills": ", ".join(self.matching_skills),
            "Missing Skills": ", ".join(self.missing_skills),
            "Extra Skills": ", ".join(self.extra_skills),
            "Justification": " | ".join(self.justification),
            "Email": self.email,
            "Phone": self.phone,
            "Model": self.model_used,
        }

    def to_public_json(self) -> dict:
        """Exactly the Module-9 contract, for the JSON download / API view."""
        return {
            "candidate": self.candidate_name,
            "summary": self.summary,
            "score": self.score,
            "matching_skills": self.matching_skills,
            "missing_skills": self.missing_skills,
            "extra_skills": self.extra_skills,
            "interview_questions": {
                "technical": self.interview_questions.technical,
                "hr": self.interview_questions.hr,
            },
            "recommendation": self.recommendation,
            "justification": self.justification,
        }
