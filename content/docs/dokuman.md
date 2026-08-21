# Proje <span class="yell">Geliştirme</span> Notları

<p class="lede">Bu döküman, retro temalı Markdown çıktısının nasıl göründüğünü ve temadaki her bileşenin nasıl kullanılacağını tek bir yerde gösteren bir kullanım kılavuzudur. Yukarıdan aşağı okuyarak özellikleri canlı görün; en sondaki "Nasıl Kullanılır" bölümü ise her birini sıfırdan yazmanın yolunu gösterir.</p>

## Dikkat Edilecek Noktalar

Lütfen canlı ortama geçmeden önce <span class="yell">kritik konfigürasyonları</span> tekrar kontrol et. Bu döküman, normal metin içinde <mark>retro temalı bir vurgu</mark> ve <span class="marker">marker ile işaretlenmiş bir ifade</span> gösterir.

### Alt Başlık Örneği

- **İlk adım:** Gereksinimleri netleştir ve <mark>kapsamı dar tut</mark>.
- **İkinci adım:** Kod parçalarını yerel ortamda test et: `npm run build`.
- **Üçüncü adım:** Gerekirse ekip arkadaşından inceleme iste.

1. Yapay zekâyı kullan, ama kendi yorumunu ekle.
2. Soruyu gerçekten yanıtlayan kısmı ayır, gerisini at.
3. Modelin uzun yanıtı yerine üç cümle yaz.

> <span class="exhibit-label">EXHIBIT A — Önemli Hatırlatma</span>
> Bu konuda kesin bir fikrim yok demek, yanlış bir bilgi üretip paylaşmaktan her zaman daha değerlidir.

> Birine bu bağlantıyı gönderdiysen, senden hoşlanıyor demektir. Oku, derin bir nefes al ve bir sonraki yanıtını kendin yaz.

| Özellik | Açıklama | Durum |
|---------|----------|-------|
| Başlıklar | § simgeli, kırmızı vurgu | Hazır |
| Tablolar | Zebra şeritli | Hazır |
| Kod blokları | Kopyala butonlu | Hazır |
| Vurgular | Marker ve uyarı | Hazır |
| Görev listeleri | Radyo/onay kutusu + display-only todo | Hazır |
| Görseller | Retro çerçeve (figure) + 1px ink sınır | Hazır |
| Lightbox | Tıkla büyüt, **ilk açılış %150 `scale(1.5)`** + `translate(tx,ty) scale(s)` pan (screen pixels), caption/toolbar sabit, `×` dış uçta, `onerror` fallback | Hazır |
| Geniş çözünürlük desteği | 320px – 4K, 320px'de yatay taşma yok (`@media 480px` rotate kapalı), `:has()` fallback ile sheet düzgün | Hazır |

Satır içi kod örneği (builder ile eşdeğer): `pandoc dokuman.md -o index.html -c retro-doc.css --standalone --metadata title="..."` — `build.py` `sanitize_title()` ile başlığı temizleyip `--standalone -c retro-doc.css --metadata title="..."` ve 30s timeout ile çalıştırır.

## Kod Örnekleri

Aşağıdaki her bloğun sağ üst köşesindeki simgeye tıklayarak kodu panoya kopyalayabilirsin. Simge, tıklandığında 2 saniyeliğine bir onay (tik) işaretine döner.

```bash
# Pandoc ile HTML çıktısı üretmek için (build.py ile aynı flags)
pandoc dokuman.md -o index.html -c retro-doc.css --standalone --metadata title="Başlık"
# build.py gerçek çağrısı (sanitize + timeout + temp file):
# pandoc <md> -o <tmp> --standalone -c retro-doc.css --metadata title="<sanitize_title(md)>"  # timeout 30s, tempfile.NamedTemporaryFile, finally unlink
```

```python
def selamla(isim):
    return f"Merhaba, {isim}!"

print(selamla("dünya"))
```

```js
// Bu blok Pandoc tarafından sözdizimi vurgulamalı olarak üretilir
const yanit = "kendi yazdığın";
console.log(yanit);
```

<div class="shout">Kendi yanıtını yaz. <span>Modelin değil.</span></div>

<p class="u-center u-mt-lg"><a class="cta-angry" href="angry.html">Öfkeli sürüme git →</a></p>

## Durum Seçimi

Aşağıdaki alanlar yalnızca gösterim amaçlıdır: durum `dokuman.md` dosyasında ayarlanır ve siteden değiştirilemez. Üstteki "Aşama Seç" tek seçimli (radyo), alttaki "Yapılacaklar" çoklu seçimli (onay kutusu) örneğidir.

