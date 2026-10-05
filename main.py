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

nav = st.navigation([st.Page("states_app.py", title="Model", default=True)])
nav.run()
