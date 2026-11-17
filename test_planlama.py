"""İkinci görevin hesaplama ve gerçek form gönderimi testleri."""

from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO
import re

from fastapi.testclient import TestClient
from pypdf import PdfWriter
import pytest

from main import uygulama_olustur
from planlama import plan_olustur


BUGUN = date(2026, 11, 17)
YARIN = BUGUN + timedelta(days=1)
SINAV = BUGUN + timedelta(days=2)


def hesapla(**degisiklik):
    girdiler = dict(
        belge_sayfa_sayisi=20, ilk_sayfa=1, son_sayfa=20,
        sayfa_dakika=Decimal("5"), sinav_tarihi=SINAV,
        musaitlik=[(BUGUN, 60), (YARIN, 30)], bugun=BUGUN,
    )
    girdiler.update(degisiklik)
    return plan_olustur(**girdiler)


def test_issue_iki_ornegi():
    plan = hesapla()
    assert [(g.ilk_sayfa, g.son_sayfa, g.calisma_dakika) for g in plan.gunler] == [
        (1, 12, Decimal("60")), (13, 18, Decimal("30")),
    ]
    assert (plan.toplam_sayfa, plan.planlanan_sayfa) == (20, 18)
    assert (plan.sigmayan_ilk_sayfa, plan.sigmayan_son_sayfa) == (19, 20)
    assert (plan.sigmayan_sayfa, plan.ek_dakika) == (2, Decimal("10"))


def test_yalnizca_secilen_aralik_ve_siralanmamis_gunler():
    plan = hesapla(ilk_sayfa=5, son_sayfa=9, musaitlik=[(YARIN, 15), (BUGUN, 10)])
    assert [(g.tarih, g.ilk_sayfa, g.son_sayfa) for g in plan.gunler] == [
        (BUGUN, 5, 6), (YARIN, 7, 9),
    ]
    assert plan.sigmayan_sayfa == 0
    assert plan.ek_dakika == 0


def test_sifir_musaitlik_ve_tam_sayfa_kurali():
    plan = hesapla(musaitlik=[(BUGUN, 0), (YARIN, 3)])
    assert all(g.ilk_sayfa is None and g.calisma_dakika == 0 for g in plan.gunler)
    assert plan.sigmayan_sayfa == 20
    assert plan.ek_dakika == 100


def test_gunler_arasinda_artik_dakika_birlestirilmez():
    plan = hesapla(son_sayfa=2, musaitlik=[(BUGUN, 4), (YARIN, 6)])
    assert [(g.ilk_sayfa, g.son_sayfa, g.calisma_dakika) for g in plan.gunler] == [
        (None, None, 0), (1, 1, 5),
    ]
    assert plan.ek_dakika == 5


def test_fazla_kapasite_ve_tek_sayfa():
    plan = hesapla(ilk_sayfa=20, musaitlik=[(BUGUN, 100), (YARIN, 100)])
    assert (plan.gunler[0].ilk_sayfa, plan.gunler[0].son_sayfa) == (20, 20)
    assert plan.gunler[1].ilk_sayfa is None
    assert plan.planlanan_dakika == 5
    assert plan.sigmayan_ilk_sayfa is None


def test_ondalik_sure_tam_hesaplanir():
    plan = hesapla(sayfa_dakika=Decimal("0.1"), musaitlik=[(BUGUN, 1), (YARIN, 1)])
    assert plan.planlanan_sayfa == 20
    assert plan.gunler[0].son_sayfa == 10
    assert plan.toplam_dakika == Decimal("2.0")
    assert plan.ek_dakika == 0


@pytest.mark.parametrize("degisiklik", [
    {"ilk_sayfa": 0}, {"son_sayfa": 21}, {"ilk_sayfa": 9, "son_sayfa": 8},
    {"sayfa_dakika": Decimal("0")}, {"sayfa_dakika": Decimal("-5")},
    {"sayfa_dakika": Decimal("NaN")}, {"sayfa_dakika": Decimal("Infinity")},
    {"sayfa_dakika": Decimal("0.001")}, {"sayfa_dakika": Decimal("1441")},
    {"sayfa_dakika": Decimal("0.125")},
    {"sinav_tarihi": BUGUN}, {"sinav_tarihi": BUGUN - timedelta(days=1)},
    {"musaitlik": []}, {"musaitlik": [(BUGUN, -1)]},
    {"musaitlik": [(BUGUN, 1441)]}, {"musaitlik": [(SINAV, 60)]},
    {"musaitlik": [(SINAV + timedelta(days=1), 60)]},
    {"musaitlik": [(BUGUN - timedelta(days=1), 60)]},
    {"musaitlik": [(BUGUN, 30), (BUGUN, 30)]},
])
def test_gecersiz_girdiler_reddedilir(degisiklik):
    with pytest.raises(ValueError):
        hesapla(**degisiklik)


