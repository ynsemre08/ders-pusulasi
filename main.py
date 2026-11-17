"""DersPusulası: PDF materyalleri ve müsaitliğe göre çalışma planı."""

from contextlib import asynccontextmanager, closing, contextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from itertools import zip_longest
from pathlib import Path
import sqlite3
from typing import Annotated, Callable
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from jinja2 import Environment
from pypdf import PdfReader

from planlama import plan_olustur, turkiye_bugunu


MAKSIMUM_DOSYA_BOYUTU = 20 * 1024 * 1024


def dakika_yaz(deger):
    metin = format(deger, "f")
    return metin.rstrip("0").rstrip(".") if "." in metin else metin


SABLON_ORTAMI = Environment(autoescape=True)
SABLON_ORTAMI.filters["dakika"] = dakika_yaz

# İlk sürümde ekranı da tek dosyada tutuyoruz.
SAYFA = SABLON_ORTAMI.from_string(r"""
<!doctype html>
<html lang="tr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DersPusulası — Ders materyalleri</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; background: #f4f6fa; color: #1e293b;
      font-family: system-ui, sans-serif; line-height: 1.6; }
    main { max-width: 900px; margin: 48px auto; padding: 0 20px; }
    h1 { margin-bottom: 0; color: #173e69; }
    .intro { margin-top: 6px; color: #526176; }
    section { background: white; border: 1px solid #dbe2eb;
      border-radius: 12px; padding: 24px; margin-top: 24px; }
    h2 { margin-top: 0; font-size: 1.25rem; }
    label { display: block; font-weight: 600; margin-top: 14px; }
    input { display: block; width: 100%; padding: 10px;
      border: 1px solid #b4c1d2; border-radius: 6px; margin: 6px 0 16px; }
    button { background: #173e69; color: white; border: 0;
      border-radius: 6px; padding: 11px 20px; font: inherit; cursor: pointer; }
    a { color: #174f92; }
    .note { color: #526176; font-size: .9rem; }
    .error { background: #fff0ee; color: #962f24; padding: 12px; border-radius: 6px; }
    .success { background: #e8f6ed; color: #20643b; padding: 12px; border-radius: 6px; }
    .table-wrap { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th, td { padding: 12px 8px; border-bottom: 1px solid #e3e8ef; }
    td { overflow-wrap: anywhere; }
    .fields { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 16px; }
    .secondary { background: #e5edf7; color: #173e69; margin: 8px 8px 8px 0; }
    .remove { background: #f4e8e7; color: #962f24; padding: 7px 12px; }
    .availability input { min-width: 120px; margin: 0; }
    #calisma-plani { scroll-margin-top: 20px; }
    @media (max-width: 600px) { .fields { grid-template-columns: 1fr; gap: 0; } }
  </style>
</head>
<body>
<main>
  <h1>DersPusulası</h1>
  <p class="intro">Ders materyallerini bir araya getir. Çalışmaya buradan başla.</p>
  {% if hata %}<p class="error" role="alert">{{ hata }}</p>{% endif %}
  {% if kaydedildi %}<p class="success" role="status">PDF kaydedildi.</p>{% endif %}
  <section>
    <h2>Ders materyali ekle</h2>
    <form action="/belgeler" method="post" enctype="multipart/form-data">
      <label for="ders_adi">Ders adı</label>
      <input id="ders_adi" name="ders_adi" maxlength="120" required
        placeholder="Örnek: Algoritma Analizi" value="{{ ders_adi }}">
      <label for="dosya">PDF dosyası</label>
      <input id="dosya" name="dosya" type="file" accept=".pdf,application/pdf" required>
      <p class="note">En fazla 20 MB. Şifreli PDF’ler bu sürümde desteklenmez.</p>
      <button type="submit">PDF’yi kaydet</button>
    </form>
  </section>
  <section>
    <h2>Yüklenen materyaller <span class="note">({{ belgeler|length }})</span></h2>
    {% if belgeler %}
    <div class="table-wrap"><table>
      <thead><tr><th>Ders</th><th>Dosya</th><th>Sayfa</th><th>İşlem</th></tr></thead>
      <tbody>{% for belge in belgeler %}
      <tr>
        <td>{{ belge.ders_adi }}</td><td>{{ belge.dosya_adi }}</td>
        <td>{{ belge.sayfa_sayisi }}</td>
        <td><a href="/belgeler/{{ belge.id }}/pdf" target="_blank" rel="noopener">PDF’yi aç</a>
          · <a href="/belgeler/{{ belge.id }}/plan#calisma-plani">Plan oluştur</a></td>
      </tr>
      {% endfor %}</tbody>
    </table></div>
    {% else %}<p class="note">Henüz materyal eklemedin. İlk PDF’ni yukarıdaki formdan yükle.</p>{% endif %}
  </section>
  {% if plan_belgesi %}
  <section id="calisma-plani">
    <h2>Çalışma planı oluştur</h2>
    <p><strong>{{ plan_belgesi.ders_adi }}</strong> · {{ plan_belgesi.dosya_adi }}
      · {{ plan_belgesi.sayfa_sayisi }} sayfa</p>
    <p class="note">PDF’nin ilk sayfası 1 kabul edilir. Sınav günü planlanmaz.
      Tarih hesabında Türkiye saati kullanılır.</p>
    <form action="/belgeler/{{ plan_belgesi.id }}/plan#calisma-plani" method="post">
      <div class="fields">
        <div><label for="ilk_sayfa">İlk sayfa</label>
          <input id="ilk_sayfa" name="ilk_sayfa" type="number" min="1"
            max="{{ plan_belgesi.sayfa_sayisi }}" value="{{ plan_form.ilk_sayfa }}" required></div>
        <div><label for="son_sayfa">Son sayfa</label>
          <input id="son_sayfa" name="son_sayfa" type="number" min="1"
            max="{{ plan_belgesi.sayfa_sayisi }}" value="{{ plan_form.son_sayfa }}" required></div>
        <div><label for="sayfa_dakika">Sayfa başına tahmini süre (dakika)</label>
          <input id="sayfa_dakika" name="sayfa_dakika" type="number" min="0.01"
            max="1440" step="0.01" value="{{ plan_form.sayfa_dakika }}" required></div>
        <div><label for="sinav_tarihi">Sınav tarihi</label>
          <input id="sinav_tarihi" name="sinav_tarihi" type="date"
            min="{{ yarin }}" value="{{ plan_form.sinav_tarihi }}" required></div>
      </div>
      <h3>Günlük müsaitliğin</h3>
      <p class="note">Çalışabileceğin günleri ekle. Listede olmayan veya süresi 0 olan
        günlere çalışma atanmaz. Her sayfa tek günde tamamlanacak şekilde planlanır.</p>
      <div class="table-wrap"><table class="availability">
        <thead><tr><th>Tarih</th><th>Müsait süre (dakika)</th><th>İşlem</th></tr></thead>
        <tbody id="gunler">
          {% for tarih, dakika in plan_form.gunler %}
          <tr><td><input type="date" name="gun_tarihi" aria-label="Çalışma günü"
            min="{{ bugun }}" value="{{ tarih }}" required></td>
          <td><input type="number" name="musait_dakika" aria-label="Müsait dakika"
            min="0" max="1440" step="1" value="{{ dakika }}" required></td>
          <td><button class="remove" type="button">Günü kaldır</button></td></tr>
          {% endfor %}
        </tbody>
      </table></div>
      <button type="button" class="secondary" id="gun-ekle">Gün ekle</button>
      <button type="submit">Planı hesapla</button>
    </form>
    {% if plan_hatasi %}<p class="error" role="alert">{{ plan_hatasi }}</p>{% endif %}
    {% if sonuc %}
    <h3>Çalışma planın</h3>
    <p>Seçilen kapsam: <strong>{{ sonuc.toplam_sayfa }} sayfa</strong>,
      {{ sonuc.toplam_dakika|dakika }} dakika.
      Planlanan: <strong>{{ sonuc.planlanan_sayfa }} sayfa</strong>,
      {{ sonuc.planlanan_dakika|dakika }} dakika.</p>
    <div class="table-wrap"><table id="plan-sonucu">
      <thead><tr><th>Gün</th><th>Müsait süre</th><th>Çalışılacak sayfalar</th><th>Çalışma süresi</th></tr></thead>
      <tbody>{% for gun in sonuc.gunler %}
        <tr><td>{{ gun.tarih.strftime('%d.%m.%Y') }}</td>
          <td>{{ gun.musait_dakika }} dakika</td>
          <td>{% if gun.ilk_sayfa %}{{ gun.ilk_sayfa }}–{{ gun.son_sayfa }}{% else %}Çalışma atanmadı{% endif %}</td>
          <td>{{ gun.calisma_dakika|dakika }} dakika</td></tr>
      {% endfor %}</tbody>
    </table></div>
    {% if sonuc.sigmayan_sayfa %}
      <p class="error" role="status">Plana sığmayan: {{ sonuc.sigmayan_ilk_sayfa }}–{{ sonuc.sigmayan_son_sayfa }}.
        sayfalar ({{ sonuc.sigmayan_sayfa }} sayfa).
        Gereken ek süre: <strong>{{ sonuc.ek_dakika|dakika }} dakika</strong>.</p>
      <p class="note">Müsaitliğini artırıp yeniden hesaplayabilirsin.
        Bir güne tam sayfa sığmadığında o günün artan süresi başka güne aktarılmaz.</p>
    {% else %}<p class="success" role="status">Seçilen sayfaların tamamı plana sığıyor.</p>{% endif %}
    {% endif %}
  </section>
  <script>
    const gunler = document.getElementById('gunler');
    const sinav = document.getElementById('sinav_tarihi');
    function tarihEkle(tarih, fark) {
      if (!/^\d{4}-\d{2}-\d{2}$/.test(tarih)) return '';
      const d = new Date(tarih + 'T00:00:00Z');
      if (Number.isNaN(d.getTime())) return '';
      d.setUTCDate(d.getUTCDate() + fark);
      return d.toISOString().slice(0, 10);
    }
    function sinirlariGuncelle() {
      const sonGun = tarihEkle(sinav.value, -1);
      gunler.querySelectorAll('[name="gun_tarihi"]').forEach(input => {
        if (sonGun) input.max = sonGun;
        else input.removeAttribute('max');
      });
    }
    document.getElementById('gun-ekle').addEventListener('click', () => {
      const son = gunler.lastElementChild;
      const yeni = son.cloneNode(true);
      const yeniTarih = tarihEkle(son.querySelector('[name="gun_tarihi"]').value, 1);
      yeni.querySelector('[name="gun_tarihi"]').value =
        yeniTarih && yeniTarih < sinav.value ? yeniTarih : '';
      yeni.querySelector('[name="musait_dakika"]').value = '0';
      gunler.appendChild(yeni);
      sinirlariGuncelle();
    });
    gunler.addEventListener('click', event => {
      const button = event.target.closest('button.remove');
      if (button && gunler.children.length > 1) button.closest('tr').remove();
    });
    sinav.addEventListener('change', sinirlariGuncelle);
    sinirlariGuncelle();
  </script>
  {% endif %}
</main>
</body>
</html>
""")


