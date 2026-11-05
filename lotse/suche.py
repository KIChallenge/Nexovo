"""Schlagwortsuche (BM25) mit deutscher Wortanalyse: Kleinschreibung, leichte Stammformreduktion, Kompositazerlegung."""

from __future__ import annotations

import math
import re
from array import array
from collections import Counter
from dataclasses import dataclass, field

_WORT = re.compile(r"[0-9a-zäöüß]+")

_STOPP = frozenset(
    """
    aber alle allem allen aller alles als also am an andere anderen auch auf aus bei beim bin bis bist bitte da
    damit dann das dass dein deine dem den denen der deren des dessen die dies diese diesem diesen dieser dieses
    doch dort du durch ein eine einem einen einer eines er es etwa euch euer für gegen gibt habe haben hat hatte
    hier ich ihm ihn ihnen ihr ihre im in ins ist ja jede jedem jeden jeder jedes jetzt kann kein keine man mehr
    mein meine meinem meinen meiner mich mir mit möchte muss nach nicht noch nun nur ob oder ohne sehr sein seine
    sich sie sind so solche soll sollen sondern sowie über um und uns unser unsere unter vom von vor war was weil
    welche welcher welches wenn wer werde werden wie wir wird wo zu zum zur zwar bzw sowie gemäß
    brauche brauchst braucht brauchen bekomme bekommst bekommt bekommen kriege kriegt mache machst macht machen
    will willst wollen möchten darf dürfen weiß wissen frage fragen tun gehe etwas schon ganz immer wieder gerne
    gern jemand nichts wirklich eigentlich
    a an and are as at be can do for from get have how i if in is it me my of on or our the to what when where
    which who will with you your there this that need want please
    """.split()
)

# Englische Bürgerbegriffe → deutsche Fachbegriffe des Korpus (nur Anfrageerweiterung)
_EN_DE: dict[str, str] = {
    "care allowance": "pflegegeld",
    "long-term care allowance": "pflegegeld",
    "care benefit": "pflegegeld",
    "care level": "pflegegeld stufe",
    "nursing care": "pflege",
    "home nursing": "hauskrankenpflege",
    "home care": "pflege betreuung hause",
    "care leave": "pflegekarenz",
    "hospice": "familienhospizkarenz",
    "caring relatives": "pflegende angehörige",
    "family carer": "pflegende angehörige",
    "self-insurance": "selbstversicherung",
    "sick pay": "krankengeld",
    "sickness benefit": "krankengeld",
    "sick leave": "krankenstand",
    "rehabilitation": "rehabilitation",
    "rehab": "rehabilitation",
    "spa": "kur",
    "cure": "kur",
    "health resort": "kur",
    "check-up": "vorsorgeuntersuchung",
    "health check": "vorsorgeuntersuchung",
    "screening": "vorsorgeuntersuchung früherkennung",
    "childcare allowance": "kinderbetreuungsgeld",
    "child care allowance": "kinderbetreuungsgeld",
    "childcare benefit": "kinderbetreuungsgeld",
    "family allowance": "familienbeihilfe",
    "maternity benefit": "wochengeld",
    "maternity allowance": "wochengeld",
    "pregnancy": "schwangerschaft",
    "pregnant": "schwangerschaft",
    "braces": "zahnspange kieferorthopädie",
    "orthodontic": "kieferorthopädie",
    "orthodontics": "kieferorthopädie",
    "dental": "zahn zahnbehandlung",
    "dentures": "zahnersatz",
    "prescription fee": "rezeptgebühr",
    "exemption": "befreiung",
    "travel costs": "fahrtkosten",
    "travel expenses": "fahrtkosten",
    "transport costs": "transportkosten",
    "ambulance": "krankentransport",
    "medical aids": "heilbehelfe hilfsmittel",
    "glasses": "brillen sehbehelfe",
    "hearing aid": "hörgeräte",
    "vaccination": "impfung",
    "vaccinations": "impfungen",
    "hospital": "krankenhaus",
    "discharge": "entlassung",
    "application": "antrag",
    "apply": "antrag",
    "amount": "höhe betrag",
    "how much": "höhe betrag",
    "smoking": "rauchfrei tabak",
    "early intervention": "frühförderung",
    "mother-child": "eltern-kind-pass",
    "child": "kind",
    "children": "kinder",
    "insurance": "versicherung",
    "co-insurance": "mitversicherung",
    "radiotherapy": "strahlentherapie",
    "radiation therapy": "strahlentherapie",
    "dialysis": "dialyse",
    "how long": "dauer",
}
_EN_MUSTER = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in sorted(_EN_DE, key=len, reverse=True)) + r")\b", re.IGNORECASE
)

