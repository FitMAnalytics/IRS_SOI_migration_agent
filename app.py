import streamlit as st
from stpages import verify_api_key, init_session_state, page_api_key, page_ask_agent

def main():
    st.set_page_config(page_title="IRS SOI Migration Data Agent", layout="wide")
    init_session_state()

    st.title("IRS SOI Migration Data Agent")

    # Simple page router
    if not st.session_state.api_key_verified:
        st.session_state.page = "api_key"

    if st.session_state.page == "api_key":
        page_api_key()
    elif st.session_state.page == "ask_agent":
        page_ask_agent()
    else:
        # Fallback
        st.session_state.page = "api_key"
        page_api_key()
    

if __name__ == "__main__":
    main()
