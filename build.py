#!/usr/bin/env python3
"""Build a static site from Markdown content via pandoc.

content/*.md -> build/*.html; static assets are copied and the
sidebar tree plus "Recent" index pages are generated.
"""
import argparse
import html
import re
import shutil
import subprocess
import sys
import os
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).parent.resolve()
CONTENT = ROOT / "content"
BUILD = ROOT / "build"
CSS_SRC = ROOT / "retro-doc.css"
JS_SRC = ROOT / "lightbox.js"

# Internal constants
RECENT_LIMIT = 8
EXCERPT_LIMIT = 160  # unified excerpt length for all index pages

SIDEBAR_SCRIPT = """\
(function(){
  var btn=document.querySelector('.sidebar-toggle');
  var bar=document.getElementById('sidebar');
  var ov=document.getElementById('sidebarOverlay');
  function open(){
    bar.classList.add('is-open'); ov.classList.add('is-open');
    btn.setAttribute('aria-expanded','true'); document.body.style.overflow='hidden';
  }
  function close(){
    bar.classList.remove('is-open'); ov.classList.remove('is-open');
    btn.setAttribute('aria-expanded','false'); document.body.style.overflow='';
  }
  btn.addEventListener('click', function(){ bar.classList.contains('is-open') ? close() : open(); });
  ov.addEventListener('click', close);
  document.addEventListener('keydown', function(e){ if(e.key==='Escape') close(); });
  document.querySelectorAll('.tree-folder').forEach(function(b){
    b.addEventListener('click', function(){
      var e=b.getAttribute('aria-expanded')==='true';
      b.setAttribute('aria-expanded', e?'false':'true');
    });
  });
})();"""

PRECONNECT_LINKS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Special+Elite&family=JetBrains+Mono:wght@400;500;700;800&display=swap">"""


def sanitize_title(s: str, limit: int = 120) -> str:
    """Make a raw title safe for ``--metadata title=`` and HTML.

    Strips newlines, quotes, backticks, ``=`` and control characters;
    truncates at a word boundary so Pandoc metadata can never break the build.
    """
    s = re.sub(r'[\r\n]+', ' ', s)
    s = s.replace('"', '').replace("'", "").replace("`", "").replace("=", "")
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    s = s.strip()
    if len(s) > limit:
        s = s[:limit].rsplit(' ', 1)[0]
    return s


def get_title_from_text(text: str, fallback: str = "") -> str:
    """Extract the document title: YAML ``title:`` first, then the first ``#`` heading.

    Heading HTML tags are stripped because titles render verbatim in sidebar links.
    """
    m = re.search(r'^title:\s*[\"\']?(.+?)[\"\']?\s*$', text, re.MULTILINE)
    if m:
        return sanitize_title(m.group(1).strip(), limit=120)
    m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1))
        return sanitize_title(t.strip()[:80], limit=80)
    return fallback


def get_excerpt_from_text(text: str, limit: int = 160) -> str:
    """Build a plain-text excerpt for recent-list cards.

    Strips front matter, code fences, markup and extra whitespace; truncates
    at a word boundary with an ellipsis.
    """
    text = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL)
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[#>*_\-`\[\]\(\)]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > limit:
        return text[:limit].rsplit(' ', 1)[0] + "…"
    return text


def get_title(md_path: Path) -> str:
    """Read ``md_path`` and return its title; file stem on error."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_title read failed for {md_path}: {e}")
        return md_path.stem
    return get_title_from_text(text, fallback=md_path.stem)


def get_excerpt(md_path: Path, limit: int = 160) -> str:
    """Read ``md_path`` and return its excerpt; empty string on error."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_excerpt read failed for {md_path}: {e}")
        return ""
    return get_excerpt_from_text(text, limit=limit)


def format_date(p: Path) -> str:
    """Return the file's mtime as YYYY-MM-DD for recent-list cards."""
    ts = p.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d")