# Alltagssprache → Begriff im Korpus (nur Anfrageerweiterung)
_DE_SYNONYME: dict[str, str] = {
    "hoch": "höhe",
    "viel": "höhe betrag",
    "wieviel": "höhe betrag",
    "beantragen": "antrag",
    "beantrage": "antrag",
    "beantragt": "antrag",
    "ansuchen": "antrag",
    "kostet": "kosten",
    "zahlt": "kosten",
    "bezahlt": "kosten",
    "spital": "krankenhaus",
    "spitalsaufenthalt": "krankenhaus",
    "krankenhausaufenthalt": "krankenhaus",
    "zahnspange": "kieferregulierung",
    "zahnspangen": "kieferregulierung",
    "schwanger": "schwangerschaft",
    "baby": "geburt",
    "lange": "dauer",
    "anspruch": "anspruchsvoraussetzungen anspruchsberechtigung",
}

KOPF_GEWICHT = 3.0  # Überschriften zählen im Rumpf-Score dreifach
KOPF_BONUS = 1.0  # Zusatzpunkte je Anfrageterm in der Überschrift (× idf)
TEIL_GEWICHT = 0.5  # Kompositumteile zählen halb
ERWEITERUNG_GEWICHT = 0.8  # Synonyme und englische Begriffe
ZAHL_GEWICHT = 0.3  # Jahreszahlen u. Ä. tragen wenig Themeninformation
PERSON_GEWICHT = 0.5  # Wort nach Possessivpronomen ("meine Mutter")
_BEZUG = frozenset("mein meine meinem meinen meiner meines unser unsere unserem unseren unserer my our".split())
_MIN_TEIL_DF = 3
# Ableitungssuffixe und Fragmente sind keine Kompositumteile ("zeitlich" ≠ "zeit" + "lich")
_KEIN_TEIL = frozenset(
    "lich liche lichen licher keit keiten heit heiten ung ungen isch ische ischen chen lein bar bare los lose "
    "haft sam ige igen iger end ende enden ern tion tionen ität schaft schaften".split()
)
_FUGEN = ("", "s", "es", "n", "en", "er", "e")


def stamm(wort: str) -> str:
    """Leichte Stammformreduktion nach CISTEM (Weißweiler & Fraser 2017), ohne Präfixentfernung."""
    w = wort.replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
    w = w.replace("sch", "$").replace("ei", "%").replace("ie", "&")
    w = re.sub(r"(.)\1", r"\1*", w)
    while len(w) > 3:
        if len(w) > 5 and (w.endswith("em") or w.endswith("er") or w.endswith("nd")):
            w = w[:-2]
        elif w[-1] in "tesn":
            w = w[:-1]
        else:
            break
    w = re.sub(r"(.)\*", r"\1\1", w)
    return w.replace("&", "ie").replace("%", "ei").replace("$", "sch")


def woerter(text: str) -> list[str]:
    """Kleingeschriebene Wörter ohne Satzzeichen und Stoppwörter (Umlaute/ß bleiben erhalten)."""
    return [w for w in _WORT.findall(text.lower()) if len(w) > 1 and w not in _STOPP]


@dataclass
class Analysator:
    """Wort → gewichtete Indexterme (Stamm + Stämme der Kompositumteile). Vokabular aus dem Korpus."""

    vokabular: dict[str, int] = field(default_factory=dict)  # Oberflächenwort → Dokumentfrequenz
    _stamm: dict[str, str] = field(default_factory=dict, repr=False)
    _teile: dict[str, tuple[str, ...]] = field(default_factory=dict, repr=False)

    def stamm(self, wort: str) -> str:
        s = self._stamm.get(wort)
        if s is None:
            s = self._stamm[wort] = stamm(wort)
        return s

    def _haeufig(self, wort: str) -> int:
        if len(wort) < 3 or wort in _STOPP or wort in _KEIN_TEIL:
            return 0
        return self.vokabular.get(wort, 0)

    def zerlege(self, wort: str) -> tuple[str, ...]:
        """Kompositum → Oberflächenteile (rekursiv, beste Teilung nach geometrischem Mittel der Häufigkeit)."""
        teile = self._teile.get(wort)
        if teile is not None:
            return teile
        teile = ()
        if len(wort) >= 7 and wort.isalpha():
            bester = 0.0
            for i in range(3, len(wort) - 3):
                rechts = wort[i:]
                dr = self._haeufig(rechts)
                if dr < _MIN_TEIL_DF:
                    continue
                links_roh = wort[:i]
                for fuge in _FUGEN:
                    if fuge and not links_roh.endswith(fuge):
                        continue
                    links = links_roh[: len(links_roh) - len(fuge)]
                    dl = self._haeufig(links)
                    if dl >= _MIN_TEIL_DF:
                        wert = math.sqrt(dl * dr)
                        if wert > bester:
                            bester, teile = wert, (links, rechts)
            if teile:
                teile = tuple(t for teil in teile for t in (teil, *self.zerlege(teil)))
        self._teile[wort] = teile
        return teile

    def terme(self, text: str) -> Counter[str]:
        """Gewichtete Terme eines Texts (Ganzwort-Stamm 1.0, Kompositumteile TEIL_GEWICHT)."""
        gewichte: Counter[str] = Counter()
        for w in woerter(text):
            gewichte[self.stamm(w)] += 1.0
            for teil in self.zerlege(w):
                gewichte[self.stamm(teil)] += TEIL_GEWICHT
        return gewichte

    def anfrage(self, frage: str) -> dict[str, float]:
        """Anfrageterme mit Gewicht; Alltags- und englische Begriffe werden um Fachbegriffe des Korpus ergänzt."""
        gewichte = self.terme(frage)
        zusatz = [_EN_DE[m.group(1).lower()] for m in _EN_MUSTER.finditer(frage)]
        zusatz += [_DE_SYNONYME[w] for w in woerter(frage) if w in _DE_SYNONYME]
        for t, g in self.terme(" ".join(zusatz)).items():
            gewichte[t] = max(gewichte[t], ERWEITERUNG_GEWICHT * g)
        # "meine Mutter", "my wife": Personenbezug, kein Thema
        roh = _WORT.findall(frage.lower())
        person = {self.stamm(w) for v, w in zip(roh, roh[1:]) if v in _BEZUG and w not in _STOPP}
        # Mehrfachnennung nicht überbewerten, Zahlen (Jahre) schwach gewichten
        return {
            t: min(g, 1.0) * (ZAHL_GEWICHT if t.isdigit() else 1.0) * (PERSON_GEWICHT if t in person else 1.0)
            for t, g in gewichte.items()
        }


