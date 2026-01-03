from openai import OpenAI, OpenAIError
import streamlit as st

def verify_api_key(api_key: str) -> bool:
    """
    Try a cheap OpenAI call to verify the key.
    """
    try:
        client = OpenAI(api_key=api_key)
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

    # Conversation state
    if "conversation_history" not in st.session_state:
        st.session_state.conversation_history = []  # List of message dicts

    # Persistent data environment across queries
    if "shared_env" not in st.session_state:
        st.session_state.shared_env = {}  # DataFrame storage

    # Persistent metadata across queries
    if "shared_meta" not in st.session_state:
        st.session_state.shared_meta = {}  # Metadata storage

    # All figures from conversation
    if "all_conversation_figures" not in st.session_state:
        st.session_state.all_conversation_figures = []

    # Track highest step ID to avoid collisions
    if "max_step_id" not in st.session_state:
        st.session_state.max_step_id = 0

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

def display_conversation_history():
    """Render all messages with st.chat_message."""
    for message in st.session_state.conversation_history:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
                if message.get("query_metadata", {}).get("focus"):
                    st.caption(f"*Focus: {message['query_metadata']['focus']}*")

        elif message["role"] == "assistant":
            with st.chat_message("assistant"):
                resp_meta = message.get("response_metadata", {})

                if resp_meta.get("type") == "clarification":
                    st.warning(f"**Clarification Needed:**\n\n{resp_meta.get('clarification_question')}")
                else:
                    st.markdown(resp_meta.get("summary", ""))

                    # Display figures
                    for fig_idx in resp_meta.get("figure_indices", []):
                        if fig_idx < len(st.session_state.all_conversation_figures):
                            try:
                                st.pyplot(st.session_state.all_conversation_figures[fig_idx], clear_figure=False)
                            except Exception:
                                pass

                    # Optional: data preview in expander
                    if resp_meta.get("stat_df_keys"):
                        with st.expander("📊 View Data Tables"):
                            for df_key in resp_meta["stat_df_keys"]:
                                if df_key in st.session_state.shared_env and st.session_state.shared_env[df_key] is not None:
                                    st.write(f"**{df_key}**")

                                    # Display metadata summary if available
                                    metadata = st.session_state.shared_meta.get(df_key, {})
                                    if metadata.get("_summary"):
                                        st.caption(metadata["_summary"])

                                    # Display DataFrame
                                    st.dataframe(st.session_state.shared_env[df_key].head(10), use_container_width=True)

                                    # Display column metadata if available
                                    column_meta = {k: v for k, v in metadata.items() if k != "_summary"}
                                    if column_meta:
                                        with st.expander(f"📋 Column Descriptions ({df_key})"):
                                            for col, desc in column_meta.items():
                                                st.markdown(f"- **{col}**: {desc}")