def has_active(node: dict, current_html: Path) -> bool:
    """True if any file in this subtree is the current page.

    Parent folders use it to stay expanded (aria-expanded) around the active branch.
    """
    for _, info in node.items():
        if info["type"] == "file":
            rel_md = info["rel"]
            target = BUILD / rel_md.with_suffix(".html")
            try:
                if current_html.resolve() == target.resolve():
                    return True
            except Exception:
                if str(current_html) == str(target):
                    return True
        else:
            if has_active(info["children"], current_html):
                return True
    return False


def render_tree(node: dict, current_html: Path, prefix: Path = Path(".")) -> str:
    """Render the sidebar as nested ``<ul>`` HTML, sorted case-insensitively.

    Links are relative to ``current_html.parent`` so they work at any depth;
    the active page gets ``is-active``, index pages expand the newest folder.
    """
    html_out = '<ul class="contentTree">\n'
    files = [(k, v) for k, v in node.items() if v["type"] == "file"]
    dirs = [(k, v) for k, v in node.items() if v["type"] == "dir"]
    files.sort(key=lambda x: x[0].lower())
    dirs.sort(key=lambda x: x[0].lower())
    for name, info in files + dirs:
        if info["type"] == "file":
            rel_md = info["rel"]
            target = BUILD / rel_md.with_suffix(".html")
            link_rel = os.path.relpath(target, start=current_html.parent)
            title = html.escape(info["title"])
            try:
                active = " is-active" if current_html.resolve() == target.resolve() else ""
            except Exception:
                active = " is-active" if str(current_html) == str(target) else ""
            html_out += f'  <li><a href="{link_rel}" class="tree-link{active}">{title}</a></li>\n'
        else:
            dir_path = prefix / name if prefix != Path(".") else Path(name)
            expanded = has_active(info["children"], current_html)
            if not expanded and current_html.name == "index.html":
                try:
                    most_recent = sorted(md_files_global, key=lambda p: p.stat().st_mtime, reverse=True)[0]
                    most_rel = most_recent.relative_to(CONTENT).parent
                    under = most_rel == dir_path or str(most_rel).startswith(str(dir_path) + "/")
                    if most_rel != Path(".") and under:
                        expanded = True
                except Exception:
                    pass
            aria = "true" if expanded else "false"
            html_out += f'  <li><button class="tree-folder" aria-expanded="{aria}">{html.escape(name)}</button>\n'
            html_out += render_tree(info["children"], current_html, dir_path)
            html_out += '  </li>\n'
    html_out += '</ul>\n'
    return html_out


def resolve_attachment(md_path: Path, src: str, html_path: Path) -> tuple[str | None, str | None]:
    """Resolve an image src against the canonical _attachments lookup order.

    Order: md sibling -> md_dir/_attachments/<name> -> mirrored/global
    content and root _attachments -> content/<clean> fallback. The first hit
    is copied into build/ (structure preserved). Returns (found_path,
    html_relative_src), or (None, None) for external/data/anchor sources.
    """
    if src.startswith(("http://", "https://", "data:", "#", "/")):
        return None, None
    clean = src.split("#")[0].split("?")[0]
    if not clean:
        return None, None
    clean_path = Path(clean)
    md_dir = md_path.parent
    rel_dir = md_path.parent.relative_to(CONTENT) if md_path.parent != CONTENT else Path(".")

    candidates: list[Path] = []
    candidates.append(md_dir / clean)
    candidates.append(md_dir / "_attachments" / clean_path.name)
    if len(clean_path.parts) > 1:
        candidates.append(md_dir / "_attachments" / clean)
    if rel_dir != Path("."):
        candidates.append(CONTENT / "_attachments" / rel_dir / clean_path.name)
        if len(clean_path.parts) > 1:
            candidates.append(CONTENT / "_attachments" / rel_dir / clean)
        candidates.append(ROOT / "_attachments" / rel_dir / clean_path.name)
        if len(clean_path.parts) > 1:
            candidates.append(ROOT / "_attachments" / rel_dir / clean)
    candidates.append(CONTENT / "_attachments" / clean_path.name)
    candidates.append(CONTENT / "_attachments" / clean)
    candidates.append(ROOT / "_attachments" / clean_path.name)
    candidates.append(ROOT / "_attachments" / clean)
    candidates.append(CONTENT / clean)

    # dedup preserving order
    seen: set[Path] = set()
    uniq: list[Path] = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    for cand in uniq:
        # normalize _attachments/_attachments duplication
        cand_str = str(cand)
        if "_attachments/_attachments" in cand_str:
            cand = Path(cand_str.replace("_attachments/_attachments", "_attachments"))

        # prevent directory traversal outside project
        try:
            cand_resolved = cand.resolve()
            inside_root = cand_resolved.is_relative_to(ROOT.resolve())
            inside_content = cand_resolved.is_relative_to(CONTENT.resolve())
            if not (inside_root or inside_content):
                # candidate points outside project — skip
                if cand.exists():
                    continue
        except Exception:
            pass

        if cand.exists() and cand.is_file():
            if cand.is_relative_to(CONTENT):
                dest = BUILD / cand.relative_to(CONTENT)
            elif cand.is_relative_to(ROOT / "_attachments"):
                dest = BUILD / "_attachments" / cand.relative_to(ROOT / "_attachments")
            else:
                try:
                    dest = BUILD / cand.relative_to(CONTENT)
                except Exception:
                    dest = BUILD / cand.name
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, dest)
            new_src = os.path.relpath(dest, start=html_path.parent)
            return str(cand), new_src
    return None, None