def baue_vokabular(texte: list[str]) -> dict[str, int]:
    df: Counter[str] = Counter()
    for text in texte:
        df.update(set(woerter(text)))
    return dict(df)


class Index:
    """BM25-Index über Dokumente mit Kopf- (Überschrift) und Rumpftext."""

    def __init__(self, analysator: Analysator, k1: float = 1.2, b: float = 0.75):
        self.analysator = analysator
        self.k1 = k1
        self.b = b
        self.postings: dict[str, tuple[bytes, bytes]] = {}  # Term → (Dokument-IDs uint32, tf float32)
        self.kopf: dict[str, bytes] = {}  # Term → Dokument-IDs mit dem Term in der Überschrift
        self.norm: array = array("f")  # k1 * (1 - b + b * dl / avgdl)
        self.anzahl = 0

    def baue(self, dokumente: list[tuple[str, str]]) -> None:
        """`dokumente`: Liste (Kopf, Rumpf)."""
        listen: dict[str, tuple[array, array]] = {}
        kopf_listen: dict[str, array] = {}
        laengen: list[float] = []
        for doc_id, (kopf, rumpf) in enumerate(dokumente):
            tf = self.analysator.terme(rumpf)
            for t, g in self.analysator.terme(kopf).items():
                tf[t] += KOPF_GEWICHT * g
                # Vorkommen in der Überschrift zählt voll, auch als Kompositumteil
                (kopf_listen.get(t) or kopf_listen.setdefault(t, array("I"))).append(doc_id)
            laengen.append(sum(tf.values()))
            for t, g in tf.items():
                ids, werte = listen.get(t) or listen.setdefault(t, (array("I"), array("f")))
                ids.append(doc_id)
                werte.append(g)
        self.anzahl = len(dokumente)
        mittel = (sum(laengen) / len(laengen)) if laengen else 1.0
        self.norm = array("f", (self.k1 * (1 - self.b + self.b * dl / mittel) for dl in laengen))
        self.postings = {t: (ids.tobytes(), werte.tobytes()) for t, (ids, werte) in listen.items()}
        self.kopf = {t: ids.tobytes() for t, ids in kopf_listen.items()}

    def df(self, term: str) -> int:
        p = self.postings.get(term)
        return len(p[0]) // 4 if p else 0

    def idf(self, term: str) -> float:
        n = self.df(term)
        return math.log(1 + (self.anzahl - n + 0.5) / (n + 0.5)) if n else 0.0

    def bewerte(self, gewichte: dict[str, float]) -> dict[int, float]:
        """BM25-Score je Dokument-ID plus Überschriften-Bonus für gewichtete Anfrageterme."""
        punkte: dict[int, float] = {}
        k1 = self.k1
        norm = self.norm
        for term, gq in gewichte.items():
            p = self.postings.get(term)
            if p is None:
                continue
            idf = self.idf(term)
            ids, werte = _entpacke(p)
            faktor = gq * idf * (k1 + 1)
            for d, tf in zip(ids, werte):
                punkte[d] = punkte.get(d, 0.0) + faktor * tf / (tf + norm[d])
            k = self.kopf.get(term)
            if k is not None:
                ids = array("I")
                ids.frombytes(k)
                bonus = KOPF_BONUS * gq * idf
                for d in ids:
                    punkte[d] += bonus
        return punkte


