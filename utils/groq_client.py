"""
Groq Client Initialization
"""

import streamlit as st
from groq import Groq

@st.cache_resource
def init_groq_client(api_key):
    """Initialize and cache Groq client"""
    return Groq(api_key=api_key)