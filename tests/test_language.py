"""Answer-language pinning: the detector and its injection into prompts."""

from backend.app.services.language import dominant_language
from backend.app.services.prompts import build_pam_messages, build_summary_messages


def test_french_text_is_detected():
    """Plain French wins on stopword votes."""
    assert dominant_language("Quand est-ce que Kevin a demandé à me parler ?") == "French"


def test_english_text_is_detected():
    """Plain English wins on stopword votes."""
    assert dominant_language("What did we promise to the client last week?") == "English"


def test_marker_free_text_falls_back_to_accents():
    """Bare names and dates: any French accent tips the scale."""
    assert dominant_language("Kevin - livraison Dubreuil terminée 2026-05-02") == "French"
    assert dominant_language("Kevin - Dubreuil delivery 2026-05-02") == "English"


def test_pam_messages_pin_the_question_language():
    """The pin is explicit in the user message, per the tuning decision."""
    messages = build_pam_messages(
        "Qu'avons-nous promis à Stone & Son ?", "[1] (2026-05-02) extrait"
    )
    assert "ANSWER LANGUAGE: French" in messages[-1]["content"]

    messages = build_pam_messages("What did we promise?", "[1] excerpt")
    assert "ANSWER LANGUAGE: English" in messages[-1]["content"]


def test_summary_messages_pin_the_excerpt_language():
    """Summaries follow the excerpts (not the English template headings)."""
    messages = build_summary_messages(
        title="Team member file",
        target_label="Kevin",
        sections=("Recent facts", "Signals"),
        context_block="[1] (2026-05-02) Kevin a demandé à me parler, je le rappelle lundi.",
    )
    content = messages[-1]["content"]
    assert "DOCUMENT LANGUAGE: French" in content
    assert "Headings stay exactly as given" in content
