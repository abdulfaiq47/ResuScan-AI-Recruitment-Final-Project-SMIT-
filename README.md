# ResuScan

**AI resume screening for HR teams.**

An HR screening dashboard that reads a stack of resumes against a job
description and returns a summary, skill gap analysis, a 0-100 match score,
a hiring recommendation, tailored interview questions and a ranked comparison
table — built with **Streamlit** and a **LangChain** 5-chain pipeline running on
**free** AI models.

---

## Quick start

```bash
pip install -r requirements.txt      # 1. install
copy .env.example .env               # 2. add ONE free API key (see below)
streamlit run app.py                 # 3. run
```

Then in the browser: upload the job description → upload one or more resumes →
**Analyse**.

Sample files to try it with are in [`data/`](data/).

### Getting a free API key

You only need **one**. Paste it into `.env`, or straight into the sidebar.

| Provider | Where | Env var |
|---|---|---|
| OpenRouter | <https://openrouter.ai/keys> | `OPENROUTER_API_KEY` |
| NVIDIA NIM | <https://build.nvidia.com/> | `NVIDIA_API_KEY` |
| Google Gemini | <https://aistudio.google.com/apikey> | `GOOGLE_API_KEY` |

---

## How the model is chosen

The app does **not** hardcode a model name — provider catalogues change every
few months and hardcoded lists rot. Instead, on startup it:

1. **Discovers** every model reachable with your keys, keeping only zero-cost,
   text-in/text-out chat models (embedders, rerankers, safety filters, vision,
   audio and reward models are filtered out).
2. **Ranks** them from live signals — parameter count (including MoE
   active-vs-total), vendor tier keyword (`ultra`, `pro`, `mini`, `nano`),
   model family, context window and instruction tuning.
3. **Picks** the best one for your chosen strategy and keeps the next three as
   **automatic failovers**, preferring a different provider so one provider's
   rate limit can't stall the run.

| Strategy | Picks |
|---|---|
| **Balanced** *(default)* | Best quality that still answers quickly |
| **Best quality** | Largest model available — slower, minutes per resume |
| **Fastest** | Smallest capable model — for large batches |

You can always override the auto-pick from the sidebar dropdown, or pin one
permanently with `FORCE_PROVIDER` / `FORCE_MODEL` in `.env`.

> **Note on speed:** the provider matters more than the model size. Measured on
> the same 3-resume batch: NVIDIA NIM direct took **51s per resume**, while
> OpenRouter's shared `:free` pool took **412s per resume** for a comparable
> model — the free pool queues requests heavily. Balanced and Fastest both
> account for this, so they prefer a direct endpoint when one is available.

---

## The pipeline

```
Resume PDF + Job Description PDF
          │
          ▼
   PDF text extraction        pypdf → pdfplumber fallback
          │
          ▼
     Text cleaning            ligatures, hyphen joins, page furniture
          │
          ▼
 ┌────────┴────────┐          LangChain LCEL
 ▼                 ▼
Chain 1          Chain 2      run in parallel (RunnableParallel)
Summary          Skill match
 └────────┬────────┘
          ▼
      Chain 3  Match score        weighted 0-100
          ▼
      Chain 4  HR recommendation  Hire / Interview / Reject
          ▼
      Chain 5  Interview kit      shortlisted candidates only
          ▼
   Ranking table → CSV · Word · JSON
```

| Chain | Module | Output |
|---|---|---|
| 1 · Summary | 4 | Name, education, years of experience, key skills, highlights |
| 2 · Skill match | 5 | Matching / Missing / Extra skills |
| 3 · Match score | 6 | 0-100 — skills 55%, experience 30%, education 15% |
| 4 · Recommendation | 7 | Hire / Interview / Reject + justification |
| 5 · Interview kit | 8 | 6 technical + 5 HR questions, per candidate |

Chains 1 and 2 are independent so they run concurrently; the rest are
sequential because each consumes the previous chain's structured output.

### The verdict/score coherence guard

Models sometimes return a self-contradictory result — a 96% match marked
**Reject** because a *preferred* skill was missing. HR can't act on that, so
[`ai/chains.py`](ai/chains.py) reconciles the verdict against the score band
(≥80 Hire · 60-79 Interview · <60 Reject) and **appends a line to the
justification saying it did so**. The adjustment is never silent — you always
see both the model's reasoning and the correction.