<fieldset class="choice-group">
  <legend>Aşama Seç</legend>
  <label class="choice"><input type="radio" name="asama" value="taslak" tabindex="-1"> Taslak oluştur</label>
  <label class="choice"><input type="radio" name="asama" value="inceleme" checked tabindex="-1"> İnceleme talep edildi</label>
  <label class="choice"><input type="radio" name="asama" value="yayin" tabindex="-1"> Yayına al</label>
</fieldset>

<fieldset class="choice-group">
  <legend>Yapılacaklar</legend>
  <label class="choice"><input type="checkbox" name="todo" value="taslak" checked tabindex="-1"> Proje taslağını oluştur</label>
  <label class="choice"><input type="checkbox" name="todo" value="inceleme" tabindex="-1"> İnceleme talep et</label>
  <label class="choice"><input type="checkbox" name="todo" value="test" tabindex="-1"> Canlı ortamda test et</label>
  <label class="choice"><input type="checkbox" name="todo" value="yayin" tabindex="-1"> Yayına al</label>
</fieldset>

<div class="signature">
  <div class="name">— birisi,<br>ekip arkadaşın</div>
  <small>bilerek, bir insan tarafından yazıldı.</small>
</div>

<hr>

<div class="footer">
  <p>Çoğunlukla hiciv. Paylaşmak, uyarlamak ve çevirmek serbest.</p>
</div>

## Nasıl Kullanılır ve Markdown Yazma Rehberi

Bu bölüm, temadaki her özel sınıfı, vurguyu, damga vurgusunu ve bileşeni en temiz Markdown veya HTML etiketleriyle nasıl uygulayacağınızı açıklar. Tüm örnekler olduğu gibi yazılır; kod bloğu olduğundan gerçek başlık veya biçimlendirmeye dönüşmez.

### Başlıklar (H1 Damga Vurgusu, § / ¶)

`h1` en büyük başlıktır. `##` başlığına otomatik `§`, `###` başlığına otomatik `¶` simgesi eklenir; bunları elle yazmanıza gerek yok. Bir başlık içindeki bir kelimeyi kırmızı damga gibi vurgulamak için `.yell` (ya da `mark`, `.marker`, `.stamp-accent`) kullanın:

```html
# Proje <span class="yell">Geliştirme</span> Notları

## Bölüm Başlığı
### Alt Başlık
```

### Vurgular (.marker, .yell, mark)

Üç vurgu tipi vardır: sarı yükseklik kalemi (`mark` / `.marker`), kırmızı uyarı (`span.yell` gövde metninde), ve başlık içinde kırmızı damga (`h1 .yell`):

```html
Normal metin <mark>sarı vurgu</mark> ve <span class="marker">marker ile işaretli</span>.
Uyarı: <span class="yell">kritik ayar</span> kontrol edilmeli.
```

### Giriş Paragrafı (Lede)

İlk paragrafı öne çıkarmak için `.lede` sınıfını kullanın:

```html
<p class="lede">Bu döküman, temayı test etmek için hazırlandı.</p>
```

### Listeler (Madde, Numaralı Kurallar, Görev Listeleri)

Sırasız liste, numaralı "kural" listesi ve görev listesi desteklenir:

```markdown
- Madde bir
- Madde iki

1. İlk kural
2. İkinci kural

- [ ] Yapılacak görev
- [x] Tamamlanan görev
```

Not: Pandoc görev listelerini varsayılan olarak devre dışı (görüntüleme amaçlı) üretir. Etkileşimli, tıklanabilir bir seçim için aşağıdaki radyo/onay kutusu desenini kullanın.

### Blok Alıntılar ve Exhibit

`blockquote` sol kırmızı kenarlık ve hafif eğimle çizilir. Bir "exhibit" etiketi eklemek için `.exhibit-label` kullanın:

```html
> <span class="exhibit-label">EXHIBIT A — Hatırlatma</span>
> Bu konuda kesin bir fikrim yok demek, yanlış bilgiden her zaman daha değerlidir.
```

### Tablolar (Zebra)

Standart Markdown boru tablosu kullanın; başlık şeritli ve satırlar zebra desenlidir. Tablo, içerik alanının tamamını kaplayan %100 genişlikte oluşur; dar ekranlarda sütunlar metni sararak düzgün yerleşir:

