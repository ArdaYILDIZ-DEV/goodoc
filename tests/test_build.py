"""Tests for goodoc build helpers — pure functions with no I/O side effects.

Covers: sanitize_title, get_title_from_text, get_excerpt_from_text, format_date.
"""
import build


class TestSanitizeTitle:
    """sanitize_title must strip dangerous characters and truncate safely."""

    def test_strips_quotes_backticks_and_equals(self):
        # Quotes, backticks and '=' would break pandoc --metadata title=
        assert build.sanitize_title('a\"b\'c`d=e') == "abcde"

    def test_strips_newlines_and_control_chars(self):
        assert build.sanitize_title("hello\nworld") == "hello world"
        assert build.sanitize_title("a\x00b\x1fc") == "abc"

    def test_trims_whitespace(self):
        assert build.sanitize_title("  hello  ") == "hello"

    def test_truncates_at_word_boundary(self):
        long = "word " * 40  # 200 chars
        result = build.sanitize_title(long, limit=20)
        assert len(result) <= 20
        # truncated result must not end mid-word when possible
        assert not result.endswith("wor")

    def test_short_string_unchanged(self):
        assert build.sanitize_title("Hello World") == "Hello World"

    def test_empty_string(self):
        assert build.sanitize_title("") == ""


class TestGetTitleFromText:
    """Title extraction prefers YAML front matter, then first H1, then fallback."""

    def test_yaml_title_takes_precedence_over_heading(self):
        text = '---\ntitle: YAML Title\n---\n# Heading Title\n'
        assert build.get_title_from_text(text) == "YAML Title"

    def test_yaml_title_with_quotes(self):
        text = 'title: \"Quoted Title\"\n# Heading\n'
        assert build.get_title_from_text(text) == "Quoted Title"

    def test_yaml_title_single_quotes(self):
        text = "title: 'Single Quoted'\n"
        assert build.get_title_from_text(text) == "Single Quoted"

    def test_heading_extraction(self):
        assert build.get_title_from_text("# My Heading\nSome body") == "My Heading"

    def test_heading_strips_html_tags(self):
        text = '# Hello <span class="yell">World</span>\n'
        assert build.get_title_from_text(text) == "Hello World"

    def test_fallback_when_no_title_or_heading(self):
        assert build.get_title_from_text("Just body text", fallback="fallback") == "fallback"

    def test_empty_text_returns_fallback(self):
        assert build.get_title_from_text("", fallback="fb") == "fb"

    def test_sanitize_applied_to_heading(self):
        # Heading with quotes should have them stripped
        assert build.get_title_from_text('# A \"quoted\" heading') == "A quoted heading"


class TestGetExcerptFromText:
    """Excerpt must strip markup and truncate at word boundary with ellipsis."""

    def test_strips_front_matter(self):
        text = "---\ntitle: Foo\n---\nReal content here"
        result = build.get_excerpt_from_text(text)
        assert "title" not in result.lower() or "Real content" in result
        assert "Real content" in result

    def test_strips_code_fences(self):
        text = "Intro\n```python\ncode here\n```\nOutro"
        result = build.get_excerpt_from_text(text)
        assert "code here" not in result
        assert "Intro" in result

    def test_strips_html_tags(self):
        assert build.get_excerpt_from_text('<p class="lede">Hello</p>') == "Hello"

    def test_truncates_with_ellipsis(self):
        long = "word " * 100
        result = build.get_excerpt_from_text(long, limit=20)
        assert result.endswith("…")
        assert len(result) <= 21  # limit + ellipsis

    def test_short_text_unchanged(self):
        assert build.get_excerpt_from_text("Short text") == "Short text"

    def test_collapses_whitespace(self):
        assert build.get_excerpt_from_text("a  \n  b\t c") == "a b c"

    def test_empty_text(self):
        assert build.get_excerpt_from_text("") == ""


