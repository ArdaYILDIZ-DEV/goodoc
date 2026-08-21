# Örnek Sayfa

Bu bir test sayfasıdır — goodoc build akışını ve iç sayfa bağlantılarını
doğrulamak için eklenmiştir. Front matter kullanmaz; başlık otomatik olarak
ilk `#` başlığından alınır.

## Bağlantı

Ana dökümana dönmek için [Markdown Yazma Rehberi](dokuman.md) sayfasına göz atın.
İç linkler build sırasında otomatik olarak `.html` uzantısına çevrilir, böylece
tarayıcıda çıplak `.md` kaynağı açılmaz.

## Kod Örneği

Fenced kod bloğu, sağ üstteki simgeyle panoya kopyalanabilir:

```python
def selamla(isim: str) -> str:
    """Basit bir örnek fonksiyon."""
    return f"Merhaba, {isim}!"


if __name__ == "__main__":
    print(selamla("goodoc"))
```

## Liste

- Madde bir
- Madde iki
- Madde üç

1. İlk kural
2. İkinci kural

## Alıntı

> <span class="exhibit-label">EXHIBIT B — Not</span>
> Bu sayfa, iç link yönlendirmesinin çalıştığını göstermek içindir.

## Tablo

| Sütun A | Sütun B | Durum |
|----------|----------|-------|
| Değer 1  | Değer 2  | Hazır  |
| Değer 3  | Değer 4  | Bekliyor |

Görsel ve bileşen örnekleri için ana rehbere bakınız.
