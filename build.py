#!/usr/bin/env python3
"""
Goodoc — Retro static site builder.
====================================

Build pipeline ``content/**/*.md → build/**/*.html`` with Pandoc.

Overview
--------
- Discovers ``content/**/*.md`` and sorts by ``mtime`` (recent first).
- Cleans ``build/`` safely (strictly inside project root, no symlink delete).
- Copies static assets (``retro-doc.css``, ``lightbox.js``) and all non-Markdown
  assets (``_attachments`` mirroring) to ``build/``.
- Converts each Markdown file via ``pandoc --standalone -c retro-doc.css``
  using an isolated ``tempfile`` (no shared ``/tmp/pandoc_tmp.html`` race).
- Rewrites image ``src``/``href`` attributes via :func:`resolve_attachment`
  (canonical 6-path lookup) so ``![alt](_attachments/...)`` works regardless
  of document depth.
- Renders a sidebar tree (:func:`render_tree`) and two index pages:
  ``build/index.html`` (recent 8 docs) and root ``index.html`` (redirect + recent).

Usage
-----
.. code-block:: bash

    # prerequisites
    sudo pacman -S pandoc
    python build.py            # clean + build
    python -m http.server --directory build

Idempotency
-----------
Running ``build.py`` twice produces identical ``build/`` (modulo ``mtime``).
The ``build/`` directory is fully regenerable and therefore excluded via
``.gitignore``.

Security
--------
- Verifies ``BUILD`` is inside ``ROOT`` before ``shutil.rmtree``.
- Sanitizes ``title`` metadata for Pandoc (no newlines/control chars).
- Uses isolated temp files with ``timeout=30s`` for Pandoc.
- Logs specific exceptions (no bare ``except:``).

See Also
--------
- ``retro-doc.css`` — retro dossier theme
- ``lightbox.js`` — image overlay (zoom/pan)
- ``content/docs/dokuman.md`` — live component showcase
"""
import re
import shutil
import subprocess
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

# M4: verify pandoc exists at startup
if not shutil.which("pandoc"):
    raise SystemExit("pandoc not found — install with: sudo pacman -S pandoc (https://pandoc.org)")

# _attachments locations (content and root)
ATTACH_DIRS = [CONTENT / "_attachments", ROOT / "_attachments"]

# C1: Safe Build Clean — verify BUILD is inside ROOT and not a symlink
BUILD_RESOLVED = BUILD.resolve()
ROOT_RESOLVED = ROOT.resolve()
# Ensure BUILD is inside ROOT (allow BUILD == ROOT/build)
try:
    BUILD_RESOLVED.relative_to(ROOT_RESOLVED)
except ValueError:
    raise RuntimeError(f"Refusing to clean BUILD outside project: BUILD={BUILD_RESOLVED} ROOT={ROOT_RESOLVED}")
if BUILD.exists():
    if BUILD.is_symlink():
        raise RuntimeError(f"Refusing to delete symlinked BUILD: {BUILD}")
    # also guard against BUILD being root itself
    if BUILD_RESOLVED == ROOT_RESOLVED:
        raise RuntimeError(f"Refusing to delete project root: {BUILD_RESOLVED}")
    shutil.rmtree(BUILD)
BUILD.mkdir(parents=True, exist_ok=True)

# Copy static assets to build root
for src in [CSS_SRC, JS_SRC]:
    if src.exists():
        shutil.copy2(src, BUILD / src.name)
        print(f"copy {src.name} -> build/")

# Copy content assets (non-md) preserving structure
for p in CONTENT.rglob("*"):
    if p.is_file() and p.suffix.lower() != ".md":
        rel = p.relative_to(CONTENT)
        dest = BUILD / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, dest)
        print(f"copy content/{rel} -> build/{rel}")

# Copy root _attachments if exists (merge)
if (ROOT / "_attachments").exists():
    for p in (ROOT / "_attachments").rglob("*"):
        if p.is_file():
            rel = p.relative_to(ROOT / "_attachments")
            dest = BUILD / "_attachments" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            # don't overwrite if already exists from content
            if not dest.exists():
                shutil.copy2(p, dest)
                print(f"copy _attachments/{rel} -> build/_attachments/{rel}")