class TestFormatDate:
    """format_date must return YYYY-MM-DD from file mtime."""

    def test_returns_iso_date(self, tmp_path):
        p = tmp_path / "file.md"
        p.write_text("hello")
        result = build.format_date(p)
        # Should match YYYY-MM-DD
        import re

        assert re.match(r"^\d{4}-\d{2}-\d{2}$", result), result


# ---------------------------------------------------------------------------
# Tree / rendering helpers
# ---------------------------------------------------------------------------


class TestHasActive:
    """has_active must detect whether the current page is inside a subtree."""

    def test_detects_active_file_in_subtree(self, tmp_path, monkeypatch):
        # Build a minimal tree that points into tmp_path, patch BUILD to tmp_path
        monkeypatch.setattr(build, "BUILD", tmp_path)
        target = tmp_path / "docs" / "page.html"
        target.parent.mkdir(parents=True)
        target.write_text("x")

        # Tree with one file whose rel is docs/page.md -> BUILD/docs/page.html
        from pathlib import Path

        node = {
            "docs": {
                "type": "dir",
                "children": {
                    "page": {
                        "type": "file",
                        "rel": Path("docs/page.md"),
                        "title": "Page",
                        "mtime": 0,
                    }
                },
            }
        }
        # Current page is exactly that file
        assert build.has_active(node, target) is True
        # Different page is not active
        other = tmp_path / "other.html"
        other.write_text("y")
        assert build.has_active(node, other) is False

    def test_empty_node_not_active(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "BUILD", tmp_path)
        assert build.has_active({}, tmp_path / "index.html") is False


class TestRenderTree:
    """render_tree must produce sorted, escaped, linked HTML."""

    def test_renders_file_links_with_escaping(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "BUILD", tmp_path)
        monkeypatch.setattr(build, "md_files_global", [])
        from pathlib import Path

        node = {
            "b_file": {
                "type": "file",
                "rel": Path("b.md"),
                "title": "B & Title",
                "mtime": 0,
            },
            "a_file": {
                "type": "file",
                "rel": Path("a.md"),
                "title": "A Title",
                "mtime": 0,
            },
        }
        current = tmp_path / "index.html"
        current.write_text("x")
        html = build.render_tree(node, current)
        # Sorted case-insensitively: a before b
        assert html.index("A Title") < html.index("B &amp; Title")
        # Ampersand must be escaped
        assert "B &amp; Title" in html
        assert "B & Title" not in html.replace("&amp;", "")

    def test_active_file_gets_is_active_class(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "BUILD", tmp_path)
        monkeypatch.setattr(build, "md_files_global", [])
        from pathlib import Path

        node = {
            "page": {"type": "file", "rel": Path("page.md"), "title": "Page", "mtime": 0}
        }
        current = tmp_path / "page.html"
        current.write_text("x")
        html = build.render_tree(node, current)
        assert "is-active" in html

    def test_folder_aria_expanded_false_when_not_active(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "BUILD", tmp_path)
        monkeypatch.setattr(build, "md_files_global", [])
        from pathlib import Path

        node = {
            "docs": {
                "type": "dir",
                "children": {
                    "page": {"type": "file", "rel": Path("docs/page.md"), "title": "P", "mtime": 0}
                },
            }
        }
        current = tmp_path / "other.html"
        current.write_text("x")
        html = build.render_tree(node, current)
        assert 'aria-expanded="false"' in html

    def test_escapes_folder_names(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "BUILD", tmp_path)
        monkeypatch.setattr(build, "md_files_global", [])
        from pathlib import Path

        node = {
            "a<b": {
                "type": "dir",
                "children": {
                    "f": {"type": "file", "rel": Path("a<b/f.md"), "title": "F", "mtime": 0}
                },
            }
        }
        current = tmp_path / "index.html"
        current.write_text("x")
        html = build.render_tree(node, current)
        assert "a&lt;b" in html