def uygulama_olustur(
    veri_klasoru: Path | None = None,
    bugun_fonksiyonu: Callable[[], date] | None = None,
) -> FastAPI:
    bugunu_al = bugun_fonksiyonu or turkiye_bugunu
    # Dosya konumu terminalin açıldığı klasörden etkilenmez.
    veri_klasoru = (
        Path(veri_klasoru) if veri_klasoru is not None
        else Path(__file__).resolve().parent / "data"
    )
    pdf_klasoru = veri_klasoru / "pdfler"
    veritabani = veri_klasoru / "ders_pusulasi.sqlite3"

    @contextmanager
    def baglanti():
        with closing(sqlite3.connect(veritabani)) as db:
            db.row_factory = sqlite3.Row
            with db:
                yield db

    @asynccontextmanager
    async def yasam_dongusu(app: FastAPI):
        pdf_klasoru.mkdir(parents=True, exist_ok=True)
        with baglanti() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS belgeler (
                    id TEXT PRIMARY KEY,
                    ders_adi TEXT NOT NULL,
                    dosya_adi TEXT NOT NULL,
                    sayfa_sayisi INTEGER NOT NULL CHECK (sayfa_sayisi > 0),
                    kayit_zamani TEXT NOT NULL
                )
            """)
        yield

    app = FastAPI(title="DersPusulası", lifespan=yasam_dongusu)

    def ekran(
        hata=None, ders_adi="", kaydedildi=False, durum=200,
        plan_belgesi=None, plan_form=None, sonuc=None, plan_hatasi=None,
    ):
        bugun = bugunu_al()
        if plan_belgesi is not None and plan_form is None:
            plan_form = {
                "ilk_sayfa": "1", "son_sayfa": str(plan_belgesi["sayfa_sayisi"]),
                "sayfa_dakika": "5", "sinav_tarihi": (bugun + timedelta(days=2)).isoformat(),
                "gunler": [(bugun.isoformat(), "0")],
            }
        with baglanti() as db:
            belgeler = db.execute(
                "SELECT * FROM belgeler ORDER BY kayit_zamani DESC, id"
            ).fetchall()
        return HTMLResponse(
            SAYFA.render(
                belgeler=belgeler, hata=hata,
                ders_adi=ders_adi, kaydedildi=kaydedildi,
                plan_belgesi=plan_belgesi, plan_form=plan_form,
                sonuc=sonuc, plan_hatasi=plan_hatasi,
                bugun=bugun.isoformat(), yarin=(bugun + timedelta(days=1)).isoformat(),
            ),
            status_code=durum,
        )

    @app.get("/", response_class=HTMLResponse)
    def ana_sayfa(kaydedildi: bool = False):
        return ekran(kaydedildi=kaydedildi)

    @app.post("/belgeler", response_class=HTMLResponse)
    def belge_yukle(
        ders_adi: Annotated[str, Form()] = "",
        dosya: Annotated[UploadFile | None, File()] = None,
    ):
        ders_adi = ders_adi.strip()

        def reddet(mesaj):
            return ekran(hata=mesaj, ders_adi=ders_adi, durum=400)

        try:
            if not ders_adi:
                return reddet("Ders adı boş bırakılamaz.")
            if len(ders_adi) > 120:
                return reddet("Ders adı en fazla 120 karakter olabilir.")
            if dosya is None or not dosya.filename:
                return reddet("Yüklenecek PDF dosyasını seçin.")

            dosya_adi = Path(dosya.filename.replace("\\", "/")).name
            if not dosya_adi.lower().endswith(".pdf"):
                return reddet("Lütfen .pdf uzantılı bir PDF dosyası seçin.")

            icerik = dosya.file.read(MAKSIMUM_DOSYA_BOYUTU + 1)
            if len(icerik) > MAKSIMUM_DOSYA_BOYUTU:
                return reddet("PDF dosyası 20 MB sınırını aşıyor.")
            if not icerik.startswith(b"%PDF-"):
                return reddet("Dosya geçerli bir PDF değil.")

            try:
                okuyucu = PdfReader(BytesIO(icerik), strict=True)
                if okuyucu.is_encrypted:
                    return reddet("Şifreli PDF desteklenmiyor. Şifresiz bir kopya yükleyin.")
                sayfa_sayisi = len(okuyucu.pages)
                if sayfa_sayisi < 1:
                    return reddet("PDF en az bir sayfa içermelidir.")
            except Exception:
                # Kullanıcının yüklediği bozuk PDF, sunucu hatasına dönüşmemeli.
                return reddet("PDF okunamadı. Dosya bozuk veya desteklenmeyen bir yapıda olabilir.")

            belge_id = uuid4().hex
            hedef = pdf_klasoru / f"{belge_id}.pdf"
            try:
                hedef.write_bytes(icerik)
                with baglanti() as db:
                    db.execute(
                        "INSERT INTO belgeler VALUES (?, ?, ?, ?, ?)",
                        (belge_id, ders_adi, dosya_adi, sayfa_sayisi,
                         datetime.now(timezone.utc).isoformat()),
                    )
            except Exception:
                # Veritabanı kaydı başarısızsa sahipsiz dosya bırakma.
                hedef.unlink(missing_ok=True)
                raise

            # Sayfayı yenilemek aynı PDF'yi tekrar yüklemez.
            return RedirectResponse("/?kaydedildi=true", status_code=303)
        finally:
            if dosya is not None:
                dosya.file.close()

    @app.get("/belgeler/{belge_id}/pdf")
    def pdf_ac(belge_id: str):
        with baglanti() as db:
            belge = db.execute(
                "SELECT * FROM belgeler WHERE id = ?", (belge_id,)
            ).fetchone()
        if belge is None:
            raise HTTPException(status_code=404, detail="Belge bulunamadı.")
        hedef = pdf_klasoru / f"{belge['id']}.pdf"
        if not hedef.is_file():
            raise HTTPException(status_code=404, detail="PDF dosyası bulunamadı.")
        return FileResponse(
            hedef, media_type="application/pdf", filename=belge["dosya_adi"],
            content_disposition_type="inline",
        )

    def belge_bul(belge_id):
        with baglanti() as db:
            belge = db.execute(
                "SELECT * FROM belgeler WHERE id = ?", (belge_id,)
            ).fetchone()
        if belge is None:
            raise HTTPException(status_code=404, detail="Belge bulunamadı.")
        if not (pdf_klasoru / f"{belge['id']}.pdf").is_file():
            raise HTTPException(status_code=404, detail="PDF dosyası bulunamadı.")
        return belge

    @app.get("/belgeler/{belge_id}/plan", response_class=HTMLResponse)
    def plan_ekrani(belge_id: str):
        return ekran(plan_belgesi=belge_bul(belge_id))

    @app.post("/belgeler/{belge_id}/plan", response_class=HTMLResponse)
    def plan_hesapla(
        belge_id: str,
        ilk_sayfa: Annotated[str, Form()] = "",
        son_sayfa: Annotated[str, Form()] = "",
        sayfa_dakika: Annotated[str, Form()] = "",
        sinav_tarihi: Annotated[str, Form()] = "",
        gun_tarihi: Annotated[list[str] | None, Form()] = None,
        musait_dakika: Annotated[list[str] | None, Form()] = None,
    ):
        belge = belge_bul(belge_id)
        tarihler = gun_tarihi or []
        dakikalar = musait_dakika or []
        form = {
            "ilk_sayfa": ilk_sayfa, "son_sayfa": son_sayfa,
            "sayfa_dakika": sayfa_dakika, "sinav_tarihi": sinav_tarihi,
            "gunler": list(zip_longest(tarihler, dakikalar, fillvalue=""))
            or [(bugunu_al().isoformat(), "0")],
        }

        def hata(mesaj):
            return ekran(plan_belgesi=belge, plan_form=form, plan_hatasi=mesaj, durum=400)

        try:
            ilk, son = int(ilk_sayfa), int(son_sayfa)
        except ValueError:
            return hata("Başlangıç ve bitiş sayfalarını tam sayı olarak girin.")
        try:
            sure = Decimal(sayfa_dakika.replace(",", "."))
        except InvalidOperation:
            return hata("Sayfa başına çalışma süresini sayı olarak girin.")
        try:
            sinav = date.fromisoformat(sinav_tarihi)
        except ValueError:
            return hata("Geçerli bir sınav tarihi girin.")
        if not tarihler or len(tarihler) != len(dakikalar):
            return hata("Her çalışma günü için tarih ve müsait süre girin.")
        try:
            musaitlik = [(date.fromisoformat(t), int(d)) for t, d in zip(tarihler, dakikalar)]
        except ValueError:
            return hata("Çalışma günlerinde geçerli tarih ve tam sayı dakika kullanın.")
        try:
            sonuc = plan_olustur(
                belge_sayfa_sayisi=belge["sayfa_sayisi"], ilk_sayfa=ilk, son_sayfa=son,
                sayfa_dakika=sure, sinav_tarihi=sinav,
                musaitlik=musaitlik, bugun=bugunu_al(),
            )
        except ValueError as exc:
            return hata(str(exc))
        return ekran(plan_belgesi=belge, plan_form=form, sonuc=sonuc)

    return app


app = uygulama_olustur()
