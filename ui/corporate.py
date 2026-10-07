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

FONT = 'Helvetica, Arial, sans-serif'
INK = "#000000"
INK_2 = "#222222"
MUTED = "#555555"
FAINT = "#777777"
RULE = "#c8c8c8"
HAIR = "#e4e4e4"
BG = "#ffffff"
NAVY = "#0b2545"
ACCENT = "#0000ee"
POS = "#1a7f37"
RED = "#b00020"
GOLD = "#c9a227"
NAVY_ROW = "#13315c"
ROW_ALT = "#ffffff"
# baseline first (gold, as in the original tool), then navy, then plain colours
PALETTE = [GOLD, NAVY, "#4a5a6a", "#8a1c1c", "#2b6f3a", "#6b4f9a", "#000000"]

pio.templates["corporate"] = go.layout.Template(layout=go.Layout(
    font=dict(family=FONT, size=12, color=INK),
    title=dict(font=dict(family=FONT, size=15, color=INK, weight=700), x=0.0),
    colorway=PALETTE,
    paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
    xaxis=dict(gridcolor="#dddddd", zeroline=False, showline=True, linecolor="#888888", ticks="outside",
               tickcolor="#888888", tickfont=dict(color=INK, size=11)),
    yaxis=dict(gridcolor="#dddddd", zeroline=False, showline=True, linecolor="#888888", ticks="outside",
               tickcolor="#888888", tickfont=dict(color=INK, size=11)),
    legend=dict(font=dict(size=12, color=INK)),
    hoverlabel=dict(font=dict(family=FONT, size=12), bgcolor=NAVY, font_color="#ffffff", bordercolor=NAVY),
))
pio.templates.default = "corporate"