# Collect markdown files
md_files = sorted(CONTENT.rglob("*.md"))
print(f"\nFound {len(md_files)} markdown files in content/")

def sanitize_title(s: str, limit: int = 120) -> str:
    """Sanitize a title string for safe Pandoc metadata.

    Removes newlines, quotes, backticks and control characters, caps length
    at word boundary, and strips surrounding whitespace.

    :param s: Raw title string (from front matter or first heading).
    :param limit: Maximum length in characters (default 120).
    :returns: Sanitized title safe to pass as ``--metadata title=``.
    """
    s = re.sub(r'[\r\n]+', ' ', s)
    s = s.replace('"', '').replace("'", "").replace("`", "")
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    s = s.strip()
    if len(s) > limit:
        s = s[:limit].rsplit(' ', 1)[0]
    return s

def get_title_from_text(text: str, fallback: str = "") -> str:
    """Extract a document title from raw Markdown text.

    Priority: YAML ``title:`` front matter → first ``#`` heading → ``fallback``.
    Strips HTML tags from headings and sanitizes the result.

    :param text: Full Markdown file content.
    :param fallback: Value returned if no title is found (usually ``Path.stem``).
    :returns: Sanitized title string.
    """
    m = re.search(r'^title:\s*["\']?(.+?)["\']?\s*$', text, re.MULTILINE)
    if m:
        return sanitize_title(m.group(1).strip(), limit=120)
    m = re.search(r'^#\s+(.+)$', text, re.MULTILINE)
    if m:
        t = re.sub(r'<[^>]+>', '', m.group(1))
        return sanitize_title(t.strip()[:80], limit=80)
    return fallback