def test_cesitli_kapasitelerde_sinirlar_ve_sayfalar_korunur():
    # Farklı süre ve kapasiteler: hiçbir sayfa kaybolmaz veya iki kez atanmaz.
    for sayfa_dakika in [Decimal("0.5"), Decimal("3"), Decimal("5.25")]:
        for ilk_gun in [0, 4, 15, 60]:
            for ikinci_gun in [0, 3, 30]:
                plan = hesapla(sayfa_dakika=sayfa_dakika,
                               musaitlik=[(BUGUN, ilk_gun), (YARIN, ikinci_gun)])
                sayfalar = []
                for gun in plan.gunler:
                    assert 0 <= gun.calisma_dakika <= gun.musait_dakika
                    assert gun.tarih < SINAV
                    if gun.ilk_sayfa is not None:
                        sayfalar.extend(range(gun.ilk_sayfa, gun.son_sayfa + 1))
                assert sayfalar == list(range(1, plan.planlanan_sayfa + 1))
                assert plan.planlanan_sayfa + plan.sigmayan_sayfa == 20
                assert plan.planlanan_dakika + plan.ek_dakika == plan.toplam_dakika


@pytest.fixture
def kurulum(tmp_path):
    writer = PdfWriter()
    for _ in range(20):
        writer.add_blank_page(width=100, height=100)
    buffer = BytesIO()
    writer.write(buffer)
    app = uygulama_olustur(tmp_path, bugun_fonksiyonu=lambda: BUGUN)
    with TestClient(app) as client:
        sonuc = client.post("/belgeler", data={"ders_adi": "Algoritma"},
                            files={"dosya": ("20sayfa.pdf", buffer.getvalue(), "application/pdf")})
        pdf_yolu = re.search(r'href="(/belgeler/[^\"]+/pdf)"', sonuc.text)[1]
        yield client, pdf_yolu.removesuffix("/pdf") + "/plan"


def gonder(client, yol, **degisiklik):
    form = dict(ilk_sayfa="1", son_sayfa="20", sayfa_dakika="5",
                sinav_tarihi=SINAV.isoformat(),
                gun_tarihi=[BUGUN.isoformat(), YARIN.isoformat()],
                musait_dakika=["60", "30"])
    form.update(degisiklik)
    return client.post(yol, data=form)


def test_plan_formu_ve_sonuc_gercek_pdf_ile(kurulum):
    client, yol = kurulum
    form = client.get(yol)
    assert form.status_code == 200
    assert 'value="20"' in form.text
    assert "Algoritma" in form.text and "20sayfa.pdf" in form.text
    sonuc = gonder(client, yol)
    assert sonuc.status_code == 200
    assert "1–12" in sonuc.text and "13–18" in sonuc.text
    assert "19–20" in sonuc.text and "(2 sayfa)" in sonuc.text
    assert "<strong>10 dakika</strong>" in sonuc.text
    assert sonuc.text.count("<strong>18 sayfa</strong>") == 1
    assert "1–12" not in client.get(yol).text


def test_yeterli_sure_ve_yeniden_hesaplama(kurulum):
    client, yol = kurulum
    eksik = gonder(client, yol)
    assert "Plana sığmayan:" in eksik.text
    tam = gonder(client, yol, musait_dakika=["60", "40"])
    assert tam.status_code == 200
    assert "Seçilen sayfaların tamamı plana sığıyor." in tam.text
    assert "13–20" in tam.text
    assert "Plana sığmayan:" not in tam.text


@pytest.mark.parametrize("degisiklik", [
    {"ilk_sayfa": "0"}, {"son_sayfa": "21"}, {"ilk_sayfa": "abc"},
    {"sayfa_dakika": "0"}, {"sayfa_dakika": "-1"},
    {"sayfa_dakika": "metin"}, {"sayfa_dakika": "NaN"},
    {"sayfa_dakika": "1e999999"},
    {"sinav_tarihi": "2026-02-30"}, {"sinav_tarihi": BUGUN.isoformat()},
    {"gun_tarihi": [SINAV.isoformat()], "musait_dakika": ["30"]},
    {"gun_tarihi": ["bozuk"], "musait_dakika": ["30"]},
    {"musait_dakika": ["-1", "30"]}, {"musait_dakika": ["1.5", "30"]},
    {"musait_dakika": ["60"]}, {"gun_tarihi": [], "musait_dakika": []},
    {"gun_tarihi": [BUGUN.isoformat(), BUGUN.isoformat()]},
])
def test_form_gecersiz_girdilerde_turkce_hata_verir(kurulum, degisiklik):
    client, yol = kurulum
    sonuc = gonder(client, yol, **degisiklik)
    assert sonuc.status_code == 400
    assert 'role="alert"' in sonuc.text
    assert 'id="plan-sonucu"' not in sonuc.text
    assert "Yüklenen materyaller" in sonuc.text


def test_form_degerleri_korunur_ve_kullanici_metni_html_olarak_calistirilmaz(kurulum):
    client, yol = kurulum
    sonuc = gonder(client, yol, ilk_sayfa="<img src=x onerror=alert(1)>")
    assert sonuc.status_code == 400
    assert "&lt;img src=x onerror=alert(1)&gt;" in sonuc.text
    assert "<img src=x onerror=alert(1)>" not in sonuc.text
    assert 'value="30"' in sonuc.text


def test_turkce_ondalik_ve_sifir_gun(kurulum):
    client, yol = kurulum
    sonuc = gonder(client, yol, sayfa_dakika="2,5", musait_dakika=["0", "50"])
    assert sonuc.status_code == 200
    assert "Çalışma atanmadı" in sonuc.text
    assert "1–20" in sonuc.text
    assert "Seçilen sayfaların tamamı plana sığıyor." in sonuc.text


def test_taninmayan_belge_404(kurulum):
    client, _ = kurulum
    assert client.get("/belgeler/yok/plan").status_code == 404
    assert client.post("/belgeler/yok/plan").status_code == 404
