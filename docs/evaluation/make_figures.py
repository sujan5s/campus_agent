"""Figures + tables for the agent evaluation (docs/12-AGENT-EVALUATION-RESULTS.md).

Reads docs/evaluation/results/eval_*.json (written by services/backend/eval/run_eval.py)
and writes
  figures/*.png (300 dpi) and figures/*.pdf (vector, for LaTeX)
  tables/*.md   (GitHub markdown)  and  tables/*.tex (booktabs, \\input{} into the paper)
  tables/*.csv

    py docs/evaluation/make_figures.py

Colours: validated categorical slots (blue, orange, aqua, yellow; adjacent CVD
dE >= 9.1). Two slots sit below 3:1 on white, so every bar is direct-labelled
and every figure has a matching table.
"""
import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
RES, FIG, TAB = HERE / "results", HERE / "figures", HERE / "tables"
FIG.mkdir(exist_ok=True)
TAB.mkdir(exist_ok=True)

BLUE, ORANGE, AQUA, YELLOW = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e6e5e1"
SEQ = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5, "axes.titlesize": 9.5,
    "axes.titleweight": "bold", "axes.titlelocation": "left", "axes.labelsize": 8.5,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "axes.linewidth": 0.6,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "legend.fontsize": 8, "figure.dpi": 110,
    "savefig.dpi": 300, "savefig.bbox": "tight", "pdf.fonttype": 42,
})

# ---- load ------------------------------------------------------------------
R: dict = {}
for p in sorted(RES.glob("eval_*.json")):
    d = json.loads(p.read_text())
    R.update({k: v for k, v in d.items() if k != "meta"})
    R.setdefault("meta", d.get("meta"))


def save(fig, name):
    fig.savefig(FIG / f"{name}.png")
    fig.savefig(FIG / f"{name}.pdf")
    plt.close(fig)
    print("figure", name)