def render_recent_cards(md_list: list[Path], link_base: Path, link_prefix: str = "") -> str:
    """Render recent-card HTML for a list of markdown files.

    ``link_base`` is the directory links are relative to (BUILD or ROOT).
    ``link_prefix`` is prepended to hrefs when needed (e.g. ``build/`` for root index).
    Results are cached from the tree build to avoid re-reading files.
    """
    parts: list[str] = []
    for md in md_list:
        rel = md.relative_to(CONTENT)
        target = BUILD / rel.with_suffix(".html")
        if link_prefix:
            href = f"{link_prefix}{rel.with_suffix('.html')}"
        else:
            href = os.path.relpath(target, start=link_base)

        # reuse cached text when available
        cached = file_text_cache.get(md)
        if cached is not None:
            title = get_title_from_text(cached, fallback=md.stem)
            excerpt = get_excerpt_from_text(cached, limit=EXCERPT_LIMIT)
        else:
            try:
                txt = md.read_text(encoding="utf-8", errors="ignore")
                title = get_title_from_text(txt, fallback=md.stem)
                excerpt = get_excerpt_from_text(txt, limit=EXCERPT_LIMIT)
            except Exception as e:
                print(f"warn recent excerpt for {md}: {e}")
                title = md.stem
                excerpt = ""

        title_esc = html.escape(title)
        excerpt_esc = html.escape(excerpt)
        date = format_date(md)
        folder = html.escape(str(rel.parent) if rel.parent != Path(".") else "content")
        parts.append(
            f'  <article class="recent-card">\n'
            f'    <div class="recent-meta">'
            f'<span class="recent-folder">{folder}</span> \u2022 '
            f'<span class="recent-date">{date}</span></div>\n'
            f'    <h3 class="recent-title"><a href="{href}">{title_esc}</a></h3>\n'
            f'    <p class="recent-excerpt">{excerpt_esc}</p>\n'
            f'  </article>'
        )
    return "\n".join(parts)