```markdown
| Sütun A | Sütun B | Durum |
|----------|----------|-------|
| Değer 1  | Değer 2  | Hazır  |
| Değer 3  | Değer 4  | Bekliyor |
```

### Kod Blokları ve Kopyala Butonu

Fenced kod blokları (```) Pandoc tarafından sözdizimi vurgulamalı üretilir ve her bloğun sağ üst köşesinde otomatik bir **Kopyala** simgesi belirir; bu, hem elle yazılmış hem de Pandoc üretimi bloklar için geçerlidir. Simge bir emoji değil, CSS/SVG ile çizilen minimalist bir klipsdir.

```bash
pandoc dit --standalone
```

Gerçek kopyalama ve tıklama animasyonu (klips → tik, 2 saniye) sayfadaki küçük betik tarafından tüm `div.sourceCode` bloklarına uygulanır; görsel yerleşim ve konumlandırma CSS'te çözülmüştür.

### Görseller, Retro Çerçeve ve Lightbox

Tüm görseller otomatik olarak retro kağıt çerçeveye alınır (`figure` veya tek başına `![alt](src)`), üzerine gelince çok hafif `scale(1.005)` büyür (kararma yok), tıklayınca retro lightbox **%150 (`scale(1.5)`, `tx=0, ty=0` merkezde) ile** açılır — sadece resim zoom/pan olur, alttaki caption/toolbar sabit kalır.

**Canlı örnek — dokümandaki gibi görünür:**

<figure>
  <img src="../_attachments/ImageCompare.png" alt="Örnek görsel — ImageCompare 2.5.7 tek görüntü modu" />
  <figcaption><span class="exhibit-label">GÖRSEL — Örnek</span> Tek görüntü modu (1494×1078 px). Üzerine gelince %0.5 büyür, tıklayınca lightbox **%150 ile** açılır — tekerlek/drag/pinch ile sadece resim hareket eder (caption sabit).</figcaption>
</figure>

**Kullanım — iki yol:**

1. *Markdown tek satır* (otomatik çerçeve + lightbox):
```markdown
![Alternatif metin](../_attachments/ImageCompare.png)
```

2. *Figür + açıklama* (tavsiye edilen, retro etiketiyle):
```html
<figure>
  <img src="../_attachments/ImageCompare.png" alt="ImageCompare 2.5.7 — Tek görüntü modunda BrowseComp.png" />
  <figcaption><span class="exhibit-label">GÖRSEL — ImageCompare 2.5.7</span> Tek görüntü modu. Üstte sekmeler, ortada grafik.</figcaption>
</figure>
```

**Çerçeve:** `figure` `12px` kağıt dolgu + `2px ink` çerçeve + `5px 5px` sert gölge + `-0.25deg` eğim; `img` içinde `1px solid ink` ince siyah çizgi ile sınır belli. Tek başına `p > img:only-child` de aynı çerçeveyi alır.

**Lightbox (C4/D1 güncel — %150 varsayılan):** `lightbox.js` tüm `figure img` ve `p > img:only-child` görsellerini dinler, tıklayınca `lightbox-overlay` **%150 (`scale = 1.5, tx=0, ty=0` merkezde)** ile açılır — arka plan `rgba(21,18,14,0.88)` + `blur(2px)`, çerçeve `paper-alt` + `3px ink` + `8px gölge`, kapanış `×` dış beyaz çerçevenin ucunda (`-22px`, damga dokulu `paper-grain` + kesik iç çerçeve, tam ortalı). **Viewport içinde sadece resim hareket eder, caption/toolbar sabit** — transform sırası `translate(tx,ty) scale(s)` (önce translate, sonra scale) ile pan screen-pixel alanında yapılır; eski `scale() translate()` hatası düzeltildi. `getBounds()` `maxX = (iw*scale - vw)/2` / `maxY = (ih*scale - vh)/2` ile doğru clamp eder (kenarlar %150'de hemen görülebilir ve pan edilebilir). Sınırlar `minScale=1.0 (100%)` / `maxScale=1.5 (150%)`, `step 0.15`. Tekerlek `deltaMode` normalize (`line×16`, `page×100`) + `zoomDelta ±0.08`, drag `translate` öncesi `scale`, **çift tık `%150 ↔ %100` toggle**, pinch `scale * ratio`, **reset (`↺` butonu / `0` tuşu) → %150 merkez**, **`+/-` zoom, `Esc` kapatır**, toolbar `− % + ↺` ve seviye göstergesi açılışta `150%`. `window.__lightboxInit` guard + global `mousemove/mouseup` sadece açıkken takılır, hata durumunda `largeImg.onerror` → caption "Görsel yüklenemedi".

Not: `lightbox.js` dosyasını `retro-doc.css` yanına koy ve sayfa sonuna `<script src="lightbox.js"></script>` ekle (bu dokümanda zaten ekli).

**_attachments Mimarisi — temiz ve aynalı (D2 güncel, kanonik 8 aday):**

Site `content/` altındaki her `.md` yanında `_attachments` klasörünü anlar. Dört yol da çalışır:

```text
content/docs/dokuman.md + content/_attachments/ImageCompare.png  → ../_attachments/ImageCompare.png (global)
content/linux/foo.md + content/linux/_attachments/bar.png  → linux/_attachments/bar.png
content/linux/foo.md + content/_attachments/linux/bar.png → _attachments/linux/bar.png (aynalı)
_attachments/linux/bar.png (proje kök) → build/_attachments/linux/bar.png
```

Markdown'da her zaman dosyanın yanına göre yaz: `![alt](_attachments/bar.png)` veya `![alt](bar.png)` — `build.py` **kanonik 8 aday** sırasıyla arar (D2): `1) md yanındaki dosya (md_dir/clean)` → `2) md_dir/_attachments/<basename>` → `3) content/_attachments/<rel_dir>/<basename>` (aynalı) → `4) content/_attachments/<basename>` → `5) content/_attachments/<clean>` (subpath korumalı) → `6) ROOT/_attachments/<rel_dir>/<basename>` → `7) ROOT/_attachments/<basename>` → `8) CONTENT/clean` (content kök). Subpath içeren `clean` için `_attachments/_attachments` tekrarı normalize edilir, `src`/`href` hem `"` hem `'` ile doğru yeniden yazılır (`re: ((?:src|href)\s*=\s*)(["'])([^"']+)\2`). Bulduğunu `build/` içine aynı yapıda kopyalar ve `src`'yi html'den göreceli yeniden yazar. Yani `content/linux/` içindeysen `_attachments/` içine `linux/` klasörü açıp oraya koyman da okunur. `src`/`href` tek tırnaklı yazımlar da düzeltilir (C6).

### Bileşenler (Shout, CTA, İmza, Altlık)

```html
<div class="shout">Büyük uyarı kutusu. <span>Vurgulu kısım.</span></div>

