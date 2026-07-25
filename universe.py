"""
BIST Hisse Evreni Listeleri
BIST 30, BIST 100 ve tüm taranacak hisseler
"""

# BIST 30 - En likit 30 hisse (yfinance için .IS ekli)
# Not: KOZAA.IS, KOZAL.IS, SODA.IS yfinance'ta bulunamadı (listeleme değişikliği olabilir).
#      Bunların yerine aktif hisseler eklendi.
BIST_30 = [
    "AKBNK.IS", "AKSEN.IS", "ALARK.IS", "ARCLK.IS", "ASELS.IS",
    "BIMAS.IS", "DOHOL.IS", "EKGYO.IS", "EREGL.IS", "FROTO.IS",
    "GARAN.IS", "HEKTS.IS", "ISCTR.IS", "KCHOL.IS", "ENKAI.IS",
    "KRDMD.IS", "MGROS.IS", "ODAS.IS",  "PETKM.IS", "PGSUS.IS",
    "SAHOL.IS", "SISE.IS",  "TAVHL.IS", "TCELL.IS", "THYAO.IS",
    "TKFEN.IS", "TOASO.IS", "TUPRS.IS", "TTKOM.IS", "VESTL.IS",
    "YKBNK.IS"
]

# BIST 100 - BIST 30 + ek hisseler
BIST_100 = BIST_30 + [
    "AEFES.IS", "AGHOL.IS", "AGESA.IS", "AKENR.IS", "AKGRT.IS",
    "ALGYO.IS", "ALYAG.IS", "ANACM.IS", "ANHYT.IS", "ANSGR.IS",
    "ARASE.IS", "ASGYO.IS", "AVOD.IS",  "AYDEM.IS", "AYEN.IS",
    "BERA.IS",  "BIOEN.IS", "BRISA.IS", "BRYAT.IS", "BUCIM.IS",
    "CANTE.IS", "CCOLA.IS", "CEMTS.IS", "CIMSA.IS", "CLEBI.IS",
    "CWENE.IS", "DENGE.IS", "DOGUB.IS", "DYOBY.IS", "EGEEN.IS",
    "ENKAI.IS", "ENJSA.IS", "EUPWR.IS", "FENER.IS", "FLAP.IS",
    "FMIZP.IS", "GCOLD.IS", "GESAN.IS", "GIMAT.IS", "GLYHO.IS",
    "GOLTS.IS", "GUBRF.IS", "GWIND.IS", "HALKB.IS", "ICBCT.IS",
    "IHLGM.IS", "INDES.IS", "IPEKE.IS", "ISGYO.IS", "ISMEN.IS",
    "IZMDC.IS", "JANTS.IS", "KARSN.IS", "KCAER.IS", "KENT.IS",
    "KLGYO.IS", "KLRHO.IS", "KMPUR.IS", "KONTR.IS", "KOPOL.IS",
    "KORDS.IS", "LOGO.IS",  "MAVI.IS",  "MIATK.IS", "MIGROS.IS",
    "MPARK.IS", "NETAS.IS", "NTHOL.IS", "NUGYO.IS", "NUHCM.IS",
    "OSMEN.IS", "OYAKC.IS", "PAPIL.IS", "PARSN.IS", "PETUN.IS",
    "PKART.IS", "POLHO.IS", "PRKAB.IS", "QUAGR.IS", "RAYSG.IS",
    "REEDR.IS", "RHEAG.IS", "RYGYO.IS", "SAFKN.IS", "SANKO.IS",
    "SELEC.IS", "SILVR.IS", "SKBNK.IS", "SMART.IS", "SOKM.IS",
    "TBORG.IS", "TGSAS.IS", "TLMAN.IS", "TMSN.IS",  "TOASO.IS",
    "TRCAS.IS", "TRILC.IS", "TURSG.IS", "USDTR.IS", "VAKBN.IS",
    "VKGYO.IS", "YATAS.IS", "ZRGYO.IS"
]

