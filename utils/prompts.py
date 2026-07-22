from langchain_core.prompts import ChatPromptTemplate

# Shared system persona — a strict, evidence-driven technical recruiter.
_SYSTEM = (
    "You are an elite technical recruiter and hiring analyst with 15 years of "
    "experience screening CVs for engineering and data roles.\n"
    "Rules you never break:\n"
    "• You rely ONLY on evidence present in the supplied text. You never "
    "invent skills, employers, degrees or dates.\n"
    "• You output ONE single valid JSON object and absolutely nothing else — "
    "no explanation before it, no markdown code fence around it.\n"
    "• All JSON strings use double quotes; no trailing commas; no comments."
)


def _tpl(human: str) -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([("system", _SYSTEM), ("human", human)])


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 4 · Chain 1 — Resume Summary
#  Goal: pull out education, years of experience and key skills.
# ─────────────────────────────────────────────────────────────────────────────
SUMMARY_PROMPT = _tpl(
    """Read the resume below and extract a factual profile of the candidate.

RESUME
------
{resume_text}
------

Extraction guidance:
• candidate_name — the person's full name as printed on the resume. If it is
  genuinely not present, use "Unknown Candidate".
• education — one entry per qualification, formatted "Degree, Institution, Year"
  (omit any part that is missing).
• experience_years — total PROFESSIONAL experience as a number (internships
  count as half). Add up the date ranges; if none are given, estimate from the
  roles listed and return 0 when there is no work history at all.
• key_skills — 8 to 15 concrete, named skills (languages, frameworks, tools,
  cloud platforms, domains). No soft-skill fluff like "hard working".
• highlights — 3 to 5 achievements or projects, each one short line, with the
  measurable impact when the resume states one.
• summary — 2 to 3 sentences describing who this candidate is professionally.

Return exactly this JSON shape:
{{
  "candidate_name": "string",
  "email": "string",
  "phone": "string",
  "education": ["string"],
  "experience_years": number,
  "current_role": "string",
  "key_skills": ["string"],
  "highlights": ["string"],
  "summary": "string"
}}"""
)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 5 · Chain 2 — Skill Match (Matching / Missing / Extra)
# ─────────────────────────────────────────────────────────────────────────────
SKILLS_PROMPT = _tpl(
    """Compare the candidate's skills against the job description and split them
into three buckets.

JOB DESCRIPTION
---------------
{job_description}
---------------

CANDIDATE SKILLS (extracted from the resume)
{candidate_skills}

FULL RESUME TEXT (use it to catch skills demonstrated in projects but not listed)
---------------
{resume_text}
---------------

Bucket definitions:
• matching_skills — required/preferred in the JD AND evidenced in the resume.
  Treat obvious equivalents as a match (e.g. "PyTorch" satisfies "deep learning
  framework", "GCP" satisfies "cloud platform").
• missing_skills — required or preferred by the JD with NO evidence in the
  resume. This drives the hiring gap analysis, so be honest and specific.
• extra_skills — real, valuable skills the candidate has that the JD never asks
  for. Cap this at 10 entries, most relevant first.

Use the JD's own wording for skill names so HR can trace each one back.

Return exactly this JSON shape:
{{
  "matching_skills": ["string"],
  "missing_skills": ["string"],
  "extra_skills": ["string"]
}}"""
)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 6 · Chain 3 — Match Score (0-100)
# ─────────────────────────────────────────────────────────────────────────────
SCORE_PROMPT = _tpl(
    """Score how well this candidate fits the job, as a single percentage.

JOB DESCRIPTION
---------------
{job_description}
---------------

CANDIDATE PROFILE
- Current role: {current_role}
- Years of experience: {experience_years}
- Education: {education}
- Matching skills: {matching_skills}
- Missing skills: {missing_skills}
- Extra skills: {extra_skills}
- Profile summary: {summary}

Scoring method — compute the sub-scores first, then the weighted total:
• skills_score (weight 55%) — share of the JD's REQUIRED skills that are
  matched. A missing must-have costs far more than a missing nice-to-have.
• experience_score (weight 30%) — years AND relevance versus what the JD asks.
  Meeting the requirement ≈ 85; clearly exceeding it ≈ 95; roughly half the
  required years ≈ 45.
• education_score (weight 15%) — degree level and field versus the JD.

score = round(0.55*skills_score + 0.30*experience_score + 0.15*education_score)

Calibration you must respect — do NOT inflate:
  90-100 outstanding, near-perfect fit   |  75-89 strong fit, minor gaps
  60-74  moderate fit, real gaps         |  40-59 weak fit, major gaps
  0-39   not suitable for this role
score_reason: one sentence, max 25 words, naming the decisive factor.

Return exactly this JSON shape:
{{
  "score": number,
  "skills_score": number,
  "experience_score": number,
  "education_score": number,
  "score_reason": "string"
}}"""
)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 7 · Chain 4 — HR Recommendation
# ─────────────────────────────────────────────────────────────────────────────
RECOMMENDATION_PROMPT = _tpl(
    """Give the hiring decision for this candidate against this role.

JOB DESCRIPTION
---------------
{job_description}
---------------

EVIDENCE
- Overall match score: {score}/100 ({score_reason})
- Matching skills: {matching_skills}
- Missing skills: {missing_skills}
- Years of experience: {experience_years}
- Profile summary: {summary}
- Highlights: {highlights}

Decision rule — apply the steps IN ORDER and stop at the first one that fires:

STEP 1. Is a genuinely non-negotiable requirement absent? ALL of these must be
        true for something to count as non-negotiable:
          (a) the JD lists it under required / must-have — anything under
              "preferred", "nice to have", "bonus" or "plus" can NEVER make a
              candidate a reject, no matter how many of them are missing;
          (b) the job cannot be performed at all without it (a licence, a legal
              eligibility, a specific degree, a hard minimum of years);
          (c) it is not something a competent hire picks up in a few weeks —
              Docker, an unfamiliar cloud vendor, or a second ML framework when
              they already ship with one are all learnable, not blockers.
        → If yes: "Reject". Name that exact blocker first in the justification.

STEP 2. Otherwise decide purely on the score band:
        • score ≥ 80  → "Hire"
        • score 60-79 → "Interview"
        • score < 60  → "Reject"

Never claim a score sits below a band it actually falls inside — state the real
band or the real blocker. A candidate scoring 60-79 with only closable gaps is
an "Interview", not a "Reject".

• justification — 3 to 4 bullet points, each under 15 words, each pointing at
  concrete resume evidence. State the blocking reason first when rejecting.
• strengths — up to 4 things this candidate brings to THIS role.
• concerns  — up to 4 risks or gaps a hiring manager should probe.

Return exactly this JSON shape:
{{
  "recommendation": "Hire" | "Interview" | "Reject",
  "justification": ["string"],
  "strengths": ["string"],
  "concerns": ["string"]
}}"""
)


# ─────────────────────────────────────────────────────────────────────────────
#  MODULE 8 · Chain 5 — Interview Questions
#  Only run for candidates recommended Hire / Interview.
# ─────────────────────────────────────────────────────────────────────────────
INTERVIEW_PROMPT = _tpl(
    """Write an interview kit tailored to THIS candidate and THIS role.

JOB DESCRIPTION
---------------
{job_description}
---------------

CANDIDATE
- Summary: {summary}
- Matching skills: {matching_skills}
- Missing skills: {missing_skills}
- Highlights / projects: {highlights}
- Years of experience: {experience_years}

Write 6 technical questions:
• 2 that probe depth in their strongest matching skills — reference their own
  project or employer by name so the question could not be reused verbatim for
  anyone else.
• 2 scenario questions drawn from the day-to-day work the JD describes.
• 2 that check whether a missing skill is a real gap or just an unlisted one.

Write 5 HR / behavioural questions:
• Tailored to their career path — gaps, job changes, seniority jump, relocation
  or domain switch, whichever their resume actually raises.
• Include one on motivation for this specific role and one on collaboration.

Every question must be a single sentence a human would say out loud.

Return exactly this JSON shape:
{{
  "technical": ["string"],
  "hr": ["string"]
}}"""
)
