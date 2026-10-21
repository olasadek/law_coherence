import datetime as dt

import networkx as nx

from .dates import RANK, STRICT

LONG_GAP_DAYS = 365
MIN_LINK = 0.10                                    # centred-cosine floor for a form/merits order (demo setting, not tuned)


def build_graph(events, ruling):
    """one node per event, an edge between events that follow each other in time (weight = days between them)"""
    G = nx.DiGraph(ruling=ruling)
    for i, e in enumerate(sorted(events, key=lambda e: e.date)):
        G.add_node(i, kind=e.kind, date=e.date, imputed=e.imputed, lo=e.lo, hi=e.hi, quote=e.quote)
    for i in range(len(G) - 1):
        a, b = G.nodes[i], G.nodes[i + 1]
        G.add_edge(i, i + 1, days=(b["date"] - a["date"]).days)
    return G


def flag(G, links=(), min_link=MIN_LINK):
    """review candidates, not verdicts: each one says what to look at and why"""
    ruling, out = G.graph["ruling"], []
    for i, n in G.nodes(data=True):
        if n["imputed"]:
            out.append(dict(level="info", flag="imputed date", where=n["kind"],
                            why=f"no readable date; placed at {n['date']} between {n['lo']} and {n['hi']}"))
        if n["kind"] == "ruling (signature line)":
            if n["date"] != ruling:
                out.append(dict(level="check", flag="ruling date mismatch", where=n["kind"],
                                why=f"signature line says {n['date']}, catalogue says {ruling} ({(n['date'] - ruling).days:+d} days)"))
        elif n["date"] > ruling:
            out.append(dict(level="check", flag="event after ruling", where=n["kind"], why=f"{n['date']} is after the ruling ({ruling})"))
    stages = [n for _, n in G.nodes(data=True) if n["kind"] in STRICT and not n["imputed"]]
    for a, b in zip(stages, stages[1:]):
        if RANK[b["kind"]] < RANK[a["kind"]]:
            out.append(dict(level="check", flag="out of sequence", where=f"{a['kind']} -> {b['kind']}",
                            why=f"{b['kind']} ({b['date']}) is dated after {a['kind']} ({a['date']}) but should come before it"))
    for i, j, d in G.edges(data=True):
        a, b = G.nodes[i], G.nodes[j]
        if a["kind"] not in RANK or b["kind"] not in RANK:
            continue
        if d["days"] > LONG_GAP_DAYS:
            out.append(dict(level="info", flag="long gap", where=f"{a['kind']} -> {b['kind']}", why=f"{d['days']} days between {a['date']} and {b['date']}"))
    for l in links:
        if l["kind"] in ("form", "merits") and l["links"] and l["links"][0]["score"] < min_link:
            out.append(dict(level="check", flag="order without matching reasoning", where=l["order"][:70],
                            why=f"closest reasoning clause scores {l['links'][0]['score']:.2f} (< {min_link})"))
    return out


def plot_timelines(cases, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    style = {"underlying agreement": ("#8C8C8C", "s"), "first-instance judgment": ("#0072B2", "D"), "appeal filed": ("#56B4E9", "o"),
             "submission": ("#CC79A7", "^"), "petition": ("#117733", "P"), "expert report": ("#000000", "p"),
             "court decision": ("#D55E00", "h"), "hearing closed": ("#E69F00", "v"), "ruling (signature line)": ("#009E73", "*"),
             "other": ("#B0B0B0", "x")}
    ink, muted = "#1c2433", "#566174"
    fig, axes = plt.subplots(len(cases), 1, figsize=(10, 1.9 * len(cases) + 1.2), squeeze=False)
    for ax, c in zip(axes[:, 0], cases):
        G, ruling = c["graph"], c["graph"].graph["ruling"]
        nodes = [n for _, n in G.nodes(data=True)]
        ax.plot([n["date"] for n in nodes], [0] * len(nodes), color="#c9cfd9", lw=1.2, zorder=1)
        for n in nodes:
            col, mk = style.get(n["kind"], style["other"])
            if n["imputed"]:
                ax.plot([n["lo"], n["hi"]], [0, 0], color=col, lw=5, alpha=0.25, solid_capstyle="round", zorder=2)
                ax.scatter(n["date"], 0, s=70, marker=mk, facecolor="white", edgecolor=col, lw=1.8, zorder=3)
            else:
                ax.scatter(n["date"], 0, s=110 if mk == "*" else 62, marker=mk, color=col, zorder=3, **({} if mk == "x" else dict(edgecolor="white", lw=0.8)))
        ax.axvline(ruling, color=ink, lw=1, ls=(0, (2, 3)), zorder=0)
        ax.text(ruling, 0.62, "catalogue\nruling date", ha="center", va="bottom", fontsize=7, color=muted)
        for k, f in enumerate([f for f in c["flags"] if f["level"] == "check"][:2]):
            ax.text(0.0, 0.93 - 0.2 * k, f"⚑ {f['flag']}", transform=ax.transAxes, fontsize=8, color="#B3261E", va="top")
        ax.set_title(c["name"], loc="left", fontsize=10, color=ink, pad=4)
        ax.set_ylim(-0.5, 1.1)
        ax.set_yticks([])
        pad = max(40, (nodes[-1]["date"] - nodes[0]["date"]).days * 0.05)
        ax.set_xlim(min(nodes[0]["date"], ruling) - dt.timedelta(days=pad), max(nodes[-1]["date"], ruling) + dt.timedelta(days=pad))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(maxticks=8))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        ax.tick_params(axis="x", labelsize=8, colors=muted)
        for s in ("top", "right", "left"):
            ax.spines[s].set_visible(False)
        ax.spines["bottom"].set_color("#c9cfd9")
    used = [k for k in style if any(n["kind"] == k for c in cases for _, n in c["graph"].nodes(data=True))]
    handles = [Line2D([], [], marker=style[k][1], color=style[k][0], ls="", markersize=7, label=k) for k in used]
    handles.append(Line2D([], [], marker="o", markerfacecolor="white", markeredgecolor=muted, ls="", markersize=7, label="imputed date"))
    fig.legend(handles=handles, loc="lower center", ncol=4, fontsize=8, frameon=False)
    fig.tight_layout(rect=(0, 0.1, 1, 1))
    fig.savefig(path, dpi=160, facecolor="white")
    plt.close(fig)
