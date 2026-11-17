# DersPusulası

DersPusulası, üniversite öğrencilerinin ders materyallerini sınava kadar çalışabilecekleri bir plana dönüştürmelerine yardımcı olan bir uygulamadır.

Öğrenci ders PDF’lerini yükler, çalışacağı sayfaları, sınav tarihini ve günlük müsaitliğini belirtir. Uygulama, öğrencinin belirlediği sayfa başına tahmini çalışma süresini kullanarak günlük plan oluşturur. Mevcut süre yetersizse plana sığmayan çalışmayı gösterir.

## Vize kapsamında geliştirilecek özellikler

1. PDF yükleme, saklama ve yeniden görüntüleme.
2. Çalışılacak sayfaları günlük müsaitliğe göre planlama.

## Planlanan geliştirmeler

- Tamamlanan sayfaları kaydetme.
- Yeni belgeler ve değişen müsaitliğe göre planı güncelleme.
- Seçilen sayfalardan kaynak bilgisiyle kısa çalışma notları üretme.

## İş takip panosu

[DersPusulası İş Takibi](https://github.com/users/ynsemre08/projects/1)

## Çalıştırma adımları

Gereksinimler: Python 3.13 ve Git.

```powershell
git clone https://github.com/ynsemre08/ders-pusulasi.git
cd ders-pusulasi
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

Tarayıcıda http://127.0.0.1:8000 adresini açın.

Bu komutlar Windows PowerShell içindir. Uygulamayı durdurmak için
terminalde Ctrl+C kullanın.

## Özellikleri deneme

### 1. PDF yükleme, saklama ve yeniden görüntüleme

1. Ders adını girin.
2. Sayfa sayısını bildiğiniz, şifresiz bir PDF seçin.
3. “PDF’yi kaydet” düğmesine basın.
4. Listede ders adını, dosya adını ve sayfa sayısını kontrol edin.
5. “PDF’yi aç” bağlantısıyla dosyanın açıldığını doğrulayın.
6. Uygulamayı durdurup yeniden başlatın. Kaydın korunduğunu
   ve PDF’nin yeniden açıldığını kontrol edin.

Hata kontrolleri:
- Ders adına yalnızca boşluk girildiğinde kayıt reddedilir.
- PDF olmayan bir dosya seçildiğinde kayıt reddedilir.
- Hatalı girişlerde yeni belge kaydı oluşturulmaz.

Dosya boyutu sınırı 20 MB’dir. Şifreli PDF’ler desteklenmez.
Belgeler ve veritabanı yerel `data/` klasöründe saklanır.
Bu klasör Git deposuna dahil edilmez.

### 2. Günlük müsaitliğe göre çalışma planı oluşturma

1. Yüklenen PDF’nin satırındaki “Plan oluştur” bağlantısına tıklayın.
2. Çalışılacak ilk ve son sayfayı seçin.
3. Sayfa başına tahmini çalışma süresini dakika olarak girin.
4. Sınav tarihini belirleyin.
5. Çalışabileceğiniz tarihleri ve her günün müsaitlik süresini girin.
   Ek tarihler için “Gün ekle” düğmesini kullanın.
6. “Planı hesapla” düğmesine basın.

Örnek deneme — en az 8 sayfalık bir PDF için:
- Sayfa aralığı: 1–8.
- Sayfa başına süre: 5 dakika.
- Sınav tarihi: bugünden iki gün sonra.
- Bugünkü müsaitlik: 20 dakika.
- Yarınki müsaitlik: 10 dakika.

Beklenen sonuç:
- Bugüne 1–4. sayfalar, yarına 5–6. sayfalar atanır.
- 7–8. sayfalar plana sığmaz; gereken ek süre 10 dakika gösterilir.
- Yarınki müsaitlik 20 dakikaya çıkarılıp yeniden hesaplandığında
  8 sayfanın tamamı plana sığar.

Ek kontroller:
- Sayfa aralığını 3–6, bugünkü müsaitliği 0 ve yarınki
  müsaitliği 20 dakika yapın. Yalnızca yarına 3–6. sayfalar atanmalıdır.
- PDF sınırları dışındaki sayfalar ve sıfır veya negatif
  sayfa başına çalışma süresi reddedilir.

Planlama kuralları:
- Tarihler Türkiye saatine göre değerlendirilir.
- Geçmiş günler, sınav günü ve sınavdan sonraki günler kullanılamaz.
- Günlük müsaitlik aşılmaz; 0 dakika olan güne çalışma atanmaz.
- Sayfalar sırayla dağıtılır. Her sayfa tek günde tamamlanır;
  bir güne sığmayan sayfa sonraki müsait güne bırakılır.
- Listede olmayan günlere çalışma atanmaz.
- Aynı tarih birden fazla girilemez.

Bu sürümde her plan tek PDF için hesaplanır ve sonuç ekranda
gösterilir. İlerleme kaydı ve yeni materyallere göre otomatik
plan güncelleme, sonraki geliştirmeler arasındadır.

## Otomatik testler

Proje klasöründe çalıştırın:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Mevcut sürümde 66 test bulunmaktadır. Testler geçici klasörlerde
çalışır; kullanıcının yüklediği belgeleri değiştirmez.

## Proje durumu

Vize kapsamındaki iki özellik uygulanmıştır:
1. PDF yükleme, kalıcı saklama ve yeniden görüntüleme.
2. Günlük müsaitliğe göre sayfa bazında çalışma planı oluşturma.

Manuel senaryolar doğrulanmış ve 66 otomatik test geçmiştir.
Diğer geliştirmeler iş takip panosunda planlanmıştır.