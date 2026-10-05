"""
One design for the whole app: plain corporate admin styling.

Helvetica at 14px, regular weight body, medium-weight headings, navy table
headers with alternating navy rows, red titles, white cards with a thin
border. Importing this module registers the "corporate" Plotly template and
makes it the default, so every chart in the app picks it up.
"""
from __future__ import annotations

import html as _html

import numpy as np
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

FONT = '"Helvetica Neue", Helvetica, Arial, sans-serif'
INK = "#212529"
MUTED = "#6c757d"
RULE = "#dee2e6"
NAVY = "#0b2545"
NAVY_ROW = "#13315c"
ROW_ALT = "#f3f5f8"  # alternating table rows (was navy with white text)
RED = "#c8102e"
GOLD = "#d4a017"
BG = "#f4f5f7"
PALETTE = [GOLD, NAVY, RED, "#2a7d4f", "#1f6fb2", "#6c757d", "#5b4b8a"]

pio.templates["corporate"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, size=12, color=INK),
    title=dict(font=dict(family=FONT, size=17, color=INK, weight=400), x=0.01),
    colorway=PALETTE,
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    xaxis=dict(gridcolor="#eceff3", zeroline=False, linecolor=RULE, ticks="outside", tickcolor=RULE),
    yaxis=dict(gridcolor="#eceff3", zerolinecolor="#c9ced6", linecolor=RULE),
    legend=dict(font=dict(size=12)),
    hoverlabel=dict(font=dict(family=FONT)),
))
pio.templates.default = "corporate"


def inject_css() -> None:
    st.markdown(f"""
<style>
.stApp {{ background: {BG}; }}
.stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"],
.stApp [data-testid="stExpander"] summary, .stApp [data-baseweb="select"],
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stSidebarNav"] span {{
    font-family: {FONT} !important; letter-spacing: 0; }}
.stApp p, .stApp li, .stApp label {{ font-size: 14px; line-height: 1.5; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ font-family: {FONT} !important;
    font-weight: 500 !important; color: {INK} !important; letter-spacing: 0; }}
.stApp h1 {{ font-size: 28px !important; }}
.stApp h2 {{ font-size: 24px !important; }}
.stApp h3 {{ font-size: 20px !important; }}
.stApp h4 {{ font-size: 18px !important; margin: 18px 0 6px; }}
[data-testid="stCaptionContainer"] p {{ color: {MUTED} !important; font-size: 13px !important; }}
[data-testid="stMetricValue"] {{ font-size: 22px !important; font-weight: 400 !important; color: {INK}; }}
[data-testid="stMetricLabel"] p {{ font-size: 13px !important; color: {MUTED} !important; }}
[data-testid="stToolbar"], [data-testid="stDecoration"] {{ display: none; }}
.c-evtype {{ font-weight: 500; color: #0b2545; margin: 14px 0 6px 0; font-size: 0.95rem; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ display: none; }}
.stApp input {{ font-variant-numeric: tabular-nums; }}
[data-testid="stSidebar"] {{ background: #ffffff; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{ border: none; background: transparent;
    justify-content: flex-start; padding: 2px 6px; min-height: 0; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {{ color: {RED}; font-size: 14px; text-align: left; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"]:hover p {{ text-decoration: underline; }}
.block-container {{ padding-top: 2rem; max-width: 100%; }}
[data-testid="stExpander"] details {{ background: #fff; border: 1px solid {RULE}; border-radius: 4px; }}
[data-testid="stMetric"] {{ background: #fff; border: 1px solid {RULE}; border-radius: 4px; padding: 10px 14px; }}

.c-card {{ background: #fff; border: 1px solid {RULE}; border-radius: 4px; padding: 16px 18px 18px;
          margin-bottom: 20px; }}
.c-card h4 {{ font-family: {FONT}; font-size: 20px; font-weight: 500 !important; color: {INK};
             margin: 0 0 12px !important; padding: 0 !important; }}
.c-scroll {{ overflow-x: auto; }}
table.c-t {{ font-family: {FONT}; border-collapse: collapse; width: 100%; font-size: 14px;
            white-space: nowrap; color: {INK}; margin: 0; }}
table.c-t th {{ background: {NAVY}; color: #fff; text-align: left; padding: 9px 12px; font-weight: 500;
               font-size: 13.5px; border: none; }}
table.c-t td {{ padding: 8px 12px; border: none; border-top: 1px solid {RULE}; font-weight: 400; color: {INK}; }}
table.c-t tr:nth-child(even) td {{ background: {ROW_ALT}; }}
table.c-t tr:hover td {{ background: #e8edf5; }}
table.c-t td.num, table.c-t th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
table.c-t tr.c-total td {{ font-weight: 500; border-top: 2px solid {INK}; }}
table.c-t tr.c-section td {{ background: #e9ecef !important; color: {INK} !important; font-weight: 500; }}
table.c-kv {{ white-space: normal; }}
table.c-kv td:first-child {{ font-weight: 500; width: 46%; }}
.c-red, a.c-red, .stApp a.c-red {{ color: {RED} !important; font-weight: 400; text-decoration: none; }}
a.c-red:hover {{ text-decoration: underline !important; }}
.c-pos {{ color: #2a7d4f; }}
.c-neg {{ color: {RED}; }}
.c-muted {{ font-family: {FONT}; color: {MUTED}; font-size: 14px; }}
.c-title {{ font-family: {FONT}; color: {INK}; font-size: 28px; font-weight: 500; margin: 0 0 4px; }}
.c-sub {{ font-family: {FONT}; color: {INK}; font-size: 22px; font-weight: 500; margin: 12px 0 12px; }}
.c-statetitle {{ font-family: {FONT}; color: {RED}; font-weight: 400; font-size: 18px; margin: 4px 0 12px; }}
.c-summary {{ font-family: {FONT}; background: #fff; border: 1px solid {RULE}; border-left: 4px solid {NAVY};
             border-radius: 4px; padding: 14px 18px; margin-bottom: 20px; font-size: 14px; color: {INK}; }}
.c-summary .val {{ font-size: 24px; font-weight: 500; color: {INK}; margin-top: 2px; }}
.c-summary .sub {{ color: {MUTED}; font-size: 13px; margin-top: 2px; }}
.c-tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; margin: 4px 0 18px; }}
@media (min-width: 1500px) {{ .c-tiles {{ grid-template-columns: repeat(8, 1fr); }} }}
.c-tile {{ font-family: {FONT}; background: #fff; border: 1px solid {RULE}; border-top: 3px solid {NAVY};
          border-radius: 4px; padding: 10px 12px 12px; min-width: 0; }}
.c-tile .lbl {{ color: {MUTED}; font-size: 12.5px; line-height: 1.3; min-height: 32px; }}
.c-tile .val {{ color: {INK}; font-size: 20px; font-weight: 500; margin-top: 4px; font-variant-numeric: tabular-nums;
               white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.c-hyp {{ color: {RED}; }}
[data-testid="stButtonGroup"] {{ margin: 2px 0 8px; }}
[data-testid="stButtonGroup"] button {{ border-radius: 4px !important; font-family: {FONT} !important;
    border: 1px solid {RULE} !important; background: #fff; }}
[data-testid="stButtonGroup"] button p {{ color: {INK} !important; font-size: 14px !important; }}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] {{
    background: {NAVY} !important; border-color: {NAVY} !important; }}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p {{ color: #fff !important; }}
</style>
""", unsafe_allow_html=True)


