from openai import OpenAI, OpenAIError
import streamlit as st

def verify_api_key(api_key: str) -> bool:
    """
    Try a tiny OpenAI call to verify the key.
    You can use models.list() since it's very cheap and simple.
    """
    try:
        client = OpenAI(api_key=api_key)
        # This will fail quickly if the key is invalid
        client.models.list()
        return True
    except OpenAIError:
        return False 
    
def init_session_state():
    if "page" not in st.session_state:
        st.session_state.page = "api_key"   # "api_key" or "ask_agent"
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "api_key_verified" not in st.session_state:
        st.session_state.api_key_verified = False

def page_api_key():
    st.subheader("Step 1: Enter your OpenAI API key")

    st.write(
        "This app uses **your own OpenAI API key**. "
        "The key is kept only in this Streamlit session and is not written to disk."
    )

    api_key_input = st.text_input(
        "OpenAI API key",
        type="password",
        value=st.session_state.api_key,
    )

    col1, col2 = st.columns(2)
    with col1:
        verify_clicked = st.button("Verify API key")
    with col2:
        clear_clicked = st.button("Clear")

    if clear_clicked:
        st.session_state.api_key = ""
        st.session_state.api_key_verified = False
        st.rerun()

    if verify_clicked:
        if not api_key_input:
            st.error("Please enter an API key.")
            return

        with st.spinner("Verifying your API key..."):
            ok = verify_api_key(api_key_input)

        if ok:
            st.session_state.api_key = api_key_input
            st.session_state.api_key_verified = True
            st.session_state.page = "ask_agent"
            st.success("API key verified! You can now ask questions.")
            st.rerun()
        else:
            st.error("API key is invalid. Please check and try again.")

def page_ask_agent():
    from agents import run_all_agents
    from helper import load_metadata_text

    st.subheader("Step 2: Ask the IRS SOI Migration Data Agent")

    st.write(
        "For example: *How many people under age 35 moved to Minnesota between 2012 and 2022?*"
    )

    user_prompt = st.text_area("Your Question", height=100)

    st.write("Optional: special instructions (e.g., focus on AGI classes, age bins, etc.)")
    focus = st.text_area("User Instruction", height=80)

    col1, col2 = st.columns(2)
    with col1:
        ask_clicked = st.button("Ask Agent")
    with col2:
        back_clicked = st.button("Back to API key setup")

    if back_clicked:
        # Let user switch key or reset
        st.session_state.page = "api_key"
        st.rerun()

    if ask_clicked:
        if not user_prompt.strip():
            st.error("Please enter a question.")
            return

        if not st.session_state.api_key:
            st.error("OpenAI API key missing. Please go back and enter it again.")
            return

        metadata_text = load_metadata_text()

        with st.spinner("Running agents..."):
            result = run_all_agents(
                original_prompt=user_prompt,
                metadata_text=metadata_text,
                focus=focus,
                OpenAI_API_key=st.session_state.api_key,
                verbose=False,
            )

        st.subheader("Answer")
        st.write(result.get("summary", result))

        figs = result.get("figures", [])
        for fig in figs:
            try:
                st.pyplot(fig)
            except Exception:
                pass

