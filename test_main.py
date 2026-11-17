from io import BytesIO
import re
import sqlite3

from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pytest

import main


def pdf_bytes(sayfa=3, sifre=None):
    writer = PdfWriter()
    for _ in range(sayfa):
        writer.add_blank_page(width=100, height=100)
    if sifre:
        writer.encrypt(sifre)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def yukle(client, ders="Algoritma", ad="hafta1.pdf", icerik=None):
    return client.post(
        "/belgeler", data={"ders_adi": ders},
        files={"dosya": (ad, pdf_bytes() if icerik is None else icerik,
                         "application/pdf")},
    )


def kayitlar(tmp_path):
    with sqlite3.connect(tmp_path / "ders_pusulasi.sqlite3") as db:
        return db.execute("SELECT * FROM belgeler").fetchall()


def test_kayit_sayfa_sayisi_ve_yeniden_acma(tmp_path):
    content = pdf_bytes(7)
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        result = yukle(client, ders="  Algoritma  ", icerik=content)
        assert result.status_code == 200
        assert "PDF kaydedildi." in result.text
        rows = kayitlar(tmp_path)
        assert len(rows) == 1
        assert rows[0][1:4] == ("Algoritma", "hafta1.pdf", 7)
        url = re.search(r'href="(/belgeler/[^\"]+/pdf)"', result.text)[1]
        opened = client.get(url)
        assert opened.status_code == 200
        assert opened.content == content
        assert opened.headers["content-disposition"].startswith("inline;")
        client.get("/")
        assert len(kayitlar(tmp_path)) == 1

    # Yeni uygulama örneği, aynı kalıcı klasörü açar.
    with TestClient(main.uygulama_olustur(tmp_path)) as restarted:
        assert "hafta1.pdf" in restarted.get("/").text
        assert restarted.get(url).content == content


@pytest.mark.parametrize("ders", ["", "   ", "\t\n", "x" * 121])
def test_gecersiz_ders_kayit_olusturmaz(tmp_path, ders):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        result = yukle(client, ders=ders)
        assert result.status_code == 400
        assert not kayitlar(tmp_path)
        assert not list((tmp_path / "pdfler").iterdir())


@pytest.mark.parametrize("ad,icerik", [
    ("not.txt", b"metin"),
    ("sahte.pdf", b"PDF degil"),
    ("bos.pdf", b""),
    ("bozuk.pdf", b"%PDF-1.7\nbozuk icerik"),
    ("sifresiz_degil.pdf", pdf_bytes(sifre="test")),
    ("sayfasiz.pdf", pdf_bytes(0)),
])
def test_gecersiz_pdf_kayit_olusturmaz(tmp_path, ad, icerik):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        result = yukle(client, ad=ad, icerik=icerik)
        assert result.status_code == 400
        assert not kayitlar(tmp_path)
        assert not list((tmp_path / "pdfler").iterdir())


def test_dosya_secilmemis(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        result = client.post("/belgeler", data={"ders_adi": "Algoritma"})
        assert result.status_code == 400
        assert "PDF dosyasını seçin" in result.text
        assert not kayitlar(tmp_path)


def test_boyut_siniri(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "MAKSIMUM_DOSYA_BOYUTU", 100)
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        assert yukle(client).status_code == 400
        assert not kayitlar(tmp_path)


def test_ayni_adli_dosyalar_birbirini_ezmez(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        assert yukle(client, icerik=pdf_bytes(2)).status_code == 200
        assert yukle(client, icerik=pdf_bytes(4)).status_code == 200
        rows = kayitlar(tmp_path)
        assert len(rows) == 2
        assert sorted(row[3] for row in rows) == [2, 4]
        assert len(list((tmp_path / "pdfler").glob("*.pdf"))) == 2


def test_html_kacisi_ve_dosya_yolu(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        result = yukle(client, ders="<script>alert(1)</script>", ad="../../not.pdf")
        assert result.status_code == 200
        assert "<script>" not in result.text
        assert "&lt;script&gt;" in result.text
        assert kayitlar(tmp_path)[0][2] == "not.pdf"
        assert not (tmp_path / "not.pdf").exists()


def test_belge_bulunamadi(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        assert client.get("/belgeler/yok/pdf").status_code == 404


def test_eksik_dosya_anlasilir_404(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        yukle(client)
        belge_id = kayitlar(tmp_path)[0][0]
        (tmp_path / "pdfler" / f"{belge_id}.pdf").unlink()
        assert client.get(f"/belgeler/{belge_id}/pdf").status_code == 404


def test_veritabani_hatasinda_sahipsiz_dosya_kalmaz(tmp_path):
    with TestClient(main.uygulama_olustur(tmp_path)) as client:
        with sqlite3.connect(tmp_path / "ders_pusulasi.sqlite3") as db:
            db.execute("""CREATE TRIGGER engelle BEFORE INSERT ON belgeler
                          BEGIN SELECT RAISE(ABORT, 'test'); END;""")
        with pytest.raises(sqlite3.IntegrityError):
            yukle(client)
        assert not list((tmp_path / "pdfler").iterdir())