class TestBuildPageShell:
    """build_page_shell must assemble a complete, escaped HTML document."""

    def test_escapes_title(self):
        html = build.build_page_shell(
            title='A & B <test>',
            sidebar_html="<ul></ul>",
            body_html="<p>hi</p>",
            css_rel="retro-doc.css",
            js_rel="lightbox.js",
        )
        assert "A &amp; B &lt;test&gt;" in html
        assert "<title>A &amp; B &lt;test&gt;</title>" in html

    def test_includes_sidebar_and_body(self):
        html = build.build_page_shell(
            title="T",
            sidebar_html='<ul class="contentTree"><li>x</li></ul>',
            body_html="<h1>Hello</h1>",
            css_rel="retro-doc.css",
            js_rel="lightbox.js",
        )
        assert '<ul class="contentTree">' in html
        assert "<h1>Hello</h1>" in html

    def test_includes_sidebar_script_and_preconnect(self):
        html = build.build_page_shell(
            title="T",
            sidebar_html="",
            body_html="",
            css_rel="c.css",
            js_rel="j.js",
        )
        assert "sidebar-toggle" in html
        assert "preconnect" in html
        assert 'href="c.css"' in html
        assert 'src="j.js"' in html


# ---------------------------------------------------------------------------
# Attachment resolution
# ---------------------------------------------------------------------------


