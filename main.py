"""DersPusulası: PDF yükleme, kalıcı kayıt ve yeniden görüntüleme."""

from contextlib import asynccontextmanager, closing, contextmanager
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
import sqlite3
from typing import Annotated
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from jinja2 import Environment
from pypdf import PdfReader


MAKSIMUM_DOSYA_BOYUTU = 20 * 1024 * 1024

# İlk sürümde ekranı da tek dosyada tutuyoruz.
SAYFA = Environment(autoescape=True).from_string("""
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
        <td><a href="/belgeler/{{ belge.id }}/pdf" target="_blank" rel="noopener">PDF’yi aç</a></td>
      </tr>
      {% endfor %}</tbody>
    </table></div>
    {% else %}<p class="note">Henüz materyal eklemedin. İlk PDF’ni yukarıdaki formdan yükle.</p>{% endif %}
  </section>
</main>
</body>
</html>
""")


def uygulama_olustur(veri_klasoru: Path | None = None) -> FastAPI:
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

    def ekran(hata=None, ders_adi="", kaydedildi=False, durum=200):
        with baglanti() as db:
            belgeler = db.execute(
                "SELECT * FROM belgeler ORDER BY kayit_zamani DESC, id"
            ).fetchall()
        return HTMLResponse(
            SAYFA.render(
                belgeler=belgeler, hata=hata,
                ders_adi=ders_adi, kaydedildi=kaydedildi,
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

    return app


app = uygulama_olustur()