<p class="u-center u-mt-lg">
  <a class="cta-angry" href="angry.html">Öfkeli sürüme git →</a>
</p>

<div class="signature">
  <div class="name">— birisi,<br>ekip arkadaşın</div>
  <small>bilerek, bir insan tarafından yazıldı.</small>
</div>

<div class="footer">
  <p>Çoğunlukla hiciv.</p>
</div>
```

`.cta-calm` yeşil, sakin bir alternatif buton stilidir; `.cta-angry` ile aynı biçimde kullanılır:

```html
<a class="cta-calm" href="calm.html">Sakin sürüme git →</a>
```

### Durum Göstergesi (Radyo / Onay Kutusu)

Bu bileşen bir durumu göstermek içindir: durumu `dokuman.md` içinde ilgili seçeneğe `checked` ekleyerek belirlersin. Sitede ziyaretçi değiştiremez; kilit CSS'te (`.choice` üzerinde `pointer-events: none`) çözülür ve input'lara `tabindex="-1"` eklenir, böylece `disabled` gerekmez ve görünüm normal kalır. (M7) `.choice:hover` ölü kod olduğu için kaldırıldı — `pointer-events:none` hover'ı zaten engellediğinden highlight yok, davranış dokümanla tam uyumlu. Radyo tek seçim, onay kutusu çoklu seçim içindir; görünüm tamamen özel CSS ile çizilir:

```html
<fieldset class="choice-group">
  <legend>Aşama Seç</legend>
  <label class="choice"><input type="radio" name="asama" value="taslak" tabindex="-1"> Taslak oluştur</label>
  <label class="choice"><input type="radio" name="asama" value="inceleme" checked tabindex="-1"> İnceleme talep edildi</label>
</fieldset>

<fieldset class="choice-group">
  <legend>Yapılacaklar</legend>
  <label class="choice"><input type="checkbox" name="todo" value="taslak" checked tabindex="-1"> Proje taslağını oluştur</label>
  <label class="choice"><input type="checkbox" name="todo" value="inceleme" tabindex="-1"> İnceleme talep et</label>
