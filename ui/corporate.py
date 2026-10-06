"""
One design for the whole app.

Inter with tabular figures, a neutral slate palette, navy as the single
accent, hairline tables without header bars, underline tabs, and compact
numbers (no cents above $1,000). Green and red only carry meaning: up or
down. Importing this module registers the "corporate" Plotly template and
makes it the default, so every chart picks it up.
"""
from __future__ import annotations

import html as _html

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

FONT = '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'
INK = "#0f172a"
INK_2 = "#334155"
MUTED = "#64748b"
FAINT = "#94a3b8"
RULE = "#e2e8f0"
HAIR = "#f1f5f9"
BG = "#f8fafc"
NAVY = "#0b2545"
ACCENT = "#1d4ed8"
POS = "#047857"
RED = "#b91c1c"
GOLD = "#b45309"
NAVY_ROW = HAIR  # kept for older imports
ROW_ALT = HAIR
# first colour is the baseline (dark), the rest are the alternatives
PALETTE = ["#0f172a", "#2563eb", "#0d9488", "#d97706", "#7c3aed", "#db2777", "#64748b"]

pio.templates["corporate"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, size=12, color=INK_2),
    title=dict(font=dict(family=FONT, size=14, color=INK, weight=600), x=0.01),
    colorway=PALETTE,
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    xaxis=dict(gridcolor=HAIR, zeroline=False, showline=False, ticks="", tickfont=dict(color=MUTED, size=11)),
    yaxis=dict(gridcolor=HAIR, zeroline=False, showline=False, ticks="", tickfont=dict(color=MUTED, size=11)),
    legend=dict(font=dict(size=12, color=INK_2)),
    hoverlabel=dict(font=dict(family=FONT, size=12), bgcolor="#ffffff", bordercolor=RULE),
))
pio.templates.default = "corporate"


def inject_css() -> None:
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
.stApp {{ background: {BG}; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stExpander"] summary, .stApp [data-baseweb="select"],
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stSidebarNav"] span {{
    font-family: {FONT} !important; font-feature-settings: "tnum" 1, "cv11" 1; letter-spacing: -0.003em; }}
.stApp p, .stApp li, .stApp label {{ font-size: 14px; line-height: 1.55; color: {INK_2}; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ font-family: {FONT} !important;
    font-weight: 600 !important; color: {INK} !important; letter-spacing: -0.015em; }}
