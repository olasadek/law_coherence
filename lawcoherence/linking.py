import re

import numpy as np

from .preprocess import fold

MODEL = "CAMeL-Lab/bert-base-arabic-camelbert-msa"

# what an operative order does; only form and merits orders are expected to rest on specific reasoning
CONSEQUENTIAL = [("deposit", r"التامين"), ("residual", r"الزائده|المخالفه"), ("costs", r"النفقات|الرسوم|المصاريف|الاتعاب"),
                 ("remand", r"اعاده الملف")]
MERITS = r"اساسا|تصديق|فسخ|رد الاست\S{1,4}ف|رد الطلب|شطب|ابطال|الغاء"


def order_kind(text):
    f = fold(text)
    for kind, pat in CONSEQUENTIAL:
        if re.search(pat, f):
            return kind
    return "merits" if re.search(MERITS, f) else "form" if "شكل" in f else "other"


_cache = {}


def _camelbert(texts, model_name=MODEL, max_len=256, batch=16):
    import torch
    from transformers import AutoModel, AutoTokenizer
    if model_name not in _cache:
        _cache[model_name] = (AutoTokenizer.from_pretrained(model_name), AutoModel.from_pretrained(model_name).eval())
    tok, model = _cache[model_name]
    out = []
    with torch.no_grad():
        for i in range(0, len(texts), batch):
            enc = tok(texts[i:i + batch], padding=True, truncation=True, max_length=max_len, return_tensors="pt")
            h = model(**enc).last_hidden_state
            m = enc["attention_mask"].unsqueeze(-1)
            out.append(((h * m).sum(1) / m.sum(1)).numpy())          # mean over real tokens
    return np.vstack(out)


def _tfidf(texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    return TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4), sublinear_tf=True).fit_transform(
        [fold(t) for t in texts]).toarray()


def embed(texts, backend="camelbert"):
    return _camelbert(texts) if backend == "camelbert" else _tfidf(texts)


def link_orders(orders, reasoning, backend="camelbert", top_k=2):
    """for each operative order, the reasoning clauses whose meaning is closest to it.
    Vectors are centred on the judgment's own mean first: raw BERT vectors of one text all look alike (cosine ~0.9)."""
    if not orders or not reasoning:
        return []
    E = embed([o for o in orders] + [c["text"] for c in reasoning], backend)
    E = E - E[len(orders):].mean(0)
    E = E / (np.linalg.norm(E, axis=1, keepdims=True) + 1e-9)
    S = E[:len(orders)] @ E[len(orders):].T
    links = []
    for i, o in enumerate(orders):
        idx = np.argsort(-S[i])[:top_k]
        links.append(dict(order=o, kind=order_kind(o), links=[dict(clause=int(j), score=float(S[i, j])) for j in idx]))
    return links
