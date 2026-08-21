<p align="center">
  <strong>goodoc</strong>
</p>

<p align="center">
  <strong>Tek komutla Markdown → retro HTML — daktilo temalı statik site derleyici.</strong>
</p>

<p align="center">
  <img alt="Python 3.11+" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="pandoc" src="https://img.shields.io/badge/pandoc-required-0A2A4A">
  <img alt="platform" src="https://img.shields.io/badge/platform-Linux-FCC624?logo=linux&logoColor=black">
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-green.svg"></a>
</p>

goodoc, `content/**/*.md` içindeki her Markdown dosyasını `build/**/*.html` altında retro dossier temasıyla HTML'e çevirir. Sidebar, lightbox, `_attachments` aynalama ve son eklenenler listesi tek komutla üretilir.

```
content/docs/dokuman.md  →  build/docs/dokuman.html
content/_attachments/a.png  →  build/_attachments/a.png
→ build/index.html + index.html (recent 8)
```

## Hızlı başlangıç

`pandoc` kuruluysa depoyu klonlayıp derleyin:

```bash
git clone https://github.com/ArdaYILDIZ-DEV/goodoc.git
cd goodoc
sudo pacman -S pandoc   # Arch / Manjaro — Debian: sudo apt install pandoc
python build.py
python -m http.server --directory build  # http://localhost:8000
```

`build/` ve `index.html` yeniden üretilir. `content/` içine `.md` atıp `python build.py` yeterlidir.

## Özellikler

* Tek komutla temiz derleme — `build/` güvenli temizlenir (proje kökü dışı ve symlink korumalı)
* Pandoc `--standalone -c retro-doc.css` + izole `tempfile` ve `timeout=30s`
* `_attachments` aynalama — `![alt](_attachments/a.png)` her derinlikte doğru `src`'ye yazılır
* Sidebar ağacı — klasör hiyerarşisi, aktif sayfa vurgusu, `aria-expanded`, mobil drawer (900px)
* Lightbox — `figure img` ve yalnız `p>img` için overlay, 150% açılış, sürükle/pan, wheel/pinch zoom, `+/- / 0 / Esc`
* Retro tema — Special Elite başlıklar, JetBrains Mono gövde, ink-on-paper, stamp kırmızısı, hard shadow, `§`/`¶` başlıklar, zebra tablolar, copy butonlu kod blokları
* Son eklenenler — `mtime`'a göre son 8 belge, `build/index.html` ve kök `index.html` otomatik
* Responsive — 320px → 4K, `prefers-reduced-motion` uyumlu
* Sıfır bağımlılık (pandoc hariç) — Python stdlib + kopyalanan `retro-doc.css` / `lightbox.js`

## Gereksinimler

* Python 3.11+
* [`pandoc`](https://pandoc.org/) (standalone HTML üretimi için)
* Linux / macOS / WSL — ANSI ve UTF-8 destekleyen terminal

## Kaynaktan derleme ve kullanım

Derleme adımı yoktur, doğrudan çalışır:

```bash
python build.py            # temizle + tüm md'leri derle
python build.py 2>&1 | tail   # log: kopyalanan asset'ler ve recent listesi
```

İçerik ekleme:

```bash
mkdir -p content/notlar/_attachments
cp ~/resim.png content/notlar/_attachments/
cat > content/notlar/merhaba.md <<'MD'
---
title: Merhaba
---
# Merhaba

![resim](_attachments/resim.png)
MD
python build.py
```

Çıktı `build/notlar/merhaba.html` olur, görsel `build/notlar/_attachments/` yerine global aynalama ile `build/_attachments/` veya `build/notlar/_attachments/`'a kopyalanır.

## İçerik yapısı

```text
goodoc/
├── content/
│   ├── docs/
│   │   ├── dokuman.md          # tema canlı kılavuzu — tüm bileşenler burada
│   │   └── _attachments/.keep
│   └── _attachments/           # global görseller (isteğe bağlı)
├── retro-doc.css               # tema
├── lightbox.js                 # overlay
├── build.py                    # derleyici
└── index.html                  # kök recent (build.py üretir, track'li)
```

Görsel arama sırası (kanonik): dosya yanı → `md/_attachments/<ad>` → `content/_attachments/<rel>/<ad>` → `content/_attachments/<ad>` → `ROOT/_attachments/...` → `content/<yol>`.

## Tema bileşenleri

`content/docs/dokuman.md` her bileşeni canlı gösterir:

| Bileşen | Kullanım |
| Başlıklar | `##` → `§`, `###` → `¶` otomatik, `.yell` / `.marker` vurgu |
| Lede | `<p class="lede">` giriş paragrafı |
| Listeler | `ul`/`ol`/`task-list` (display-only) |
| Blockquote | `> ` + `.exhibit-label` |
| Tablolar | zebra, %100 genişlik |
| Kod | ```` ``` ```` + SVG copy butonu (2sn tık) |
| Figure | `figure>img` + `figcaption` — hover `scale(1.005)`, lightbox |
| Shout/CTA | `.shout`, `.cta-angry` / `.cta-calm` |
| Choice | `.choice-group` display-only radio/checkbox |
| Sidebar | `.site-wrap` + `.sidebar` + `.sidebar-overlay` |
| Recent | `.recent-card` grid (8 kart) |

## Proje yapısı

```text
goodoc/
├── build.py          # Markdown keşfi, asset kopyalama, pandoc, sidebar/index
├── retro-doc.css     # @layer mimarisi + pandoc-overrides (unlayered)
├── lightbox.js       # overlay, zoom/pan, toolbar, a11y
├── content/          # kaynak md + _attachments
└── build/            # üretilen site (gitignore)
```

Ana fonksiyonlar (`build.py`): `sanitize_title`, `get_title_from_text`, `get_excerpt_from_text`, `render_tree`, `resolve_attachment`, `format_date`.

## Geliştirme

Doğrulama:

```bash
python -m py_compile build.py
node --check lightbox.js
python build.py
```

`pandoc` yoksa `SystemExit: pandoc not found` ile net hata verir. `build/` her zaman yeniden üretilebilir olduğu için commitlenmez.

## Sorun giderme

### `pandoc not found`

Dağıtımına göre kur:

```bash
sudo pacman -S pandoc
sudo apt install pandoc
brew install pandoc
```

### Görsel 404

Kaynak görseli `_attachments` kuralına göre yerleştir ve `![alt](_attachments/...)` kanonik yolunu kullan. `build.py` log'unda `copy content/... -> build/...` satırı görünmüyorsa dosya `content` altında değildir.

### Sidebar açılmıyor

`build/index.html` ve `build/docs/dokuman.html` içinde `site.js` değil `lightbox.js` sonrası inline toggle script'i vardır — üç kopya senkron olmalı (şablon içinde).

### 320px'de taşma

`retro-doc.css` 480px altında `transform: none` uygular. Hâlâ taşıyorsa Pandoc inline `<style>`'i override eden unlayered `div.sourceCode` kuralını kontrol et.

## Lisans

[MIT](LICENSE) — paylaşmak, uyarlamak ve dağıtmak serbest.
