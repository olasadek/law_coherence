import datetime as dt
import re

DATE_YMD = re.compile(r"(?<!\d)(19\d{2}|20[0-3]\d)/(\d{1,2})/(\d{1,2})(?!\d)")


def shift_dates(text, days):
    """move every readable y/m/d date by the same number of days: intervals between events stay exact"""
    def move(m):
        try:
            d = dt.date(int(m[1]), int(m[2]), int(m[3])) + dt.timedelta(days=days)
        except ValueError:
            return m[0]
        return f"{d.year}/{d.month}/{d.day}"
    return DATE_YMD.sub(move, text)


def redact(text, names, placeholder="[اسم]"):
    """replace each name (longest first) wherever it is not part of a longer Arabic word; a leading 'و' (and) stays"""
    for n in sorted(names, key=len, reverse=True):
        text = re.sub(r"(?<![ء-ي])(و?)" + r"\s+".join(re.escape(w) for w in n.split()) + r"(?![ء-ي])", r"" + placeholder, text)
    return text