def table(name, header, rows, caption=""):
    """Write the same table as markdown, booktabs LaTeX and CSV."""
    rows = [[("" if c is None else str(c)) for c in r] for r in rows]
    md = ["| " + " | ".join(header) + " |", "|" + "|".join([" --- "] * len(header)) + "|"]
    md += ["| " + " | ".join(r) + " |" for r in rows]
    (TAB / f"{name}.md").write_text((f"**{caption}**\n\n" if caption else "") + "\n".join(md) + "\n",
                                    encoding="utf-8")

    def tex(s):
        for a, b in [("\\", r"\textbackslash{}"), ("&", r"\&"), ("%", r"\%"), ("#", r"\#"),
                     ("_", r"\_"), ("×", r"$\times$"), ("≥", r"$\geq$"), ("≤", r"$\leq$"),
                     ("→", r"$\rightarrow$"), ("±", r"$\pm$"), ("✓", r"\checkmark"),
                     ("✗", r"$\times$"), ("–", "--"), ("⚠", "(!)"), ("μ", r"$\mu$")]:
            s = s.replace(a, b)
        return s.replace("**", "")
    lines = [r"\begin{table}[t]", r"\centering", r"\small",
             r"\begin{tabular}{" + "l" * 1 + "r" * 0 + "l" * (len(header) - 1) + "}", r"\toprule",
             " & ".join(tex(h) for h in header) + r" \\", r"\midrule"]
    lines += [" & ".join(tex(c) for c in r) + r" \\" for r in rows]
    lines += [r"\bottomrule", r"\end{tabular}"]
    if caption:
        lines.append(r"\caption{" + tex(caption) + "}")
    lines += [r"\label{tab:" + name.replace("_", "-") + "}", r"\end{table}"]
    (TAB / f"{name}.tex").write_text("\n".join(lines) + "\n", encoding="utf-8")
    with open(TAB / f"{name}.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)
    print("table ", name)


def pct(a, b):
    return f"{100 * a / b:.1f}%" if b else "–"


def fmt_ms(v):
    if v is None:
        return "–"
    if v < 0.01:
        return "< 0.01 ms"
    return f"{v:.2f} ms" if v < 10 else (f"{v:.0f} ms" if v < 1000 else f"{v / 1000:.2f} s")


def label_bars(ax, bars, fmt="{:.0f}", inside=False, color=INK, dy=0.0):
    for b in bars:
        h = b.get_height()
        ax.annotate(fmt.format(h), (b.get_x() + b.get_width() / 2, h), xytext=(0, 2 + dy),
                    textcoords="offset points", ha="center", va="bottom", fontsize=7.5, color=color)


# =============================================================================
# Routing
# =============================================================================
rt = R.get("routing", {})
labels = ["timetable", "substitution", "scheduler", "facility", "general"]
routers = [("keyword", "Keyword fallback")] + ([("llm", "LLM supervisor")] if "accuracy" in rt.get("llm", {}) else [])
if rt:
    fig, axes = plt.subplots(1, len(routers), figsize=(3.4 * len(routers), 3.1))
    axes = np.atleast_1d(axes)
    for ax, (k, title) in zip(axes, routers):
        cm = np.array(rt[k]["confusion"])
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list("seq", SEQ)
        ax.imshow(cm, cmap=cmap, vmin=0, vmax=20)
        ax.grid(False)
        for i in range(5):
            for j in range(5):
                v = cm[i, j]
                ax.text(j, i, str(v), ha="center", va="center", fontsize=8,
                        color="#ffffff" if v >= 12 else (INK if v else MUTED))
        ax.set_xticks(range(5), [l[:5] + "." if len(l) > 6 else l for l in labels], rotation=0)
        ax.set_yticks(range(5), labels)
        ax.set_xlabel("predicted route")
        if ax is axes[0]:
            ax.set_ylabel("true route")
        ax.set_title(f"{title}  (acc {rt[k]['accuracy'] * 100:.0f}%)")
        for s in ax.spines.values():
            s.set_visible(False)
    fig.tight_layout()
    save(fig, "fig1_routing_confusion")

    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    x = np.arange(len(labels) + 1)
    w = 0.38 if len(routers) == 2 else 0.6
    for n, ((k, title), col) in enumerate(zip(routers, [MUTED, BLUE])):
        vals = [rt[k]["per_class"][l]["f1"] for l in labels] + [rt[k]["macro_f1"]]
        off = (n - (len(routers) - 1) / 2) * (w + 0.03)
        bars = ax.bar(x + off, vals, w, color=col, label=title)
        label_bars(ax, bars, "{:.2f}")
    ax.set_xticks(x, labels + ["macro-F1"])
    ax.set_ylim(0, 1.12)
    ax.set_ylabel("F1 score")
    ax.set_title("Supervisor routing: per-class F1 on 100 labelled queries")
    ax.legend(loc="upper left", ncol=2, bbox_to_anchor=(0, 1.02))
    ax.grid(axis="x", visible=False)
    save(fig, "fig2_routing_f1")

    rows = []
    for k, title in routers:
        m = rt[k]
        rows.append([title, f"{m['accuracy'] * 100:.1f}%", f"{m['macro_f1']:.3f}"]
                    + [f"{m['per_class'][l]['precision']:.2f} / {m['per_class'][l]['recall']:.2f}" for l in labels]
                    + [fmt_ms(m["latency_ms"]["median"])])
    table("t2_routing", ["Router", "Accuracy", "Macro-F1"] + [f"{l} P/R" for l in labels] + ["Median latency"],
          rows, "Supervisor routing on 100 hand-labelled queries (20 per route)")

# =============================================================================
# Latency overview (one series, log scale)
# =============================================================================
lat = []
def add(name, med, p25=None, p75=None):  # noqa: E302
    if med is not None:
        lat.append((name, med, p25 if p25 is not None else med, p75 if p75 is not None else med))

if rt:
    s = rt["system_bypass"]["latency_ms"]
    add("Supervisor: system-trigger bypass", s["median"], s["p25"], s["p75"])
    s = rt["keyword"]["latency_ms"]
    add("Supervisor: keyword router", s["median"], s["p25"], s["p75"])
    if "latency_ms" in rt.get("llm", {}):
        s = rt["llm"]["latency_ms"]
        add("Supervisor: LLM structured routing", s["median"], s["p25"], s["p75"])
sp = R.get("specialists", {})
if sp:
    for key, name in [("facility", "Facility Agent: venue resolution"), ("scheduler", "Scheduler Agent: registry audit"),
                      ("general_canned", "General Agent: offline reply")]:
        s = sp[key]["ms"]
        add(name, s["median"], s["p25"], s["p75"])
    if sp.get("general_llm", {}).get("ms"):
        s = sp["general_llm"]["ms"]
        add("General Agent: LLM answer", s["median"], s["p25"], s["p75"])
ex = R.get("exchange", {})
if ex:
    s = ex["latency_ms"]
    add("Substitution Agent: exchange plan", s["median"], s["p25"], s["p75"])
    s = ex["legacy_latency_ms"]
    add("Legacy stand-in planner (baseline)", s["median"], s["p25"], s["p75"])
hi = R.get("hitl", {})
if hi:
    s = hi["pause_ms"]
    add("HITL: trigger → interrupt()", s["median"], s["p25"], s["p75"])
    s = hi["resume_ms"]
    add("HITL: resume after restart", s["median"], s["p25"], s["p75"])
rg = R.get("registry", {})
if rg:
    s = rg["compile_ms"]
    add("Constraint registry: compile", s["median"], s["p25"], s["p75"])
asst = R.get("assistant", {})
if asst:
    s = asst["plan_ms"]
    add("Assistant: validate plan", s["median"], s["p25"], s["p75"])
    if asst.get("llm", {}).get("latency_s"):
        s = asst["llm"]["latency_s"]
        add("Assistant: LLM NL → plan", s["median"] * 1000, s["p25"] * 1000, s["p75"] * 1000)
sv = R.get("solver", {})
if sv:
    for mode, name in [("warm", "Timetable Agent: warm solve (8 s cap)"), ("cold", "Timetable Agent: cold solve (8 s cap)")]:
        xs = sorted(r["wall_s"] * 1000 for r in sv["modes"][mode])
        add(name, float(np.median(xs)), xs[0], xs[-1])

if lat:
    FLOOR = 0.005    # timer resolution of the harness (3-decimal ms); smaller values are drawn at the floor
    lat = [(n, max(m, FLOOR), max(a, FLOOR), max(b, FLOOR)) for n, m, a, b in lat]
    lat.sort(key=lambda t: t[1])
    fig, ax = plt.subplots(figsize=(6.6, 0.28 * len(lat) + 0.8))
    y = np.arange(len(lat))
    cols = [ORANGE if "baseline" in n else BLUE for n, *_ in lat]
    ax.barh(y, [m for _, m, *_ in lat], height=0.55, color=cols)
    ax.errorbar([m for _, m, *_ in lat], y,
                xerr=[[m - a for _, m, a, _ in lat], [b - m for _, m, _, b in lat]],
                fmt="none", ecolor=INK2, elinewidth=0.8, capsize=2)
    for yi, (_, m, _, b) in zip(y, lat):
        ax.text(max(b, m) * 1.15, yi, fmt_ms(m), va="center", fontsize=7.5, color=INK)
    ax.set_yticks(y, [n for n, *_ in lat])
    ax.set_xscale("log")
    ax.set_xlim(FLOOR / 2, max(b for *_, b in lat) * 8)
    ax.set_xlabel("median latency, ms (log scale; whiskers = interquartile range, solver = min–max)")
    ax.set_title("End-to-end latency per agent operation")
    ax.grid(axis="y", visible=False)
    save(fig, "fig3_latency")
    table("t3_latency", ["Operation", "Median", "P25", "P75 / max"],
          [[n, fmt_ms(m), fmt_ms(a), fmt_ms(b)] for n, m, a, b in lat], "Latency per agent operation")

# =============================================================================
# Solver
# =============================================================================
if sv:
    inst = sv["instance"]
    cold, warm = sv["modes"]["cold"], sv["modes"]["warm"]
    c120 = sv["modes"]["cold_120s"][0]
    v = next(r["verify"] for r in cold + warm if r.get("verify"))
    allv = [r["verify"] for r in cold + warm if r.get("verify")]
    viol_total = sum(sum(x["violations"].values()) for x in allv)
    table("t4_solver_instance", ["Property", "Value"], [
        ["Sections / teachers / rooms", f"{inst['sections']} / {inst['teachers']} / {inst['rooms']}"],
        ["Timeslots (MON–FRI × 7)", inst["slots"]], ["Weekly lessons demanded", inst["lessons_demanded"]],
        ["Open-elective bands / pinned assignments", f"{inst['elective_bands']} / {inst['pins']}"],
        ["Enabled scheduling rules", inst["rules_enabled"]],
        ["Cold solve, 8 s cap (median of runs)", f"{np.median([r['wall_s'] for r in cold]):.2f} s, status "
         f"{', '.join(sorted({r['status'] for r in cold}))}"],
        ["Warm (preserve) solve, 8 s cap", f"{np.median([r['wall_s'] for r in warm]):.2f} s, status "
         f"{', '.join(sorted({r['status'] for r in warm}))}"],
        ["Cold solve, 120 s cap", f"{c120['wall_s']:.2f} s, {c120['status']}, objective {c120['objective']}"],
        ["Objective cold / warm (median)", f"{np.median([r['objective'] for r in cold]):.0f} / "
                                           f"{np.median([r['objective'] for r in warm]):.0f}"],
        ["Lessons moved vs published (cold / warm)",
         f"{np.median([r['moved_vs_published'] for r in cold]):.0f} / {np.median([r['moved_vs_published'] for r in warm]):.0f}"
         f" of {cold[0]['lessons']}"],
        ["Independent hard-constraint checks", f"{v['checks']} checks × {len(allv)} solutions, {viol_total} violations"],
    ], "Timetable Agent on the campus instance (CP-SAT, 8 workers)")
    table("t5_hard_constraints", ["Check", "Violations (all solutions)"],
          [[c, sum(x["violations"][c] for x in allv)] for c in v["violations"]],
          f"Independent verification of solver output ({len(allv)} solutions)")

    # Fig 4: churn per scenario, preserve vs fresh (one measure, one axis)
    sc = sv["scenarios"]
    names = list(sc)
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.7), layout="constrained")
    x = np.arange(len(names))
    for ax, metric, ylabel, title in [
        (axes[0], "moved", "lessons moved", "Schedule churn after a small change"),
        (axes[1], "wall_s", "solve time, s", "Re-solve time (8 s budget)")]:
        for n, (mode, col, lab) in enumerate([("preserve", BLUE, "preserve (warm hints + move penalty)"),
                                              ("fresh", ORANGE, "fresh re-plan (cold)")]):
            vals = [float(np.median([m for m in sc[s][mode][metric] if m is not None])) for s in names]
            bars = ax.bar(x + (n - 0.5) * 0.4, vals, 0.38, color=col, label=lab)
            label_bars(ax, bars, "{:.0f}" if metric == "moved" else "{:.1f}")
        ax.set_xticks(x, ["+2-period\nsubject", "teacher off\nWednesday", "+1 period\nper week"])
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(axis="x", visible=False)
        ax.margins(y=0.15)
    h, l_ = axes[0].get_legend_handles_labels()
    fig.legend(h, l_, loc="outside lower center", ncol=2)
    save(fig, "fig4_solver_churn")
    pub = sc[names[0]]["preserve"]["published_lessons"]
    table("t6_incremental", ["Change", "Mode", "Status", "Median time", "Lessons moved", "Checks passed"],
          [[s, m, sc[s][m]["status"][-1], f"{np.median(sc[s][m]['wall_s']):.2f} s",
            f"{np.median([x for x in sc[s][m]['moved'] if x is not None]):.0f} / {pub}",
            f"{sc[s][m]['verify_passed']}/{sc[s][m]['verify_checks']}"] for s in names for m in ("preserve", "fresh")],
          "Incremental re-planning: preserve vs fresh")

