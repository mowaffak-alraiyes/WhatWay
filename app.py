import streamlit as st
import ollama

st.set_page_config(page_title="Ollama Chat")

st.title("💬 Chat with Local LLM")

# Use session state to store messages
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# User input
prompt = st.chat_input("Type your question here...")

# Display chat history
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

# When user submits a prompt
if prompt:
    # Show user message
    st.session_state.chat_history.append(("user", prompt))
    with st.chat_message("user"):
        st.markdown(prompt)

    # Send to Ollama
    response = ollama.chat(
        model="llama3",
        messages=[{"role": role, "content": msg} for role, msg in st.session_state.chat_history]
    )

    reply = response['message']['content']

    # Show assistant message
    st.session_state.chat_history.append(("assistant", reply))
    with st.chat_message("assistant"):
        st.markdown(reply)
