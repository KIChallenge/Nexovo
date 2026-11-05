"""Wissensbasis: Rechtsstand Pflegegeld, Suchgüte (20 Bürgerfragen), Normen, PDF-Seiten, Cache."""

from __future__ import annotations

import pickle
import time

import pytest

from lotse import pdfquellen, recht, wissen
from lotse.models import Treffer
from lotse.suche import Analysator, Index, stamm

SR = pdfquellen.SERVICERATGEBER
PAL080 = "Anträge und Formulare/PAL080_0125_Mpfl_052026.pdf"
KUR1 = "Anträge und Formulare/Antrag Kur und Reha.pdf"
FAHRTKOSTEN = "Anträge und Formulare/Antrag-auf-Zuschuss-zu-Fahrtkosten_Wien.pdf"
FSW = "Anträge und Formulare/fsw-antrag-auf-foerderung-von-leistungen.1779095804.pdf"
VO_2026 = "Rechtstexte/Aufwertung_und_Anpassung_nach_ASVG,_GSVG,_BSVG,_B-KUVG,_BPGG_fuer_2026=ART=3="


def R(datei_praefix: str) -> tuple[str, str]:
    """Sollquelle Recht: Dateiname beginnt mit `Rechtstexte/<Kürzel>=<Typ>=<Nr>=`."""
    return ("recht", datei_praefix if datei_praefix.startswith("Rechtstexte/") else f"Rechtstexte/{datei_praefix}")


def P(datei: str, seite: int) -> tuple[str, str]:
    """Sollquelle PDF-Seite."""
    return ("pdf", f"{datei}#{seite}")


# Jede Sollquelle wurde im Original gelesen (Fundstelle enthält das erfragte Thema).
FRAGEN: list[tuple[str, str, list[tuple[str, str]]]] = [
    # Szenario pflege
    ("pflege", "Wie hoch ist das Pflegegeld 2026?", [R(VO_2026)]),  # § 1: Stufe 1–7 für 2026
    ("pflege", "Meine Mutter braucht ständig Hilfe – wer hat Anspruch auf Pflegegeld?",
     [R("BPGG=PARA=4="), R("BPGG=PARA=3=")]),  # Anspruchsvoraussetzungen / Personenkreis
    ("pflege", "Wie stelle ich einen Antrag auf Pflegegeld?",
     [P(PAL080, 1), R("BPGG=PARA=25=")]),  # PAL 080 Antrag / § 25 Antragstellung
    ("pflege", "Gibt es Pflegekarenzgeld, wenn ich für die Pflege meiner Mutter in Karenz gehe?",
     [R("BPGG=PARA=21c=")]),  # § 21c Pflegekarenzgeld
    ("pflege", "Selbstversicherung in der Pensionsversicherung für pflegende Angehörige",
     [R("ASVG=PARA=18b="), P(SR, 11)]),  # § 18b / Serviceratgeber „Pflege eines nahen Angehörigen“
    ("pflege", "Förderung für Pflege und Betreuung zu Hause in Wien beantragen",
     [P(FSW, 5), P(FSW, 3)]),  # FSW-Antrag: „Pflege und Betreuung zu Hause / Tagesbetreuung“
    # Szenario entlassung
    ("entlassung", "Medizinische Hauskrankenpflege nach dem Krankenhaus",
     [R("ASVG=PARA=151="), P(SR, 25)]),
    ("entlassung", "Wie beantrage ich eine Rehabilitation nach dem Spitalsaufenthalt?",
     [P(KUR1, 1), R("ASVG=PARA=154a="), P(SR, 25)]),
    ("entlassung", "Zuschuss zu den Fahrtkosten zur Strahlentherapie",
     [P(FAHRTKOSTEN, 2), P(FAHRTKOSTEN, 1)]),  # S. 2: Ausnahme Dialyse, Chemo- oder Strahlentherapie
    ("entlassung", "Wer zahlt den Krankentransport, wenn ich nicht gehen kann?", [P(SR, 32)]),  # Transportkosten
    ("entlassung", "Befreiung von der Rezeptgebühr beantragen", [P(SR, 22), R("RRZ_2008=")]),
    ("entlassung", "Wie lange bekomme ich Krankengeld?", [R("ASVG=PARA=139="), P(SR, 27)]),
    ("entlassung", "Übernimmt die Kasse Heilbehelfe wie Brillen oder Schuheinlagen?",
     [P(SR, 23), R("ASVG=PARA=137=")]),
    # Szenario gesundheit
    ("gesundheit", "Kostenlose Vorsorgeuntersuchung machen", [P(SR, 12), R("ASVG=PARA=132b=")]),
    ("gesundheit", "Wie komme ich zu einer Kur?", [P(SR, 32), P(KUR1, 1), R("ASVG=PARA=155=")]),
    ("gesundheit", "How can I get help to quit smoking?", [P(SR, 16)]),  # Rauchfrei Telefon
    # Szenario kind
    ("kind", "Kinderbetreuungsgeld beantragen", [P(SR, 35), R("KBGG=PARA=2="), R("KBGG=PARA=3=")]),
    ("kind", "Zahlt die Krankenkasse eine Zahnspange für mein Kind?", [P(SR, 39), R("ASVG=PARA=153a=")]),
    ("kind", "Anspruch auf Familienbeihilfe für mein Kind", [R("FLAG=PARA=2="), R("FLAG=PARA=8=")]),
    ("kind", "Is there maternity benefit before and after the birth?", [R("ASVG=PARA=162="), P(SR, 34)]),
]