def st_(status):
    return "no solution in limit" if status == "error" else status


def run_(r, key):
    return f"{r[key + '_s']:.1f} s ({st_(r[key + '_status'])})" if key + "_s" in r else "– (no cold solution)"


sc_ = R.get("scale", {})
if sc_:
    rows = sc_["rows"]
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.6))
    L = [r["lessons"] for r in rows]
    for key, col, lab, mk in [("cold_s", ORANGE, "cold solve", "o"), ("fresh_s", YELLOW, "fresh re-plan after change", "s"),
                              ("warm_s", BLUE, "warm re-plan after change", "D")]:
        ys = [r.get(key) for r in rows]
        axes[0].plot(L, ys, color=col, lw=2, marker=mk, ms=5, label=lab)
    axes[0].axhline(sc_["time_limit_s"], color=MUTED, lw=0.8, ls="--")
    axes[0].text(L[0], sc_["time_limit_s"] * 1.03, f"time limit {sc_['time_limit_s']:.0f} s", fontsize=7, color=INK2)
    axes[0].set_xlabel("weekly lessons in instance")
    axes[0].set_ylabel("wall time, s")
    axes[0].set_title("Scalability (sections ×1…×5)")
    axes[0].legend(loc="upper left", fontsize=7)
    for key, col, lab in [("fresh_moved", ORANGE, "fresh"), ("warm_moved", BLUE, "preserve")]:
        axes[1].plot(L, [r.get(key) for r in rows], color=col, lw=2, marker="o", ms=5, label=lab)
    axes[1].set_xlabel("weekly lessons in instance")
    axes[1].set_ylabel("lessons moved")
    axes[1].set_title("Churn after adding one subject")
    axes[1].legend(loc="upper left", fontsize=7)
    fig.tight_layout()
    save(fig, "fig5_scalability")
    table("t7_scalability", ["Factor", "Sections", "Teachers", "Lessons", "Cold", "Warm (change)", "Fresh (change)",
                             "Moved warm / fresh", "Verified"],
          [[f"×{r['factor']}", r["sections"], r["teachers"], r["lessons"],
            f"{r['cold_s']:.1f} s ({st_(r['cold_status'])}, obj {r.get('cold_objective')})",
            run_(r, "warm"), run_(r, "fresh"),
            f"{r.get('warm_moved')} / {r.get('fresh_moved')}" if "warm_s" in r else "–",
            r.get("cold_verify") or "–"] for r in rows],
          f"Synthetic scaling, {sc_['time_limit_s']:.0f} s time limit per solve")

