"""Sayfaları sınavdan önceki müsait günlere sırasıyla dağıtır."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal


def turkiye_bugunu() -> date:
    # Sunucunun veya bilgisayarın saat diliminden bağımsız Türkiye tarihi.
    return datetime.now(timezone(timedelta(hours=3))).date()


@dataclass(frozen=True)
class GunlukPlan:
    tarih: date
    musait_dakika: int
    ilk_sayfa: int | None
    son_sayfa: int | None
    calisma_dakika: Decimal


@dataclass(frozen=True)
class CalismaPlani:
    gunler: list[GunlukPlan]
    toplam_sayfa: int
    planlanan_sayfa: int
    toplam_dakika: Decimal
    planlanan_dakika: Decimal
    sigmayan_ilk_sayfa: int | None
    sigmayan_son_sayfa: int | None
    sigmayan_sayfa: int
    ek_dakika: Decimal


def plan_olustur(
    *,
    belge_sayfa_sayisi: int,
    ilk_sayfa: int,
    son_sayfa: int,
    sayfa_dakika: Decimal,
    sinav_tarihi: date,
    musaitlik: list[tuple[date, int]],
    bugun: date,
) -> CalismaPlani:
    """Her sayfa tek günde tamamlanır; sıralama PDF sayfa sırasıdır.

    Listede olmayan günlerin müsaitliği sıfır kabul edilir. Sınav günü
    kullanılmaz. Bir güne sığmayan tam sayfa sonraki müsait güne bırakılır.
    """
    if not 1 <= ilk_sayfa <= son_sayfa <= belge_sayfa_sayisi:
        raise ValueError("Sayfa aralığı PDF sınırları içinde olmalı; başlangıç bitişi aşamaz.")
    if not sayfa_dakika.is_finite() or sayfa_dakika <= 0:
        raise ValueError("Sayfa başına çalışma süresi sıfırdan büyük olmalıdır.")
    if not Decimal("0.01") <= sayfa_dakika <= Decimal("1440"):
        raise ValueError("Sayfa başına süre 0.01 ile 1440 dakika arasında olmalıdır.")
    if sayfa_dakika != sayfa_dakika.quantize(Decimal("0.01")):
        raise ValueError("Sayfa başına süre en fazla iki ondalık basamak içerebilir.")
    if sinav_tarihi <= bugun:
        raise ValueError("Sınav tarihi bugünden sonra olmalıdır.")
    if not musaitlik:
        raise ValueError("En az bir günün müsaitliğini girin.")

    gorulen_tarihler = set()
    for tarih, dakika in musaitlik:
        if tarih < bugun or tarih >= sinav_tarihi:
            raise ValueError("Çalışma günleri bugün veya sonrasında ve sınavdan önce olmalıdır.")
        if tarih in gorulen_tarihler:
            raise ValueError("Aynı tarih birden fazla girilemez.")
        if not 0 <= dakika <= 1440:
            raise ValueError("Günlük müsaitlik 0 ile 1440 dakika arasında olmalıdır.")
        gorulen_tarihler.add(tarih)

    siradaki_sayfa = ilk_sayfa
    gunler = []
    for tarih, dakika in sorted(musaitlik):
        kalan_sayfa = son_sayfa - siradaki_sayfa + 1
        # Decimal kullanımı, 2.5 dakika gibi sürelerde yuvarlama hatasını önler.
        adet = min(kalan_sayfa, int(Decimal(dakika) // sayfa_dakika))
        gunler.append(GunlukPlan(
            tarih=tarih,
            musait_dakika=dakika,
            ilk_sayfa=siradaki_sayfa if adet else None,
            son_sayfa=siradaki_sayfa + adet - 1 if adet else None,
            calisma_dakika=sayfa_dakika * adet,
        ))
        siradaki_sayfa += adet

    toplam_sayfa = son_sayfa - ilk_sayfa + 1
    sigmayan_sayfa = son_sayfa - siradaki_sayfa + 1
    planlanan_sayfa = toplam_sayfa - sigmayan_sayfa
    return CalismaPlani(
        gunler=gunler,
        toplam_sayfa=toplam_sayfa,
        planlanan_sayfa=planlanan_sayfa,
        toplam_dakika=sayfa_dakika * toplam_sayfa,
        planlanan_dakika=sayfa_dakika * planlanan_sayfa,
        sigmayan_ilk_sayfa=siradaki_sayfa if sigmayan_sayfa else None,
        sigmayan_son_sayfa=son_sayfa if sigmayan_sayfa else None,
        sigmayan_sayfa=sigmayan_sayfa,
        ek_dakika=sayfa_dakika * sigmayan_sayfa,
    )
