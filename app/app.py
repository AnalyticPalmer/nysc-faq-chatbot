"""Professional Streamlit interface for the NYSC FAQ Chatbot."""

import json
import os
import sys
from html import escape
from pathlib import Path

import streamlit as st


# Add the project root to Python's import path.
# This allows Streamlit Cloud to locate the src package.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


from src.chat_service import NYSCChatService


st.set_page_config(
    page_title="NYSC FAQ Chatbot",
    page_icon="💬",
    layout="wide",
)



FAQ_DATA_PATH = PROJECT_ROOT / "data" / "faq" / "nysc_faq.json"
PDF_DATA_DIR = PROJECT_ROOT / "data" / "raw"
VECTOR_METADATA_PATH = PROJECT_ROOT / "vector_store" / "metadata.json"
FAISS_INDEX_PATH = PROJECT_ROOT / "vector_store" / "nysc_faq.index"
EVALUATION_REPORT_PATH = (
    PROJECT_ROOT / "reports" / "evaluation_report.json"
)
RESPONSE_MODE_OPTIONS = {
    "Automatic": "auto",
    "AI Enhanced": "ai",
    "Verified FAQ Only": "faq",
}
RESPONSE_MODE_LABELS = {
    mode: label for label, mode in RESPONSE_MODE_OPTIONS.items()
}