inf = R.get("infeasible", {})
if inf:
    table("t8_infeasibility", ["Broken instance", "Status", "Diagnosed by", "Groups blamed", "Time",
                               "Explanation (truncated)"],
          [[r["case"], r["status"], r["source"],
            r.get("groups_named") or "1 (exact cause)" if r["source"] == "precheck" else r.get("groups_named"),
            f"{r['wall_s'] * 1000:.0f} ms", r["reason"][:90]]
           for r in inf["rows"]],
          f"Infeasibility diagnosis: {inf['detected']}/{inf['n']} detected, {inf['specific']}/{inf['n']} with a specific cause")

# =============================================================================
# Substitution / exchange
# =============================================================================
if ex:
    kinds = ["1-day", "2-day", "3-day", "5-day"]
    bk = ex["by_kind"]
    clean = [bk[k]["exchanged"] - bk[k]["warned"] for k in kinds]
    warned = [bk[k]["warned"] for k in kinds]
    lab = [bk[k]["lab_manual"] for k in kinds]
    nop = [bk[k]["no_partner"] for k in kinds]
    tot = [bk[k]["affected"] for k in kinds]
    fig, ax = plt.subplots(figsize=(4.6, 2.7))
    x = np.arange(len(kinds))
    bottom = np.zeros(len(kinds))
    for vals, col, lab_ in [(clean, BLUE, "exchanged, clean"), (warned, AQUA, "exchanged, ⚠ flagged"),
                            (lab, YELLOW, "lab block → manual"), (nop, ORANGE, "no partner → manual")]:
        share = np.array([v / t * 100 if t else 0 for v, t in zip(vals, tot)])
        ax.bar(x, share, 0.6, bottom=bottom, color=col, label=lab_, edgecolor="white", linewidth=1.5)
        for xi, (b, s_) in enumerate(zip(bottom, share)):
            if s_ >= 6:
                ax.text(xi, b + s_ / 2, f"{s_:.0f}%", ha="center", va="center", fontsize=7.5,
                        color="#ffffff" if col == BLUE else INK)
        bottom += share
    for xi, t in enumerate(tot):
        ax.text(xi, 101.5, f"n={t}", ha="center", va="bottom", fontsize=7, color=INK2)
    ax.set_xticks(x, [k + " leave" for k in kinds])
    ax.set_ylim(0, 110)
    ax.set_ylabel("% of affected lessons")
    ax.set_title("Substitution Agent: outcome of every affected lesson")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=7.5)
    ax.grid(axis="x", visible=False)
    save(fig, "fig6_exchange_outcomes")

    # vs legacy baseline: coverage and subject-hour preservation (both %, one axis)
    theory = ex["theory_affected"]
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    metrics = ["lessons covered", "subject hours preserved\n(right teacher, right subject)"]
    exv = [ex["exchanged"] / ex["affected"] * 100, ex["exchanged"] / ex["affected"] * 100]
    lgv = [ex["legacy_covered"] / ex["affected"] * 100, ex["legacy_same_subject"] / ex["affected"] * 100]
    x = np.arange(2)
    b1 = ax.bar(x - 0.2, exv, 0.38, color=BLUE, label="period exchange (this work)")
    b2 = ax.bar(x + 0.2, lgv, 0.38, color=ORANGE, label="stand-in substitute (legacy)")
    label_bars(ax, b1, "{:.1f}%")
    label_bars(ax, b2, "{:.1f}%")
    ax.set_xticks(x, metrics)
    ax.set_ylim(0, 118)
    ax.set_ylabel(f"% of {ex['affected']} affected lessons")
    ax.set_title("Exchange planner vs legacy substitution")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.25), ncol=1, fontsize=7.5)
    ax.grid(axis="x", visible=False)
    save(fig, "fig7_exchange_vs_legacy")

    gaps = [g for r in ex["rows"] for g in r["gaps_days"]]
    if gaps:
        fig, ax = plt.subplots(figsize=(4.0, 2.3))
        bins = np.arange(min(gaps) - 0.5, max(gaps) + 1.5, 1)
        ax.hist(gaps, bins=bins, color=BLUE, edgecolor="white", linewidth=1.5)
        ax.set_xlabel("days between missed lesson and recovery lesson")
        ax.set_ylabel("exchanges")
        ax.set_title("Recovery delay of exchanged lessons")
        ax.grid(axis="x", visible=False)
        save(fig, "fig8_recovery_gap")

    table("t9_exchange", ["Metric", "Period exchange (this work)", "Legacy stand-in planner"], [
        ["Simulated leaves (teachers × patterns)", f"{ex['leaves']} ({ex['teachers']} teachers)", "same"],
        ["Lessons affected", ex["affected"], ex["affected"]],
        ["Covered automatically", f"{ex['exchanged']} ({pct(ex['exchanged'], ex['affected'])})",
         f"{ex['legacy_covered']} ({pct(ex['legacy_covered'], ex['affected'])})"],
        ["Theory lessons covered", f"{ex['exchanged']}/{theory} ({pct(ex['exchanged'], theory)})", "–"],
        ["Subject hours preserved", f"{ex['exchanged']} ({pct(ex['exchanged'], ex['affected'])})",
         f"{ex['legacy_same_subject']} ({pct(ex['legacy_same_subject'], ex['affected'])})"],
        ["Lab blocks routed to manual handling", ex["lab_manual"], "– (not distinguished)"],
        ["Exchanges flagged ⚠ (hectic sequence)", f"{ex['warned']} ({pct(ex['warned'], ex['exchanged'])})", "–"],
        ["Invariant violations (independent check)", ex["invariant_violations"], "–"],
        ["Master timetable rows changed", ex["master_rows_after"] - ex["master_rows_before"], "–"],
        ["Rebuild idempotent", "yes" if ex["idempotent_all"] else "no", "–"],
        ["Median plan latency", fmt_ms(ex["latency_ms"]["median"]), fmt_ms(ex["legacy_latency_ms"]["median"])],
        ["Median recovery delay", f"{ex['gap_days']['median']:.0f} days", "–"],
    ], "Substitution Agent vs legacy stand-in substitution")