.stApp h4 {{ font-size: 15px !important; margin: 26px 0 4px; }}
.stApp h5 {{ font-size: 14px !important; margin: 18px 0 2px; }}
[data-testid="stCaptionContainer"] p {{ color: {MUTED} !important; font-size: 13px !important; }}
[data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1440px; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ display: none; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ text-transform: uppercase; font-size: 11px !important;
    letter-spacing: 0.06em; color: {FAINT} !important; font-weight: 600; margin-top: 10px; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{ border: none; background: transparent;
    justify-content: flex-start; padding: 4px 8px; min-height: 0; border-radius: 6px; width: 100%; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {{ color: {INK_2}; font-size: 13.5px; text-align: left; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover {{ background: {HAIR}; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ border: none; background: transparent; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{ font-size: 13px; color: {MUTED}; }}

/* buttons and inputs */
.stApp [data-testid="stBaseButton-primary"] {{ background: {NAVY}; border: 1px solid {NAVY}; border-radius: 8px; }}
.stApp [data-testid="stBaseButton-primary"]:hover {{ background: #13315c; border-color: #13315c; }}
.stApp [data-testid="stBaseButton-primary"] p {{ color: #ffffff !important; font-weight: 500; }}
.stApp [data-testid="stBaseButton-primary"]:disabled {{ opacity: 0.35; }}
.stApp [data-testid="stBaseButton-secondary"] {{ border-radius: 8px; border-color: {RULE}; }}
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div, .stApp textarea {{ border-radius: 8px !important; }}
[data-testid="stExpander"] details {{ background: #fff; border: 1px solid {RULE}; border-radius: 10px; }}
[data-testid="stExpander"] summary p {{ font-weight: 500; color: {INK_2}; }}

/* tabs: segmented controls drawn as underline tabs */
[data-testid="stButtonGroup"] {{ margin: 6px 0 14px; }}
[data-testid="stButtonGroup"] > div {{ gap: 2px !important; flex-wrap: wrap; border-bottom: 1px solid {RULE}; }}
[data-testid="stButtonGroup"] button {{ background: transparent !important; border: none !important;
    border-radius: 0 !important; border-bottom: 2px solid transparent !important; padding: 8px 10px !important;
    min-height: 0 !important; margin-bottom: -1px; box-shadow: none !important; }}
[data-testid="stButtonGroup"] button p {{ color: {MUTED} !important; font-size: 13.5px !important; font-weight: 500 !important; }}
[data-testid="stButtonGroup"] button:hover p {{ color: {INK} !important; }}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] {{ border-bottom-color: {INK} !important; }}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p {{ color: {INK} !important; }}

/* cards */
.c-card {{ background: #fff; border: 1px solid {RULE}; border-radius: 12px; padding: 18px 20px 16px;
          margin-bottom: 18px; }}
.c-card h4 {{ font-family: {FONT}; font-size: 14px; font-weight: 600 !important; color: {INK};
             margin: 0 0 10px !important; padding: 0 !important; letter-spacing: -0.01em; }}
[data-testid="stPlotlyChart"] {{ background: #fff; border: 1px solid {RULE}; border-radius: 12px; padding: 6px 4px 0;
    overflow: hidden; margin-bottom: 4px; }}

/* tables: no header bar, hairlines, numbers right-aligned */
.c-scroll {{ overflow-x: auto; }}
table.c-t {{ font-family: {FONT}; border-collapse: collapse; width: 100%; font-size: 13.5px;
            white-space: nowrap; color: {INK}; margin: 0; font-feature-settings: "tnum" 1; }}
table.c-t th {{ background: transparent; color: {MUTED}; text-align: left; padding: 8px 12px; font-weight: 500;
               font-size: 12px; border: none; border-bottom: 1px solid {RULE}; white-space: normal; vertical-align: bottom;
               line-height: 1.3; min-width: 72px; }}
table.c-t td {{ padding: 9px 10px; border: none; border-bottom: 1px solid {HAIR}; font-weight: 400; color: {INK}; }}
table.c-t tr:last-child td {{ border-bottom: none; }}
table.c-t tbody tr:hover td {{ background: {BG}; }}
table.c-t td.num, table.c-t th.num {{ text-align: right; }}
table.c-t tr.c-total td {{ font-weight: 600; border-top: 1px solid {INK}; }}
table.c-t tr.c-section td {{ color: {MUTED} !important; font-weight: 600; font-size: 11.5px; text-transform: uppercase;
    letter-spacing: 0.05em; padding-top: 16px; background: transparent !important; }}
table.c-kv {{ white-space: normal; }}
table.c-kv td {{ padding: 7px 0; }}
table.c-kv td:first-child {{ color: {MUTED}; width: 58%; padding-right: 12px; }}
table.c-kv td:last-child {{ text-align: right; font-weight: 500; }}
.c-evtype {{ font-weight: 600; color: {INK}; margin: 16px 0 4px 0; font-size: 13px; }}

/* text and links */
.c-red, a.c-red, .stApp a.c-red {{ color: {INK} !important; font-weight: 500; text-decoration: none; }}
a.c-red {{ color: {ACCENT} !important; }}
a.c-red:hover {{ text-decoration: underline !important; }}
.c-pos {{ color: {POS}; }}
.c-neg {{ color: {RED}; }}
.c-hyp {{ color: {GOLD}; }}
.c-muted {{ font-family: {FONT}; color: {MUTED}; font-size: 14px; line-height: 1.55; }}
.c-title {{ font-family: {FONT}; color: {INK}; font-size: 26px; font-weight: 600; margin: 0 0 6px; letter-spacing: -0.02em; }}
.c-desc {{ font-family: {FONT}; color: {MUTED}; font-size: 14px; line-height: 1.6; max-width: 900px; margin-bottom: 18px; }}
.c-sub {{ font-family: {FONT}; color: {INK}; font-size: 16px; font-weight: 600; margin: 22px 0 12px; letter-spacing: -0.01em; }}
.c-statetitle {{ font-family: {FONT}; color: {INK}; font-weight: 600; font-size: 15px; margin: 4px 0 12px; }}
.c-statetitle a {{ color: {INK} !important; }}

/* metric tiles */
.c-tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0; margin: 4px 0 18px; background: #fff;
           border: 1px solid {RULE}; border-radius: 12px; overflow: hidden; }}
@media (min-width: 1500px) {{ .c-tiles {{ grid-template-columns: repeat(8, 1fr); }} }}
.c-tile {{ font-family: {FONT}; padding: 14px 16px 15px; min-width: 0; border-right: 1px solid {HAIR};
          border-bottom: 1px solid {HAIR}; }}
.c-tile .lbl {{ color: {MUTED}; font-size: 12px; line-height: 1.35; min-height: 32px; }}
.c-tile .val {{ color: {INK}; font-size: 21px; font-weight: 600; margin-top: 4px; letter-spacing: -0.02em;
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}

/* comparison headline cards */
.c-heads {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; margin: 4px 0 18px; }}
.c-head {{ font-family: {FONT}; background: #fff; border: 1px solid {RULE}; border-radius: 12px; padding: 16px 20px 18px; }}
.c-head .lbl {{ color: {MUTED}; font-size: 12.5px; }}
.c-head .lbl b {{ color: {INK}; font-weight: 600; }}
.c-head .val {{ font-size: 30px; font-weight: 600; letter-spacing: -0.025em; margin: 6px 0 2px; color: {INK}; }}
.c-head .val.pos {{ color: {POS}; }}
.c-head .val.neg {{ color: {RED}; }}
.c-head .sub {{ color: {MUTED}; font-size: 12.5px; }}
.c-pill {{ display: inline-block; font-size: 12px; font-weight: 600; padding: 2px 8px; border-radius: 999px; margin-left: 6px;
          vertical-align: middle; }}
.c-pill.pos {{ background: #ecfdf5; color: {POS}; }}
.c-pill.neg {{ background: #fef2f2; color: {RED}; }}
/* legacy summary box */
.c-summary {{ font-family: {FONT}; background: #fff; border: 1px solid {RULE}; border-radius: 12px;
             padding: 16px 20px; margin-bottom: 18px; font-size: 13px; color: {MUTED}; }}
.c-summary .val {{ font-size: 26px; font-weight: 600; color: {INK}; margin-top: 4px; }}
.c-summary .sub {{ color: {MUTED}; font-size: 12.5px; margin-top: 2px; }}
</style>
""", unsafe_allow_html=True)


# ── Formatting ────────────────────────────────────────────────────────

def esc(s) -> str:
    return _html.escape(str(s))


def money(v, dec: int | None = None) -> str:
    """$ with thousands separators. Cents only below $1,000 unless dec is given."""
    if v is None or not np.isfinite(v):
        return "–"
    if v == 0:
        return "$0"
    if dec is None:
        dec = 0 if abs(v) >= 1000 else 2
    s = f"${abs(v):,.{dec}f}"
    return f"−{s}" if v < 0 else s


def money_short(v) -> str:
    if v is None or not np.isfinite(v):
        return "–"
    a = abs(v)
    if a >= 1e9:
        s = f"${a / 1e9:,.2f}B"
    elif a >= 1e6:
        s = f"${a / 1e6:,.2f}M"
    elif a >= 1e4:
        s = f"${a / 1e3:,.0f}K"
    elif a >= 1e3:
        s = f"${a / 1e3:,.1f}K"
    else:
        s = f"${a:,.0f}"
    return f"−{s}" if v < 0 else s


def num(v, dec: int = 2) -> str:
    """Plain numbers: whole numbers without decimals, others with up to `dec` decimals."""
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return "–"
    v = float(v)
    if abs(v - round(v)) < 1e-9:
        return f"{round(v):,}"
    out = f"{v:,.{dec}f}".rstrip("0").rstrip(".")
    return out


def rate(v) -> str:
    """Fractions shown as percentages: 0.15 -> 15%, 0.053 -> 5.3%, 1/12 -> 8.33%."""
    if v is None or not np.isfinite(v):
        return "–"
    x = float(v) * 100.0
    if abs(x - round(x)) < 1e-9:
        return f"{round(x):,}%"
    return f"{x:,.2f}".rstrip("0").rstrip(".") + "%"


def pct(v, dec: int = 1) -> str:
    return "–" if v is None or not np.isfinite(v) else f"{v:,.{dec}f}%"


def days(v) -> str:
    if v is None or (isinstance(v, float) and not np.isfinite(v)) or v < 0:
        return "Never"
    return f"{int(round(v)):,} days"


def signed(v, fmt=money, lower_is_better: bool | None = False) -> str:
    """+/- value coloured green when the change is good, red when it is bad. None = no colour."""
    if v is None or not np.isfinite(v):
        return "–"
    good = (v < 0) if lower_is_better else (v > 0)
    cls = "" if (v == 0 or lower_is_better is None) else ("c-pos" if good else "c-neg")
    txt = fmt(v)
    if v > 0:
        txt = "+" + txt
    return f'<span class="{cls}">{txt}</span>'


def red(s) -> str:
    return f'<span class="c-red">{esc(s)}</span>'


# ── Building blocks ───────────────────────────────────────────────────

def table(headers: list, rows: list, num_cols=frozenset(), kv: bool = False, row_classes: list | None = None) -> str:
    th = "".join(f'<th class="num">{esc(h)}</th>' if i in num_cols else f"<th>{esc(h)}</th>"
                 for i, h in enumerate(headers)) if headers else ""
    body = []
    for ri, r in enumerate(rows):
        tds = "".join(f'<td class="num">{c}</td>' if i in num_cols else f"<td>{c}</td>" for i, c in enumerate(r))
        cls = f' class="{row_classes[ri]}"' if row_classes and row_classes[ri] else ""
        body.append(f"<tr{cls}>{tds}</tr>")
    cls = "c-t c-kv" if kv else "c-t"
    head = f"<thead><tr>{th}</tr></thead>" if th else ""
    return f'<div class="c-scroll"><table class="{cls}">{head}<tbody>{"".join(body)}</tbody></table></div>'


def card(title: str, inner_html: str, target=None) -> None:
    (target or st).markdown(f'<div class="c-card"><h4>{esc(title)}</h4>{inner_html}</div>', unsafe_allow_html=True)


def page_title(title: str, description: str = "") -> None:
    st.markdown(f'<div class="c-title">{esc(title)}</div>', unsafe_allow_html=True)
    if description:
        st.markdown(f'<div class="c-desc">{esc(description)}</div>', unsafe_allow_html=True)


def subtitle(text: str) -> None:
    st.markdown(f'<div class="c-sub">{esc(text)}</div>', unsafe_allow_html=True)


def chart(fig: go.Figure, title: str, height: int = 360, ytitle: str = "", money_axis: bool = False,
          key: str | None = None, xtitle: str = "Days", zero: bool = False) -> None:
    # Legend sits in its own band under the title; the band grows with the number of legend rows,
    # so long or many labels never run over the title or the plot.
    for tr in fig.data:
        if isinstance(tr, go.Scatter) and tr.line is not None and tr.line.width and tr.line.width > 2:
            tr.line.width = 2
    names = [t.name for t in fig.data if t.name and t.showlegend is not False]
    rows = 0
    if len(names) > 1:
        rows, used = 1, 0
        for n in names:
            w = len(n) * 7 + 50
            if used and used + w > 900:
                rows, used = rows + 1, 0
            used += w
    title_px, row_px = 44, 20
    top = title_px + rows * row_px + 10
    height = height + rows * row_px
    fig.update_layout(
        template="corporate", height=height,
        title=dict(text=title, y=1 - 16 / height, yanchor="top", yref="container", x=0, xanchor="left", pad=dict(l=14)),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        margin=dict(l=64, r=20, t=top, b=56), hovermode="x unified",
        showlegend=rows > 0,
        legend=dict(orientation="h", yref="container", yanchor="top", y=1 - title_px / height, x=0.0, xanchor="left",
                    font=dict(size=12, color=INK_2), itemwidth=30, bgcolor="rgba(0,0,0,0)") if rows else dict(),
        xaxis=dict(title=dict(text=xtitle, font=dict(size=11, color=FAINT)), gridcolor=HAIR, automargin=True,
                   showline=False, zeroline=False),
        yaxis=dict(title=None if money_axis else (ytitle or None), tickprefix="$" if money_axis else "",
                   gridcolor=HAIR, automargin=True, separatethousands=True, zeroline=False, tickformat="~s",
                   **({"rangemode": "tozero"} if zero else {})),
    )
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False})