def _trifft(t: Treffer, soll: tuple[str, str]) -> bool:
    art, ziel = soll
    if art == "recht":
        return t.quelle.art == "recht" and t.quelle.datei.startswith(ziel)
    datei, seite = ziel.rsplit("#", 1)
    return t.quelle.datei == datei and t.quelle.fundstelle == f"PDF-S. {seite}"


@pytest.fixture(scope="module")
def wb() -> wissen.Wissensbasis:
    return wissen.wissensbasis()


# -- Rechtsstand Pflegegeld ----------------------------------------------------------------------------------


@pytest.mark.daten
def test_pflegegeld_2026_aus_anpassungsverordnung(wb):
    p = wb.pflegegeld(2026)
    assert p.betraege == {1: 206.20, 2: 380.30, 3: 592.60, 4: 888.50, 5: 1206.90, 6: 1685.40, 7: 2214.80}
    assert p.betraege[3] != 451.80  # Grundbetrag aus § 5 BPGG darf nie für 2026 erscheinen
    vo, basis = p.quellen
    assert "263/2025" in vo.fundstelle and vo.art == "recht"
    assert "592,60" in vo.zitat and len(vo.zitat) <= 300
    assert basis.titel == "BPGG § 5"
    assert "592,60 €" in p.belege[3]
    assert p.hinweis["de"] and p.hinweis["en"] and "263/2025" in p.hinweis["en"]


@pytest.mark.daten
def test_pflegegeld_vorjahr_aus_eigener_verordnung(wb):
    p = wb.pflegegeld(2025)
    assert p.betraege[1] == 200.80 and p.betraege[7] == 2156.60
    assert "417/2024" in p.quellen[0].fundstelle


@pytest.mark.daten
@pytest.mark.parametrize("jahr", [1995, 2019, 2027])  # 1995: Verordnung nur in Schilling
def test_pflegegeld_ohne_verordnung_leer_mit_hinweis(wb, jahr):
    p = wb.pflegegeld(jahr)
    assert p.betraege == {}
    assert str(jahr) in p.hinweis["de"] and "nicht enthalten" in p.hinweis["de"]
    assert str(jahr) in p.hinweis["en"] and "not contained" in p.hinweis["en"]
    assert all("157,30" not in q.zitat for q in p.quellen)
    assert "(lokal belegt: 2020, 2021, 2022, 2023, 2024, 2025, 2026)" in p.hinweis["de"]