if hi:
    table("t10_hitl", ["Metric", "Value"], [
        ["Approved leaves with classes", hi["n"]],
        ["Supervisor skipped the LLM (system trigger)", f"{hi['llm_skipped']}/{hi['n']}"],
        ["Graph paused at interrupt()", f"{hi['paused']}/{hi['n']}"],
        ["Resumed correctly after simulated restart", f"{hi['resumed_ok']}/{hi['n']}"],
        ["No duplicate plan rows after resume", f"{hi['no_duplicates']}/{hi['n']}"],
        ["Median trigger → pause", fmt_ms(hi["pause_ms"]["median"])],
        ["Median resume → applied", fmt_ms(hi["resume_ms"]["median"])],
        ["Notifications per approved plan (median)", f"{hi['notifications_per_approved_plan']['median']:.0f}"],
    ], "Human-in-the-loop durability (fresh checkpointer per resume)")

sw = R.get("sweep", {})
if sw:
    table("t11_sweep", ["Tick", "Agent invocations", "Duration", "Re-fired for no-class leave"],
          [[t["tick"], t["fired"], fmt_ms(t["ms"]), "yes" if t["fired_for_weekend_leave"] else "no"] for t in sw["ticks"]],
          f"Safety sweep: recovered {sw['recovered']}/{sw['missed_leaves']} missed leaves")