def _entpacke(p: tuple[bytes, bytes]) -> tuple[array, array]:
    ids = array("I")
    ids.frombytes(p[0])
    werte = array("f")
    werte.frombytes(p[1])
    return ids, werte


_SATZ = re.compile(r"(?<=[.;:!?])\s+(?=[A-ZÄÖÜ(„\"0-9§])")
# Kein Satzende nach Abkürzungen und Ordnungszahlen ("Abs. 1", "BGBl. II Nr. 263", "§ 1. Die …")
_ABKUERZUNG = re.compile(
    r"(?:\b(?:Abs|BGBl|Nr|Art|lit|Z|Ziff|bzw|vgl|idF|gem|iVm|Anm|Pkt|ca|lt|zB|Dr|Mag|Kap|Anh|Anl|Abschn|Stk|S|"
    r"z\.\s?B|d\.\s?h|u\.\s?a)|\d)\.$"
)


def segment_spannen(text: str, max_laenge: int = 400) -> list[tuple[int, int]]:
    """(Start, Ende) von Absätzen/Sätzen; überlange Stücke werden an Wortgrenzen geteilt."""
    spannen: list[tuple[int, int]] = []
    for zeile in re.finditer(r"[^\n]+", text):
        z0, zeilentext = zeile.start(), zeile.group()
        grenzen, a = [], 0
        for m in _SATZ.finditer(zeilentext):
            if _ABKUERZUNG.search(zeilentext, max(0, m.start() - 8), m.start()):
                continue
            grenzen.append((a, m.start()))
            a = m.end()
        grenzen.append((a, len(zeilentext)))
        for a, b in grenzen:
            while a < b and zeilentext[a].isspace():
                a += 1
            while b > a and zeilentext[b - 1].isspace():
                b -= 1
            while b - a > max_laenge:
                schnitt = zeilentext.rfind(" ", a, a + max_laenge)
                schnitt = schnitt if schnitt > a + max_laenge // 2 else a + max_laenge
                spannen.append((z0 + a, z0 + schnitt))
                a = schnitt
                while a < b and zeilentext[a].isspace():
                    a += 1
            if b > a:
                spannen.append((z0 + a, z0 + b))
    return spannen


def segmente(text: str, max_laenge: int = 400) -> list[str]:
    """Text in Absätze/Sätze zerlegen; überlange Stücke an Wortgrenzen teilen."""
    return [text[a:b] for a, b in segment_spannen(text, max_laenge)]


def stuecke(text: str, max_laenge: int = 1000) -> list[tuple[int, int]]:
    """Suchstücke aus aufeinanderfolgenden Segmenten (≤ max_laenge), je ein Segment Überlappung."""
    spannen = segment_spannen(text)
    ergebnis: list[tuple[int, int]] = []
    i = 0
    while i < len(spannen):
        j = i + 1
        while j < len(spannen) and spannen[j][1] - spannen[i][0] <= max_laenge:
            j += 1
        ergebnis.append((spannen[i][0], spannen[j - 1][1]))
        if j >= len(spannen):
            break
        i = j - 1 if j - 1 > i else j
    return ergebnis


def ausschnitt(
    analysator: Analysator, text: str, gewichte: dict[str, float], idf, zitat_max: int = 300, kontext_max: int = 1200
) -> tuple[str, str]:
    """Bester Textausschnitt zur Anfrage → (Zitat ≤ zitat_max, Kontext ≤ kontext_max), beides wörtlich."""
    teile = segmente(text)
    if not teile:
        return "", ""
    bester, bester_wert = 0, -1.0
    for i, seg in enumerate(teile):
        terme = analysator.terme(seg)
        wert = sum(gewichte[t] * idf(t) for t in terme if t in gewichte)
        if wert > bester_wert + 1e-9:
            bester, bester_wert = i, wert
    zitat = teile[bester][:zitat_max]
    if len(teile[bester]) > zitat_max:
        schnitt = zitat.rfind(" ")
        zitat = zitat[:schnitt] if schnitt > zitat_max // 2 else zitat
    # Kontext: Nachbarsegmente, solange Platz ist
    von, bis = bester, bester + 1
    laenge = len(teile[bester])
    while True:
        erweitert = False
        if bis < len(teile) and laenge + len(teile[bis]) + 1 <= kontext_max:
            laenge += len(teile[bis]) + 1
            bis += 1
            erweitert = True
        if von > 0 and laenge + len(teile[von - 1]) + 1 <= kontext_max:
            von -= 1
            laenge += len(teile[von]) + 1
            erweitert = True
        if not erweitert:
            break
    return zitat, " ".join(teile[von:bis])
