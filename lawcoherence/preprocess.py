import re
import unicodedata

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
MARKS = re.compile(r"[ً-ْـ​-‏‪-‮﻿]")          # diacritics, tatweel, zero-width and bidi controls
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})

# a new paragraph starts at these openers; every other line is a wrapped continuation of the one above
PARA_START = re.compile(r"^\s*(?:و?حيث|و?بتاريخ|و?طلب|و?تبين|و?تقدم|لدى|اول|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|لهذه|لذلك|تقرر|قرارا|\d{1,2}\s?[-–]?\s|-\s)")


LOOSE_REASONS = re.compile(r"ل\s?ه\s?ذ\s?[هة]?\s?ا?\s?ل\s?ا?\s?س\s?ب\s?ا\s?ب")   # "لهذه الأسباب", tolerating OCR gaps inside the words


def fold(t):
    return t.translate(FOLD)


def clean_ocr(text):
    """Arabic OCR output -> paragraphs: unify digits and dates, drop junk lines, re-join wrapped lines"""
    t = unicodedata.normalize("NFKC", text).translate(DIGITS)
    t = MARKS.sub("", t)
    t = re.sub(r"(\d{1,4})\s*/\s*(\d{1,2})\s*/\s*(\d{1,4})", r"\1/\2/\3", t)
    t = re.sub(r"[<>|©_~*]+", " ", t)
    paras, cur = [], []
    for line in t.splitlines():
        line = " ".join(line.split())
        has_word = re.search(r"[ء-ي]{3,}", line)
        has_date = re.search(r"\d{1,4}/\d{1,2}/\d{1,4}", line)
        if not (has_word or has_date):                     # page numbers, stamps, stray glyphs
            continue
        if cur and (PARA_START.match(fold(line)) or LOOSE_REASONS.match(fold(line))):
            paras.append(" ".join(cur))
            cur = []
        cur.append(line)
    if cur:
        paras.append(" ".join(cur))
    return paras


ORDER_START = r"^(?:(?:اولا?|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا)\s?[:\-–]|\d{1,2}\s?[-–]?\s)"


def split_judgment(paras):
    """header (procedure), reasoning (court's 'whereas' clauses) and operative orders"""
    folded = [fold(p) for p in paras]
    cut = next((i for i in range(len(paras) - 1, -1, -1) if LOOSE_REASONS.search(folded[i])), None)
    if cut is None:
        cut = next((i for i in range(len(paras) - 1, -1, -1) if re.search(r"^تقرر", folded[i])), len(paras))
    body, operative = paras[:cut], paras[cut:]
    first = next((i for i, p in enumerate(body) if re.match(r"^و?حيث", fold(p))), len(body))     # the court's first "whereas"
    header, reasoning = body[:first], body[first:]
    orders = [p for p in operative if re.match(ORDER_START, fold(p))]     # "أولاً: قبول الاستئناف شكلاً ..."
    return dict(header=header, reasoning=reasoning, operative=orders)


def clauses(reasoning):
    """one clause per paragraph that opens with 'حيث' (the court's units of reasoning), headings kept as context"""
    out, heading = [], ""
    for p in reasoning:
        f = fold(p)
        if re.match(r"^(?:اولا|ثانيا|ثالثا)\s?:?\s*(?:ف[يى]\s)", f) or len(p) < 40:
            heading = p
            continue
        out.append(dict(text=p, heading=heading))
    return out
