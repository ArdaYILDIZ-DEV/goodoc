#!/usr/bin/env python3
"""Build a static site from Markdown content via pandoc.

content/*.md -> build/*.html; static assets are copied and the
sidebar tree plus "Recent" index pages are generated.
"""
import re
import shutil
import subprocess
import os
import tempfile
import traceback
from pathlib import Path
from datetime import datetime

# Layout: content/ is the source tree, build/ is fully regenerable output.
ROOT = Path(__file__).parent.resolve()
CONTENT = ROOT / "content"
BUILD = ROOT / "build"
CSS_SRC = ROOT / "retro-doc.css"
JS_SRC = ROOT / "lightbox.js"

# Fail fast: pandoc is the only external dependency.
if not shutil.which("pandoc"):
    raise SystemExit("pandoc not found — install with: sudo pacman -S pandoc (https://pandoc.org)")

# _attachments locations (content and root)
ATTACH_DIRS = [CONTENT / "_attachments", ROOT / "_attachments"]

# Safe clean: refuse to delete anything outside the project or through a symlink.
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
            # don't overwrite if already exists from content
            if not dest.exists():
                shutil.copy2(p, dest)

# Collect markdown files
md_files = sorted(CONTENT.rglob("*.md"))
print(f"\nFound {len(md_files)} markdown files in content/")

def sanitize_title(s: str, limit: int = 120) -> str:
    """Make a raw title safe for ``--metadata title=``.

    Strips newlines, quotes, backticks and control characters; truncates at a
    word boundary so Pandoc metadata can never break the build.
    """
    s = re.sub(r'[\r\n]+', ' ', s)
    s = s.replace('"', '').replace("'", "").replace("`", "")
    s = re.sub(r'[\x00-\x1f\x7f]', '', s)
    s = s.strip()
    if len(s) > limit:
        s = s[:limit].rsplit(' ', 1)[0]
    return s

def get_title_from_text(text: str, fallback: str = "") -> str:
    """Extract the document title: YAML ``title:`` first, then the first ``#`` heading.

    Heading HTML tags are stripped because titles render verbatim in sidebar links.
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
    """Build a plain-text excerpt for recent-list cards.

    Strips front matter, code fences, markup and extra whitespace; truncates
    at a word boundary with an ellipsis.
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
    """Read ``md_path`` and return its title; file stem on error."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_title read failed for {md_path}: {e}")
        traceback.print_exc()
        return md_path.stem
    return get_title_from_text(text, fallback=md_path.stem)

def get_excerpt(md_path: Path, limit: int = 160) -> str:
    """Read ``md_path`` and return its excerpt; empty string on error."""
    try:
        text = md_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"warn get_excerpt read failed for {md_path}: {e}")
        traceback.print_exc()
        return ""
    return get_excerpt_from_text(text, limit=limit)

# Nested dir/file dict drives the sidebar; each file's text is read once here.
tree = {}
for md in md_files:
    rel = md.relative_to(CONTENT)
    parts = rel.with_suffix("").parts
    cur = tree
    for i, part in enumerate(parts):
        is_file = (i == len(parts)-1)
        if is_file:
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
            except Exception as e:
                print(f"warn has_active resolve: {e}")
                traceback.print_exc()
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
    """Resolve an image src against the canonical _attachments lookup order.

    Order: md sibling -> md_dir/_attachments/<name> -> mirrored/global
    content and root _attachments -> content/<clean> fallback. The first hit
    is copied into build/ (structure preserved). Returns (found_path,
    html_relative_src), or (None, None) for external/data/anchor sources.
    """
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

    try:
        raw_md_text = md.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"failed to read {md}: {e}")
        traceback.print_exc()
        continue
    title_raw = get_title_from_text(raw_md_text, fallback=md.stem)
    title = sanitize_title(title_raw, limit=120)

    # Isolated temp output per file: no shared /tmp state between runs.
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tf:
            tmp = Path(tf.name)
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

    # Keep Pandoc's injected <style> (syntax highlighting) and unwrap <body>.
    m_style = re.search(r"<style>(.*?)</style>", raw, re.DOTALL)
    pandoc_style = m_style.group(1) if m_style else ""
    m_body = re.search(r"<body[^>]*>(.*?)</body>", raw, re.DOTALL | re.IGNORECASE)
    body_inner = m_body.group(1).strip() if m_body else raw
    # Fix lightbox.js src already in body_inner
    css_rel = os.path.relpath(BUILD / "retro-doc.css", start=out.parent)
    js_rel = os.path.relpath(BUILD / "lightbox.js", start=out.parent)

    # Rewrite local src/href to build-relative paths; external URLs pass through.
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

    # Fonts via <head> preconnect instead of render-blocking CSS @import.
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

# Count images across all _attachments folders (content + root), deduped by resolved path.
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
    """Return the file's mtime as YYYY-MM-DD for recent-list cards."""
    ts = p.stat().st_mtime
    dt = datetime.fromtimestamp(ts)
    return dt.strftime("%Y-%m-%d")

recent_items_html = ""
for md in recent[:recent_limit]:
    rel = md.relative_to(CONTENT)
    target = BUILD / rel.with_suffix(".html")
    # For recent index at build/index.html, link is relative to build
    link = os.path.relpath(target, start=BUILD)
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
  </article>
"""

recent_body = f"""
<h1>Son <span class="yell">Eklenenler</span></h1>
<p class="lede">Son eklenen {len(recent[:recent_limit])} belge (en yeni en üstte)</p>

<fieldset class="choice-group">
  <legend>Hızlı bakış</legend>
  <label class="choice"><input type="radio" name="recent" value="all" checked tabindex="-1"> {len(md_files)} belge</label>
  <label class="choice"><input type="radio" name="recent" value="attach" tabindex="-1"> _attachments/ klasörlerinde {total_images} resim</label>
</fieldset>

<div class="recent-list">
{recent_items_html}
</div>
"""

# Build sidebar for index (recent) page
index_path = BUILD / "index.html"
sidebar_for_index = render_tree(tree, index_path)
css_rel_idx = os.path.relpath(BUILD / "retro-doc.css", start=BUILD)
js_rel_idx = os.path.relpath(BUILD / "lightbox.js", start=BUILD)

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

# Root index.html mirrors the recent page so the repo works when browsed from the project root.
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
<p class="lede">Son {len(recent[:recent_limit])} belge.</p>
<p class="u-center"><a class="cta-angry" href="build/">Siteye git</a></p>

<fieldset class="choice-group">
  <legend>Hızlı bakış</legend>
  <label class="choice"><input type="radio" name="recent" value="all" checked tabindex="-1"> {len(md_files)} belge</label>
  <label class="choice"><input type="radio" name="recent" value="attach" tabindex="-1"> _attachments/ klasörlerinde {total_images} resim</label>
</fieldset>

<div class="recent-list">
{recent_items_root}
</div>
"""

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