# Internal styling keeps the app self-contained and preserves Streamlit
# navigation, menus, branding, and accessibility features.
st.markdown(
    """
    <style>
    :root {
        --nysc-green: var(--primary-color);
        --nysc-green-soft: color-mix(
            in srgb,
            var(--primary-color) 14%,
            transparent
        );
        --nysc-border: color-mix(
            in srgb,
            var(--text-color) 18%,
            transparent
        );
        --nysc-text-muted: color-mix(
            in srgb,
            var(--text-color) 68%,
            transparent
        );
        --nysc-surface: color-mix(
            in srgb,
            var(--secondary-background-color) 72%,
            var(--background-color)
        );
    }

    .block-container {
        max-width: 1180px;
        padding-top: 2rem;
        padding-bottom: 2rem;
    }

    h1, h2, h3 {
        color: color-mix(
            in srgb,
            var(--nysc-green) 78%,
            var(--text-color)
        );
        letter-spacing: -0.02em;
    }

    .app-header {
        padding: 1.6rem 1.75rem;
        margin-bottom: 1rem;
        border: 1px solid var(--nysc-border);
        border-radius: 1rem;
        background: linear-gradient(
            135deg,
            var(--background-color) 0%,
            var(--nysc-surface) 100%
        );
    }

    .app-header h1 {
        margin: 0 0 0.4rem 0;
        font-size: 2.15rem;
    }

    .app-header p {
        margin: 0;
        max-width: 850px;
        color: var(--text-color);
        font-size: 1.02rem;
        line-height: 1.65;
    }

    div[data-testid="stMetric"] {
        min-height: 118px;
        padding: 1rem 1.1rem;
        border: 1px solid var(--nysc-border);
        border-radius: 0.9rem;
        background: var(--nysc-surface);
        box-shadow: 0 3px 12px color-mix(
            in srgb,
            var(--primary-color) 8%,
            transparent
        );
    }

    div[data-testid="stMetricLabel"] {
        color: var(--nysc-text-muted);
        font-weight: 600;
    }

    div[data-testid="stMetricValue"] {
        color: color-mix(
            in srgb,
            var(--nysc-green) 75%,
            var(--text-color)
        );
        font-size: 1.45rem;
    }

    div.stButton > button {
        min-height: 2.7rem;
        border: 1px solid var(--nysc-border);
        border-radius: 0.7rem;
        color: var(--text-color);
        background: var(--background-color);
        font-weight: 600;
        transition: all 0.15s ease-in-out;
    }

    div.stButton > button:hover {
        border-color: var(--primary-color);
        color: var(--text-color);
        background: var(--nysc-green-soft);
    }

    div[data-testid="stAlert"] {
        border-radius: 0.85rem;
    }

    div[data-testid="stChatMessage"] {
        margin-bottom: 0.9rem;
        padding: 1rem 1.1rem;
        border: 1px solid var(--nysc-border);
        border-radius: 0.9rem;
        color: var(--text-color);
        background: var(--nysc-surface);
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
        border: 1px solid var(--nysc-border);
        border-radius: 999px;
        color: var(--text-color);
        background: var(--nysc-green-soft);
        font-size: 0.82rem;
        font-weight: 600;
    }

    .section-label {
        margin: 1.4rem 0 0.65rem;
        color: var(--nysc-green);
        font-size: 1rem;
        font-weight: 700;
    }

    .welcome-container {
        margin: 1rem 0 1.25rem;
        padding: 1.25rem 1.4rem;
        border: 1px solid var(--nysc-border);
        border-radius: 0.9rem;
        background: var(--nysc-surface);
    }

    .welcome-container h3 {
        margin: 0 0 0.45rem;
    }

    .welcome-container p {
        margin: 0 0 0.65rem;
        color: var(--text-color);
        line-height: 1.6;
    }

    .welcome-container ul {
        margin-bottom: 0;
        color: var(--text-color);
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
        color: var(--text-color);
        line-height: 1.5;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-color: var(--nysc-border);
        background: color-mix(
            in srgb,
            var(--secondary-background-color) 45%,
            transparent
        );
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


@st.cache_data
def load_knowledge_base_statistics() -> dict:
    """Load safe knowledge-base counts without blocking the application."""
    statistics = {
        "total_faqs": 0,
        "total_pdf_files": 0,
        "total_faq_chunks": 0,
        "total_pdf_chunks": 0,
        "total_vectors": 0,
        "vector_store_ready": False,
    }

    try:
        with FAQ_DATA_PATH.open("r", encoding="utf-8") as file:
            faq_records = json.load(file)

        if isinstance(faq_records, list):
            statistics["total_faqs"] = len(faq_records)
    except (OSError, json.JSONDecodeError):
        pass

    try:
        if PDF_DATA_DIR.exists():
            statistics["total_pdf_files"] = sum(
                path.is_file()
                for path in PDF_DATA_DIR.glob("*.pdf")
            )
    except OSError:
        pass

    try:
        with VECTOR_METADATA_PATH.open("r", encoding="utf-8") as file:
            vector_metadata = json.load(file)

        if isinstance(vector_metadata, list):
            statistics["total_vectors"] = len(vector_metadata)

            for record in vector_metadata:
                if not isinstance(record, dict):
                    continue

                metadata = record.get("metadata", record)
                document_type = (
                    metadata.get("document_type", "faq")
                    if isinstance(metadata, dict)
                    else "faq"
                )

                if document_type == "pdf":
                    statistics["total_pdf_chunks"] += 1
                else:
                    statistics["total_faq_chunks"] += 1
    except (OSError, json.JSONDecodeError):
        pass

    statistics["vector_store_ready"] = (
        FAISS_INDEX_PATH.exists() and VECTOR_METADATA_PATH.exists()
    )

    return statistics


def is_local_development() -> bool:
    """Return whether safe environment indicators identify a local run."""
    try:
        sharing_mode = os.getenv("STREAMLIT_SHARING_MODE")
        cloud_flag = os.getenv("IS_STREAMLIT_CLOUD", "")

        return (
            sharing_mode is None
            and cloud_flag.strip().lower() != "true"
        )
    except Exception:
        # Uncertain environments must not expose the rebuild control.
        return False


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


def get_confidence_label(confidence: float) -> str:
    """Return a clear label for a numeric confidence score."""
    if confidence >= 85:
        return "High"

    if confidence >= 70:
        return "Medium"

    return "Low"


def calculate_session_statistics(
    messages: list[dict],
) -> tuple[int, int, int, float]:
    """Calculate question, feedback, and RAG confidence statistics."""
    questions_asked = sum(
        message.get("role") == "user" for message in messages
    )
    helpful_ratings = sum(
        message.get("feedback") == "helpful" for message in messages
    )
    not_helpful_ratings = sum(
        message.get("feedback") == "not_helpful" for message in messages
    )
    rag_confidences = [
        float(message.get("confidence", 0.0))
        for message in messages
        if message.get("role") == "assistant"
        and message.get("response_type", "rag") == "rag"
        and message.get("success", True)
    ]
    average_confidence = (
        sum(rag_confidences) / len(rag_confidences)
        if rag_confidences
        else 0.0
    )

    return (
        questions_asked,
        helpful_ratings,
        not_helpful_ratings,
        average_confidence,
    )


def _valid_source_records(value: object) -> list[dict]:
    """Return only mapping-like source records safe for UI rendering."""
    if not isinstance(value, list):
        return []

    return [source for source in value if isinstance(source, dict)]


def get_follow_up_questions(message: dict) -> list[str]:
    """Return up to three follow-up questions based on source categories."""
    category_questions = {
        "Registration": [
            "How do I correct a mistake in my NYSC registration?",
            "How can I print my NYSC green card?",
            "Why is my registration incomplete?",
        ],
        "Orientation Camp": [
            "What should I wear to orientation camp?",
            "What happens if I miss orientation camp?",
            "Can I leave camp before it ends?",
        ],
        "Camp Requirements": [
            "What should I wear to orientation camp?",
            "What happens if I miss orientation camp?",
            "Can I leave camp before it ends?",
        ],
        "Relocation": [
            "What grounds are accepted for NYSC relocation?",
            "How do I check my relocation status?",
            "Can I apply for relocation after camp?",
        ],
        "Place of Primary Assignment": [
            "Can I reject my PPA?",
            "Can my PPA be changed?",
            "What happens after receiving my PPA letter?",
        ],
        "Community Development Service": [
            "Is CDS compulsory?",
            "How often does CDS take place?",
            "What happens if I miss CDS?",
        ],
        "Monthly Clearance": [
            "What happens if I miss monthly clearance?",
            "How do I complete monthly clearance?",
            "Why is monthly clearance important?",
        ],
        "Foreign-Trained Graduates": [
            "Which documents must foreign-trained graduates provide?",
            "Must original documents be presented in camp?",
            "How are foreign certificates verified?",
        ],
        "Portal Support": [
            "How do I reset my NYSC portal password?",
            "What should I do when the portal is unavailable?",
            "Can I reprint my call-up letter?",
        ],
    }
    default_questions = [
        "How do I register for NYSC?",
        "What should I take to orientation camp?",
        "How can I apply for relocation?",
    ]

    follow_up_questions = []

    for source in _valid_source_records(message.get("sources")):
        category = source.get("category", "")

        for question in category_questions.get(category, []):
            if question not in follow_up_questions:
                follow_up_questions.append(question)

            if len(follow_up_questions) == 3:
                return follow_up_questions

    return follow_up_questions or default_questions


def format_conversation_for_download(messages: list[dict]) -> str:
    """Format visible conversation content as a plain-text transcript."""
    transcript_lines = [
        "NYSC FAQ Assistant Conversation",
        "Generated from the NYSC FAQ Chatbot",
        "",
    ]

    for message in messages:
        role = message.get("role")
        content = message.get("content", "")

        if role == "user":
            transcript_lines.extend(["User:", content, ""])
            continue

        if role != "assistant":
            continue

        transcript_lines.extend(["Assistant:", content])
        response_type = message.get("response_type", "rag")

        if response_type == "rag":
            confidence = float(message.get("confidence", 0.0))
            confidence_label = get_confidence_label(confidence)
            requested_mode = message.get(
                "requested_response_mode",
                "auto",
            )
            requested_mode_label = RESPONSE_MODE_LABELS.get(
                requested_mode,
                requested_mode,
            )
            transcript_lines.append(
                f"Requested response mode: {requested_mode_label}"
            )
            transcript_lines.append(
                f"Confidence: {confidence_label} ({confidence:.2f}%)"
            )
            transcript_lines.append(
                f"Response time: "
                f"{float(message.get('response_time', 0.0)):.2f} seconds"
            )
            transcript_lines.append(
                "Generation mode: "
                f"{message.get('generation_mode', 'unavailable')}"
            )
            cache_status = (
                "Loaded from session cache"
                if message.get("cache_hit", False)
                else "Not cached"
            )
            transcript_lines.append(f"Cache status: {cache_status}")

            feedback = message.get("feedback")
            if feedback:
                feedback_label = (
                    "Helpful"
                    if feedback == "helpful"
                    else "Not Helpful"
                )
                transcript_lines.append(f"Feedback: {feedback_label}")

            sources = _valid_source_records(message.get("sources"))
            if sources:
                transcript_lines.append("Sources:")

                for source in sources:
                    title = source.get("title", "NYSC source")
                    category = source.get("category", "")
                    url = source.get("url", "")
                    document_type = source.get(
                        "document_type",
                        "faq",
                    )

                    if document_type == "pdf":
                        source_path = source.get("source_path", "")
                        filename = (
                            Path(source_path).name
                            if source_path
                            else ""
                        )
                        page_number = source.get("page_number")
                        section_title = (
                            source.get("section_title")
                            or source.get("section")
                            or ""
                        )

                        transcript_lines.append(
                            "- Source type: Official PDF Document"
                        )
                        transcript_lines.append(
                            f"  Document title: {title}"
                        )
                        transcript_lines.append(
                            "  Category: Official Document"
                        )

                        if filename:
                            transcript_lines.append(
                                f"  Document file: {filename}"
                            )

                        if page_number not in (None, ""):
                            transcript_lines.append(
                                f"  Page: {page_number}"
                            )

                        if section_title:
                            transcript_lines.append(
                                f"  Section: {section_title}"
                            )
                    else:
                        transcript_lines.append(
                            "- Source type: Verified FAQ"
                        )
                        transcript_lines.append(
                            f"  Source title: {title}"
                        )
                        transcript_lines.append(
                            f"  Category: {category}"
                        )

                        if url:
                            transcript_lines.append(
                                f"  Official URL: {url}"
                            )

        transcript_lines.append("")

    return "\n".join(transcript_lines).strip() + "\n"


def display_developer_information(message: dict) -> None:
    """Display safe diagnostic metadata for a successful RAG response."""
    sources = _valid_source_records(message.get("sources"))
    requested_mode = (
        message.get("requested_response_mode") or "auto"
    )
    response_mode = RESPONSE_MODE_LABELS.get(
        requested_mode,
        requested_mode,
    )
    generation_mode = (
        message.get("generation_mode") or "unavailable"
    )
    generation_mode_labels = {
        "gemini": "Gemini Enhanced",
        "retrieval_fallback": "Retrieval Fallback",
        "verified_faq": "Verified FAQ",
        "unavailable": "Information Unavailable",
    }
    generation_mode_label = generation_mode_labels.get(
        generation_mode,
        str(generation_mode).replace("_", " ").title(),
    )
    source_type_counts = {
        "faq": 0,
        "pdf": 0,
    }

    for source in sources:
        document_type = source.get("document_type", "faq")

        if document_type == "pdf":
            source_type_counts["pdf"] += 1
        else:
            source_type_counts["faq"] += 1

    document_types = []
    if source_type_counts["faq"]:
        document_types.append("Verified FAQ")
    if source_type_counts["pdf"]:
        document_types.append("Official PDF Document")

    with st.expander("Developer Information"):
        st.markdown(
            f"**Requested Response Mode:** {response_mode}"
        )
        st.markdown(
            "**Generation Mode:** "
            f"{generation_mode_label}"
        )
        st.markdown(
            "**Cache Hit:** "
            f"{'Yes' if message.get('cache_hit', False) else 'No'}"
        )
        st.markdown(
            "**Confidence:** "
            f"{float(message.get('confidence', 0.0)):.2f}%"
        )
        st.markdown(
            "**Response Time:** "
            f"{float(message.get('response_time', 0.0)):.2f} seconds"
        )
        st.markdown(
            f"**Detected Topic:** {message.get('topic') or 'None'}"
        )
        st.markdown(
            "**Document Types Used:** "
            f"{', '.join(document_types) if document_types else 'None'}"
        )
        st.markdown(f"**Source Count:** {len(sources)}")

        st.markdown("**Sources used:**")
        if source_type_counts["faq"]:
            st.markdown(
                f"- {source_type_counts['faq']} Verified "
                f"FAQ{'s' if source_type_counts['faq'] != 1 else ''}"
            )
        if source_type_counts["pdf"]:
            st.markdown(
                f"- {source_type_counts['pdf']} Official PDF "
                f"Document"
                f"{'s' if source_type_counts['pdf'] != 1 else ''}"
            )
        if not sources:
            st.markdown("- None")

        for source_index, source in enumerate(sources, start=1):
            st.divider()
            source_rank = source.get("rank") or source_index
            document_type = source.get("document_type", "faq")
            source_type = (
                "Official PDF Document"
                if document_type == "pdf"
                else "Verified FAQ"
            )
            title = source.get("title", "")
            category = source.get("category", "")
            url = source.get("url", "")
            source_path = source.get("source_path", "")
            filename = (
                Path(source_path).name
                if document_type == "pdf" and source_path
                else ""
            )
            page_number = source.get("page_number")
            section_title = (
                source.get("section_title")
                or source.get("section")
                or ""
            )
            similarity_score = None

            for score_field in ("score", "similarity", "confidence"):
                if source.get(score_field) is not None:
                    similarity_score = source[score_field]
                    break

            st.markdown(f"**Rank:** {source_rank}")
            st.markdown(f"**Source Type:** {source_type}")

            if title:
                st.markdown(f"**Title:** {escape(str(title))}")
            if category:
                st.markdown(
                    f"**Category:** {escape(str(category))}"
                )
            if url:
                st.markdown(
                    f"**Official URL:** {escape(str(url))}"
                )
            if filename:
                st.markdown(
                    f"**PDF filename:** {escape(filename)}"
                )
            if page_number not in (None, ""):
                st.markdown(
                    f"**Page number:** {escape(str(page_number))}"
                )
            if section_title:
                st.markdown(
                    f"**Section:** {escape(str(section_title))}"
                )

            if similarity_score is not None:
                if isinstance(similarity_score, (int, float)):
                    score_display = f"{similarity_score:.4f}"
                else:
                    score_display = escape(str(similarity_score))

                st.markdown(
                    f"**Similarity Score:** {score_display}"
                )
            else:
                st.markdown("**Similarity Score:** Not available")


def display_assistant_message(
    message: dict,
    message_index: int,
    developer_mode: bool,
) -> None:
    """Display an assistant message according to its response type."""
    st.markdown(message["content"])
    response_type = message.get("response_type", "rag")
    is_successful_rag = (
        response_type == "rag" and message.get("success", True)
    )

    if is_successful_rag:
        confidence = float(message.get("confidence", 0.0))
        confidence_label = get_confidence_label(confidence)
        response_time = float(message.get("response_time", 0.0))

        st.markdown(
            '<div class="response-details">'
            f'<span class="detail-badge">'
            f"Confidence: {confidence_label} ({confidence:.2f}%)"
            "</span>"
            f'<span class="detail-badge">'
            f"Response Time: {response_time:.2f} seconds"
            "</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        if message.get("cache_hit", False):
            st.caption("Loaded from session cache")

        sources = _valid_source_records(message.get("sources"))

        if sources:
            with st.expander("View sources"):
                for source in sources:
                    title = source.get("title", "NYSC source")
                    category = source.get("category", "")
                    url = source.get("url", "")
                    document_type = source.get(
                        "document_type",
                        "faq",
                    )
                    source_path = source.get("source_path", "")
                    page_number = source.get("page_number")
                    section_title = (
                        source.get("section_title")
                        or source.get("section")
                        or ""
                    )

                    with st.container(border=True):
                        if document_type == "pdf":
                            filename = (
                                Path(source_path).name
                                if source_path
                                else ""
                            )
                            st.caption(
                                "Source type: Official PDF Document"
                            )
                            st.markdown(
                                "**Document title:** "
                                f"{escape(str(title))}"
                            )
                            st.markdown(
                                "**Category:** Official Document"
                            )

                            if filename:
                                st.markdown(
                                    "**Document file:** "
                                    f"{escape(filename)}"
                                )

                            if page_number not in (None, ""):
                                st.markdown(
                                    "**Page:** "
                                    f"{escape(str(page_number))}"
                                )

                            if section_title:
                                st.markdown(
                                    "**Section:** "
                                    f"{escape(str(section_title))}"
                                )
                        else:
                            st.caption("Source type: Verified FAQ")
                            st.markdown(
                                "**Source title:** "
                                f"{escape(str(title))}"
                            )
                            st.markdown(
                                f"**Category:** {escape(str(category))}"
                            )

                            if url:
                                st.link_button(
                                    "Open official source",
                                    url,
                                    use_container_width=False,
                                )

        is_unavailable_response = (
            message.get("generation_mode") == "unavailable"
            or (
                not message.get("sources")
                and float(message.get("confidence", 0.0)) <= 0.0
            )
        )
        if developer_mode and not is_unavailable_response:
            display_developer_information(message)

        feedback = message.get("feedback")
        if feedback is None:
            feedback_columns = st.columns(2)

            with feedback_columns[0]:
                if st.button(
                    "Helpful",
                    key=f"feedback_helpful_{message_index}",
                    use_container_width=True,
                ):
                    message["feedback"] = "helpful"
                    st.rerun()

            with feedback_columns[1]:
                if st.button(
                    "Not Helpful",
                    key=f"feedback_not_helpful_{message_index}",
                    use_container_width=True,
                ):
                    message["feedback"] = "not_helpful"
                    st.rerun()
        else:
            st.success("Thank you for your feedback.")

    if response_type != "error":
        with st.expander("Copy Answer"):
            st.code(message["content"], language=None)


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


_, retrieval_accuracy = load_dashboard_data()
knowledge_base_statistics = load_knowledge_base_statistics()
total_faqs = knowledge_base_statistics["total_faqs"]
average_response_time = calculate_average_response_time(
    st.session_state.messages
)
(
    questions_asked,
    helpful_ratings,
    not_helpful_ratings,
    average_confidence,
) = calculate_session_statistics(st.session_state.messages)
active_model = chat_service.model_name


with st.sidebar:
    st.header("NYSC FAQ Assistant")

    st.markdown('<div class="sidebar-label">About</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="sidebar-value">'
        "A source-grounded AI assistant for NYSC questions, powered by "
        "semantic retrieval, verified FAQs and official NYSC PDF documents."
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
        - NYSC Bye-Laws and Official Documents
        """
    )

    st.markdown(
        '<div class="sidebar-label">Knowledge Base</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="sidebar-value">'
        f"<strong>Verified FAQs:</strong> "
        f"{knowledge_base_statistics['total_faqs']}<br>"
        f"<strong>Official PDFs:</strong> "
        f"{knowledge_base_statistics['total_pdf_files']}<br>"
        f"<strong>FAQ Chunks:</strong> "
        f"{knowledge_base_statistics['total_faq_chunks']}<br>"
        f"<strong>PDF Chunks:</strong> "
        f"{knowledge_base_statistics['total_pdf_chunks']}<br>"
        f"<strong>Total Vectors:</strong> "
        f"{knowledge_base_statistics['total_vectors']}<br>"
        f"<strong>Vector Store Status:</strong> "
        f"{'Ready' if knowledge_base_statistics['vector_store_ready'] else 'Not Ready'}"
        "</div>",
        unsafe_allow_html=True,
    )

    if st.session_state.pop(
        "knowledge_base_refresh_success",
        False,
    ):
        st.success("Knowledge base refreshed successfully.")

    if is_local_development():
        if st.button(
            "Refresh Knowledge Base",
            key="refresh_knowledge_base",
            use_container_width=True,
        ):
            try:
                from src.vector_store import build_vector_store

                with st.status(
                    "Refreshing the knowledge base...",
                    expanded=True,
                ) as refresh_status:
                    build_vector_store()
                    load_knowledge_base_statistics.clear()
                    load_chat_service.clear()
                    refresh_status.update(
                        label="Knowledge base refresh complete",
                        state="complete",
                        expanded=False,
                    )

                st.session_state[
                    "knowledge_base_refresh_success"
                ] = True
                st.rerun()
            except Exception:
                from src.logger import logger

                logger.exception(
                    "Local knowledge-base refresh failed."
                )
                st.error(
                    "The knowledge base could not be refreshed. "
                    "Please check the local application logs."
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
        '<div class="sidebar-label">Response Mode</div>',
        unsafe_allow_html=True,
    )
    selected_response_mode_label = st.radio(
        "Response Mode",
        options=list(RESPONSE_MODE_OPTIONS),
        index=0,
        key="response_mode_selection",
        label_visibility="collapsed",
    )
    selected_response_mode = RESPONSE_MODE_OPTIONS[
        selected_response_mode_label
    ]

    response_mode_help = {
        "Automatic": (
            "Uses Gemini when available and automatically falls back to "
            "the verified FAQ knowledge base."
        ),
        "AI Enhanced": (
            "Uses Gemini to create a natural answer from retrieved NYSC "
            "information."
        ),
        "Verified FAQ Only": (
            "Returns information directly from the verified FAQ "
            "knowledge base without calling Gemini."
        ),
    }
    st.caption(response_mode_help[selected_response_mode_label])

    with st.expander("System Information"):
        st.markdown("**Retriever:** FAISS")
        st.markdown(
            "**Embedding Model:** all-MiniLM-L6-v2"
        )
        st.markdown("**Vector Dimension:** 384")
        st.markdown("**Supported Sources:** FAQ and PDF")
        st.markdown(
            f"**Active Response Mode:** "
            f"{selected_response_mode_label}"
        )

    developer_mode = st.checkbox(
        "Developer Mode",
        value=False,
        key="developer_mode_enabled",
        help=(
            "Displays technical retrieval and response details for "
            "demonstrations."
        ),
    )

    st.markdown(
        '<div class="sidebar-label">Session Statistics</div>',
        unsafe_allow_html=True,
    )
    st.metric("Questions Asked", questions_asked)
    st.metric("Helpful Ratings", helpful_ratings)
    st.metric("Not Helpful Ratings", not_helpful_ratings)
    st.metric("Average Confidence", f"{average_confidence:.2f}%")

    st.markdown(
        '<div class="sidebar-label">Conversation</div>',
        unsafe_allow_html=True,
    )

    if st.button("Clear Conversation", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    if st.session_state.messages:
        st.download_button(
            "Download Conversation",
            data=format_conversation_for_download(
                st.session_state.messages
            ),
            file_name="nysc_chat_conversation.txt",
            mime="text/plain",
            use_container_width=True,
        )


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
    "Bye-Laws": (
        "What happens when a corps member travels outside the state "
        "without permission?"
    ),
}

