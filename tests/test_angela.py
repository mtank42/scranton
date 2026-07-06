"""Send Angela: the export seam and the delivery endpoint."""

from datetime import datetime, timezone

import pytest

from backend.app.adapters.export.base import export_filename, slugify
from backend.app.adapters.export.html import HtmlExporter
from backend.app.adapters.export.markdown import MarkdownExporter
from backend.app.domain.models import DataType
from backend.app.domain.schemas import PamSource, SummaryResponse, SummarySection
from backend.app.services.angela_service import AngelaService, UnknownFormatError


def sample_summary() -> SummaryResponse:
    """A small filled summary, with content that needs HTML escaping."""
    return SummaryResponse(
        template_id="client_file",
        title="Client File",
        target_label="Stone & Son Suit Warehouse",
        generated_at=datetime(2026, 7, 6, 12, 0, tzinfo=timezone.utc),
        window_days=None,
        sections=[
            SummarySection(heading="Commitments made", content="Revised quote promised [1]."),
            SummarySection(heading="Recent activity", content="Nothing recorded yet."),
        ],
        sources=[
            PamSource(
                segment_id=1,
                entry_id=1,
                content="Promised Stone & Son a revised <quote>.",
                data_type=DataType.COLD,
                sensitivity_level=1,
                created_at=datetime(2026, 6, 20, 9, 0),
            )
        ],
    )


def test_markdown_export_carries_the_whole_document():
    """Title, provenance, sections, numbered sources: paste-anywhere ready."""
    file = MarkdownExporter().render(sample_summary())

    text = file.content.decode()
    assert file.filename == "scranton_client_file_stone-son-suit-warehouse_20260706.md"
    assert "# Client File - Stone & Son Suit Warehouse" in text
    assert "## Commitments made" in text
    assert "Revised quote promised [1]." in text
    assert "1. (2026-06-20) [cold] Promised Stone & Son a revised <quote>." in text
    assert "Delivered by Send Angela" in text


def test_html_export_is_standalone_and_escaped():
    """One self-contained printable page; model text never becomes markup."""
    file = HtmlExporter().render(sample_summary())

    html = file.content.decode()
    assert file.filename.endswith(".html")
    assert html.startswith("<!doctype html>")
    assert "<h2>Commitments made</h2>" in html
    # The angle brackets in the source content must arrive escaped.
    assert "&lt;quote&gt;" in html
    assert "<quote>" not in html.split("<style>")[1]


def test_slug_and_filename_helpers():
    """Slugs stay filesystem-safe whatever the entity name throws at them."""
    assert slugify("Stone & Son Suit Warehouse") == "stone-son-suit-warehouse"
    assert slugify("---") == "summary"
    no_target = sample_summary().model_copy(update={"target_label": None})
    assert export_filename(no_target, "md") == "scranton_client_file_20260706.md"


def test_unknown_format_fails_loudly():
    """A typo in the format names the available ones."""
    service = AngelaService(summary_service=None)  # never reached
    with pytest.raises(UnknownFormatError, match="md"):
        service.export("client_file", 1, "docx")


def test_export_endpoint_delivers_an_attachment(app, client):
    """Empty memory still exports honestly; headers make it a download."""
    from backend.app.domain.models import TeamMember

    with app.state.session_factory() as session:
        session.add(TeamMember(full_name="Kelly"))
        session.commit()

    response = client.get(
        "/api/v1/angela/export/team_member_file",
        params={"target_id": 1, "format": "md"},
    )

    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "scranton_team_member_file_kelly_" in response.headers["content-disposition"]
    assert "Nothing recorded yet." in response.text

    assert client.get("/api/v1/angela/export/nope").status_code == 404
    assert (
        client.get(
            "/api/v1/angela/export/team_member_file",
            params={"target_id": 1, "format": "docx"},
        ).status_code
        == 422
    )