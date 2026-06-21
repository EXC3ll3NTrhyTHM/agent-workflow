"""Load a résumé from a PDF or plain-text / Markdown file into text."""

from __future__ import annotations

from pathlib import Path


def load_resume(path: str | Path) -> str:
    """Return the résumé as plain text.

    Supports PDF (.pdf) and text formats (.txt, .md). PDF is parsed with pypdf;
    layout-heavy PDFs may extract imperfectly — plain text is the safest input.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Résumé not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return _load_pdf(path)
    if suffix in {".txt", ".md", ".markdown"}:
        return path.read_text(encoding="utf-8")

    raise ValueError(f"Unsupported résumé format: {suffix} (use .pdf, .txt, or .md)")


def _load_pdf(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(pages).strip()
    if not text:
        raise ValueError(
            f"No extractable text in {path}. Is it a scanned image? "
            "Try exporting a text-based PDF or supplying a .txt/.md résumé."
        )
    return text