selected_question = None
quick_question_columns = st.columns(4)

for index, (button_label, predefined_question) in enumerate(
    quick_questions.items()
):
    column = quick_question_columns[index % 4]

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

if not st.session_state.messages:
    st.markdown(
        """
        <div class="welcome-container">
            <h3>Welcome to the NYSC FAQ Assistant</h3>
            <p>
                Ask clear questions about NYSC registration, mobilization,
                orientation camp, relocation, PPA, CDS, monthly clearance,
                exemption, passing out, portal support and the NYSC
                Bye-Laws.
            </p>
            <ul>
                <li>Type a question in the chat box.</li>
                <li>Select one of the quick questions.</li>
                <li>Ask follow-up questions where necessary.</li>
                <li>
                    Confirm time-sensitive information through official
                    NYSC channels.
                </li>
            </ul>
        </div>
        """,
        unsafe_allow_html=True,
    )

# Display all messages already stored in the current conversation.
selected_follow_up = None
last_message_index = len(st.session_state.messages) - 1

for message_index, message in enumerate(st.session_state.messages):
    with st.chat_message(message["role"]):
        if message["role"] == "user":
            st.write(message["content"])
        else:
            display_assistant_message(
                message,
                message_index,
                developer_mode,
            )

    response_type = message.get("response_type", "rag")
    is_latest_successful_rag = (
        message_index == last_message_index
        and message.get("role") == "assistant"
        and response_type == "rag"
    )

    if is_latest_successful_rag:
        follow_up_questions = get_follow_up_questions(message)
        follow_up_columns = st.columns(len(follow_up_questions))

        for follow_up_index, follow_up_question in enumerate(
            follow_up_questions
        ):
            with follow_up_columns[follow_up_index]:
                if st.button(
                    follow_up_question,
                    key=f"follow_up_{follow_up_index}",
                    use_container_width=True,
                ):
                    selected_follow_up = follow_up_question