</fieldset>
```

### Görev Listeleri (Todo) — Display-Only ve Boşluk

Pandoc'un `- [ ]` / `- [x]` görev listesi bu temada **display-only** kilitlidir — tıpkı `choice-group` gibi `pointer-events:none` ile ziyaretçi değiştiremez, `checked` durumu `dokuman.md` kaynağında belirlenir. Kareler `choice` ile aynı retro stil: `1.15rem`, `2px ink` çerçeve, `ink` dolgu + sarı tik, `border-radius:2px`.

Boşluk düzeni: `ul.task-list li` artık `flex` değil, `li` `padding:0.32rem 0` + `line-height:1.55`, `label` `display:inline`, `input` `margin-inline-end:0.55rem` + `vertical-align:-0.12em` — kare ile metin arası tam 0.55rem, kod etiketli satırlarda bile (`--hwdec=auto` gibi) hizalı. Pandoc'un enjekte ettiği `width:0.8em` kuralı `retro-doc.css` unlayered override ile `1.15rem !important` olarak ezilir, odak halkası kapatılır.

```markdown
- [ ] Gerekirse --hwdec=auto eklemeyi değerlendir
- [x] v0.6.0 yayımlandı
```

Canlı todo (tıklanamaz, sadece gösterir):

- [ ] Gerekirse `--hwdec=auto` donanım hızlandırma bayrağını varsayılan eklemeyi değerlendir
- [x] Retro çerçeve + lightbox eklendi

### Otomatik Site — content/ → build/ + Sidebar + Son Eklenenler (D3/D8/C1-C3 güncel)

`content/` içine (alt klasör dahil) attığın her `.md` otomatik sitede görünür. Derleme `build.py` ile (güvenli temizlik + izole tmp):

```bash
python3 build.py   # content/**/*.md → build/**/*.html + sidebar + _attachments kopyalama
# C1: BUILD=ROOT/build resolve edilip ROOT içinde ve symlink değilse silinir, aksi halde RuntimeError
# C2: pandoc her md için tempfile.NamedTemporaryFile(suffix=.html) ile izole, subprocess.run(..., timeout=30), finally unlink
# M4: shutil.which("pandoc") yoksa SystemExit
```

* `content/` → `build/` aynalı: `content/linux/foo.md` → `build/linux/foo.html` (klasör yapısı korunur)
* `build/` içinde `retro-doc.css` + `lightbox.js` her sayfaya **göreceli `os.path.relpath`** ile eklenir; fontlar `retro-doc.css` `@import` olmadan HTML `<link rel="preconnect" href="https://fonts.googleapis.com">` + `crossorigin` + `stylesheet` ile yüklenir (M1, render-blocking yok)
* Pandoc çağrısı: `pandoc <md> -o <tmp> --standalone -c retro-doc.css --metadata title="<sanitize_title>"` — `sanitize_title()` newlines/quotes siler, 120 karaktere kırpar, `title=` güvenli (C7)
* `build.py` hatalar `except Exception:` + `traceback.print_exc()` ile loglanır, bare `except:` yok (C3); her `md` tek kez okunur ve `get_title_from_text`/`get_excerpt_from_text`e verilir (M5)
* `src`/`href` (çift ve tek tırnak) `_attachments` 8 aday ile `re: ((?:src|href)\s*=\s*)(["'])([^"']+)\2` üzerinden düzeltilir (C6)
* Sol sidebar `contentTree` tarzı: tüm klasör/dosyalar `▸` hiyerarşi, aktif sayfa vurgulu, retro kağıt (`paper-alt` + `ink` çerçeve + gölge), mobilde `☰` ile açılır overlay'li
* **Sheet fallback (C5/D3):** `body:not(:has(.sheet))` kaldırıldı; yerine `body` fallback sheet + `body.has-sheet` (build.py `class="has-sheet"` ekler) ve `@supports selector(:has(*)) { body:has(.sheet) }` progressive enhancement. Eski Firefox/Safari'de de sheet düzgün render olur
* **320px güvenlik (D3/M8):** `@media (max-width:480px) { .recent-card, .sheet { transform:none } }` ile 320px'de yatay taşma yok; `recent-card` rotate sadece >480px'de
* Ana dizine `build/index.html` (ve köke `index.html`) otomatik **Son Eklenenler** sayfası üretilir — en yeni 8 belge `mtime`'a göre üstte, kartlarda başlık/klasör/tarih/özet ve `contentTree` ile birlikte
* `content/` dışındaki `_attachments` aynalı mimarisi de desteklenir (yukarıdaki _attachments bölümüne bak)

### Dekoratif Damga ve Karalama (Stamp / Scribble)

İsteğe bağlı, salt görsel süsleme öğeleridir; `.sheet` veya `body`'ye göre konumlanır ve `pointer-events: none` ile etkileşimden muaftır. Uzun sayfalarda birden fazla `.scribble-N` konumu tanımlayabilirsiniz:

```html
<span class="stamp">Onaylandı</span>
<span class="scribble scribble-1">bkz. dipnot →</span>
```

### Yararlı Hizalama Sınıfları

`.u-center` (ortala), `.u-muted` (sönük metin), `.u-small` (küçük metin), `.u-mt-lg` / `.u-mt-md` (üst boşluk) gibi yardımcı sınıflar hizalamayı kolaylaştırır:

```html
<p class="u-center u-small u-muted">Küçük, ortalı, sönük bir not.</p>
```

### Sheet Container & Responsive Güvenlik (C5/D3/M8 güncel)

* **Sheet fallback:** Eski `body:not(:has(.sheet))` kaldırıldı. Yerine `body` fallback sheet (`max-inline-size: min(880px,100% -2rem)` + `paper-alt` + `2px ink` + `6px gölge`) ve `body.has-sheet` (build.py her sayfada `class="has-sheet"` ekler) + `@supports selector(:has(*)) { body:has(.sheet) }` progressive enhancement. Böylece Firefox <121 / Safari <15.4 dahil tüm tarayıcılarda Pandoc standalone (sheet yok) ve `main.sheet` (sheet var) doğru render olur.
* **320px güvenlik:** `@media (max-width:480px) { .recent-card, .recent-card:nth-child(even), .sheet { transform:none } }` ile 320px'de `rotate(-0.15deg)` ve `6px` gölge taşması engellenir; yatay scrollbar yok. Sheet `padding` `clamp(1.2rem,5vw,2rem)` ile dar ekranda küçülür.
* **Font yükleme (M1):** `retro-doc.css` `@import` kaldırıldı; fontlar HTML `<link rel="preconnect">` + `crossorigin` ile yüklenir, render-blocking yok.
* **Kod kopya:** `div.sourceCode` her bloğa `.copy-btn` (SVG clip → tik 2s, `is-copied` sınıfı) eklenir; `navigator.clipboard.writeText` birincil, fallback `document.execCommand("copy")`.
* **Tipografi & interaksiyon:** `choice-group` ve `task-list` `pointer-events:none` kilitli display-only, `:focus-visible` outline korunur, `task-list` `1.15rem !important` override ile Pandoc `0.8em` ezilir.

<script>
(function () {
  "use strict";
  function copyText(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      return navigator.clipboard.writeText(text);
    }
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.style.position = "fixed";
      ta.style.top = "-9999px";
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); resolve(); }
      catch (e) { reject(e); }
      finally { document.body.removeChild(ta); }
    });
  }
  function makeButton(pre) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "copy-btn";
    btn.setAttribute("aria-label", "Kodu kopyala");
    btn.innerHTML =
      '<svg class="ic ic-copy" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">' +
        '<rect x="6" y="4" width="12" height="17" rx="1"></rect>' +
        '<rect x="9" y="2" width="6" height="3"></rect>' +
        '<line x1="9" y1="10" x2="15" y2="10"></line>' +
        '<line x1="9" y1="14" x2="15" y2="14"></line>' +
      '</svg>' +
      '<svg class="ic ic-check" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="square" stroke-linejoin="miter" aria-hidden="true">' +
        '<polyline points="5 12 10 17 19 7"></polyline>' +
      '</svg>';
    btn.addEventListener("click", function () {
      var node = pre.querySelector("code") || pre;
      var text = node.innerText || node.textContent || "";
      copyText(text).then(function () { flag(btn); }, function () { flag(btn); });
    });
    return btn;
  }
  function flag(btn) {
    btn.classList.add("is-copied");
    btn.setAttribute("aria-label", "Kopyalandı");
    setTimeout(function () {
      btn.classList.remove("is-copied");
      btn.setAttribute("aria-label", "Kodu kopyala");
    }, 2000);
  }
  function init() {
    var blocks = document.querySelectorAll("div.sourceCode");
    for (var i = 0; i < blocks.length; i++) {
      var wrapper = blocks[i];
      if (wrapper.querySelector(".copy-btn")) continue;
      var pre = wrapper.querySelector("pre") || wrapper;
      wrapper.appendChild(makeButton(pre));
    }
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
</script>
