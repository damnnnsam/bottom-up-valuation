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


def _guest_passwords() -> dict:
    """CLIENT_PASSWORDS="gleap:abc,axisbrands:def" gives each client its own login."""
    out = {}
    for part in os.environ.get("CLIENT_PASSWORDS", "").split(","):
        if ":" in part:
            slug, pw = part.split(":", 1)
            out[slug.strip()] = pw.strip()
    return out


def _gate() -> None:
    """Share links (?share=1) are open. Otherwise: the admin password opens everything; a client password
    opens that client only (st.session_state["_scope"])."""
    admin = os.environ.get("APP_PASSWORD", "")
    guests = _guest_passwords()
    if (not admin and not guests) or st.query_params.get("share") == "1" or st.session_state.get("_authed"):
        return
    st.markdown('<div style="max-width:360px;margin:12vh auto 0"><h3 style="margin-bottom:4px">Sign in</h3>'
                '<p style="color:#555;font-size:13px">Enter the password you were given.</p></div>', unsafe_allow_html=True)
    _, c, _ = st.columns([1, 1.2, 1])
    with c.form("login", border=False):
        given = st.text_input("Password", type="password", label_visibility="collapsed", placeholder="Password")
        if st.form_submit_button("Open", type="primary"):
            if admin and given == admin:
                st.session_state["_authed"] = True
                st.session_state["_scope"] = None
                st.rerun()
            for slug, pw in guests.items():
                if pw and given == pw:
                    st.session_state["_authed"] = True
                    st.session_state["_scope"] = slug
                    st.query_params.clear()
                    st.query_params["client"] = slug
                    st.rerun()
            if given:
                st.error("Wrong password.")
    st.stop()


_gate()

nav = st.navigation([st.Page("states_app.py", title="Model", default=True)])
nav.run()