@pytest.mark.daten
def test_suche_pflegegeld_hoehe_2026_nennt_verordnung_vor_grundnorm(wb):
    treffer = wb.suche("Pflegegeld Höhe 2026", k=5)
    dateien = [t.quelle.datei for t in treffer]
    vo = next(i for i, d in enumerate(dateien) if d.startswith(VO_2026))
    assert vo < 3
    grund = next((i for i, d in enumerate(dateien) if d.startswith("Rechtstexte/BPGG=PARA=5=")), None)
    assert grund is None or vo < grund
    # ältere Anpassungsverordnungen (2025 und früher) verdrängen die geltende nicht
    assert not any("_2025=ART=3" in d or "_2024=ART=3" in d for d in dateien[: vo + 1])


# -- Suchgüte ------------------------------------------------------------------------------------------------


@pytest.mark.daten
def test_20_buergerfragen_trefferquote(wb, capsys):
    assert len(FRAGEN) == 20
    assert {s for s, _, _ in FRAGEN} == {"pflege", "gesundheit", "entlassung", "kind"}
    treffer_anzahl = 0
    zeilen = []
    for szenario, frage, soll in FRAGEN:
        treffer = wb.suche(frage, k=5)
        ok = any(_trifft(t, s) for t in treffer for s in soll)
        treffer_anzahl += ok
        zeilen.append(f"{'✓' if ok else '✗'} [{szenario}] {frage} → {[t.quelle.titel + ' ' + t.quelle.fundstelle for t in treffer][:3]}")
    with capsys.disabled():
        print(f"\nTrefferquote Sollquelle in Top 5: {treffer_anzahl}/20")
        print("\n".join(zeilen))
    assert treffer_anzahl >= 18


@pytest.mark.daten
def test_treffer_zitat_woertlich_und_begrenzt(wb):
    normtext = {n.datei: " ".join(n.text.split()) for n in wb.normen}
    for frage in ("Wie lange bekomme ich Krankengeld?", "Kinderbetreuungsgeld beantragen", "Pflegegeld Höhe 2026"):
        for t in wb.suche(frage, k=5):
            q = t.quelle
            assert 0 < len(q.zitat) <= 300 and q.titel and q.fundstelle
            assert q.zitat in t.text and len(t.text) <= 1200
            if q.art == "recht":
                assert q.zitat in normtext[q.datei]
            else:
                seite = int(q.fundstelle.removeprefix("PDF-S. "))
                assert q.zitat in wb.pdf_seite(q.datei, seite)


@pytest.mark.daten
def test_suche_arten_filter_und_leere_anfrage(wb):
    nur_pdf = wb.suche("Kinderbetreuungsgeld", k=5, arten={"serviceratgeber"})
    assert nur_pdf and all(t.quelle.art == "serviceratgeber" for t in nur_pdf)
    assert all(t.quelle.art == "recht" for t in wb.suche("Kinderbetreuungsgeld", k=5, arten={"recht"}))
    assert wb.suche("und oder der", k=5) == []
    assert wb.suche("", k=5) == []


@pytest.mark.daten
def test_suche_unter_200_ms(wb):
    fragen = [f for _, f, _ in FRAGEN]
    wb.suche(fragen[0])  # Analysator-Caches warm
    start = time.perf_counter()
    for f in fragen:
        wb.suche(f, k=5)
    mittel = (time.perf_counter() - start) / len(fragen)
    assert mittel < 0.2, f"{mittel * 1000:.0f} ms je Anfrage"


@pytest.mark.daten
def test_inhaltsverzeichnis_ist_kein_beleg(wb):
    treffer = wb.suche("Kinderbetreuungsgeld Wochengeld Krankengeld", k=5, arten={"serviceratgeber"})
    assert all(t.quelle.fundstelle != "PDF-S. 2" for t in treffer)


@pytest.mark.daten
def test_doppelt_abgelegte_verordnung_erscheint_einmal(wb):
    # Art. 3 der VO BGBl. II Nr. 263/2025 liegt in vier Dateien vor (zwei Familiennamen, StF-Varianten)
    treffer = wb.suche("Angehörigenbonus 2026 statt 130,80 € mit 134,30 €", k=5, arten={"recht"})
    art3 = [t for t in treffer if t.quelle.fundstelle == "BGBl. II Nr. 263/2025" and t.quelle.titel.endswith("Art. 3")]
    assert len(art3) == 1