# ── Formatting ────────────────────────────────────────────────────────

def esc(s) -> str:
    return _html.escape(str(s))


def money(v, dec: int = 2) -> str:
    if v is None or not np.isfinite(v):
        return "–"
    s = f"${abs(v):,.{dec}f}"
    return f"-{s}" if v < 0 else s


def money_short(v) -> str:
    if v is None or not np.isfinite(v):
        return "–"
    a = abs(v)
    s = f"${a / 1e6:,.1f}M" if a >= 1e6 else (f"${a / 1e3:,.0f}K" if a >= 1e3 else f"${a:,.0f}")
    return f"-{s}" if v < 0 else s


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


def signed(v, fmt=money) -> str:
    if v is None or not np.isfinite(v):
        return "–"
    cls = "c-pos" if v > 0 else ("c-neg" if v < 0 else "")
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
        st.markdown(f'<div class="c-muted">{esc(description)}</div>', unsafe_allow_html=True)
    st.write("")


def subtitle(text: str) -> None:
    st.markdown(f'<div class="c-sub">{esc(text)}</div>', unsafe_allow_html=True)


def chart(fig: go.Figure, title: str, height: int = 360, ytitle: str = "", money_axis: bool = False,
          key: str | None = None, xtitle: str = "Days", zero: bool = False) -> None:
    # Legend sits in its own band under the title; the band grows with the number of legend rows,
    # so long or many labels never run over the title or the plot.
    names = [t.name for t in fig.data if t.name and t.showlegend is not False]
    rows = 0
    if len(names) > 1:
        rows, used = 1, 0
        for n in names:
            w = len(n) * 7 + 60
            if used and used + w > 1000:
                rows, used = rows + 1, 0
            used += w
    title_px, row_px = 40, 22
    top = title_px + rows * row_px + 6
    height = height + rows * row_px
    fig.update_layout(
        template="corporate", height=height,
        title=dict(text=title, y=1 - 12 / height, yanchor="top", yref="container", x=0, xanchor="left", pad=dict(l=8)),
        paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
        margin=dict(l=70, r=24, t=top, b=50), hovermode="x unified",
        showlegend=rows > 0,
        legend=dict(orientation="h", yref="container", yanchor="top", y=1 - title_px / height, x=0,
) if rows else dict(),
        xaxis=dict(title=xtitle, gridcolor="#eceff3", automargin=True),
        yaxis=dict(title=None if money_axis else ytitle, tickprefix="$" if money_axis else "",
                   gridcolor="#eceff3", automargin=True, separatethousands=True,
                   **({"rangemode": "tozero"} if zero else {})),
    )
    st.plotly_chart(fig, theme=None, key=key)