def inject_css() -> None:
    st.markdown(f"""
<style>
.stApp {{ background: #ffffff; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp input, .stApp textarea, .stApp button, .stApp td, .stApp th,
.stApp [data-testid="stMarkdownContainer"], .stApp [data-testid="stWidgetLabel"],
.stApp [data-testid="stExpander"] summary, .stApp [data-baseweb="select"],
.stApp [data-testid="stCaptionContainer"], .stApp [data-testid="stSidebarNav"] span {{
    font-family: {FONT} !important; letter-spacing: 0; }}
.stApp p, .stApp li, .stApp label {{ font-size: 13px; line-height: 1.45; color: {INK}; }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ font-family: {FONT} !important; font-weight: 700 !important;
    color: {INK} !important; letter-spacing: 0; }}
.stApp h4 {{ font-size: 15px !important; margin: 22px 0 4px; }}
.stApp h5 {{ font-size: 13px !important; margin: 14px 0 2px; }}
[data-testid="stCaptionContainer"] p {{ color: {MUTED} !important; font-size: 12px !important; }}
[data-testid="stToolbar"], [data-testid="stDecoration"], [data-testid="stHeaderActionElements"] {{ display: none; }}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{ padding-top: 1.6rem; padding-bottom: 3rem; max-width: 100%; }}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {{ display: none; }}

/* sidebar */
[data-testid="stSidebar"] {{ background: #f4f4f4; border-right: 1px solid {RULE}; }}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {{ font-size: 12px !important; color: {INK} !important;
    font-weight: 700; margin-top: 10px; }}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stCaptionContainer"] p {{ font-weight: 400;
    color: {MUTED} !important; line-height: 1.45; margin-top: 0; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] {{ border: none; background: transparent;
    justify-content: flex-start; padding: 1px 4px; min-height: 0; border-radius: 0; width: 100%; }}
[data-testid="stSidebar"] [data-testid="stBaseButton-secondary"] p {{ color: {ACCENT}; font-size: 13px; text-align: left;
    text-decoration: underline; }}
[data-testid="stSidebar"] [data-testid="stExpander"] details {{ border: 1px solid {RULE}; border-radius: 0; background: #fff; }}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {{ font-size: 13px; color: {INK}; font-weight: 700; }}

/* buttons and inputs: square, plain */
.stApp [data-testid="stBaseButton-primary"] {{ background: {NAVY}; border: 1px solid {NAVY}; border-radius: 0; }}
.stApp [data-testid="stBaseButton-primary"]:hover {{ background: #13315c; border-color: #13315c; }}
.stApp [data-testid="stBaseButton-primary"] p {{ color: #ffffff !important; }}
.stApp [data-testid="stBaseButton-primary"]:disabled {{ opacity: 0.35; }}
.stApp [data-testid="stBaseButton-secondary"] {{ border-radius: 0; border-color: {RULE}; }}
.stApp [data-baseweb="input"], .stApp [data-baseweb="select"] > div, .stApp textarea {{ border-radius: 0 !important; }}
[data-testid="stExpander"] details {{ background: #fff; border: 1px solid {RULE}; border-radius: 0; }}
[data-testid="stExpander"] summary p {{ font-weight: 700; color: {INK}; }}

/* section switches: plain links */
[data-testid="stButtonGroup"] {{ margin: 4px 0 10px; }}
[data-testid="stButtonGroup"] > div {{ gap: 14px !important; flex-wrap: wrap; }}
[data-testid="stButtonGroup"] button {{ background: transparent !important; border: none !important; border-radius: 0 !important;
    padding: 2px 0 !important; min-height: 0 !important; box-shadow: none !important; }}
[data-testid="stButtonGroup"] button p {{ color: {ACCENT} !important; font-size: 13px !important; text-decoration: underline; }}
[data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p {{ color: {INK} !important; font-weight: 700;
    text-decoration: none; }}

/* sections, not cards */
.c-card {{ background: transparent; border: none; border-radius: 0; padding: 0; margin: 0 0 22px; }}
.c-card h4 {{ font-family: {FONT}; font-size: 15px; font-weight: 700 !important; color: {INK}; margin: 0 0 6px !important;
             padding: 0 !important; }}
[data-testid="stPlotlyChart"] {{ background: transparent; border: none; border-radius: 0; padding: 0; margin-bottom: 8px; }}

/* tables: bordered, navy header, dense */
.c-scroll {{ overflow-x: auto; }}
table.c-t {{ font-family: {FONT}; border-collapse: collapse; width: auto; min-width: 50%; font-size: 13px;
            white-space: nowrap; color: {INK}; margin: 0; }}
table.c-t th {{ background: {NAVY}; color: #fff; text-align: left; padding: 5px 9px; font-weight: 700; font-size: 12px;
               border: 1px solid {NAVY}; white-space: nowrap; vertical-align: bottom; }}
table.c-t td {{ padding: 4px 9px; border: 1px solid {RULE}; font-weight: 400; color: {INK}; }}
table.c-t td.num, table.c-t th.num {{ text-align: right; }}
table.c-t tr.c-total td {{ font-weight: 700; }}
table.c-t tr.c-section td {{ background: #eeeeee; font-weight: 700; }}
table.c-kv {{ white-space: normal; }}
table.c-kv td:first-child {{ font-weight: 700; width: 55%; }}
table.c-kv td:last-child {{ text-align: left; }}
table.c-kv {{ width: 100%; }}
.c-evtype {{ font-weight: 700; color: {INK}; margin: 12px 0 4px 0; font-size: 13px; }}

/* text and links */
span.c-red {{ color: {INK}; font-weight: 700; }}
a.c-red, .stApp a.c-red {{ color: {ACCENT} !important; font-weight: 400; text-decoration: underline; }}
.c-pos {{ color: {INK}; }}
.c-neg {{ color: {RED}; }}
.c-hyp {{ color: {RED}; }}
.c-muted {{ font-family: {FONT}; color: {MUTED}; font-size: 13px; line-height: 1.45; }}
.c-title {{ font-family: {FONT}; color: {INK}; font-size: 22px; font-weight: 700; margin: 0 0 4px; }}
.c-desc {{ font-family: {FONT}; color: {INK}; font-size: 13px; line-height: 1.5; max-width: 980px; margin-bottom: 14px; }}
.c-sub {{ font-family: {FONT}; color: {INK}; font-size: 16px; font-weight: 700; margin: 24px 0 8px; border-bottom: 1px solid {INK};
         padding-bottom: 3px; }}
.c-statetitle {{ font-family: {FONT}; color: {INK}; font-weight: 700; font-size: 14px; margin: 4px 0 8px; }}
.c-statetitle a {{ color: {ACCENT} !important; }}

/* metric strips: plain key-value tables */
.c-tiles {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 0 28px; margin: 4px 0 14px; }}
.c-tile {{ font-family: {FONT}; display: flex; justify-content: space-between; gap: 10px; padding: 3px 0;
          border-bottom: 1px solid {HAIR}; min-width: 0; }}
.c-tile .lbl {{ color: {INK}; font-size: 13px; }}
.c-tile .val {{ color: {INK}; font-size: 13px; font-weight: 700; white-space: nowrap; }}
.c-heads {{ margin: 4px 0 14px; }}
.c-head {{ font-family: {FONT}; font-size: 13px; padding: 2px 0; }}
.c-head .lbl {{ display: inline; color: {INK}; }}
.c-head .lbl b {{ font-weight: 700; }}
.c-head .val {{ display: inline; font-size: 13px; font-weight: 700; margin: 0 6px; color: {INK}; }}
.c-head .val.neg {{ color: {RED}; }}
.c-head .sub {{ display: inline; color: {MUTED}; font-size: 13px; }}
.c-pill {{ display: inline; font-size: 13px; font-weight: 400; padding: 0; margin-left: 4px; }}
.c-pill.pos {{ color: {INK}; }}
.c-pill.neg {{ color: {RED}; }}
.c-summary {{ font-family: {FONT}; font-size: 13px; color: {INK}; margin-bottom: 14px; }}
.c-summary .val {{ font-size: 13px; font-weight: 700; display: inline; margin: 0 6px; }}
.c-summary .sub {{ display: inline; color: {MUTED}; }}

.c-ask {{ font-family: {FONT}; font-size: 12.5px; line-height: 1.5; color: {MUTED}; margin: 0 0 8px; }}
/* navigation */
.c-nav {{ display: block; font-family: {FONT}; font-size: 13px; color: {ACCENT}; text-decoration: underline; line-height: 1.5;
         margin: 1px 0; }}
.c-crumbs {{ display: flex; justify-content: space-between; align-items: baseline; gap: 16px; flex-wrap: wrap;
            font-family: {FONT}; font-size: 13px; margin: -6px 0 14px; padding-bottom: 8px; border-bottom: 1px solid {RULE}; }}
.c-crumbs a {{ color: {ACCENT}; text-decoration: underline; }}
.c-crumbs .sep {{ color: {FAINT}; margin: 0 2px; }}
.c-crumbs .cur {{ color: {INK}; }}
.c-crumbs .modes a, .c-crumbs .modes .on {{ margin-left: 14px; }}
.c-crumbs .modes .on {{ color: {INK}; font-weight: 700; }}
/* graph shortcuts */
.c-shortcuts {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 4px 22px; margin: 6px 0 16px; }}
.c-sc-title {{ font-size: 12px; color: {INK}; font-weight: 700; margin: 6px 0 2px; }}
.c-shortcuts a {{ display: block; font-size: 13px; color: {ACCENT}; text-decoration: underline; line-height: 1.5; }}
.c-anchor {{ position: relative; top: -60px; height: 0; }}
/* sticky variant: one column, stays in view while the graphs scroll */
.c-shortcuts.c-sticky {{ display: block; position: sticky; top: 8px; max-height: calc(100vh - 24px); overflow-y: auto;
    margin: 0; padding-right: 6px; }}
.c-shortcuts.c-sticky .c-sc-head {{ font-size: 15px; font-weight: 700; color: {INK}; margin: 0 0 6px; }}
.c-shortcuts.c-sticky .c-sc-title {{ margin-top: 10px; }}
.c-shortcuts.c-sticky a {{ font-size: 12.5px; line-height: 1.4; margin-bottom: 3px; }}
[data-testid="stColumn"]:has(> div > div > div > .c-shortcuts.c-sticky),
[data-testid="stColumn"]:has(.c-shortcuts.c-sticky) {{ align-self: flex-start; position: sticky; top: 0; }}
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
    head = f"<h4>{esc(title)}</h4>" if title else ""
    (target or st).markdown(f'<div class="c-card">{head}{inner_html}</div>', unsafe_allow_html=True)


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
    is_pct = bool(fig.layout.yaxis.ticksuffix == "%")
    for tr in fig.data:
        if isinstance(tr, go.Scatter) and tr.line is not None and tr.line.width and tr.line.width > 2:
            tr.line.width = 2
        if getattr(tr, "hovertemplate", None) in (None, ""):
            # plain numbers on hover: $1,234,567 / 173.64 / 12.3%, never "173.636m" (SI milli)
            if money_axis and tr.y is not None:
                # "-$61,095", not "$-61,095": the label is prepared per point
                y = np.asarray(tr.y, dtype=float)
                tr.customdata = [("-$" if v < 0 else "$") + f"{abs(v):,.0f}" for v in y]
                tr.hovertemplate = "%{fullData.name}: %{customdata}<extra></extra>"
            else:
                fmt = "%{y:,.1f}%" if is_pct else "%{y:,.2f}"
                tr.hovertemplate = f"%{{fullData.name}}: {fmt}<extra></extra>"
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
                   showline=False, zeroline=False, hoverformat=","),
        yaxis=dict(title=None if money_axis else (ytitle or None), tickprefix="$" if money_axis else "",
                   gridcolor=HAIR, automargin=True, separatethousands=True, zeroline=False, tickformat="~s" if money_axis else ",~r",
                   **({"rangemode": "tozero"} if zero else {})),
    )
    st.plotly_chart(fig, theme=None, key=key, config={"displayModeBar": False})