def build_page_shell(
    *,
    title: str,
    sidebar_html: str,
    body_html: str,
    css_rel: str,
    js_rel: str,
    sidebar_title: str = "İçerik",
    sidebar_sub: str = "content /",
    doc_count: int = 0,
    pandoc_style: str = "",
) -> str:
    """Assemble a complete HTML document from parts."""
    title_esc = html.escape(title)
    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{title_esc}</title>
{PRECONNECT_LINKS}
<style>
{pandoc_style}
</style>
<link rel="stylesheet" href="{css_rel}" />
</head>
<body class="has-sheet">
<button class="sidebar-toggle" aria-label="Menüyü aç/kapat" aria-expanded="false">☰</button>
<div class="sidebar-overlay" id="sidebarOverlay"></div>
<div class="site-wrap">
  <nav class="sidebar" id="sidebar" aria-label="İçerik ağacı">
    <div class="sidebar-head">
      <div class="sidebar-head-text">
        <span class="sidebar-title">{html.escape(sidebar_title)}</span>
        <span class="sidebar-sub">{html.escape(sidebar_sub)}</span>
      </div>
      <a href="index.html" class="sidebar-home">Ana Sayfa</a>
    </div>
    {sidebar_html}
    <div class="sidebar-foot">{doc_count} belge</div>
  </nav>
  <main class="sheet site-main">
{body_html}
  </main>