### Structured output (Module 9)

Every chain returns JSON, validated into Pydantic models in
[`ai/schemas.py`](ai/schemas.py). The parser in
[`utils/parser.py`](utils/parser.py) is deliberately forgiving — it strips
markdown fences and `<think>` blocks, repairs trailing commas and smart quotes,
and falls back field-by-field, so one malformed reply degrades gracefully
instead of crashing the batch.

```json
{
  "candidate": "Sara Khan",
  "summary": "...",
  "score": 88,
  "matching_skills": ["Python", "TensorFlow", "SQL"],
  "missing_skills": ["Docker", "Azure"],
  "extra_skills": ["Power BI"],
  "interview_questions": { "technical": ["..."], "hr": ["..."] },
  "recommendation": "Hire",
  "justification": ["..."]
}
```

---

## Exports (Module 11)

| Export | Scope | Contents |
|---|---|---|
| CSV | Whole batch | Ranking table — opens in Excel |
| Word report | Whole batch | Ranking table + one page per candidate |
| Word summary | One candidate | Shareable profile (Module 4 deliverable) |
| JSON | Either | Structured output for downstream systems |

---

## Project structure

```
ResuScan/
├── app.py                  Streamlit entry point, session state, run loop
├── requirements.txt
├── .env                    your API keys (not committed)
├── .streamlit/config.toml  white theme
│
├── components/
│   ├── sidebar.py          engine status, JD + resume upload, settings
│   ├── uploader.py         cached extraction widgets
│   ├── ranking.py          ranking dashboard + exports  (Modules 10, 11)
│   ├── results.py          per-candidate detail view    (Modules 4-9)
│   └── styles.py           white-theme design system
│
├── utils/
│   ├── pdf_reader.py       extraction + cleaning        (Module 2)
│   ├── prompts.py          all five prompts             (Modules 4-8)
│   ├── parser.py           defensive JSON parsing       (Modules 3, 9)
│   └── exporter.py         Word / CSV / JSON exports    (Modules 4, 11)
│
├── ai/
│   ├── llm.py              provider discovery, ranking, failover
│   ├── chains.py           the 5-chain LangChain pipeline (Module 3)
│   └── schemas.py          Pydantic output schemas       (Module 9)
│
├── images/                 SVG icon set (no emoji anywhere in the UI)
├── data/                   sample JD + resumes
└── outputs/                archived exports
```

---

## Icons

The interface uses **no emoji** — every mark is an SVG in [`images/`](images/).

- **Inside HTML** (hero, cards, badges, section titles, ranking rows) icons come
  from `images/` via `styles.icon("ranking")`. The SVG source is *inlined*
  rather than linked through an `<img>`, because an `<img>` renders the file as
  a separate document where `fill="currentColor"` resolves to black. Inlining
  lets one asset take its colour from wherever it sits — green in *Matching*,
  red in *Missing*, indigo in a section title.
- **Inside widget labels** (buttons, expanders, download buttons, alert icons)
  Streamlit renders plain text and cannot display an image, so those use
  Streamlit's built-in Material icons — `icon=":material/rocket_launch:"`.

To swap any icon, drop a replacement SVG into `images/` under the same name; to
add one, put the file there and add a line to the `ICONS` map in
[`components/styles.py`](components/styles.py). Authoring an icon with
`fill="currentColor"` makes it theme-aware; a hardcoded fill keeps its own
brand colour. Missing or zero-byte files degrade to nothing rather than a
broken-image box.

---

## Notes

- **Scanned PDFs** (image-only, no text layer) can't be read — the app detects
  this and tells you which file to re-save. There is no OCR step.
- **Scoring is decision support, not a decision.** The model can misread dates
  and infer seniority from job titles; always read the justification.
- `LLM_TEMPERATURE` in `.env` controls consistency. Keep it low (`0.1`) so the
  same resume scores the same way twice; higher values make scores drift.
- Resumes are truncated to 14k characters and job descriptions to 8k before
  being sent, to stay inside free-tier context limits.
