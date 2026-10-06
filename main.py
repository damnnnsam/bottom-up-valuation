"""
Bottom-up valuation: value a business from its marketing metrics.

    streamlit run main.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import streamlit as st

st.set_page_config(page_title="Bottom-up valuation", layout="wide", initial_sidebar_state="expanded")

from ui.corporate import inject_css  # registers the chart template

inject_css()


def _gate() -> None:
    """Share links (?share=1) are open. Everything else needs the password from APP_PASSWORD, if one is set."""
    pw = os.environ.get("APP_PASSWORD", "")
    if not pw or st.query_params.get("share") == "1" or st.session_state.get("_authed"):
        return
    st.markdown('<div style="max-width:360px;margin:12vh auto 0"><h3 style="margin-bottom:4px">Sign in</h3>'
                '<p style="color:#64748b;font-size:14px">This model is private. Share links open without a password.</p></div>',
                unsafe_allow_html=True)
    _, c, _ = st.columns([1, 1.2, 1])
    with c.form("login", border=False):
        given = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        if st.form_submit_button("Open", type="primary") and given == pw:
            st.session_state["_authed"] = True
            st.rerun()
        elif given and given != pw:
            st.error("Wrong password.")
    st.stop()


_gate()

nav = st.navigation([st.Page("states_app.py", title="Model", default=True)])
nav.run()