</div>
<script src="{js_rel}"></script>
<script>
{SIDEBAR_SCRIPT}
</script>
</body>
</html>
"""


# Global populated inside main() — needed by render_tree
md_files_global: list[Path] = []
file_text_cache: dict[Path, str] = {}


def _check_broken_links(build_dir: Path) -> list[str]:
    """Scan built HTML for broken internal links.

    Only relative href/src without scheme are checked; external URLs,
    data:, mailto:, tel:, protocol-relative (//) and pure fragments are skipped.
    Query strings and hash fragments are stripped before FS lookup.
    """
    broken: list[str] = []
    html_files = list(build_dir.rglob("*.html"))
    link_re = re.compile(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    for html_path in html_files:
        try:
            text = html_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for m in link_re.finditer(text):
            raw = m.group(1).strip()
            if not raw or raw.startswith(("#", "data:", "mailto:", "tel:", "//")):
                continue
            if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", raw):
                continue  # external scheme (http:, https:, etc.)
            # Strip query and fragment, then skip if empty or absolute
            clean = raw.split("?", 1)[0].split("#", 1)[0].strip()
            if not clean or clean.startswith("/"):
                continue
            target = (html_path.parent / clean).resolve()
            # Only flag if the resolved target is inside build_dir and missing
            try:
                target.relative_to(build_dir.resolve())
            except ValueError:
                continue  # points outside build — not our concern
            if not target.exists():
                broken.append(f"{html_path.relative_to(build_dir)} -> {raw}")
    return broken


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build goodoc static site")
    parser.add_argument("--strict", action="store_true", help="fail on broken internal links")
    args = parser.parse_args(argv) if argv is not None else parser.parse_args()

    global md_files_global, file_text_cache

    if not shutil.which("pandoc"):
        raise SystemExit("pandoc not found — install with: sudo pacman -S pandoc (https://pandoc.org)")

    # Safe clean: refuse to delete anything outside the project or through a symlink.
    build_resolved = BUILD.resolve()
    root_resolved = ROOT.resolve()
    try:
        build_resolved.relative_to(root_resolved)
    except ValueError:
        raise RuntimeError(f"Refusing to clean BUILD outside project: BUILD={build_resolved} ROOT={root_resolved}")
    if BUILD.exists():
        if BUILD.is_symlink():
            raise RuntimeError(f"Refusing to delete symlinked BUILD: {BUILD}")
        if build_resolved == root_resolved:
            raise RuntimeError(f"Refusing to delete project root: {build_resolved}")
        shutil.rmtree(BUILD)
    BUILD.mkdir(parents=True, exist_ok=True)

    # Copy static assets to build root
    for src in [CSS_SRC, JS_SRC]:
        if src.exists():
            shutil.copy2(src, BUILD / src.name)

    # Copy content assets (non-md) preserving structure
    for p in CONTENT.rglob("*"):
        if p.is_file() and p.suffix.lower() != ".md":
            rel = p.relative_to(CONTENT)
            dest = BUILD / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)

    # Copy root _attachments if exists (merge)
    if (ROOT / "_attachments").exists():
        for p in (ROOT / "_attachments").rglob("*"):
            if p.is_file():
                rel = p.relative_to(ROOT / "_attachments")
                dest = BUILD / "_attachments" / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                if not dest.exists():
                    shutil.copy2(p, dest)

    # Collect markdown files
    md_files = sorted(CONTENT.rglob("*.md"))
    md_files_global = md_files
    print(f"\nFound {len(md_files)} markdown files in content/")

    # Build tree — each file's text is read once and cached
    tree: dict = {}
    for md in md_files:
        rel = md.relative_to(CONTENT)
        parts = rel.with_suffix("").parts
        cur = tree
        for i, part in enumerate(parts):
            is_file = (i == len(parts) - 1)
            if is_file:
                try:
                    txt = md.read_text(encoding="utf-8", errors="ignore")
                    file_text_cache[md] = txt
                    title = get_title_from_text(txt, fallback=md.stem)
                except Exception as e:
                    print(f"warn tree title for {md}: {e}")
                    title = md.stem
                cur[part] = {"type": "file", "md_path": md, "rel": rel, "title": title, "mtime": md.stat().st_mtime}
            else:
                if part not in cur:
                    cur[part] = {"type": "dir", "children": {}}
                cur = cur[part]["children"]

    # Generate HTML for each md
    built_html_paths: list[Path] = []
    for md in md_files:
        rel = md.relative_to(CONTENT)
        out = BUILD / rel.with_suffix(".html")
        out.parent.mkdir(parents=True, exist_ok=True)

        raw_md_text = file_text_cache.get(md)
        if raw_md_text is None:
            try:
                raw_md_text = md.read_text(encoding="utf-8", errors="ignore")
                file_text_cache[md] = raw_md_text
            except Exception as e:
                print(f"failed to read {md}: {e}")
                traceback.print_exc()
                continue
        title_raw = get_title_from_text(raw_md_text, fallback=md.stem)
        title = sanitize_title(title_raw, limit=120)

        tmp = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
                tmp = Path(tf.name)
            cmd = [
                "pandoc", str(md), "-o", str(tmp),
                "--standalone", "-c", "retro-doc.css",
                "--metadata", f"title={title}",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                print(f"pandoc failed for {md}: {result.stderr}")
                continue
            raw = tmp.read_text(encoding="utf-8")
        except subprocess.TimeoutExpired:
            print(f"pandoc timeout for {md} (30s)")
            traceback.print_exc()
            continue
        except Exception as e:
            print(f"pandoc error for {md}: {e}")
            traceback.print_exc()
            continue
        finally:
            if tmp is not None:
                try:
                    tmp.unlink(missing_ok=True)
                except Exception as e:
                    print(f"warn tmp cleanup: {e}")

        m_style = re.search(r"<style>(.*?)</style>", raw, re.DOTALL)
        pandoc_style = m_style.group(1) if m_style else ""
        m_body = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
        body_inner = m_body.group(1).strip() if m_body else raw

        css_rel = os.path.relpath(BUILD / "retro-doc.css", start=out.parent)
        js_rel = os.path.relpath(BUILD / "lightbox.js", start=out.parent)

        def repl_attr(m: re.Match[str]) -> str:
            attr = m.group(1)
            q = m.group(2)
            src = m.group(3)
            if src.startswith(("http", "data:")):
                return m.group(0)
            found, new_src = resolve_attachment(md, src, out)
            if new_src:
                return f'{attr}{q}{new_src}{q}'
            maybe = BUILD / src
            if maybe.exists():
                new_rel = os.path.relpath(maybe, start=out.parent)
                return f'{attr}{q}{new_rel}{q}'
            return m.group(0)

        body_inner = re.sub(r'((?:src|href)\s*=\s*)(["\'])([^"\']+)\2', repl_attr, body_inner)
        body_fixed = (
            body_inner.replace('src="lightbox.js"', f'src="{js_rel}"')
            .replace("src='lightbox.js'", f"src='{js_rel}'")
        )

        sidebar_tree = render_tree(tree, out)
        doc_title_match = re.search(r"<title>(.*?)</title>", raw, re.DOTALL)
        doc_title = doc_title_match.group(1).strip() if doc_title_match else title
        home_rel = os.path.relpath(BUILD / "index.html", start=out.parent)

        final = build_page_shell(
            title=doc_title,
            sidebar_html=sidebar_tree,
            body_html=body_fixed,
            css_rel=css_rel,
            js_rel=js_rel,
            sidebar_title="İçerik",
            sidebar_sub="content /",
            doc_count=len(md_files),
            pandoc_style=pandoc_style,
        )
        # Fix home link for nested pages (build_page_shell uses index.html)
        final = final.replace('href="index.html" class="sidebar-home"', f'href="{home_rel}" class="sidebar-home"', 1)

        out.write_text(final, encoding="utf-8")
        built_html_paths.append(out)
        print(f"built {out.relative_to(BUILD)}")

    # --- Build recent indexes ---
    recent = sorted(md_files, key=lambda p: p.stat().st_mtime, reverse=True)

    image_exts = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp"}
    total_images = 0
    seen_imgs: set[Path] = set()
    for base in [CONTENT / "_attachments", ROOT / "_attachments"] + list(CONTENT.rglob("_attachments")):
        if base.exists():
            for img in base.rglob("*"):
                if img.is_file() and img.suffix.lower() in image_exts:
                    try:
                        key = img.resolve()
                    except Exception:
                        key = img
                    if key not in seen_imgs:
                        seen_imgs.add(key)
                        total_images += 1

    # Extract pandoc style from first built page (no hardcoded path)
    pandoc_style_idx = ""
    if built_html_paths:
        try:
            txt = built_html_paths[0].read_text(encoding="utf-8")
            m = re.search(r"<style>(.*?)</style>", txt, re.DOTALL)
            if m:
                pandoc_style_idx = m.group(1)
        except Exception as e:
            print(f"warn pandoc_style_idx: {e}")

    recent_cards_build = render_recent_cards(recent[:RECENT_LIMIT], BUILD)
    recent_body_build = f"""\
<h1>Son <span class="yell">Eklenenler</span></h1>
<p class="lede">Son eklenen {len(recent[:RECENT_LIMIT])} belge (en yeni en üstte)</p>

<fieldset class="choice-group">
  <legend>Hızlı bakış</legend>
  <label class="choice">
    <input type="radio" name="recent" value="all" checked tabindex="-1"> {len(md_files)} belge
  </label>
  <label class="choice">
    <input type="radio" name="recent" value="attach" tabindex="-1">
    _attachments/ klasörlerinde {total_images} resim
  </label>
</fieldset>

<div class="recent-list">
{recent_cards_build}
</div>"""

    index_path = BUILD / "index.html"
    sidebar_for_index = render_tree(tree, index_path)
    css_rel_idx = os.path.relpath(BUILD / "retro-doc.css", start=BUILD)
    js_rel_idx = os.path.relpath(BUILD / "lightbox.js", start=BUILD)

    index_html = build_page_shell(
        title="Son Eklenenler — goodoc",
        sidebar_html=sidebar_for_index,
        body_html=recent_body_build,
        css_rel=css_rel_idx,
        js_rel=js_rel_idx,
        sidebar_title="İçerik",
        sidebar_sub="content /",
        doc_count=len(md_files),
        pandoc_style=pandoc_style_idx,
    )
    index_path.write_text(index_html, encoding="utf-8")
    print(f"built recent index -> {index_path} ({len(recent)} items)")

    # --- Strict: fail on broken internal links ---
    if args.strict:
        broken = _check_broken_links(BUILD)
        if broken:
            print("\nBROKEN LINKS:")
            for b in broken:
                print(f"  {b}")
            sys.exit("build failed: broken internal links detected")

    # --- Strict: fail if no HTML output produced ---
    if args.strict and not built_html_paths:
        sys.exit("build failed: no HTML files produced")


if __name__ == "__main__":
    main()
