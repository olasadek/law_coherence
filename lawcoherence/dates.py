import datetime as dt
import re
from dataclasses import dataclass

from .preprocess import fold

WINDOW_YEARS = 12                                  # a procedural date must fall within 12 years before the ruling
DATE_RE = re.compile(r"(?<!\d)\d{1,4}/\d{1,2}/\d{1,4}(?!\d)")

# kind of event, read from the nearest of these words around the date (patterns run on alef/ya/ta-marbuta folded text)
KINDS = [("first-instance judgment", r"الحكم الصادر|القرار الصادر|الحكم المستانف|القرار المستانف"),
         ("appeal filed", r"است\S{1,3}[فق]|استحضار"),
         ("submission", r"لايحه|لائحه|مذكره|جوابيه|قدما|قدم"),
         ("petition", r"استدعاء"),
         ("expert report", r"تقريره|تقرير"),
         ("court decision", r"قراراً? تمهيدي|صدر قرار|القرار تاريخ|قررت|ضم الملف"),
         ("hearing closed", r"اختتمت|الجلسه|المنعقده"),
         ("ruling (signature line)", r"قرارا صدر"),
         ("underlying agreement", r"الاتفاقيه|الملحق|العقد|الوكاله|البيع|اتفاق")]
RANK = {"first-instance judgment": 1, "appeal filed": 2, "submission": 3, "hearing closed": 4, "ruling (signature line)": 5}
STRICT = ("first-instance judgment", "appeal filed", "hearing closed", "ruling (signature line)")   # stages that must come in this order
PRIORITY = ["hearing closed", "appeal filed", "first-instance judgment", "ruling (signature line)", "expert report", "court decision",
            "petition", "submission", "underlying agreement", "other"]
NOT_AN_EVENT = r"قانون|القانون|المرسوم|مرسوم|الماده|المادة"       # dates of laws and decrees


@dataclass
class Event:
    kind: str
    date: dt.date
    quote: str
    imputed: bool = False
    lo: dt.date = None
    hi: dt.date = None


def year_candidates(y, end_year):
    """OCR reads 2 as 7 or 0 (7019 -> 2019) and drops digits; two-digit years can be 19xx or 20xx"""
    c = []
    if len(y) == 4:
        c.append(int(y))
        if y[0] in "07":
            c.append(int("2" + y[1:]))
    elif len(y) == 2:
        c += [1900 + int(y), 2000 + int(y)]
    return [v for v in c if end_year - WINDOW_YEARS <= v <= end_year + 1]


def parse_date(s, end):
    m = re.fullmatch(r"(\d{1,4})/(\d{1,2})/(\d{1,4})", s)
    if not m:
        return None
    a, b, c = m.groups()
    for yy, mo, d in ((c, b, a), (a, b, c)):             # day/month/year or year/month/day
        if len(yy) in (2, 4) and len(d) <= 2:
            for y in year_candidates(yy, end.year):
                try:
                    x = dt.date(y, int(mo), int(d))
                except ValueError:
                    continue
                if dt.date(end.year - WINDOW_YEARS, 1, 1) <= x <= end + dt.timedelta(days=366):
                    return x
    return None


def nearest_kind(f, start, stop):
    lo = max(0, start - 110)
    best = ("other", 10 ** 9)
    for kind, pat in KINDS:
        for m in re.finditer(pat, f[lo: stop + 70]):
            a, b = m.start() + lo, m.end() + lo
            gap = start - b if b <= start else a - stop + 1 if a >= stop else 0      # a keyword before the date wins a tie
            if gap < best[1]:
                best = (kind, gap)
    return best[0]


def extract_events(text, ruling):
    """dated events (kind, date, quote); a date or 'بتاريخ' that cannot be read stays as an undated slot (date=None)"""
    f = fold(text)
    out = []
    for m in DATE_RE.finditer(f):
        if re.search(NOT_AN_EVENT, f[max(0, m.start() - 40): m.start()]):
            continue
        out.append(Event(nearest_kind(f, m.start(), m.end()), parse_date(m.group(), ruling), text[max(0, m.start() - 60): m.end() + 30]))
    for m in re.finditer(r"بتاريخ", f):
        after = f[m.end(): m.end() + 14].strip()
        if not DATE_RE.match(after) and not re.match(r"(?:لاحق|سابق|اخر|هذا|ذلك|معين|محدد)", after):   # "at a later date" is no slot
            out.append(Event(nearest_kind(f, m.end(), m.end() + 1), None, text[max(0, m.start() - 60): m.end() + 40]))
    return out


def impute(events, ruling):
    """an event with no readable date lies between the last earlier stage and the first later stage of the procedure;
    the ruling date closes the interval, and the signature line of the ruling is the ruling date itself"""
    known = [e for e in events if e.date]
    for e in events:
        if e.date or e.kind not in RANK:
            continue
        if e.kind == "ruling (signature line)":
            e.lo = e.hi = e.date = ruling
            e.imputed = True
            continue
        before = [k.date for k in known if RANK.get(k.kind, 99) < RANK[e.kind]]
        if not before:
            continue
        lo = max(before)
        after = [k.date for k in known if RANK.get(k.kind, 0) > RANK[e.kind] and k.date >= lo] + [ruling]   # first-instance submissions come earlier: skipped
        e.lo, e.hi = lo, min(after)
        e.date = e.lo + (e.hi - e.lo) / 2
        e.imputed = True
    return dedupe([e for e in events if e.date])


def dedupe(events):
    """a date mentioned several times is one event; it keeps the most specific kind any mention gave it"""
    by_date = {}
    for e in sorted(events, key=lambda e: e.date):
        old = by_date.get(e.date)
        if old is None or PRIORITY.index(e.kind) < PRIORITY.index(old.kind):
            by_date[e.date] = e
    return list(by_date.values())


def signature_date(text, ruling):
    f = fold(text)
    m = re.search(r"قرارا صدر.{0,50}?بتاريخ\s*(" + DATE_RE.pattern + ")", f)
    return parse_date(m.group(1), ruling) if m else None