@pytest.mark.daten
def test_aufgehobene_norm_abrufbar_aber_kein_suchtreffer(wb):
    n = wb.norm("BPGG", "14")
    assert n.aufgehoben and n.text == "§ 14. Aufgehoben."
    assert all(not t.quelle.datei.startswith("Rechtstexte/BPGG=PARA=14=") for t in wb.suche("BPGG § 14 aufgehoben", k=5))


# -- Normen und Metadaten ------------------------------------------------------------------------------------


@pytest.mark.daten
def test_norm_metadaten_und_quelle(wb):
    n = wb.norm("BPGG", "5")
    assert n.ueberschrift == "Höhe des Pflegegeldes"
    q = n.quelle()
    assert (q.art, q.titel, q.fundstelle, q.stand) == ("recht", "BPGG § 5", "BGBl. I Nr. 80/2019", "2020-01-01")
    assert q.datei == "Rechtstexte/BPGG=PARA=5=80=2019-07-31=2020-01-01.xml"
    assert len(q.zitat) <= 300 and q.zitat.startswith("§ 5. (1)")
    assert wb.norm("bpgg", "5") is n
    assert wb.norm("ASVG", "143A").titel == "ASVG § 143a"
    assert wb.norm("BPGG", "999") is None
    vo = wb.norm("Aufwertung_und_Anpassung_nach_ASVG,_GSVG,_BSVG,_B-KUVG,_BPGG_fuer_2026", "3", "ART")
    assert vo.titel.endswith("für 2026 Art. 3") and vo.bgbl == "BGBl. II Nr. 263/2025"


@pytest.mark.daten
def test_korpus_vollstaendig_mit_platzhalter_und_abweichenden_namen(wb):
    assert len(wb.normen) == 14244
    assert sum(1 for n in wb.normen if n.inkrafttreten == "") == 215
    abweichend = [n for n in wb.normen if n.datei.removeprefix("Rechtstexte/").count("=") < 5]
    assert len(abweichend) == 6
    assert all(n.kundmachung and n.inkrafttreten for n in abweichend)  # aus den Metadaten ergänzt
    assert all(n.bgbl for n in wb.normen)


@pytest.mark.daten
def test_pdf_seiten_und_gueltigkeit_honorarordnungen(wb):
    assert len(wb.pdfs[SR]) == 59
    assert "Leistungen und Services 2026" in wb.pdf_seite(SR, 1)
    zahn = "Leistungskataloge/Zahnärzte Honorarordnung_2026_aktuellste_Version_MAI_070526.pdf"
    assert wb.pdf_seite(zahn, 48) == ""
    q = pdfquellen.quelle(zahn, 3)
    assert q.art == "honorarordnung" and "gültig ab 1. Jänner 2026" in q.titel and q.fundstelle == "PDF-S. 3"
    oegk = pdfquellen.quelle("Leistungskataloge/ÖGK Honorarordnung-fuer-Vertragsaerzte-und-Vertragsgruppenpraxen.pdf", 1)
    assert "Steiermark" in oegk.titel and "01.01.2025" in oegk.titel and oegk.stand == "2025-01-01"
    with pytest.raises(IndexError):
        wb.pdf_seite(SR, 60)
    with pytest.raises(KeyError):
        wb.pdf_seite("Befunde/x.pdf", 1)


@pytest.mark.daten
def test_formulartext_ohne_symbolzeichen_und_ligaturen(wb):
    text = wb.pdf_seite(PAL080, 1)
    assert "ANTRAG auf PFLEGEGELD" in text
    assert "finden Sie auf unserer Website" in text
    assert not any("\ue000" <= c <= "\uf8ff" for c in text)


@pytest.mark.daten
def test_cache_signatur_erkennt_aenderung(tmp_path, wb):
    signatur = wissen._signatur()
    pfad = tmp_path / "wb.pkl"
    wissen._schreibe_cache(pfad, signatur, wb)
    start = time.perf_counter()
    geladen = wissen._lade_cache(pfad, signatur)
    warm = time.perf_counter() - start
    assert geladen is not None and len(geladen.doks) == len(wb.doks)
    assert wissen._lade_cache(pfad, signatur[:-1] + (0,)) is None
    assert warm < 3.0, f"Warmstart {warm:.2f} s"


