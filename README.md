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

Bu özellik henüz geliştirilmemiştir. İş takip panosundaki #2
numaralı görev kapsamında uygulanacaktır.

## Otomatik testler

Proje klasöründe çalıştırın:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Mevcut sürümde 18 test bulunmaktadır. Testler geçici klasörlerde
çalışır; kullanıcının yüklediği belgeleri değiştirmez.

## Proje durumu

PDF yükleme, kalıcı saklama ve yeniden görüntüleme özelliği
uygulanmıştır. Manuel kontroller ve 18 otomatik test geçmiştir.
Çalışma planı oluşturma özelliği sıradaki geliştirme görevidir.