# =============================================================================
# Registry / assistant / facility / degradation
# =============================================================================
rows = []
if rg:
    rows.append(["Constraint registry validator", f"{rg['n']} ({rg['kinds_covered']}/{rg['catalog_size']} kinds)",
                 f"{rg['valid_accepted']}/{rg['valid_total']}", f"{rg['invalid_rejected']}/{rg['invalid_total']}",
                 f"{rg['correct']}/{rg['n']}", fmt_ms(rg["validate_ms"]["median"])])
if asst:
    rows.append(["Assistant op compiler", asst["n"], f"{asst['valid_accepted']}/{asst['valid_total']}",
                 f"{asst['invalid_rejected']}/{asst['invalid_total']}", f"{asst['correct']}/{asst['n']}",
                 fmt_ms(asst["plan_ms"]["median"])])
if sp:
    f_ = sp["facility"]
    rows.append(["Facility venue resolution", f_["n"], "–", "–", f"{f_['correct']}/{f_['n']}", fmt_ms(f_["ms"]["median"])])
dg = R.get("degrade", {})
if dg:
    rows.append(["Degradation (LLM outage)", dg["n"], "–", "–",
                 f"{dg['answered']}/{dg['n']} answered, {dg['exceptions']} exceptions", fmt_ms(dg["latency_ms"]["median"])])
