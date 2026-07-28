"""Streamlit interface for the NYSC FAQ Chatbot."""

import streamlit as st

from src.chat_service import NYSCChatService


st.set_page_config(
    page_title="NYSC FAQ Chatbot",
    page_icon="💬",
    layout="wide",
)


# Simple internal styling keeps the interface clean without external CSS.
st.markdown(
    """
    <style>
    h1, h2, h3 {
        color: #14532d;
    }

    div.stButton > button {
        background-color: #166534;
        color: white;
        border: none;
        border-radius: 0.75rem;
        padding: 0.6rem 1rem;
    }

    div.stButton > button:hover {
        background-color: #14532d;
        color: white;
        border: none;
    }

    div[data-testid="stAlert"] {
        background-color: #e8f5e9;
        border-radius: 0.75rem;
    }

    div[data-testid="stChatMessage"] {
        border-radius: 0.75rem;
        padding: 0.5rem;
        margin-bottom: 0.75rem;
    }

    .app-footer {
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #d1d5db;
        color: #4b5563;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_chat_service():
    """Load the chatbot resources once and reuse them across reruns."""
    return NYSCChatService()


def display_assistant_message(message: dict) -> None:
    """Display an assistant answer, metrics, and verified sources."""
    st.write(message["content"])

    confidence_column, time_column = st.columns(2)

    with confidence_column:
        st.caption(
            f"Confidence: {message.get('confidence', 0.0):.2f}%"
        )

    with time_column:
        st.caption(
            "Response time: "
            f"{message.get('response_time', 0.0):.2f} seconds"
        )

    sources = message.get("sources", [])

    if sources:
        with st.expander("View sources"):
            for source in sources:
                title = source.get("title", "NYSC source")
                url = source.get("url", "")
                category = source.get("category", "")

                if url:
                    st.markdown(f"**[{title}]({url})**")
                else:
                    st.markdown(f"**{title}**")

                st.write(f"Category: {category}")


try:
    chat_service = load_chat_service()
except Exception:
    st.error("The chatbot could not be initialized.")
    st.write(
        "Please confirm that the required local chatbot resources and "
        "environment settings are available, then try again."
    )
    st.stop()


# Initialize conversation history before displaying sidebar controls.
if "messages" not in st.session_state:
    st.session_state.messages = []


with st.sidebar:
    st.header("About this assistant")
    st.write(
        "This assistant can answer common questions about:"
    )
    st.markdown(
        """
        - Registration
        - Mobilization
        - Orientation camp
        - Relocation
        - Monthly clearance
        - PPA
        - CDS
        - Passing out
        - Exemption
        - Foreign-trained graduates
        """
    )

    if st.button("Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


st.title("🇳🇬 NYSC FAQ Assistant")
st.subheader(
    "Get clear and source-grounded answers to common NYSC questions."
)
st.info(
    "This is an independent educational AI project and is not an "
    "official NYSC platform. Confirm time-sensitive information through "
    "official NYSC channels."
)


st.markdown("### Suggested questions")

suggested_questions = [
    "How do I register for NYSC?",
    "What documents should I take to orientation camp?",
    "How can I apply for relocation?",
    "What is monthly clearance?",
]

selected_question = None
suggestion_columns = st.columns(4)

for column, suggested_question in zip(
    suggestion_columns,
    suggested_questions,
):
    with column:
        if st.button(
            suggested_question,
            use_container_width=True,
        ):
            selected_question = suggested_question


# Show every message already stored in the current conversation.
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            display_assistant_message(message)


prompt = st.chat_input("Ask an NYSC-related question...")
question = prompt or selected_question


if question:
    user_message = {
        "role": "user",
        "content": question,
    }
    st.session_state.messages.append(user_message)

    with st.chat_message("user"):
        st.write(question)

    with st.spinner("Searching verified NYSC information..."):
        result = chat_service.ask(question)

    # The service returns a safe answer even when processing is unsuccessful.
    assistant_message = {
        "role": "assistant",
        "content": result["answer"],
        "confidence": result["confidence"],
        "response_time": result["response_time"],
        "sources": result["sources"],
    }
    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        display_assistant_message(assistant_message)


st.markdown(
    '<div class="app-footer">'
    "Built by Palmer Ogiriki as an AI/ML Capstone Project."
    "</div>",
    unsafe_allow_html=True,
)
