"""Text extraction from uploaded files (task 3.2)."""

import io
import zipfile

import docx
import pytest

from nfactory_core.knowledge import ExtractionError, extract


def _pdf(pages: list[str]) -> bytes:
    """A minimal valid PDF with one text line per page (no PDF writer dependency)."""
    objects: list[bytes] = []
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages)))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font = 3 + 2 * len(pages)
    for i, text in enumerate(pages):
        content = 4 + 2 * i
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content} 0 R "
            f"/Resources << /Font << /F1 {font} 0 R >> >> >>".encode()
        )
        stream = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode()
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    )
    return out.getvalue()


def _docx() -> bytes:
    document = docx.Document()
    document.add_heading("Procédure VPN", level=1)
    document.add_paragraph("Ouvrir le client et choisir le profil Siège.")
    document.add_heading("Dépannage", level=2)
    document.add_paragraph("Redémarrer le service si la connexion échoue.")
    out = io.BytesIO()
    document.save(out)
    return out.getvalue()


def test_markdown_is_kept_as_text() -> None:
    result = extract("guide.md", b"# Titre\n\nCorps du guide.\n")

    assert result.kind == "markdown"
    assert result.text.splitlines()[0] == "# Titre"


def test_text_decodes_utf8_with_bom_and_windows_1252() -> None:
    assert extract("a.txt", "﻿été".encode()).text == "été"
    assert extract("b.txt", "café".encode("cp1252")).text == "café"


def test_code_gets_its_language() -> None:
    result = extract("src/app/main.py", b"def run():\n    return 1\n")

    assert (result.kind, result.language) == ("code", "python")
    assert extract("deploy.ps1", b"Write-Host 'ok'\n").language == "powershell"


def test_pdf_text_is_extracted_page_by_page() -> None:
    result = extract("rapport.pdf", _pdf(["Premiere page", "Seconde page"]))

    assert result.kind == "pdf"
    assert "Premiere page" in result.text and "Seconde page" in result.text
    second = next(i for i, line in enumerate(result.text.splitlines(), 1) if "Seconde" in line)
    assert result.page_at(second) == 2
    assert result.page_at(1) == 1


def test_docx_headings_become_markdown_sections() -> None:
    result = extract("procedure.docx", _docx())

    lines = result.text.splitlines()
    assert result.kind == "docx"
    assert "# Procédure VPN" in lines
    assert "## Dépannage" in lines
    assert "Redémarrer le service si la connexion échoue." in lines


@pytest.mark.parametrize(
    ("name", "data", "code"),
    [
        ("photo.png", b"\x89PNG\r\n", "unsupported_file_type"),
        ("notes.txt", b"abc\x00def", "binary_content"),
        ("vide.md", b"   \n", "empty_document"),
        ("faux.pdf", b"not a pdf", "unreadable_document"),
        ("faux.docx", b"not a zip", "unreadable_document"),
    ],
)
def test_bad_files_are_refused_with_a_code(name: str, data: bytes, code: str) -> None:
    with pytest.raises(ExtractionError) as caught:
        extract(name, data)

    assert caught.value.code == code


def test_oversized_upload_is_refused() -> None:
    with pytest.raises(ExtractionError) as caught:
        extract("big.txt", b"a" * (10 * 1024 * 1024 + 1))

    assert caught.value.code == "file_too_large"


def test_zip_bomb_docx_is_refused_before_parsing() -> None:
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("word/document.xml", b"0" * (60 * 1024 * 1024))

    with pytest.raises(ExtractionError) as caught:
        extract("bombe.docx", out.getvalue())

    assert caught.value.code == "file_too_large"