# Tüm BIST (daha kapsamlı liste)
BIST_ALL = BIST_100 + [
    "ABALB.IS", "ABANA.IS", "ACSEL.IS", "ADEL.IS",  "ADESE.IS",
    "AFYON.IS", "AGYO.IS",  "AHGAZ.IS", "AHSGY.IS", "AKMGY.IS",
    "AKPAZ.IS", "AKSA.IS",  "AKSGY.IS", "AKTIF.IS", "ALBRK.IS",
    "ALFAS.IS", "ALKA.IS",  "ALKIM.IS", "ALMAD.IS", "ALTNY.IS",
    "ALVES.IS", "ANGEN.IS", "ARAR.IS",  "ARSAN.IS", "ARTMS.IS",
    "ARZUM.IS", "ASLAN.IS", "ASTOR.IS", "ATAGY.IS", "ATEKS.IS",
    "ATLAS.IS", "AVGYO.IS", "AYCES.IS", "BAFRA.IS", "BAGFS.IS",
    "BAKAB.IS", "BALAT.IS", "BANVT.IS", "BARMA.IS", "BASGZ.IS",
    "BAYRK.IS", "BFREN.IS", "BIMAS.IS", "BJKAS.IS", "BLCYT.IS",
    "BMEKS.IS", "BNTAS.IS", "BOSSA.IS", "BOYNR.IS", "BRKVY.IS",
    "BRLSM.IS", "BSOKE.IS", "BTCIM.IS", "BURCE.IS", "BURVA.IS",
    "BVSAN.IS", "BYENO.IS", "CEMAS.IS", "CEOEM.IS", "CFACT.IS",
    "CMBTN.IS", "CMENT.IS", "CONSE.IS", "COSMO.IS", "CRDFA.IS",
    "CRFSA.IS", "CUSAN.IS", "DAGHL.IS", "DAPGM.IS", "DARDL.IS",
    "DENGE.IS", "DERHL.IS", "DESA.IS",  "DEVA.IS",  "DGATE.IS",
    "DGKLB.IS", "DGNMO.IS", "DIRIT.IS", "DITAS.IS", "DMRGD.IS",
    "DNISI.IS", "DOFER.IS", "DOKTA.IS", "DURDO.IS", "DYOBY.IS",
    "DZGYO.IS", "EBEBK.IS", "EGGUB.IS", "EGPRO.IS", "EGSER.IS",
    "ELITE.IS", "EMKEL.IS", "EMNIS.IS", "ENERY.IS", "ENGYO.IS",
    "EPLAS.IS", "ERSU.IS",  "ESCOM.IS", "ESSEN.IS", "EUREN.IS",
    "EYGYO.IS", "FADE.IS",  "FENER.IS", "FMIZP.IS", "FORMT.IS",
    "FRIGO.IS", "FROTO.IS", "FZLGY.IS", "GARAN.IS", "GARFA.IS"
]

# Hisse adları (görüntüleme için)
TICKER_NAMES = {
    "THYAO": "Türk Hava Yolları",
    "GARAN": "Garanti BBVA",
    "AKBNK": "Akbank",
    "EREGL": "Ereğli Demir Çelik",
    "BIMAS": "BİM Mağazalar",
    "ASELS": "Aselsan",
    "SISE": "Şişecam",
    "KCHOL": "Koç Holding",
    "TOASO": "Tofaş",
    "FROTO": "Ford Otosan",
    "ISCTR": "İş Bankası C",
    "YKBNK": "Yapı Kredi",
    "SAHOL": "Sabancı Holding",
    "TUPRS": "Tüpraş",
    "TCELL": "Turkcell",
    "EKGYO": "Emlak Konut GYO",
    "ARCLK": "Arçelik",
    "MGROS": "Migros",
    "PETKM": "Petkim",
    "PGSUS": "Pegasus",
    "AKSEN": "Aksa Enerji",
    "TAVHL": "TAV Havalimanları",
    "SODA": "Soda Sanayii",
    "TKFEN": "Tekfen Holding",
    "VESTL": "Vestel",
    "KRDMD": "Kardemir",
    "KOZAL": "Koza Altın",
    "KOZAA": "Koza Anadolu",
    "DOHOL": "Doğan Holding",
    "HEKTS": "Hektaş",
    "ALARK": "Alarko Holding",
    "TTKOM": "Türk Telekom",
    "ODAS": "Odaş Elektrik",
}

# Sektör etiketleri
TICKER_SECTORS = {
    "THYAO": "Havacılık",
    "GARAN": "Bankacılık",
    "AKBNK": "Bankacılık",
    "EREGL": "Demir-Çelik",
    "BIMAS": "Perakende",
    "ASELS": "Savunma",
    "SISE": "Cam/Kimya",
    "KCHOL": "Holding",
    "TOASO": "Otomotiv",
    "FROTO": "Otomotiv",
    "ISCTR": "Bankacılık",
    "YKBNK": "Bankacılık",
    "SAHOL": "Holding",
    "TUPRS": "Enerji",
    "TCELL": "Telekom",
    "EKGYO": "GYO",
    "ARCLK": "Teknoloji",
    "MGROS": "Perakende",
    "PETKM": "Petrokimya",
    "PGSUS": "Havacılık",
    "AKSEN": "Enerji",
    "TAVHL": "Havacılık",
    "SODA": "Kimya",
    "TKFEN": "İnşaat",
    "VESTL": "Teknoloji",
    "KRDMD": "Demir-Çelik",
    "KOZAL": "Madencilik",
    "KOZAA": "Madencilik",
    "DOHOL": "Holding",
    "HEKTS": "Tarım",
    "ALARK": "Enerji",
    "TTKOM": "Telekom",
    "ODAS": "Enerji",
}


def get_universe(choice: str) -> list:
    """
    Seçilen evrene göre hisse listesi döndür.
    choice: 'bist30', 'bist100', 'bistall', 'custom'
    """
    universes = {
        'bist30': BIST_30,
        'bist100': BIST_100,
        'bistall': BIST_ALL,
    }
    return universes.get(choice.lower(), BIST_30)


def get_display_name(ticker: str) -> str:
    """THYAO.IS -> 'Türk Hava Yolları' """
    base = ticker.replace('.IS', '')
    return TICKER_NAMES.get(base, base)


def get_sector(ticker: str) -> str:
    base = ticker.replace('.IS', '')
    return TICKER_SECTORS.get(base, "Diğer")


def normalize_ticker(ticker: str) -> str:
    """Kullanıcı 'THYAO' yazarsa 'THYAO.IS' yap"""
    ticker = ticker.upper().strip()
    if not ticker.endswith('.IS'):
        ticker = ticker + '.IS'
    return ticker