def handle_user_query(user_prompt: str, focus: str = None):
    """Process query, call agents, update history."""
    import datetime
    from agents import run_all_agents
    from helper import load_metadata_text

    if not user_prompt.strip():
        return

    # Add user message to history
    user_message = {
        "role": "user",
        "content": user_prompt,
        "timestamp": datetime.datetime.now(),
        "query_metadata": {"original_prompt": user_prompt, "focus": focus}
    }
    st.session_state.conversation_history.append(user_message)

    # Display user message
    with st.chat_message("user"):
        st.write(user_prompt)
        if focus:
            st.caption(f"*Focus: {focus}*")

    # Run agents
    with st.chat_message("assistant"):
        with st.spinner("Analyzing..."):
            metadata_text = load_metadata_text()

            try:
                result = run_all_agents(
                    original_prompt=user_prompt,
                    metadata_text=metadata_text,
                    focus=focus,
                    OpenAI_API_key=st.session_state.api_key,
                    conversation_history=st.session_state.conversation_history[:-1],  # Exclude current user msg
                    shared_env=st.session_state.shared_env,
                    shared_meta=st.session_state.shared_meta,
                    verbose=False,
                )
            except Exception as e:
                st.error(f"Error processing query: {str(e)}")

                # Add error to conversation history
                assistant_message = {
                    "role": "assistant",
                    "content": f"Sorry, I encountered an error: {str(e)}",
                    "timestamp": datetime.datetime.now(),
                    "response_metadata": {"type": "error", "error_message": str(e)}
                }
                st.session_state.conversation_history.append(assistant_message)
                return

        # Handle clarification
        if result.get("type") == "clarification":
            st.warning(f"**Clarification Needed:**\n\n{result.get('question')}")
            assistant_message = {
                "role": "assistant",
                "content": result.get("question"),
                "timestamp": datetime.datetime.now(),
                "response_metadata": {
                    "type": "clarification",
                    "clarification_question": result.get("question")
                }
            }
            st.session_state.conversation_history.append(assistant_message)
            return

        # Display summary
        summary = result.get("summary", "")
        st.markdown(summary)

        # Update shared environment
        st.session_state.shared_env = result["full_shared_env"]
        st.session_state.shared_meta = result["full_shared_meta"]

        # Store and display figures
        figures = result.get("figures", [])
        figure_start_idx = len(st.session_state.all_conversation_figures)
        st.session_state.all_conversation_figures.extend(figures)
        figure_indices = list(range(figure_start_idx, figure_start_idx + len(figures)))

        for fig in figures:
            try:
                st.pyplot(fig, clear_figure=False)
            except Exception:
                pass

        # Optional data preview
        new_df_keys = result.get("new_df_keys", [])
        if new_df_keys:
            with st.expander("📊 View Data Tables"):
                for df_key in new_df_keys:
                    if df_key in st.session_state.shared_env and st.session_state.shared_env[df_key] is not None:
                        st.write(f"**{df_key}**")

                        # Display metadata summary if available
                        metadata = st.session_state.shared_meta.get(df_key, {})
                        if metadata.get("_summary"):
                            st.caption(metadata["_summary"])

                        # Display DataFrame
                        st.dataframe(st.session_state.shared_env[df_key].head(10), use_container_width=True)

                        # Display column metadata if available
                        column_meta = {k: v for k, v in metadata.items() if k != "_summary"}
                        if column_meta:
                            with st.expander(f"📋 Column Descriptions ({df_key})"):
                                for col, desc in column_meta.items():
                                    st.markdown(f"- **{col}**: {desc}")

        # Update max_step_id
        if new_df_keys:
            numeric_ids = [int(k.split('_')[1]) for k in new_df_keys if k.startswith('df_')]
            if numeric_ids:
                st.session_state.max_step_id = max(numeric_ids)

        # Add assistant message to history
        assistant_message = {
            "role": "assistant",
            "content": summary,
            "timestamp": datetime.datetime.now(),
            "response_metadata": {
                "type": "answer",
                "summary": summary,
                "stat_df_keys": new_df_keys,
                "ds_report": result.get("report", {}),
                "figure_indices": figure_indices
            }
        }
        st.session_state.conversation_history.append(assistant_message)

def page_ask_agent():
    st.subheader("IRS SOI Migration Data Agent")

    # Sidebar controls
    with st.sidebar:
        st.subheader("Conversation Controls")
        if st.button("🔄 Clear Conversation"):
            st.session_state.conversation_history = []
            st.session_state.shared_env = {}
            st.session_state.shared_meta = {}
            st.session_state.all_conversation_figures = []
            st.session_state.max_step_id = 0
            st.rerun()

        if st.button("🔑 Change API Key"):
            st.session_state.page = "api_key"
            st.rerun()

        # Show conversation stats
        num_turns = len([m for m in st.session_state.conversation_history if m["role"] == "user"])
        num_dfs = len(st.session_state.shared_env)
        st.info(f"**Conversation Stats**\n\n"
                f"- Turns: {num_turns}\n"
                f"- Cached DataFrames: {num_dfs}\n"
                f"- Messages in history: {len(st.session_state.conversation_history)}")

    # Display conversation history
    display_conversation_history()

    # Chat input at bottom
    user_input = st.chat_input("Ask a question about IRS migration data...")

    if user_input:
        handle_user_query(user_input, focus=None)

