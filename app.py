import streamlit as st


def main():
    st.title("IRS SOI Migration Data Agent")
    st.write("This data agent uses GPT model, enter your OpenAI API key here. The key you input is never logged and the app runs fully in the browser when using this key.")

    api_key = st.text_input("Your OpenAi API key", type = "password")

    from agents import run_all_agents
    from helper import load_metadata_text
    
    st.write("Ask a question about the IRS SOI Migration Data, for example: How many people under age 35 moved to Minnesota?")

    user_prompt = st.text_area("Your Question", height=100)
    st.write("Is there a special instruction?")
    focus = st.text_area("User Instruction", height=100)

    if st.button("Ask Agent"):
        metadata_text = load_metadata_text()
        with st.spinner("Running agents..."):
            result = run_all_agents(
                original_prompt=user_prompt,
                metadata_text= metadata_text,
                focus = focus,
                verbose=False,
            )
        st.subheader("Answer")
        st.write(result.get("summary", result))

        figs = result.get("figures",[])
        try:
            for fig in figs:
                st.pyplot(fig)
        except:
            pass

if __name__ == "__main__":
    main()