if rows:
    table("t12_deterministic", ["Component", "Cases", "Valid accepted", "Invalid rejected", "Correct", "Median time"],
          rows, "Deterministic components: validation accuracy")

if asst:
    P = asst["payload"]
    fig, ax = plt.subplots(figsize=(4.0, 2.5))
    n = [p["entities_each"] for p in P]
    ax.plot(n, [p["longhand_chars"] / 4 for p in P], color=ORANGE, lw=2, marker="o", ms=5, label="longhand ops")
    ax.plot(n, [p["bulk_chars"] / 4 for p in P], color=BLUE, lw=2, marker="D", ms=5, label="bulk forms")
    ax.text(n[-1], P[-1]["longhand_chars"] / 4, f"  {P[-1]['reduction']:.1f}× ", va="center", fontsize=7.5, color=INK)
    ax.set_xlabel("subjects + teachers added (each)")
    ax.set_ylabel("≈ output tokens (chars / 4)")
    ax.set_title("Assistant plan size: bulk vs longhand")
    ax.legend(loc="upper left")
    save(fig, "fig9_assistant_payload")
    table("t13_payload", ["Entities each", "Ops after expansion", "Bulk chars", "Longhand chars", "Reduction"],
          [[p["entities_each"], p["ops_after_expand"], p["bulk_chars"], p["longhand_chars"], f"{p['reduction']}×"]
           for p in P], "Plan payload the LLM must generate (compact JSON)")
    if asst.get("llm", {}).get("n"):
        L_ = asst["llm"]
        table("t14_assistant_llm", ["Prompt", "Ops", "All valid", "Expected op kinds", "Latency"],
              [[r["prompt"][:60], r["ops"], "✓" if r["all_valid"] else "✗",
                "✓" if r["expected_ops_present"] else "✗",
                f"{r['latency_s']:.1f} s" if r["latency_s"] else (r["error"] or "")[:30]] for r in L_["rows"]],
              f"Assistant NL → plan with the LLM: {L_['end_to_end']}/{L_['n']} fully valid with expected ops")

