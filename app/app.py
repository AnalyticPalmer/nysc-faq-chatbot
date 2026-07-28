"""Professional Streamlit interface for the NYSC FAQ Chatbot."""

import json
from html import escape
from pathlib import Path

import streamlit as st

from src.chat_service import NYSCChatService


st.set_page_config(
    page_title="NYSC FAQ Chatbot",
    page_icon="💬",
    layout="wide",
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
FAQ_DATA_PATH = PROJECT_ROOT / "data" / "faq" / "nysc_faq.json"
EVALUATION_REPORT_PATH = (
    PROJECT_ROOT / "reports" / "evaluation_report.json"
)


# Internal styling keeps the app self-contained and preserves Streamlit
# navigation, menus, branding, and accessibility features.
st.markdown(
    """
    <style>
    :root {
        --nysc-green: #14532d;
        --nysc-green-medium: #166534;
        --nysc-green-light: #ecfdf3;
        --nysc-border: #dce5df;
        --nysc-text-muted: #5f6b64;
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: var(--nysc-green);
        letter-spacing: -0.02em;
    }

    .app-header {
        padding: 1.6rem 1.75rem;
        margin-bottom: 1rem;
        border: 1px solid var(--nysc-border);
        border-radius: 1rem;
        background: linear-gradient(135deg, #f7fff9 0%, #ecfdf3 100%);
    }

    .app-header h1 {
        margin: 0 0 0.4rem 0;
        font-size: 2.15rem;
    }

    .app-header p {
        margin: 0;
        max-width: 850px;
        color: #3f5146;
        font-size: 1.02rem;
        line-height: 1.65;
    }

    div[data-testid="stMetric"] {
        min-height: 118px;
        padding: 1rem 1.1rem;
        border: 1px solid var(--nysc-border);
        border-radius: 0.9rem;
        background: #ffffff;
        box-shadow: 0 3px 12px rgba(20, 83, 45, 0.05);
    }

    div[data-testid="stMetricLabel"] {
        color: var(--nysc-text-muted);
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: var(--nysc-green);
        font-size: 1.45rem;
    }

    div.stButton > button {
        min-height: 2.7rem;
        border: 1px solid #b8c9bd;
        border-radius: 0.7rem;
        color: var(--nysc-green);
        background: #ffffff;
        font-weight: 600;
        transition: all 0.15s ease-in-out;
    }

    div.stButton > button:hover {
        border-color: var(--nysc-green-medium);
        color: #ffffff;
        background: var(--nysc-green-medium);
    }

    div[data-testid="stAlert"] {
        border-radius: 0.85rem;
    }

    div[data-testid="stChatMessage"] {
        margin-bottom: 0.9rem;
        padding: 1rem 1.1rem;
        border: 1px solid #e4e9e5;
        border-radius: 0.9rem;
        background: #ffffff;
    }

    .response-details {
        display: flex;
        flex-wrap: wrap;
        gap: 0.55rem;
        margin: 0.8rem 0 0.25rem;
    }

    .detail-badge {
        display: inline-block;
        padding: 0.35rem 0.7rem;
        border: 1px solid #c9ddd0;
        border-radius: 999px;
        color: var(--nysc-green);
        background: var(--nysc-green-light);
        font-size: 0.82rem;
        font-weight: 600;
    }

    .section-label {
        margin: 1.4rem 0 0.65rem;
        color: var(--nysc-green);
        font-size: 1rem;
        font-weight: 700;
    }

    .sidebar-label {
        margin: 1.15rem 0 0.3rem;
        color: var(--nysc-green);
        font-size: 0.85rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
    }

    .sidebar-value {
        margin-bottom: 0.4rem;
        color: #425047;
        line-height: 1.5;
    }

    .app-footer {
        margin-top: 2.5rem;
        padding: 1.4rem 1rem 0.4rem;
        border-top: 1px solid var(--nysc-border);
        color: var(--nysc-text-muted);
        text-align: center;
        line-height: 1.7;
    }

    .app-footer strong {
        color: var(--nysc-green);
    }

    @media (max-width: 700px) {
        .block-container {
            padding-top: 1rem;
        }

        .app-header {
            padding: 1.25rem;
        }

        .app-header h1 {
            font-size: 1.75rem;
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def load_chat_service() -> NYSCChatService:
    """Load chatbot resources once and reuse them across Streamlit reruns."""
    return NYSCChatService()


@st.cache_data
def load_dashboard_data() -> tuple[int, str]:
    """Load read-only knowledge-base and evaluation summary values."""
    total_faqs = 0
    retrieval_accuracy = "Not evaluated"

    try:
        with FAQ_DATA_PATH.open("r", encoding="utf-8") as file:
            faq_records = json.load(file)

        if isinstance(faq_records, list):
            total_faqs = len(faq_records)
    except (OSError, json.JSONDecodeError):
        # Dashboard values must never prevent the chatbot from starting.
        total_faqs = 0

    try:
        with EVALUATION_REPORT_PATH.open(
            "r",
            encoding="utf-8",
        ) as file:
            evaluation_report = json.load(file)

        accuracy = evaluation_report.get("summary", {}).get("accuracy")
        if isinstance(accuracy, (int, float)):
            retrieval_accuracy = f"{accuracy:.2f}%"
    except (OSError, json.JSONDecodeError):
        retrieval_accuracy = "Not evaluated"

    return total_faqs, retrieval_accuracy


def calculate_average_response_time(messages: list[dict]) -> str:
    """Calculate the average response time from assistant chat messages."""
    response_times = [
        float(message.get("response_time", 0.0))
        for message in messages
        if message.get("role") == "assistant"
    ]

    if not response_times:
        return "No responses yet"

    average_time = sum(response_times) / len(response_times)
    return f"{average_time:.2f} sec"


def display_assistant_message(message: dict) -> None:
    """Display an assistant answer, performance badges, and sources."""
    st.markdown(message["content"])

    confidence = float(message.get("confidence", 0.0))
    response_time = float(message.get("response_time", 0.0))

    st.markdown(
        '<div class="response-details">'
        f'<span class="detail-badge">Confidence: {confidence:.2f}%</span>'
        f'<span class="detail-badge">'
        f"Response Time: {response_time:.2f} seconds"
        "</span>"
        "</div>",
        unsafe_allow_html=True,
    )

    sources = message.get("sources", [])

    if sources:
        with st.expander("View sources"):
            for source in sources:
                title = source.get("title", "NYSC source")
                category = source.get("category", "")
                url = source.get("url", "")

                with st.container(border=True):
                    st.markdown(f"**{escape(str(title))}**")
                    st.caption(f"Category: {category}")

                    if url:
                        st.link_button(
                            "Open official source",
                            url,
                            use_container_width=False,
                        )


try:
    chat_service = load_chat_service()
except Exception:
    st.error("The chatbot could not be initialized.")
    st.write(
        "Please confirm that the required local chatbot resources and "
        "environment settings are available, then try again."
    )
    st.stop()


# Keep the existing conversation state available across Streamlit reruns.
if "messages" not in st.session_state:
    st.session_state.messages = []


total_faqs, retrieval_accuracy = load_dashboard_data()
average_response_time = calculate_average_response_time(
    st.session_state.messages
)
active_model = chat_service.model_name


with st.sidebar:
    st.header("NYSC FAQ Assistant")

    st.markdown('<div class="sidebar-label">About</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-value">'
        "A source-grounded AI assistant for common NYSC questions, "
        "powered by semantic retrieval and verified FAQ information."
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-label">Supported Topics</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        """
        - Registration
        - Mobilization
        - Orientation Camp
        - Camp Requirements
        - Relocation
        - Monthly Clearance
        - Place of Primary Assignment (PPA)
        - Community Development Service (CDS)
        - Passing Out
        - Exemption
        - Foreign-Trained Graduates
        - Portal Support
        """
    )

    st.markdown(
        '<div class="sidebar-label">Knowledge Base</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sidebar-value">{total_faqs} verified FAQs</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-label">Retriever</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sidebar-value">FAISS Vector Database</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-label">Embedding Model</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sidebar-value">'
        "Sentence Transformers<br>all-MiniLM-L6-v2"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-label">Language Model</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<div class="sidebar-value">{escape(active_model)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="sidebar-label">Conversation</div>',
        unsafe_allow_html=True,
    )

    if st.button("Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


st.markdown(
    """
    <div class="app-header">
        <h1>NYSC FAQ Assistant</h1>
        <p>
            AI-powered Retrieval-Augmented Generation (RAG) Assistant
            for answering common NYSC questions using verified information.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

st.info(
    "This is an independent educational AI project and is not an "
    "official NYSC platform. Confirm time-sensitive information through "
    "official NYSC channels."
)


# Top-level metrics provide a quick view of the current app state.
metric_columns = st.columns(4)

with metric_columns[0]:
    st.metric("Total FAQs", total_faqs)

with metric_columns[1]:
    st.metric("Retrieval Accuracy", retrieval_accuracy)

with metric_columns[2]:
    st.metric("Average Response Time", average_response_time)

with metric_columns[3]:
    st.metric("AI Model", active_model)


st.markdown(
    '<div class="section-label">Quick questions</div>',
    unsafe_allow_html=True,
)

quick_questions = {
    "Registration": "How do I register for NYSC?",
    "Orientation Camp": (
        "What documents should I take to orientation camp?"
    ),
    "Relocation": "How can I apply for relocation?",
    "PPA": "What is a PPA in NYSC?",
    "CDS": "What is CDS?",
    "Monthly Clearance": "What is monthly clearance?",
}

selected_question = None
quick_question_columns = st.columns(3)

for index, (button_label, predefined_question) in enumerate(
    quick_questions.items()
):
    column = quick_question_columns[index % 3]

    with column:
        if st.button(
            button_label,
            key=f"quick_question_{index}",
            use_container_width=True,
        ):
            selected_question = predefined_question


st.markdown(
    '<div class="section-label">Conversation</div>',
    unsafe_allow_html=True,
)

# Display all messages already stored in the current conversation.
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

    # Preserve the existing assistant-message and session-state structure.
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
    """
    <div class="app-footer">
        <strong>Built by Palmer Ogiriki</strong><br>
        AI/ML Capstone Project<br>
        Powered by Streamlit • FAISS • Sentence Transformers • Google Gemini
    </div>
    """,
    unsafe_allow_html=True,
)