prompt = st.chat_input("Ask an NYSC-related question...")
question = prompt or selected_question or selected_follow_up


if question:
    user_message = {
        "role": "user",
        "content": question,
    }
    st.session_state.messages.append(user_message)

    with st.chat_message("user"):
        st.write(question)

    with st.status(
        "Understanding your question",
        expanded=True,
    ) as processing_status:
        st.write("1. Understanding your question")
        st.write("2. Searching the verified NYSC knowledge base")
        st.write("3. Retrieving the most relevant information")
        result = chat_service.ask(
            question,
            response_mode=selected_response_mode,
        )
        st.write("4. Preparing your response")
        processing_status.update(
            label="Response ready",
            state="complete",
            expanded=False,
        )

    # Preserve the existing assistant-message and session-state structure.
    assistant_message = {
        "role": "assistant",
        "content": result["answer"],
        "confidence": result["confidence"],
        "response_time": result["response_time"],
        "sources": result["sources"],
        "response_type": result.get("response_type", "rag"),
        "generation_mode": result.get(
            "generation_mode",
            "unavailable",
        ),
        "requested_response_mode": result.get(
            "requested_response_mode",
            selected_response_mode,
        ),
        "topic": result.get("topic"),
        "cache_hit": result.get("cache_hit", False),
        "feedback": None,
        "success": result.get("success", True),
    }
    st.session_state.messages.append(assistant_message)

    with st.chat_message("assistant"):
        display_assistant_message(
            assistant_message,
            len(st.session_state.messages) - 1,
            developer_mode,
        )


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
