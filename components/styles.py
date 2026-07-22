from __future__ import annotations

import base64
import html
import os

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

:root{
  --ink:#0B1020; --ink-2:#1F2937; --muted:#6B7280; --faint:#9CA3AF;
  --line:#ECEEF3; --line-2:#F5F6FA;
  --bg:#FFFFFF; --bg-2:#FBFBFD;
  --indigo:#4F46E5; --violet:#7C3AED; --pink:#EC4899;
  --emerald:#059669; --amber:#D97706; --rose:#E11D48;
  --grad:linear-gradient(135deg,#4F46E5 0%,#7C3AED 55%,#EC4899 100%);
  --shadow-sm:0 1px 2px rgba(16,24,40,.05);
  --shadow-md:0 1px 3px rgba(16,24,40,.06), 0 12px 28px -14px rgba(16,24,40,.18);
  --shadow-lg:0 2px 6px rgba(16,24,40,.06), 0 28px 60px -28px rgba(79,70,229,.32);
  --r-lg:20px; --r-md:14px; --r-sm:10px;
}

/* ── canvas ─────────────────────────────────────────────────────────────── */
html, body, [class*="css"], .stApp{
  font-family:'Plus Jakarta Sans',-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
  color:var(--ink);
}
.stApp{
  background:
    radial-gradient(900px 480px at 88% -8%, rgba(124,58,237,.07), transparent 60%),
    radial-gradient(760px 420px at 2% 0%, rgba(79,70,229,.07), transparent 58%),
    radial-gradient(600px 400px at 60% 100%, rgba(236,72,153,.045), transparent 62%),
    #FFFFFF;
}
[data-testid="stHeader"]{background:transparent;}
[data-testid="stToolbar"]{right:12px;}
.block-container{padding-top:1.6rem; padding-bottom:4rem; max-width:1400px;}
#MainMenu, footer{visibility:hidden;}

h1,h2,h3,h4{letter-spacing:-.022em; color:var(--ink); font-weight:800;}
p, li, span, label{color:var(--ink-2);}
a{color:var(--indigo); text-decoration:none;}
a:hover{text-decoration:underline;}
hr{border:none; border-top:1px solid var(--line); margin:1.5rem 0;}

/* ── sidebar ────────────────────────────────────────────────────────────── */
[data-testid="stSidebar"]{
  background:linear-gradient(180deg,#FFFFFF 0%,#FBFBFD 100%);
  border-right:1px solid var(--line);
}
[data-testid="stSidebar"] .block-container{padding-top:1.2rem;}
[data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3{font-size:1rem;}

/* ── hero ───────────────────────────────────────────────────────────────── */
.hero{
  position:relative; overflow:hidden;
  border:1px solid var(--line); border-radius:26px;
  background:linear-gradient(180deg,#FFFFFF 0%,#FCFCFE 100%);
  box-shadow:var(--shadow-lg);
  padding:34px 38px; margin-bottom:22px;
}
.hero:before{
  content:""; position:absolute; inset:0 0 auto 0; height:4px; background:var(--grad);
}
.hero:after{
  content:""; position:absolute; right:-90px; top:-120px; width:360px; height:360px;
  background:var(--grad); filter:blur(90px); opacity:.16; border-radius:50%;
}
.hero-eyebrow{
  display:inline-flex; align-items:center; gap:8px;
  font-size:11.5px; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  color:var(--indigo); background:rgba(79,70,229,.08);
  border:1px solid rgba(79,70,229,.16); padding:6px 12px; border-radius:999px;
}
.hero h1{
  font-size:clamp(30px,4vw,46px); line-height:1.06; margin:16px 0 10px; font-weight:800;
}
.hero h1 .grad{
  background:var(--grad); -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent;
}
.hero p{color:var(--muted); font-size:15.5px; max-width:660px; margin:0; line-height:1.6;}
.hero-chips{display:flex; flex-wrap:wrap; gap:8px; margin-top:20px;}
.hero-chip{
  font-size:12px; font-weight:600; color:var(--ink-2);
  background:#fff; border:1px solid var(--line); border-radius:999px; padding:7px 13px;
  box-shadow:var(--shadow-sm);
}
.hero-chip b{color:var(--indigo);}

/* ── cards ──────────────────────────────────────────────────────────────── */
.card{
  background:#fff; border:1px solid var(--line); border-radius:var(--r-lg);
  padding:22px 24px; box-shadow:var(--shadow-md); margin-bottom:16px;
  transition:box-shadow .22s ease, transform .22s ease;
}
.card:hover{box-shadow:var(--shadow-lg);}
.card-title{
  display:flex; align-items:center; gap:9px;
  font-size:12px; font-weight:700; letter-spacing:.1em; text-transform:uppercase;
  color:var(--muted); margin:0 0 14px;
}
.card-title .dot{width:7px;height:7px;border-radius:50%;background:var(--grad);}

/* ── stat tiles ─────────────────────────────────────────────────────────── */
.stat-row{display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:14px; margin-bottom:18px;}
.stat{
  background:#fff; border:1px solid var(--line); border-radius:var(--r-md);
  padding:16px 18px; box-shadow:var(--shadow-sm); position:relative; overflow:hidden;
}
.stat:before{content:""; position:absolute; left:0; top:0; bottom:0; width:3px; background:var(--grad);}
.stat .lbl{font-size:11px; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color:var(--faint);}
.stat .val{font-size:30px; font-weight:800; color:var(--ink); line-height:1.15; margin-top:6px; letter-spacing:-.03em;}
.stat .sub{font-size:12px; color:var(--muted); margin-top:2px;}

/* ── pills / badges ─────────────────────────────────────────────────────── */
.pill{
  display:inline-flex; align-items:center; gap:6px;
  font-size:12.5px; font-weight:600; padding:6px 12px; border-radius:999px;
  margin:0 6px 8px 0; border:1px solid transparent; white-space:nowrap;
}
.pill-ok{background:rgba(5,150,105,.08); color:#047857; border-color:rgba(5,150,105,.2);}
.pill-miss{background:rgba(225,29,72,.07); color:#BE123C; border-color:rgba(225,29,72,.18);}
.pill-extra{background:rgba(79,70,229,.07); color:#4338CA; border-color:rgba(79,70,229,.18);}
.pill-neutral{background:#F7F8FB; color:var(--ink-2); border-color:var(--line);}

.badge{
  display:inline-flex; align-items:center; gap:6px; font-size:12.5px; font-weight:700;
  padding:6px 14px; border-radius:999px; letter-spacing:.01em;
}
.badge-hire{background:rgba(5,150,105,.1); color:#047857; border:1px solid rgba(5,150,105,.24);}
.badge-interview{background:rgba(217,119,6,.1); color:#B45309; border:1px solid rgba(217,119,6,.24);}
.badge-reject{background:rgba(225,29,72,.09); color:#BE123C; border:1px solid rgba(225,29,72,.22);}

/* ── score ring ─────────────────────────────────────────────────────────── */
.ring-wrap{display:flex; align-items:center; gap:20px;}
.ring{
  --pct:0; --c1:#4F46E5; --c2:#7C3AED;
  width:132px; height:132px; border-radius:50%; flex:none; position:relative;
  background:conic-gradient(from -90deg, var(--c1) 0%, var(--c2) calc(var(--pct)*1%), var(--line-2) calc(var(--pct)*1%) 100%);
  display:grid; place-items:center;
  animation:ringIn .8s cubic-bezier(.22,1,.36,1);
}
@keyframes ringIn{from{transform:scale(.86); opacity:0;} to{transform:scale(1); opacity:1;}}
.ring:after{
  content:""; position:absolute; inset:11px; background:#fff; border-radius:50%;
  box-shadow:inset 0 1px 3px rgba(16,24,40,.06);
}
.ring .inner{position:relative; z-index:1; text-align:center;}
.ring .num{font-size:33px; font-weight:800; letter-spacing:-.04em; color:var(--ink); line-height:1;}
.ring .cap{font-size:10px; font-weight:700; letter-spacing:.12em; text-transform:uppercase; color:var(--faint); margin-top:3px;}

/* ── mini bars ──────────────────────────────────────────────────────────── */
.bar-row{margin-bottom:12px;}
.bar-head{display:flex; justify-content:space-between; font-size:12.5px; font-weight:600; color:var(--ink-2); margin-bottom:5px;}
.bar-head span:last-child{color:var(--muted); font-variant-numeric:tabular-nums;}
.bar{height:7px; background:var(--line-2); border-radius:999px; overflow:hidden;}
.bar i{display:block; height:100%; border-radius:999px; background:var(--grad); animation:grow .9s cubic-bezier(.22,1,.36,1);}
@keyframes grow{from{width:0 !important;}}

/* ── candidate rank rows ────────────────────────────────────────────────── */
.rank-row{
  display:grid; grid-template-columns:52px 1fr 190px 132px; gap:16px; align-items:center;
  background:#fff; border:1px solid var(--line); border-radius:var(--r-md);
  padding:14px 18px; margin-bottom:10px; box-shadow:var(--shadow-sm);
  transition:transform .18s ease, box-shadow .18s ease, border-color .18s ease;
}
.rank-row:hover{transform:translateY(-2px); box-shadow:var(--shadow-md); border-color:#DDD9F7;}
.rank-row.top{border-color:rgba(79,70,229,.3); background:linear-gradient(90deg,rgba(79,70,229,.035),#fff 42%);}
.rank-medal{
  width:38px; height:38px; border-radius:12px; display:grid; place-items:center;
  font-weight:800; font-size:14px; color:#fff; background:var(--grad); box-shadow:var(--shadow-sm);
}
.rank-medal.silver{background:linear-gradient(135deg,#94A3B8,#64748B);}
.rank-medal.bronze{background:linear-gradient(135deg,#D6A25E,#B07C3A);}
.rank-medal.plain{background:#F3F4F8; color:var(--muted);}
.rank-name{font-weight:700; font-size:15px; color:var(--ink); letter-spacing:-.01em;}
.rank-meta{font-size:12.5px; color:var(--muted); margin-top:2px;}
.rank-score{text-align:right; font-size:20px; font-weight:800; letter-spacing:-.02em; color:var(--ink); font-variant-numeric:tabular-nums;}
.rank-bar{height:6px; background:var(--line-2); border-radius:999px; overflow:hidden; margin-top:6px;}
.rank-bar i{display:block; height:100%; background:var(--grad); border-radius:999px; animation:grow 1s cubic-bezier(.22,1,.36,1);}

/* ── question list ──────────────────────────────────────────────────────── */
.qlist{counter-reset:q; margin:0; padding:0; list-style:none;}
.qlist li{
  counter-increment:q; position:relative; padding:12px 14px 12px 46px; margin-bottom:8px;
  background:#FCFCFE; border:1px solid var(--line); border-radius:var(--r-sm);
  font-size:14px; color:var(--ink-2); line-height:1.5;
}
.qlist li:before{
  content:counter(q); position:absolute; left:13px; top:11px;
  width:22px; height:22px; border-radius:7px; background:var(--grad); color:#fff;
  font-size:11px; font-weight:700; display:grid; place-items:center;
}

/* ── bullet list ────────────────────────────────────────────────────────── */
.blist{margin:0; padding:0; list-style:none;}
.blist li{position:relative; padding:6px 0 6px 22px; font-size:14px; color:var(--ink-2); line-height:1.55;}
.blist li:before{
  content:""; position:absolute; left:4px; top:14px; width:6px; height:6px;
  border-radius:50%; background:var(--grad);
}
.blist.warn li:before{background:var(--amber);}
.blist.good li:before{background:var(--emerald);}

/* ── streamlit widgets ──────────────────────────────────────────────────── */
.stButton>button, .stDownloadButton>button{
  border-radius:12px; font-weight:700; font-size:14px; border:1px solid var(--line);
  background:#fff; color:var(--ink); padding:.55rem 1.1rem; transition:all .18s ease;
  box-shadow:var(--shadow-sm);
}
.stButton>button:hover, .stDownloadButton>button:hover{
  border-color:#C7C2F5; color:var(--indigo); transform:translateY(-1px); box-shadow:var(--shadow-md);
}
.stButton>button[kind="primary"]{
  background:var(--grad); color:#fff; border:none;
  box-shadow:0 8px 22px -8px rgba(79,70,229,.6);
}
.stButton>button[kind="primary"]:hover{
  color:#fff; transform:translateY(-2px); box-shadow:0 14px 30px -10px rgba(79,70,229,.68);
}
.stButton>button:disabled{opacity:.5; transform:none;}

[data-testid="stFileUploader"]{
  background:#FCFCFE; border:1.5px dashed #DDE1EA; border-radius:var(--r-md); padding:10px;
  transition:all .18s ease;
}
[data-testid="stFileUploader"]:hover{border-color:var(--indigo); background:rgba(79,70,229,.025);}
[data-testid="stFileUploader"] section{padding:.5rem;}
[data-testid="stFileUploader"] small{color:var(--faint);}

.stTextArea textarea, .stTextInput input{
  border-radius:var(--r-sm) !important; border:1px solid var(--line) !important;
  background:#fff !important; font-size:14px !important;
}
.stTextArea textarea:focus, .stTextInput input:focus{
  border-color:var(--indigo) !important; box-shadow:0 0 0 3px rgba(79,70,229,.12) !important;
}

.stTabs [data-baseweb="tab-list"]{
  gap:4px; background:#F7F8FB; padding:5px; border-radius:14px; border:1px solid var(--line);
}
.stTabs [data-baseweb="tab"]{
  height:38px; border-radius:10px; padding:0 18px; font-weight:600; font-size:13.5px;
  color:var(--muted); background:transparent;
}
.stTabs [aria-selected="true"]{
  background:#fff !important; color:var(--indigo) !important; box-shadow:var(--shadow-sm);
}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"]{display:none;}

[data-testid="stExpander"]{
  border:1px solid var(--line); border-radius:var(--r-md); background:#fff;
  box-shadow:var(--shadow-sm); overflow:hidden;
}
[data-testid="stExpander"] summary{font-weight:600; font-size:14px;}

[data-testid="stMetric"]{
  background:#fff; border:1px solid var(--line); border-radius:var(--r-md);
  padding:14px 16px; box-shadow:var(--shadow-sm);
}
[data-testid="stMetricValue"]{font-size:26px; font-weight:800; letter-spacing:-.02em;}
[data-testid="stMetricLabel"]{color:var(--faint); font-weight:600;}

[data-testid="stDataFrame"]{border:1px solid var(--line); border-radius:var(--r-md); overflow:hidden;}
.stProgress > div > div > div > div{background:var(--grad);}
[data-testid="stAlert"]{border-radius:var(--r-md); border:1px solid var(--line);}
code{background:#F5F6FA; color:#4338CA; border-radius:6px; padding:2px 6px; font-family:'JetBrains Mono',monospace; font-size:12.5px;}

/* ── misc ───────────────────────────────────────────────────────────────── */
.muted{color:var(--muted); font-size:13.5px;}
.tiny{color:var(--faint); font-size:11.5px;}
.section-h{
  display:flex; align-items:center;
  font-size:19px; font-weight:800; letter-spacing:-.02em; margin:6px 0 14px; color:var(--ink);
}
.section-h > .ico{color:var(--indigo);}

/* Inlined SVG icons: the wrapper fixes the box, the svg fills it and inherits
   `color`, so one asset serves every tint in the UI. */
.ico{
  display:inline-block; vertical-align:-.18em; line-height:0; flex:none;
}
.ico svg{width:100%; height:100%; display:block; fill:currentColor;}
.hero-eyebrow .ico, .hero-chip .ico{color:var(--indigo);}
.card-title .ico{color:inherit;}
.badge .ico{color:inherit;}

.empty{
  text-align:center; padding:64px 24px; border:1.5px dashed var(--line);
  border-radius:var(--r-lg); background:#FCFCFE;
}
.empty .empty-ico{margin-bottom:12px; line-height:0; color:var(--faint); opacity:.5;}
.empty h3{font-size:18px; margin:0 0 6px;}
.empty p{color:var(--muted); font-size:14px; margin:0 auto; max-width:440px;}
.status-line{
  display:flex; align-items:center; gap:8px; font-size:12.5px; font-weight:600;
  padding:9px 12px; border-radius:10px; border:1px solid var(--line); background:#FCFCFE;
}
.status-line .dot{width:8px; height:8px; border-radius:50%; flex:none;}
.dot-live{background:var(--emerald); box-shadow:0 0 0 3px rgba(5,150,105,.14); animation:pulse 2s infinite;}
.dot-off{background:var(--rose); box-shadow:0 0 0 3px rgba(225,29,72,.12);}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.45;}}
</style>
"""


def inject() -> None:
    """Load the design system. Call once, right after set_page_config."""
    st.markdown(CSS, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  Brand logo
# ─────────────────────────────────────────────────────────────────────────────
IMAGES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "images"
)

# Any of these may hold the brand mark — whichever exists first wins, so
# renaming the asset doesn't silently drop the logo.
_LOGO_NAMES = ("logo-primary.svg", "logo.svg", "favicon.svg", "logo-primary.png")


@st.cache_data(show_spinner=False)
def svg_data_uri(file_name: str) -> str:
    """
    An asset from images/ as an inline data URI, or "" if it is missing OR
    empty (a zero-byte placeholder must not render as a broken image).

    Inlined rather than linked so assets survive Streamlit's static file
    serving being disabled.
    """
    path = os.path.join(IMAGES_DIR, file_name)
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError:
        return ""
    if not raw.strip():
        return ""
    mime = "image/png" if file_name.lower().endswith(".png") else "image/svg+xml"
    return f"data:{mime};base64,{base64.b64encode(raw).decode('ascii')}"


# Semantic name → file in images/. Keeping the mapping here means the rest of
# the UI never hardcodes a filename, so assets can be renamed or swapped for
# custom artwork in one place.
ICONS = {
    "pipeline": "pipeline.svg",
    "engine": "engine.svg",
    "analyze": "analyze.svg",
    "key": "key.svg",
    "job-description": "job-description.svg",
    "resumes": "Resumes.svg",
    "failover": "failover.svg",
    "how-it-works": "How the pipeline works.svg",
    "document": "document.svg",
    "word": "word.svg",
    "csv": "csv.svg",
    "json": "json.svg",
    "export": "export.svg",
    "empty": "empty.svg",
    "ranking": "ranking.svg",
    "comparison": "comparison.svg",
    "structured": "structured.svg",
    "scale": "scale.svg",
    "technical": "technical.svg",
    "hr": "hr.svg",
    "check": "check.svg",
    "cross": "cross.svg",
    "plus": "plus.svg",
    "diamond": "diamond.svg",
}


@st.cache_data(show_spinner=False)
def _svg_markup(file_name: str) -> str:
    """Raw <svg> source from images/, or "" when missing or empty."""
    path = os.path.join(IMAGES_DIR, file_name)
    try:
        with open(path, encoding="utf-8") as handle:
            raw = handle.read()
    except OSError:
        return ""
    start = raw.find("<svg")
    if start == -1 or not raw.strip():
        return ""
    return raw[start:].strip()


def icon(name: str, size: int = 18, color: str = "", fallback: str = "") -> str:
    """
    An icon by semantic name ("ranking") or raw filename ("ranking.svg").

    The SVG is inlined rather than served through an <img>: an <img> renders the
    file as a separate document, so `fill="currentColor"` inside it resolves to
    black instead of the surrounding text colour. Inlining lets every icon take
    its tint from the element it sits in — green in the "Matching" heading, red
    in "Missing", indigo in a section title — with no per-colour asset.

    Only works inside st.markdown(..., unsafe_allow_html=True); Streamlit widget
    labels render plain text, so those use Material icons instead.
    """
    file_name = ICONS.get(name, name if name.lower().endswith((".svg", ".png")) else f"{name}.svg")

    if file_name.lower().endswith(".png"):
        uri = svg_data_uri(file_name)
        return (
            f'<img src="{uri}" alt="" style="width:{size}px;height:{size}px;'
            'object-fit:contain;vertical-align:-.18em;"/>'
            if uri else fallback
        )

    markup = _svg_markup(file_name)
    if not markup:
        return fallback

    tint = f"color:{color};" if color else ""
    return (
        f'<span class="ico" style="width:{size}px;height:{size}px;{tint}">{markup}</span>'
    )


def logo_data_uri() -> str:
    """The brand mark, whichever of the known filenames it currently lives under."""
    for name in _LOGO_NAMES:
        uri = svg_data_uri(name)
        if uri:
            return uri
    return ""


def brand_mark(size: int = 38) -> str:
    """Logo tile for the sidebar header — falls back to a gradient emoji tile."""
    uri = logo_data_uri()
    if uri:
        return (
            f'<div style="width:{size}px;height:{size}px;border-radius:12px;'
            f"background:#fff;border:1px solid var(--line);display:grid;"
            f'place-items:center;box-shadow:var(--shadow-sm);flex:none;">'
            f'<img src="{uri}" alt="logo" style="width:{int(size * .62)}px;height:auto;"/></div>'
        )
    return (
        f'<div style="width:{size}px;height:{size}px;border-radius:12px;'
        f"background:var(--grad);display:grid;place-items:center;"
        f'font-size:{int(size * .38)}px;font-weight:800;color:#fff;letter-spacing:-.02em;'
        f'box-shadow:0 8px 18px -8px rgba(79,70,229,.7);flex:none;">AI</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HTML builders
# ─────────────────────────────────────────────────────────────────────────────
def esc(text) -> str:
    return html.escape(str(text if text is not None else ""))


def score_colors(score: int) -> tuple[str, str]:
    """Ring gradient stops — green for strong, amber mid, rose weak."""
    if score >= 80:
        return "#059669", "#10B981"
    if score >= 60:
        return "#4F46E5", "#7C3AED"
    if score >= 40:
        return "#D97706", "#F59E0B"
    return "#E11D48", "#FB7185"


def ring(score: int, caption: str = "match") -> str:
    c1, c2 = score_colors(int(score))
    return (
        f'<div class="ring" style="--pct:{int(score)};--c1:{c1};--c2:{c2}">'
        f'<div class="inner"><div class="num">{int(score)}%</div>'
        f'<div class="cap">{esc(caption)}</div></div></div>'
    )


def badge(recommendation: str) -> str:
    rec = (recommendation or "Reject").strip()
    cls = {"Hire": "badge-hire", "Interview": "badge-interview"}.get(rec, "badge-reject")
    mark = {"Hire": "check", "Interview": "diamond"}.get(rec, "cross")
    return f'<span class="badge {cls}">{icon(mark, 14)} {esc(rec)}</span>'


def pills(items, kind: str = "neutral", empty: str = "—") -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return f'<span class="muted">{esc(empty)}</span>'
    return "".join(f'<span class="pill pill-{kind}">{esc(i)}</span>' for i in items)


def bar(label: str, value: int) -> str:
    value = max(0, min(100, int(value)))
    return (
        f'<div class="bar-row"><div class="bar-head"><span>{esc(label)}</span>'
        f'<span>{value}%</span></div><div class="bar"><i style="width:{value}%"></i></div></div>'
    )


def stat(label: str, value, sub: str = "") -> str:
    return (
        f'<div class="stat"><div class="lbl">{esc(label)}</div>'
        f'<div class="val">{esc(value)}</div>'
        + (f'<div class="sub">{esc(sub)}</div>' if sub else "")
        + "</div>"
    )


def stat_row(tiles: list[str]) -> str:
    return f'<div class="stat-row">{"".join(tiles)}</div>'


def bullet_list(items, tone: str = "") -> str:
    items = [str(i).strip().lstrip("•-–— ") for i in (items or []) if str(i).strip()]
    if not items:
        return '<span class="muted">Not provided.</span>'
    lis = "".join(f"<li>{esc(i)}</li>" for i in items)
    return f'<ul class="blist {tone}">{lis}</ul>'


def question_list(items) -> str:
    items = [str(i).strip() for i in (items or []) if str(i).strip()]
    if not items:
        return '<span class="muted">No questions generated.</span>'
    lis = "".join(f"<li>{esc(i)}</li>" for i in items)
    return f'<ol class="qlist">{lis}</ol>'


def empty_state(icon_name: str, title: str, body: str) -> str:
    return (
        f'<div class="empty"><div class="empty-ico">{icon(icon_name, 44)}</div>'
        f"<h3>{esc(title)}</h3><p>{esc(body)}</p></div>"
    )


def section_heading(icon_name: str, text: str) -> str:
    """Section title with a leading icon — used across the dashboard tabs."""
    return (
        f'<div class="section-h">{icon(icon_name, 19)}'
        f'<span style="margin-left:9px;">{esc(text)}</span></div>'
    )


def card(title: str, body_html: str) -> str:
    head = f'<div class="card-title"><span class="dot"></span>{esc(title)}</div>' if title else ""
    return f'<div class="card">{head}{body_html}</div>'
