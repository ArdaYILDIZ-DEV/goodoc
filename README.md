<p align="center">
  <strong>goodoc</strong>
</p>

<p align="center">
  notlarımı tek yerde toplamak için yaptığım ufak bir site derleyici — markdown yazıyorum, pandoc çeviriyor, retro tema giydiriyor.
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="pandoc" src="https://img.shields.io/badge/pandoc-gerekiyor-0A2A4A">
  <img alt="MIT" src="https://img.shields.io/badge/license-MIT-green.svg">
</p>

Pandoc'u seviyorum ama her seferinde aynı HTML'leri elle toparlamak yoruyordu. goodoc, `content/` klasörüne attığım `.md` dosyalarını alıp `build/` içinde hazır siteye çeviriyor. Sidebar, görsel büyütme falan hep içinde, ben sadece yazıyorum.

Demo / tema kataloğu için `content/docs/dokuman.md` dosyasına bak — orası bütün bileşenlerin canlı örneği.

## Hızlı başlangıç

```bash
git clone https://github.com/ArdaYILDIZ-DEV/goodoc.git
cd goodoc

# pandoc yoksa önce kur (Arch: pacman -S pandoc / Ubuntu: apt install pandoc)
python build.py

# önizle
python -m http.server --directory build
# http://localhost:8000
```

`content/` içine yeni bir dosya atıp tekrar `python build.py` demen yeterli. `build/` ve kökteki `index.html` otomatik yenileniyor.

## Nasıl çalışıyor

Çok bir şey yok aslında:

* `content/**/*.md` dosyalarını buluyor, tarihe göre sıralıyor
* `retro-doc.css` ve `lightbox.js`'i `build/`'e kopyalıyor
* her markdown'ı `pandoc --standalone` ile HTML'e çeviriyor
* görselleri `_attachments` klasörlerinden bulup doğru yere kopyalıyor, `src`'leri düzeltiyor
* sol taraftaki ağacı ve `Son eklenenler` sayfasını oluşturuyor

`build/` tamamen silinip yeniden üretilebilir. O yüzden repoda yok, `.gitignore`'da.

## Yeni bir yazı eklemek

```bash
mkdir -p content/notlar
cat > content/notlar/merhaba.md <<'MD'
---
title: Merhaba
---

# Merhaba

Bu ilk notum.

![bir resim](_attachments/resim.png)
MD

# resmi yanına koy
mkdir -p content/notlar/_attachments
cp ~/resim.png content/notlar/_attachments/

python build.py
```

`build/notlar/merhaba.html` hazır. Resmi ister notun yanındaki `_attachments`'a, ister `content/_attachments/` altına koy — ikisi de çalışıyor.

## Tema

Daktilo / dosya havası sevdiğim için böyle yaptım. Special Elite başlıklar, JetBrains Mono metinler, kağıt rengi, kırmızı damga rengi, sert gölgeler. `retro-doc.css` tek dosya, katmanlı (`@layer`) duruyor. Kurcalamak istersen oraya bak.

Canlı örnekler için `content/docs/dokuman.md` en iyi yer — başlıklar, tablolar, kod blokları, alıntılar, görseller hepsi orada.

* Kod bloklarında kopyala butonu var
* Tablolar zebra
* Görselleri tıklayınca lightbox açılıyor, sürükle / tekerlek ile zoom yapılıyor
* Mobilde sidebar çekmece oluyor

## Proje yapısı

```
goodoc/
├── build.py        # derleyici — tek dosya, hepsi orada
├── retro-doc.css   # tema
├── lightbox.js     # görsel büyütme
├── content/
│   └── docs/dokuman.md
└── build/          # çıktı (git'te yok)
```

`build.py`'yi açarsan en üstte ne yaptığı özetli, fonksiyonların başında da kısa açıklamalar var.

## Gerekenler

* Python 3.11+
* pandoc

Başka bağımlılık yok.

## Sorun çıkarsa

**`pandoc not found`**
→ `sudo pacman -S pandoc` ya da `sudo apt install pandoc`

**Görsel gözükmüyor**
→ `![alt](_attachments/resim.png)` şeklinde yazdığından ve resmin gerçekten `content/.../_attachments/` içinde olduğundan emin ol. `python build.py` log'unda `copy ... -> build/...` satırı yoksa yolu yanlıştır.

**Değişiklik gözükmüyor**
→ `python build.py`'yi tekrar çalıştırdın mı? `build/` otomatik yenileniyor ama elle tetiklemen gerekiyor.

## Lisans

MIT — al, kullan, değiştir, paylaş.