# =============================================================================
# Master matrix (evidence-based)
# =============================================================================
M = []
def row(*c):  # noqa: E302
    M.append(list(c))

if rt:
    k = rt["keyword"]
    l_ = rt.get("llm", {})
    row("Supervisor-router", "LLM structured output + keyword fallback; system triggers bypass",
        "reactive + system", (f"LLM acc {l_['accuracy'] * 100:.0f}% / " if "accuracy" in l_ else "")
        + f"keyword acc {k['accuracy'] * 100:.0f}%",
        (fmt_ms(l_["latency_ms"]["median"]) + " LLM; " if l_.get("latency_ms") else "")
        + fmt_ms(rt["system_bypass"]["latency_ms"]["median"]) + " bypass", "–", "keyword router (100/100 answered)")
if sv:
    row("Timetable Agent (F1)", "OR-Tools CP-SAT, 12 hard groups + soft objective", "reactive (admin)",
        f"{viol_total} violations / {len(allv)} solutions",
        f"{np.median([r['wall_s'] for r in warm]):.1f} s warm; {np.median([r['wall_s'] for r in cold]):.1f} s cold",
        "admin triggers", f"precheck + assumption core ({inf.get('specific', '?')}/{inf.get('n', '?')} specific)")
if ex:
    row("Substitution Agent (F2)", "period-exchange heuristic + interrupt()", "proactive (leave approved)",
        f"{pct(ex['exchanged'], ex['affected'])} auto-covered, 0 violations",
        fmt_ms(ex["latency_ms"]["median"]), f"mandatory ({hi.get('resumed_ok', '?')}/{hi.get('n', '?')} resumed)",
        "manual rows for labs / no partner")
if asst:
    l_ = asst.get("llm", {})
    row("Timetable Assistant", "LLM → 23 typed ops → validate → preview → apply", "reactive (admin NL)",
        (f"{l_['end_to_end']}/{l_['n']} NL prompts fully valid; " if l_.get("n") else "")
        + f"compiler {asst['correct']}/{asst['n']}",
        (f"{l_['latency_s']['median']:.1f} s LLM" if l_.get("latency_s") else fmt_ms(asst["plan_ms"]["median"])),
        "preview before apply", "regex parser for simple requests")
if sp:
    row("Facility Agent (F3)", "room-registry entity matching", "reactive",
        f"{sp['facility']['correct']}/{sp['facility']['n']} venues", fmt_ms(sp["facility"]["ms"]["median"]),
        "none (provisional)", "lists all venues")
    row("Scheduler Agent", "registry audit (stub)", "reactive", "not evaluated (static report)",
        fmt_ms(sp["scheduler"]["ms"]["median"]), "none", "–")
    row("General Agent (F4)", "LLM persona, pre-RAG", "reactive", "not evaluated (no ground truth)",
        (fmt_ms(sp["general_llm"]["ms"]["median"]) + " LLM; " if sp.get("general_llm", {}).get("ms") else "")
        + fmt_ms(sp["general_canned"]["ms"]["median"]) + " offline", "none", "canned reply")
if hi:
    row("Notification dispatch", "rows written on plan approval", "proactive",
        f"{hi['notifications_per_approved_plan']['median']:.0f} per approved plan", "inside resume", "follows approval", "in-app inbox")
if sw:
    row("Safety-sweep sentinel", "APScheduler, every 2 min", "proactive (cron)",
        f"recovered {sw['recovered']}/{sw['missed_leaves']} missed leaves", fmt_ms(sw["ticks"][-1]["ms"]) + " / tick",
        "bounded by F2 approval",
        "re-fires every tick for a leave with no classes" if any(t["fired_for_weekend_leave"] for t in sw["ticks"][1:])
        else "idempotent re-trigger")
if M:
    table("t1_master_matrix", ["Agent", "Mechanism", "Trigger", "Measured quality", "Measured latency",
                               "Human gate", "Fallback / degradation"], M,
          "Agent evaluation matrix (all values measured, see per-experiment tables)")
print("done")
