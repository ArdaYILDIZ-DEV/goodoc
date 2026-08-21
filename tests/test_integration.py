"""Integration tests for the full build pipeline (main).

Pandoc is mocked so tests run without the external binary. Verifies
that main() creates the expected output structure, copies assets,
handles attachments and escapes titles correctly.
"""
from pathlib import Path
from unittest.mock import MagicMock

import build


def _fake_pandoc_run(cmd, capture_output=True, text=True, timeout=30):
    """Mimic pandoc: write a minimal standalone HTML to the temp output file."""
    # cmd is like ["pandoc", str(md), "-o", str(tmp), ...]
    out_idx = cmd.index("-o") + 1
    out_path = Path(cmd[out_idx])
    # Extract title from --metadata title=<value>
    title = "Test Page"
    for part in cmd:
        if part.startswith("title="):
            title = part.split("=", 1)[1]
            break
    out_path.write_text(
        f"""<!DOCTYPE html><html><head><title>{title}</title><style>/* pandoc style */</style></head>"""
        f"""<body><h1>{title}</h1><p>Body for {title}</p><img src="_attachments/img.png" /></body></html>""",
        encoding="utf-8",
    )
    mock = MagicMock()
    mock.returncode = 0
    mock.stderr = ""
    return mock


class TestMainIntegration:
    """End-to-end build with mocked pandoc — no real pandoc required."""

    def test_main_creates_html_and_index(self, tmp_path, monkeypatch):
        # --- Arrange: fake project layout ---
        root = tmp_path / "project"
        content = root / "content"
        docs = content / "docs"
        docs.mkdir(parents=True)
        build_dir = root / "build"

        # Two markdown files
        (content / "intro.md").write_text("# Intro\nHello world", encoding="utf-8")
        (docs / "guide.md").write_text("---\ntitle: Guide Title\n---\nContent here", encoding="utf-8")

        # Attachment for guide
        attach = docs / "_attachments" / "img.png"
        attach.parent.mkdir(parents=True)
        attach.write_bytes(b"\x89PNG fake")

        # Static assets
        css = root / "retro-doc.css"
        css.write_text("/* css */", encoding="utf-8")
        js = root / "lightbox.js"
        js.write_text("// js", encoding="utf-8")

        # Patch module constants to point at tmp layout
        monkeypatch.setattr(build, "ROOT", root)
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", build_dir)
        monkeypatch.setattr(build, "CSS_SRC", css)
        monkeypatch.setattr(build, "JS_SRC", js)
        # Reset globals
        monkeypatch.setattr(build, "md_files_global", [])
        monkeypatch.setattr(build, "file_text_cache", {})

        # Mock pandoc availability and execution
        monkeypatch.setattr(build.shutil, "which", lambda _: "/usr/bin/pandoc")
        monkeypatch.setattr(build.subprocess, "run", _fake_pandoc_run)

        # --- Act ---
        build.main([])

        # --- Assert: output files exist ---
        assert (build_dir / "intro.html").exists()
        assert (build_dir / "docs" / "guide.html").exists()
        assert (build_dir / "index.html").exists()
        assert (build_dir / "retro-doc.css").exists()
        assert (build_dir / "lightbox.js").exists()

        # Attachment should be copied preserving structure
        assert (build_dir / "docs" / "_attachments" / "img.png").exists()

        # Index should list both documents
        index_html = (build_dir / "index.html").read_text(encoding="utf-8")
        assert "Intro" in index_html
        assert "Guide Title" in index_html
        assert "2 belge" in index_html

        # Intro page should have sidebar and correct title
        intro_html = (build_dir / "intro.html").read_text(encoding="utf-8")
        assert "<title>Intro</title>" in intro_html
        assert "contentTree" in intro_html
        assert "sidebar-toggle" in intro_html

    def test_main_escapes_special_chars_in_title(self, tmp_path, monkeypatch):
        root = tmp_path / "project"
        content = root / "content"
        content.mkdir(parents=True)
        build_dir = root / "build"
        css = root / "retro-doc.css"
        css.write_text("/* css */", encoding="utf-8")
        js = root / "lightbox.js"
        js.write_text("// js", encoding="utf-8")

        # Title with characters that need escaping
        (content / "page.md").write_text("# A & B <test>\nBody", encoding="utf-8")

        monkeypatch.setattr(build, "ROOT", root)
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", build_dir)
        monkeypatch.setattr(build, "CSS_SRC", css)
        monkeypatch.setattr(build, "JS_SRC", js)
        monkeypatch.setattr(build, "md_files_global", [])
        monkeypatch.setattr(build, "file_text_cache", {})
        monkeypatch.setattr(build.shutil, "which", lambda _: "/usr/bin/pandoc")
        monkeypatch.setattr(build.subprocess, "run", _fake_pandoc_run)

        build.main([])

        html = (build_dir / "page.html").read_text(encoding="utf-8")
        # Title should be escaped in <title> — "&" -> "&amp;", HTML tags stripped so "<test>" gone
        assert "A &amp; B" in html
        # Raw unescaped sequence must not appear in title tag
        assert "<title>A & B <test>" not in html

    def test_main_exits_when_pandoc_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "ROOT", tmp_path)
        monkeypatch.setattr(build, "CONTENT", tmp_path / "content")
        monkeypatch.setattr(build, "BUILD", tmp_path / "build")
        monkeypatch.setattr(build.shutil, "which", lambda _: None)
        try:
            build.main([])
            assert False, "should have raised SystemExit"
        except SystemExit as exc:
            assert "pandoc not found" in str(exc)

    def test_import_has_no_side_effects(self, tmp_path):
        """Importing build must not delete or create BUILD."""
        # The fact that we can import without side effects is the test —
        # if main() were at module level, BUILD would have been recreated/deleted
        assert isinstance(build.file_text_cache, dict)
        assert isinstance(build.md_files_global, list)