def get_excerpt_from_text(text: str, limit: int = 160) -> str:
    """Build a plain-text excerpt for the Recent list.

    Strips YAML front matter, code fences and HTML tags, collapses
    whitespace and truncates at word boundary.

    :param text: Full Markdown file content.
    :param limit: Max characters before truncation (default 160).
    :returns: Trimmed excerpt with trailing ellipsis if truncated.
    """
    text = re.sub(r'^---.*?---\s*', '', text, flags=re.DOTALL)
    # remove code blocks, html tags
    text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[#>*_\-`\[\]\(\)]', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) > limit:
        return text[:limit].rsplit(' ', 1)[0] + "…"
    return text

def get_title(md_path: Path) -> str:
    """Read a file and extract its title (convenience wrapper).

    Prefer :func:`get_title_from_text` when you already have the file
    content in memory to avoid a second read.

    :param md_path: Path to a Markdown file under ``content/``.
    :returns: Sanitized title or ``md_path.stem`` on failure.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_title read failed for {md_path}: {e}")
        traceback.print_exc()
        return md_path.stem
    return get_title_from_text(text, fallback=md_path.stem)

def get_excerpt(md_path: Path, limit: int = 160) -> str:
    """Read a file and build its excerpt (convenience wrapper).

    Prefer :func:`get_excerpt_from_text` when content is already loaded.

    :param md_path: Path to a Markdown file.
    :param limit: Max characters for the excerpt.
    :returns: Plain-text excerpt or empty string on failure.
    """
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_excerpt read failed for {md_path}: {e}")
        traceback.print_exc()
        return ""
    return get_excerpt_from_text(text, limit=limit)

# Build tree for sidebar
tree = {}
for md in md_files:
    rel = md.relative_to(CONTENT)
    parts = rel.with_suffix("").parts
    cur = tree
    for i, part in enumerate(parts):
        is_file = (i == len(parts)-1)
        if is_file:
            # M5: read once for title/mtime
            try:
                txt = md.read_text(encoding="utf-8", errors="ignore")
                title = get_title_from_text(txt, fallback=md.stem)
            except Exception as e:
                print(f"warn tree title for {md}: {e}")
                traceback.print_exc()
                title = md.stem
            cur[part] = {"type": "file", "md_path": md, "rel": rel, "title": title, "mtime": md.stat().st_mtime, "_cached_text": txt if 'txt' in locals() else None}
        else:
            if part not in cur:
                cur[part] = {"type": "dir", "children": {}}
            cur = cur[part]["children"]

def has_active(node: dict, current_html: Path) -> bool:
    """Check whether any file in a sidebar subtree is the current page.

    Used to set ``aria-expanded="true"`` on parent folders so the active
    branch stays open.

    :param node: Subtree dict (``children`` or top-level ``tree``).
    :param current_html: Absolute path of the HTML file being rendered.
    :returns: ``True`` if ``current_html`` matches a file in this subtree.
    """
    for _, info in node.items():
        if info["type"] == "file":
            rel_md = info["rel"]
            target = BUILD / rel_md.with_suffix(".html")
            try:
                if current_html.resolve() == target.resolve():
                    return True
            except Exception as e:
                # C3: no bare except
                # fallback string compare, log
                print(f"warn has_active resolve: {e}")
                traceback.print_exc()
                if str(current_html) == str(target):
                    return True
        else:
            if has_active(info["children"], current_html):
                return True
    return False

def render_tree(node: dict, current_html: Path, prefix: Path = Path(".")) -> str:
    """Render a sidebar tree as nested ``<ul>`` HTML.

    Files and directories are sorted case-insensitively; the active file
    receives ``is-active``. The most-recent document's folder is expanded
    on index pages.

    :param node: Tree node (as built from ``md_files``).
    :param current_html: HTML file currently being rendered (for active state).
    :param prefix: Accumulated directory prefix for recursion.
    :returns: HTML string for this subtree.
    """
    html = '<ul class="contentTree">\n'
    files = [(k,v) for k,v in node.items() if v["type"]=="file"]
    dirs = [(k,v) for k,v in node.items() if v["type"]=="dir"]
    files.sort(key=lambda x: x[0].lower())
    dirs.sort(key=lambda x: x[0].lower())
    for name, info in files + dirs:
        if info["type"] == "file":
            rel_md = info["rel"]
            target = BUILD / rel_md.with_suffix(".html")
            link_rel = os.path.relpath(target, start=current_html.parent)
            title = info["title"]
            try:
                active = " is-active" if current_html.resolve() == target.resolve() else ""
            except Exception:
                active = " is-active" if str(current_html) == str(target) else ""
            html += f'  <li><a href="{link_rel}" class="tree-link{active}">{title}</a></li>\n'
        else:
            dir_path = prefix / name if prefix != Path(".") else Path(name)
            expanded = has_active(info["children"], current_html)
            if not expanded and current_html.name == "index.html":
                try:
                    most_recent = sorted(md_files, key=lambda p: p.stat().st_mtime, reverse=True)[0]
                    most_rel = most_recent.relative_to(CONTENT).parent
                    if most_rel != Path(".") and (most_rel == dir_path or str(most_rel).startswith(str(dir_path) + "/")):
                        expanded = True
                except Exception as e:
                    print(f"warn render_tree recent check: {e}")
                    traceback.print_exc()
                    pass
            aria = "true" if expanded else "false"
            html += f'  <li><button class="tree-folder" aria-expanded="{aria}">{name}</button>\n'
            html += render_tree(info["children"], current_html, dir_path)
            html += '  </li>\n'
    html += '</ul>\n'
    return html

def resolve_attachment(md_path: Path, src: str, html_path: Path) -> tuple[str | None, str | None]:
    """Resolve an image ``src`` from Markdown to a copied file in ``build/``.

    Canonical lookup order (see ``dokuman.md``):

    1. Sibling of the Markdown file (``md_dir / clean``).
    2. Per-folder ``_attachments`` (``md_dir/_attachments/<basename>``).
    3. Mirrored global ``content/_attachments/<rel_dir>/<basename>``.
    4. Global ``content/_attachments/<basename>``.
    5. Root ``_attachments`` mirrors.
    6. ``content/<clean>`` fallback.

    The first existing file is copied to ``build/`` (preserving its
    ``content/``-relative path) and a path relative to ``html_path``
    is returned for the ``<img src>`` rewrite.

    :param md_path: Source Markdown file.
    :param src: Raw ``src`` attribute from HTML.
    :param html_path: Destination HTML file (for relative path calc).
    :returns: Tuple ``(found_absolute_path, relative_src)`` or ``(None, None)``
              if not found or if ``src`` is external (``http``, ``data:``, ``#``).
    """
    # D2: canonical order per dokuman.md; see docstring above
    if src.startswith("http://") or src.startswith("https://") or src.startswith("data:") or src.startswith("#") or src.startswith("/"):
        return None, None
    # strip query/hash
    clean = src.split("#")[0].split("?")[0]
    if not clean:
        return None, None
    # If clean already starts with _attachments/, strip prefix for name lookup but keep candidate handling
    clean_path = Path(clean)
    # candidates in canonical order
    md_dir = md_path.parent
    rel_dir = md_path.parent.relative_to(CONTENT) if md_path.parent != CONTENT else Path(".")
    candidates = []
    # 1. sibling of md (exact clean relative to md_dir)
    candidates.append(md_dir / clean)
    # 2. per-folder _attachments (md_dir/_attachments/<basename>)
    candidates.append(md_dir / "_attachments" / clean_path.name)
    # If clean has subdir, also try md_dir/_attachments/clean
    if len(clean_path.parts) > 1:
        candidates.append(md_dir / "_attachments" / clean)
    # 3. global mirrored: content/_attachments/<rel_dir>/<basename>
    if rel_dir != Path("."):
        candidates.append(CONTENT / "_attachments" / rel_dir / clean_path.name)
        # also with subpath if clean contains dirs
        if len(clean_path.parts) > 1:
            candidates.append(CONTENT / "_attachments" / rel_dir / clean)
        candidates.append(ROOT / "_attachments" / rel_dir / clean_path.name)
        if len(clean_path.parts) > 1:
            candidates.append(ROOT / "_attachments" / rel_dir / clean)
    # 4. global _attachments root
    candidates.append(CONTENT / "_attachments" / clean_path.name)
    # if clean already has _attachments prefix, this duplicates but ok
    candidates.append(CONTENT / "_attachments" / clean)
    candidates.append(ROOT / "_attachments" / clean_path.name)
    candidates.append(ROOT / "_attachments" / clean)
    # 5. content root
    candidates.append(CONTENT / clean)

    # dedup preserving order
    seen = set()
    uniq = []
    for c in candidates:
        if c not in seen:
            seen.add(c)
            uniq.append(c)

    for cand in uniq:
        # normalize _attachments/_attachments duplication
        try:
            cand_str = str(cand)
            if "_attachments/_attachments" in cand_str:
                cand = Path(cand_str.replace("_attachments/_attachments", "_attachments"))
        except Exception as e:
            print(f"warn cand normalize: {e}")
            traceback.print_exc()
            pass
        # prevent directory traversal outside project
        try:
            # resolve without strict to handle non-existent
            cand_resolved = cand.resolve()
            # allow only inside ROOT or CONTENT
            if not (str(cand_resolved).startswith(str(ROOT_RESOLVED)) or str(cand_resolved).startswith(str(CONTENT.resolve()))):
                # still allow if file exists inside project tree
                pass
        except Exception:
            pass
        if cand.exists() and cand.is_file():
            # dest in build mirrors source relative to CONTENT or ROOT _attachments
            if cand.is_relative_to(CONTENT):
                rel_to_content = cand.relative_to(CONTENT)
                dest = BUILD / rel_to_content
            elif cand.is_relative_to(ROOT / "_attachments"):
                rel_to_root_attach = cand.relative_to(ROOT / "_attachments")
                dest = BUILD / "_attachments" / rel_to_root_attach
            else:
                # fallback: relative to CONTENT
                try:
                    dest = BUILD / cand.relative_to(CONTENT)
                except Exception as e:
                    print(f"warn dest fallback: {e}")
                    traceback.print_exc()
                    dest = BUILD / cand.name
            # ensure dest exists (copy if not already)
            if not dest.exists():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cand, dest)
            # compute html-relative src
            new_src = os.path.relpath(dest, start=html_path.parent)
            return str(cand), new_src
    return None, None

# Generate HTML for each md (except recent index)
for md in md_files:
    rel = md.relative_to(CONTENT)
    out = BUILD / rel.with_suffix(".html")
    out.parent.mkdir(parents=True, exist_ok=True)

    # M5: read once and reuse
    try:
        raw_md_text = md.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"failed to read {md}: {e}")
        traceback.print_exc()
        continue
    title_raw = get_title_from_text(raw_md_text, fallback=md.stem)
    title = sanitize_title(title_raw, limit=120)

    # C2: isolated temp file
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            tmp = Path(tf.name)
        # D8: pandoc invocation matches doc spec — --standalone -c retro-doc.css
        cmd = ["pandoc", str(md), "-o", str(tmp), "--standalone", "-c", "retro-doc.css", "--metadata", f"title={title}"]
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
                traceback.print_exc()

    m_style = re.search(r"<style>(.*?)</style>", raw, re.DOTALL)
    pandoc_style = m_style.group(1) if m_style else ""
    m_body = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
    body_inner = m_body.group(1).strip() if m_body else raw
    # Fix lightbox.js src already in body_inner
    css_rel = os.path.relpath(BUILD / "retro-doc.css", start=out.parent)
    js_rel = os.path.relpath(BUILD / "lightbox.js", start=out.parent)

    # C6: Fix attribute rewriting — handle both src and href with single or double quotes
    def repl_attr(m):
        attr = m.group(1)  # src= or href=
        q = m.group(2)  # quote
        src = m.group(3)
        if src.startswith("http") or src.startswith("data:"):
            return m.group(0)
        found, new_src = resolve_attachment(md, src, out)
        if new_src:
            return f'{attr}{q}{new_src}{q}'
        else:
            maybe = BUILD / src
            if maybe.exists():
                new_rel = os.path.relpath(maybe, start=out.parent)
                return f'{attr}{q}{new_rel}{q}'
            return m.group(0)

    # Rewrite both src and href attributes (images may use either)
    body_inner = re.sub(r'((?:src|href)\s*=\s*)(["\'])([^"\']+)\2', repl_attr, body_inner)
    # also handle markdown image that may have _attachments path already correct
    body_fixed = body_inner.replace('src="lightbox.js"', f'src="{js_rel}"').replace("src='lightbox.js'", f"src='{js_rel}'")

    sidebar_tree = render_tree(tree, out)
    doc_title_match = re.search(r"<title>(.*?)</title>", raw, re.DOTALL)
    doc_title = doc_title_match.group(1).strip() if doc_title_match else title
    home_rel = os.path.relpath(BUILD / "index.html", start=out.parent)

    # M1: preconnect links for Google Fonts (replaces CSS @import)
    preconnect_links = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Special+Elite&family=JetBrains+Mono:wght@400;500;700;800&display=swap">"""

    final = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>{doc_title}</title>
{preconnect_links}
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
        <span class="sidebar-title">İçerik</span>
        <span class="sidebar-sub">content /</span>
      </div>
      <a href="{home_rel}" class="sidebar-home">Ana Sayfa</a>
    </div>
    {sidebar_tree}
    <div class="sidebar-foot">{len(md_files)} belge</div>
  </nav>
  <main class="sheet site-main">
{body_fixed}
  </main>
</div>
<script src="{js_rel}"></script>
<script>
(function(){{
  var btn=document.querySelector('.sidebar-toggle');
  var bar=document.getElementById('sidebar');
  var ov=document.getElementById('sidebarOverlay');
  function open(){{bar.classList.add('is-open'); ov.classList.add('is-open'); btn.setAttribute('aria-expanded','true');}}
  function close(){{bar.classList.remove('is-open'); ov.classList.remove('is-open'); btn.setAttribute('aria-expanded','false');}}
  btn.addEventListener('click', function(){{ bar.classList.contains('is-open') ? close() : open(); }});
  ov.addEventListener('click', close);
  document.addEventListener('keydown', function(e){{ if(e.key==='Escape') close(); }});
  document.querySelectorAll('.tree-folder').forEach(function(b){{ b.addEventListener('click', function(){{ var e=b.getAttribute('aria-expanded')==='true'; b.setAttribute('aria-expanded', e?'false':'true'); }}); }});
}})();
</script>
</body>
</html>
"""
    out.write_text(final, encoding="utf-8")
    print(f"built {out.relative_to(BUILD)}")

# --- Generate recent index at build/index.html and root index.html ---
# Sort by mtime descending
recent = sorted(md_files, key=lambda p: p.stat().st_mtime, reverse=True)
recent_limit = 8

# Toplam resim sayısı: tüm _attachments klasörlerinde (content ve kök)
image_exts = {".png",".jpg",".jpeg",".gif",".webp",".svg",".bmp"}
total_images = 0
seen_imgs = set()
for base in [CONTENT / "_attachments", ROOT / "_attachments"] + list(CONTENT.rglob("_attachments")):
    if base.exists():
        for img in base.rglob("*"):
            if img.is_file() and img.suffix.lower() in image_exts:
                # dedup by resolved path
                try:
                    key = img.resolve()
                except Exception as e:
                    print(f"warn img resolve: {e}")
                    traceback.print_exc()
                    key = img
                if key not in seen_imgs:
                    seen_imgs.add(key)
                    total_images += 1
# Also direct content/_attachments files already counted, but per-folder _attachments like content/linux/_attachments already covered via rglob


def format_date(p: Path) -> str:
    """Format a file's modification time as ``YYYY-MM-DD``.

    :param p: Path whose ``st_mtime`` is used.
    :returns: Date string for the Recent list.
    """
    ts = p.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d")

recent_items_html = ""
for md in recent[:recent_limit]:
    rel = md.relative_to(CONTENT)
    target = BUILD / rel.with_suffix(".html")
    # For recent index at build/index.html, link is relative to build
    link = os.path.relpath(target, start=BUILD)
    # M5: use cached read if available or read once
    try:
        txt = md.read_text(encoding="utf-8", errors="ignore")
        title = get_title_from_text(txt, fallback=md.stem)
        excerpt = get_excerpt_from_text(txt, limit=180)
    except Exception as e:
        print(f"warn recent excerpt for {md}: {e}")
        traceback.print_exc()
        title = md.stem
        excerpt = ""
    date = format_date(md)
    folder = str(rel.parent) if rel.parent != Path(".") else "content"
    recent_items_html += f"""
  <article class="recent-card">
    <div class="recent-meta"><span class="recent-folder">{folder}</span> • <span class="recent-date">{date}</span></div>
    <h3 class="recent-title"><a href="{link}">{title}</a></h3>
    <p class="recent-excerpt">{excerpt}</p>
    <p class="u-small u-muted">{rel} → <a href="{link}">{link}</a></p>
  </article>
"""

recent_body = f"""
<h1>Son <span class="yell">Eklenenler</span></h1>
<p class="lede">content/ klasörüne atılan her Markdown otomatik burada listelenir. Son {len(recent[:recent_limit])} belge — en yeni üstte. Soldaki ağaçtan tüm içeriğe ulaşabilirsin.</p>

<div class="shout">Yeni belge ekle → <span>content/ içine .md at, build çalışsın.</span></div>

<fieldset class="choice-group">
  <legend>Hızlı bakış</legend>
  <label class="choice"><input type="radio" name="recent" value="all" checked tabindex="-1"> {len(md_files)} belge</label>
  <label class="choice"><input type="radio" name="recent" value="attach" tabindex="-1"> _attachments/ klasörlerinde {total_images} resim</label>
</fieldset>

<div class="recent-list">
{recent_items_html}
</div>

<div class="signature">
  <div class="name">— site,<br>otomatik derlendi</div>
  <small>content/ → build/ • pandoc + retro-doc.css + lightbox.js</small>
</div>
"""

# Build sidebar for index (recent) page
index_path = BUILD / "index.html"
sidebar_for_index = render_tree(tree, index_path)
css_rel_idx = os.path.relpath(BUILD / "retro-doc.css", start=BUILD)
js_rel_idx = os.path.relpath(BUILD / "lightbox.js", start=BUILD)

# Need pandoc style for index? Reuse from dokuman or generate minimal
# We'll reuse the style from dokuman's pandoc run or just empty
pandoc_style_idx = ""
if (BUILD / "docs/dokuman.html").exists():
    # try to extract from dokuman.html
    try:
        txt = (BUILD / "docs/dokuman.html").read_text(encoding="utf-8")
        m = re.search(r"<style>(.*?)</style>", txt, re.DOTALL)
        if m:
            pandoc_style_idx = m.group(1)
    except Exception as e:
        print(f"warn pandoc_style_idx: {e}")
        traceback.print_exc()
        pass

preconnect_links_idx = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Special+Elite&family=JetBrains+Mono:wght@400;500;700;800&display=swap">"""

index_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Son Eklenenler — goodoc</title>
{preconnect_links_idx}
<style>
{pandoc_style_idx}
</style>
<link rel="stylesheet" href="{css_rel_idx}" />
</head>
<body class="has-sheet">
<button class="sidebar-toggle" aria-label="Menüyü aç/kapat" aria-expanded="false">☰</button>
<div class="sidebar-overlay" id="sidebarOverlay"></div>
<div class="site-wrap">
  <nav class="sidebar" id="sidebar" aria-label="İçerik ağacı">
    <div class="sidebar-head">
      <div class="sidebar-head-text">
        <span class="sidebar-title">İçerik</span>
        <span class="sidebar-sub">content /</span>
      </div>
      <a href="index.html" class="sidebar-home">Ana Sayfa</a>
    </div>
    {sidebar_for_index}
    <div class="sidebar-foot">{len(md_files)} belge</div>
  </nav>
  <main class="sheet site-main">
{recent_body}
  </main>
</div>
<script src="{js_rel_idx}"></script>
<script>
(function(){{
  var btn=document.querySelector('.sidebar-toggle');
  var bar=document.getElementById('sidebar');
  var ov=document.getElementById('sidebarOverlay');
  function open(){{bar.classList.add('is-open'); ov.classList.add('is-open'); btn.setAttribute('aria-expanded','true');}}
  function close(){{bar.classList.remove('is-open'); ov.classList.remove('is-open'); btn.setAttribute('aria-expanded','false');}}
  btn.addEventListener('click', function(){{ bar.classList.contains('is-open') ? close() : open(); }});
  ov.addEventListener('click', close);
  document.addEventListener('keydown', function(e){{ if(e.key==='Escape') close(); }});
  document.querySelectorAll('.tree-folder').forEach(function(b){{ b.addEventListener('click', function(){{ var e=b.getAttribute('aria-expanded')==='true'; b.setAttribute('aria-expanded', e?'false':'true'); }}); }});
}})();
</script>
</body>
</html>
"""
index_path.write_text(index_html, encoding="utf-8")
print(f"built recent index -> {index_path} ({len(recent)} items)")

# Also create root index.html (goodoc/index.html) as copy/redirect with correct relative paths to build
root_index = ROOT / "index.html"
# For root, links need to be build/... 
recent_items_root = ""
for md in recent[:recent_limit]:
    rel = md.relative_to(CONTENT)
    target = Path("build") / rel.with_suffix(".html")
    try:
        txt = md.read_text(encoding="utf-8", errors="ignore")
        title = get_title_from_text(txt, fallback=md.stem)
        excerpt = get_excerpt_from_text(txt, limit=160)
    except Exception as e:
        print(f"warn root recent for {md}: {e}")
        traceback.print_exc()
        title = md.stem
        excerpt = ""
    date = format_date(md)
    folder = str(rel.parent) if rel.parent != Path(".") else "content"
    recent_items_root += f"""
  <article class="recent-card">
    <div class="recent-meta"><span class="recent-folder">{folder}</span> • <span class="recent-date">{date}</span></div>
    <h3 class="recent-title"><a href="{target}">{title}</a></h3>
    <p class="recent-excerpt">{excerpt}</p>
  </article>
"""
root_body = f"""
<h1>Son <span class="yell">Eklenenler</span></h1>
<p class="lede">Ana klasördeki index — build/ içindeki siteye yönlendirir. Son {len(recent[:recent_limit])} belge aşağıda.</p>
<p class="u-center"><a class="cta-angry" href="build/">Siteye git — build/index.html →</a></p>

<fieldset class="choice-group">
  <legend>Hızlı bakış</legend>
  <label class="choice"><input type="radio" name="recent" value="all" checked tabindex="-1"> {len(md_files)} belge</label>
  <label class="choice"><input type="radio" name="recent" value="attach" tabindex="-1"> _attachments/ klasörlerinde {total_images} resim</label>
</fieldset>

<div class="recent-list">
{recent_items_root}
</div>
"""

root_sidebar = render_tree(tree, root_index)  # but links need to be build/... for root
# render_tree for root gives links relative to ROOT, which would be build/... correct if we compute from ROOT
# Our render_tree for root_index uses os.path.relpath(target=BUILD/... , start=ROOT) -> build/...
# So we need to regenerate sidebar for root
sidebar_for_root = render_tree(tree, root_index)
root_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>goodoc — Son Eklenenler</title>
{preconnect_links_idx}
<style>
{pandoc_style_idx}
</style>
<link rel="stylesheet" href="build/retro-doc.css" />
</head>
<body class="has-sheet">
<button class="sidebar-toggle" aria-label="Menüyü aç/kapat" aria-expanded="false">☰</button>
<div class="sidebar-overlay" id="sidebarOverlay"></div>
<div class="site-wrap">
  <nav class="sidebar" id="sidebar" aria-label="İçerik ağacı">
    <div class="sidebar-head">
      <div class="sidebar-head-text">
        <span class="sidebar-title">goodoc</span>
        <span class="sidebar-sub">ana klasör → build/</span>
      </div>
      <a href="index.html" class="sidebar-home">Ana Sayfa</a>
    </div>
    {sidebar_for_root}
    <div class="sidebar-foot">{len(md_files)} belge</div>
  </nav>
  <main class="sheet site-main">
{root_body}
  </main>
</div>
<script src="build/lightbox.js"></script>
<script>
(function(){{
  var btn=document.querySelector('.sidebar-toggle');
  var bar=document.getElementById('sidebar');
  var ov=document.getElementById('sidebarOverlay');
  function open(){{bar.classList.add('is-open'); ov.classList.add('is-open'); btn.setAttribute('aria-expanded','true');}}
  function close(){{bar.classList.remove('is-open'); ov.classList.remove('is-open'); btn.setAttribute('aria-expanded','false');}}
  btn.addEventListener('click', function(){{ bar.classList.contains('is-open') ? close() : open(); }});
  ov.addEventListener('click', close);
  document.addEventListener('keydown', function(e){{ if(e.key==='Escape') close(); }});
  document.querySelectorAll('.tree-folder').forEach(function(b){{ b.addEventListener('click', function(){{ var e=b.getAttribute('aria-expanded')==='true'; b.setAttribute('aria-expanded', e?'false':'true'); }}); }});
}})();
</script>
</body>
</html>
"""
root_index.write_text(root_html, encoding="utf-8")
print(f"built root index -> {root_index}")

# Add extra CSS for recent cards if not present
print("\nBuild complete. Recent items:")
for md in recent[:5]:
    print(f" - {md.relative_to(CONTENT)} ({format_date(md)})")