# -- Ohne Quelldaten lauffähig: Wortanalyse und BM25 ---------------------------------------------------------


def test_stamm_vereinheitlicht_flexion():
    assert stamm("pflegegeldes") == stamm("pflegegeld")
    assert stamm("zahnspangen") == stamm("zahnspange")
    assert stamm("höhe") == stamm("höhen")


def test_kompositum_zerlegung_mit_fugen_s():
    a = Analysator({"beitrag": 10, "grundlage": 10, "pflege": 10, "geld": 10, "pflegegeld": 10, "höhe": 10})
    assert a.zerlege("beitragsgrundlage") == ("beitrag", "grundlage")
    assert set(a.zerlege("pflegegeldhöhe")) == {"pflegegeld", "pflege", "geld", "höhe"}
    assert a.zerlege("haus") == ()
    # Ableitungssuffixe sind keine Teile
    assert Analysator({"zeit": 10, "lich": 10}).zerlege("zeitlich") == ()


def test_bm25_ueberschrift_und_kompositum_schlagen_rumpf():
    docs = [
        ("Höhe des Pflegegeldes", "Das Pflegegeld beträgt monatlich in Stufe 1 einen Betrag."),
        ("Antragstellung", "Das Pflegegeld ist zu beantragen. Pflegegeld Pflegegeld."),
        ("Rehabilitation", "Maßnahmen der Rehabilitation nach dem Krankenhaus."),
    ]
    a = Analysator({"pflegegeld": 5, "pflege": 5, "geld": 5, "höhe": 5})
    idx = Index(a)
    idx.baue(docs)
    punkte = idx.bewerte(a.anfrage("Wie hoch ist die Pflegegeldhöhe?"))
    assert max(punkte, key=punkte.get) == 0
    assert 2 not in punkte
    geladen = pickle.loads(pickle.dumps(idx))  # Index ist cachebar
    assert geladen.bewerte(a.anfrage("Pflegegeld")) == idx.bewerte(a.anfrage("Pflegegeld"))


def test_personenbezug_und_jahreszahl_schwach_gewichtet():
    g = Analysator({}).anfrage("Meine Mutter braucht Pflegegeld 2026")
    assert g[stamm("mutter")] == 0.5 and g[stamm("pflegegeld")] == 1.0 and g["2026"] < 0.5
    assert stamm("braucht") not in g


def test_segmente_trennen_nicht_nach_abkuerzungen():
    from lotse.suche import segmente, stuecke

    assert segmente("Gemäß § 5 Abs. 1 BPGG gilt das. Danach folgt BGBl. II Nr. 263/2025 hier.") == [
        "Gemäß § 5 Abs. 1 BPGG gilt das.",
        "Danach folgt BGBl. II Nr. 263/2025 hier.",
    ]
    text = "\n".join(f"Absatz {i} " + "wort " * 40 for i in range(12))
    spannen = stuecke(text, 1000)
    assert spannen[0][0] == 0 and spannen[-1][1] == len(text.rstrip())
    assert all(b - a <= 1000 for a, b in spannen)
    assert all(spannen[i + 1][0] < spannen[i][1] for i in range(len(spannen) - 1))  # Überlappung


def test_norm_kopf_bei_ordnet_ueberschriften_zu():
    n = recht.Norm("X", "PARA", "1", "", "", "", "Höhe", "a" * 100, "Rechtstexte/x.xml",
                   abschnitte=((0, "Abschnitt I"), (0, "Höhe"), (50, "Zweiter Teil")))
    assert n.kopf_bei(10) == "Abschnitt I Höhe"
    assert n.kopf_bei(60) == "Höhe Zweiter Teil"


def test_englische_anfrage_wird_erweitert():
    a = Analysator({})
    g = a.anfrage("How much is the care allowance?")
    assert stamm("pflegegeld") in g and stamm("höhe") in g


def test_recht_kuerze_wortgrenze():
    text = "wort " * 100
    k = recht.kuerze(text, 30)
    assert len(k) <= 30 and not k.endswith(" ") and k.split() == ["wort"] * len(k.split())
