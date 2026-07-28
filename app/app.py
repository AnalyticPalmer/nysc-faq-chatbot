"""Streamlit interface for the NYSC FAQ Chatbot."""

import streamlit as st


TEMPORARY_RESPONSE = (
    "The AI knowledge base will be connected in a later step."
)

SUGGESTED_QUESTIONS = [
    "How do I register for NYSC?",
    "What documents should I take to camp?",
    "How can I apply for relocation?",
    "What is monthly clearance?",
]


st.set_page_config(
    page_title="NYSC FAQ Chatbot",
    page_icon="💬",
    layout="wide",
)

st.title("NYSC FAQ Assistant")
st.subheader("Get clear answers to common NYSC questions.")
st.warning(
    "This is an independent educational project and is not an official "
    "NYSC platform."
)

st.write(
    "Welcome! This chatbot will help you find answers about registration, "
    "mobilization, orientation camp, relocation, monthly clearance, and "
    "passing out."
)

# Keep messages available when Streamlit reruns the page.
if "messages" not in st.session_state:
    st.session_state.messages = []


def add_question(question):
    """Add a question and the temporary answer to the conversation."""
    st.session_state.messages.append(
        {"role": "user", "content": question}
    )
    st.session_state.messages.append(
        {"role": "assistant", "content": TEMPORARY_RESPONSE}
    )


st.write("### Suggested questions")
button_columns = st.columns(4)

for column, question in zip(button_columns, SUGGESTED_QUESTIONS):
    with column:
        if st.button(question, use_container_width=True):
            add_question(question)

# Display every message stored during the current session.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

user_question = st.chat_input("Ask an NYSC-related question...")

if user_question:
    add_question(user_question)

    # Display the newly submitted question and response immediately.
    with st.chat_message("user"):
        st.write(user_question)

    with st.chat_message("assistant"):
        st.write(TEMPORARY_RESPONSE)