class TestResolveAttachment:
    """resolve_attachment must handle external URLs, local files and traversal."""

    def test_external_urls_return_none(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# hi")
        out = tmp_path / "out.html"
        skip_srcs = [
            "https://example.com/img.png",
            "http://x/img.png",
            "data:image/png;base64,abc",
            "#anchor",
            "/absolute/path.png",
        ]
        for src in skip_srcs:
            found, new = build.resolve_attachment(md, src, out)
            assert found is None and new is None, f"should skip {src}"

    def test_empty_and_query_only_returns_none(self, tmp_path):
        md = tmp_path / "doc.md"
        md.write_text("# hi")
        out = tmp_path / "out.html"
        found, new = build.resolve_attachment(md, "", out)
        assert found is None
        found, new = build.resolve_attachment(md, "?v=1", out)
        assert found is None

    def test_resolves_sibling_file(self, tmp_path, monkeypatch):
        # Arrange: content dir with md and sibling image
        content = tmp_path / "content"
        content.mkdir()
        md = content / "page.md"
        md.write_text("# Title")
        img = content / "photo.png"
        img.write_bytes(b"\x89PNG fake")
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", build_dir)
        monkeypatch.setattr(build, "ROOT", tmp_path)
        out = build_dir / "page.html"
        found, new = build.resolve_attachment(md, "photo.png", out)
        assert found is not None
        assert new is not None
        # Destination should have been copied
        assert (build_dir / "photo.png").exists()

    def test_resolves_per_folder_attachments(self, tmp_path, monkeypatch):
        content = tmp_path / "content"
        docs = content / "docs"
        docs.mkdir(parents=True)
        md = docs / "page.md"
        md.write_text("# Title")
        attach = docs / "_attachments" / "img.png"
        attach.parent.mkdir(parents=True)
        attach.write_bytes(b"fake")
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", build_dir)
        monkeypatch.setattr(build, "ROOT", tmp_path)
        out = build_dir / "docs" / "page.html"
        out.parent.mkdir(parents=True)
        found, new = build.resolve_attachment(md, "_attachments/img.png", out)
        assert found is not None
        assert new is not None

    def test_returns_none_when_not_found(self, tmp_path, monkeypatch):
        content = tmp_path / "content"
        content.mkdir()
        md = content / "page.md"
        md.write_text("# hi")
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", build_dir)
        monkeypatch.setattr(build, "ROOT", tmp_path)
        out = build_dir / "page.html"
        found, new = build.resolve_attachment(md, "nonexistent.png", out)
        assert found is None and new is None


# ---------------------------------------------------------------------------
# File helpers and recent cards
# ---------------------------------------------------------------------------


class TestGetTitleFile:
    """get_title reads a file and extracts its title."""

    def test_reads_yaml_title(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("---\ntitle: My Doc\n---\n# Heading\n")
        assert build.get_title(p) == "My Doc"

    def test_falls_back_to_stem_on_missing_file(self, tmp_path):
        p = tmp_path / "nope.md"
        # Do not create the file — should return stem
        assert build.get_title(p) == "nope"


class TestGetExcerptFile:
    def test_reads_excerpt(self, tmp_path):
        p = tmp_path / "doc.md"
        p.write_text("# Title\nThis is the body text for excerpt.")
        result = build.get_excerpt(p)
        assert "body text" in result

    def test_missing_file_returns_empty(self, tmp_path):
        p = tmp_path / "nope.md"
        assert build.get_excerpt(p) == ""


class TestRenderRecentCards:
    """render_recent_cards must escape HTML and honour cache."""

    def test_escapes_title_and_excerpt(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "CONTENT", tmp_path / "content")
        monkeypatch.setattr(build, "BUILD", tmp_path / "build")
        # Prepare content file with special chars — note get_title_from_text
        # strips HTML tags, so <test> is removed and only "A & B" remains
        content = tmp_path / "content"
        content.mkdir()
        md = content / "page.md"
        md.write_text('# A & B <test>\nBody with <b>html</b> and more text.')
        monkeypatch.setattr(build, "file_text_cache", {md: md.read_text()})
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        html = build.render_recent_cards([md], build_dir)
        assert "A &amp; B" in html
        assert "<b>" not in html  # should be stripped/escaped

    def test_uses_cache_when_available(self, tmp_path, monkeypatch):
        content = tmp_path / "content"
        content.mkdir()
        md = content / "page.md"
        md.write_text("# Cached Title\nBody")
        monkeypatch.setattr(build, "CONTENT", content)
        monkeypatch.setattr(build, "BUILD", tmp_path / "build")
        (tmp_path / "build").mkdir()
        # Pre-populate cache with different text than on disk
        monkeypatch.setattr(build, "file_text_cache", {md: "# Overridden Title\nOverridden body"})
        html = build.render_recent_cards([md], tmp_path / "build")
        assert "Overridden Title" in html

    def test_empty_list_returns_empty(self, tmp_path, monkeypatch):
        monkeypatch.setattr(build, "CONTENT", tmp_path / "content")
        monkeypatch.setattr(build, "BUILD", tmp_path / "build")
        monkeypatch.setattr(build, "file_text_cache", {})
        assert build.render_recent_cards([], tmp_path / "build") == ""


class TestCheckBrokenLinks:
    """_check_broken_links must ignore external URLs and flag only missing local files."""

    def test_returns_empty_when_no_broken_links(self, tmp_path):
        # Valid relative link resolves inside build dir
        (tmp_path / "page.html").write_text('<a href="other.html">link</a>')
        (tmp_path / "other.html").write_text("<p>ok</p>")
        assert build._check_broken_links(tmp_path) == []

    def test_flags_missing_local_file(self, tmp_path):
        (tmp_path / "page.html").write_text('<a href="missing.html">x</a>')
        broken = build._check_broken_links(tmp_path)
        assert len(broken) == 1
        assert "missing.html" in broken[0]

    def test_ignores_external_and_fragment_links(self, tmp_path):
        (tmp_path / "page.html").write_text(
            '<a href="https://example.com/x">e</a>'
            '<a href="#section">f</a>'
            '<a href="mailto:a@b.c">m</a>'
            '<img src="data:image/png;base64,abc">'
        )
        assert build._check_broken_links(tmp_path) == []

    def test_strips_query_and_fragment_before_lookup(self, tmp_path):
        (tmp_path / "page.html").write_text('<a href="other.html?x=1#top">x</a>')
        (tmp_path / "other.html").write_text("<p>ok</p>")
        assert build._check_broken_links(tmp_path) == []

    def test_ignores_paths_outside_build(self, tmp_path):
        # Link to a file outside build dir should not be flagged
        (tmp_path / "page.html").write_text('<a href="../outside.html">x</a>')
        assert build._check_broken_links(tmp_path) == []
