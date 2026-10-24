#!/usr/bin/env python3
"""make_charts.py RESULTS.json OUTDIR -- static README charts (light + dark SVG) from bench_tp2_night.py output.
No dependencies. Palette: dataviz reference categorical slots 1-6, validated in both modes (adjacent pairs);
light slots 3-5 sit under 3:1 contrast, so every multi-series chart carries direct end labels and the README
carries the same numbers as tables.
Charts: typesweep (aggregate tok/s, C1-C6, one line per prompt type), suite (single-stream decode),
sweep (mixed prompts, C1-C6), prefill (cold prefill tok/s by prompt size)."""
import html, json, os, sys

THEME = {
    "light": dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9", axis="#c3c2b7",
                  s=["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]),
    "dark": dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a", axis="#383835",
                 s=["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300"]),
}
FONT = 'font-family="system-ui,-apple-system,Segoe UI,sans-serif"'
TYPE_ORDER = ["code", "math", "json", "structured", "count100", "prose"]  # fixed slot per type, never by rank
TYPE_LABEL = {"count100": "count to 100", "count300": "count to 300", "tooluse": "tool call", "structured": "structured (YAML)"}


def esc(s): return html.escape(str(s))
def text(x, y, s, t, size=12, fill=None, anchor="start", weight="normal"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" {FONT} font-size="{size}" fill="{fill or t["ink2"]}" '
            f'text-anchor="{anchor}" font-weight="{weight}">{esc(s)}</text>')
def svg_open(w, h, t, title):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{esc(title)}">',
            f'<rect width="{w}" height="{h}" fill="{t["surface"]}"/>']
def nice_max(v):
    for step in (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 2500, 5000):
        n = -(-v // step)
        if n <= 6: return int(step * max(n, 3)), int(max(n, 3))
    return int(v), 4
def yticks(o, t, x0, x1, y0, h, ymax, n):
    for g in range(n + 1):
        gy = y0 + h - h * g / n
        o.append(f'<line x1="{x0}" x2="{x1}" y1="{gy:.1f}" y2="{gy:.1f}" stroke="{t["grid"] if g else t["axis"]}" stroke-width="1"/>')
        o.append(text(x0 - 8, gy + 4, f"{int(ymax * g / n):,}", t, 10, t["muted"], "end"))
def legend(x, y, t, items):
    out, cx = [], x
    for label, color in items:
        out.append(f'<rect x="{cx}" y="{y-9}" width="12" height="12" rx="3" fill="{color}"/>')
        out.append(text(cx + 17, y + 1, label, t, 12, t["ink2"])); cx += 17 + 7.0 * len(label) + 20
    return out
def end_labels(o, t, x, items, top_y, bot_y):
    """[(y, label, color)] -> right-of-endpoint labels >= 14 px apart, each led by a series-colored dot (text in ink)."""
    items = sorted(items, key=lambda it: it[0]); ys = []
    for it in items:
        ys.append(min(max(it[0] + 4, (ys[-1] + 14) if ys else top_y), bot_y))
    for (_, lab, color), ly in zip(items, ys):
        o.append(f'<circle cx="{x+3:.1f}" cy="{ly-4:.1f}" r="3.5" fill="{color}"/>')
        o.append(text(x + 10, ly, lab, t, 11, t["ink"], "start", "600"))
def polyline(o, t, pts, color):
    o.append(f'<polyline points="{" ".join(f"{x:.1f},{y:.1f}" for x, y in pts)}" fill="none" stroke="{color}" '
             f'stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>')
    for x, y in pts:
        o.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{color}" stroke="{t["surface"]}" stroke-width="2"/>')


def multi_lines(d, t):
    """d: title, sub, x labels, series [(label, values)] in slot order, note."""
    W, H, top, left, cw, ch = 900, 380, 92, 64, 690, 210
    o = svg_open(W, H, t, d["title"])
    o.append(text(24, 30, d["title"], t, 16, t["ink"], weight="600"))
    o += legend(24, 58, t, [(lab, t["s"][i]) for i, (lab, _) in enumerate(d["series"])])
    if d.get("sub"): o.append(text(24, 78, d["sub"], t, 11, t["muted"]))
    ymax, nt = nice_max(max(max(v) for _, v in d["series"]) * 1.08); y0 = top + 10
    yticks(o, t, left, left + cw, y0, ch, ymax, nt)
    xs = [left + cw * j / (len(d["x"]) - 1) for j in range(len(d["x"]))]
    for j, lv in enumerate(d["x"]): o.append(text(xs[j], y0 + ch + 18, lv, t, 11, t["muted"], "middle"))
    o.append(text(left + cw / 2, y0 + ch + 36, d.get("xlabel", "concurrent streams"), t, 10, t["muted"], "middle"))
    for i, (_, v) in enumerate(d["series"]):
        polyline(o, t, [(xs[j], y0 + ch - ch * val / ymax) for j, val in enumerate(v)], t["s"][i])
    end_labels(o, t, xs[-1] + 9, [(y0 + ch - ch * v[-1] / ymax, f"{lab} {v[-1]:.0f}", t["s"][i])
                                   for i, (lab, v) in enumerate(d["series"])], y0, y0 + ch)
    o.append(text(24, H - 8, d["note"], t, 10, t["muted"]))
    o.append("</svg>"); return "\n".join(o)


def hbars(d, t):
    cats, vals = d["cats"], d["vals"]; W, rowh, top, left, cw = 900, 26, 64, 150, 660
    H = top + rowh * len(cats) + 52
    o = svg_open(W, H, t, d["title"])
    o.append(text(24, 30, d["title"], t, 16, t["ink"], weight="600"))
    o.append(text(24, 50, d["sub"], t, 12, t["ink2"]))
    xmax, nt = nice_max(max(vals) * 1.1)
    for g in range(nt + 1):
        gx = left + cw * g / nt
        o.append(f'<line x1="{gx:.1f}" x2="{gx:.1f}" y1="{top}" y2="{top+rowh*len(cats)}" stroke="{t["grid"] if g else t["axis"]}" stroke-width="1"/>')
        o.append(text(gx, top + rowh * len(cats) + 16, int(xmax * g / nt), t, 10, t["muted"], "middle"))
    for i, (c, v) in enumerate(zip(cats, vals)):
        y = top + rowh * i + 5; bh = rowh - 10; w = cw * v / xmax
        o.append(text(left - 10, y + bh - 3, c, t, 12, t["ink2"], "end"))
        o.append(f'<path d="M{left},{y:.1f} H{left+w-4:.1f} Q{left+w:.1f},{y:.1f} {left+w:.1f},{y+4:.1f} V{y+bh-4:.1f} '
                 f'Q{left+w:.1f},{y+bh:.1f} {left+w-4:.1f},{y+bh:.1f} H{left} Z" fill="{t["s"][0]}"/>')
        o.append(text(left + w + 6, y + bh - 3, f"{v:.1f}", t, 11, t["ink"], "start", "600"))
    o.append(text(24, H - 8, d["note"], t, 10, t["muted"]))
    o.append("</svg>"); return "\n".join(o)


def vbars(d, t):
    cats, vals = d["cats"], d["vals"]; W, H, top, left, ch, cw = 900, 318, 70, 64, 170, 800
    o = svg_open(W, H, t, d["title"])
    o.append(text(24, 30, d["title"], t, 16, t["ink"], weight="600"))
    o.append(text(24, 50, d["sub"], t, 12, t["ink2"]))
    ymax, nt = nice_max(max(vals) * 1.15); y0 = top + 12
    yticks(o, t, left, left + cw, y0, ch, ymax, nt)
    slot = cw / len(cats); bw = min(64, slot / 2.4)
    for i, (c, v) in enumerate(zip(cats, vals)):
        cx = left + slot * (i + 0.5); x = cx - bw / 2; h = ch * v / ymax; y = y0 + ch - h
        o.append(f'<path d="M{x:.1f},{y0+ch:.1f} V{y+4:.1f} Q{x:.1f},{y:.1f} {x+4:.1f},{y:.1f} H{x+bw-4:.1f} '
                 f'Q{x+bw:.1f},{y:.1f} {x+bw:.1f},{y+4:.1f} V{y0+ch:.1f} Z" fill="{t["s"][0]}"/>')
        o.append(text(cx, y - 6, f"{v:,.0f}", t, 11, t["ink"], "middle", "600"))
        o.append(text(cx, y0 + ch + 18, c, t, 11, t["ink2"], "middle"))
        if d.get("under"): o.append(text(cx, y0 + ch + 34, d["under"][i], t, 10, t["muted"], "middle"))
    o.append(text(24, H - 8, d["note"], t, 10, t["muted"]))
    o.append("</svg>"); return "\n".join(o)


def med(x): return (x or {}).get("median") or 0


def build(r):
    lv = sorted({k for ty in r.get("typesweep", {}).values() for k in ty}, key=lambda k: int(k[1:]))
    note = f"MiniMax-M3.1-Flash EXL3 SAGE 2.15 bpw, TP2 on 2x DGX Spark, DSpark k=3, temperature 0, {r.get('started', '')[:10]}"
    charts = {}
    ts = r.get("typesweep", {})
    types = [ty for ty in TYPE_ORDER if ty in ts]
    if types:
        charts["typesweep"] = (multi_lines, dict(
            title="Aggregate decode by prompt type, C1 to C6 (tok/s)",
            sub="median of rounds; each stream runs the same prompt type", x=[k.upper() for k in lv],
            series=[(TYPE_LABEL.get(ty, ty), [med(ts[ty][k]["agg_tok_s"]) for k in lv]) for ty in types], note=note))
    single = {k: v for k, v in r.get("single", {}).items() if "decode_tok_s" in v}
    if single:
        rows = sorted(single.items(), key=lambda kv: -med(kv[1]["decode_tok_s"]))
        charts["suite"] = (hbars, dict(
            title="Single-stream decode by prompt (tok/s)", sub="median; DSpark acceptance drives the spread (prose ~2 tokens/step, code ~3)",
            cats=[TYPE_LABEL.get(k, k) for k, _ in rows], vals=[med(v["decode_tok_s"]) for _, v in rows], note=note))
    sw = r.get("sweep", {})
    if sw:
        ks = sorted(sw, key=lambda k: int(k[1:]))
        charts["sweep"] = (multi_lines, dict(
            title="Mixed real prompts, C1 to C6 (tok/s)", sub="8 prompt types rotated across streams; median of rounds",
            x=[k.upper() for k in ks], series=[("aggregate", [med(sw[k]["agg_tok_s"]) for k in ks]),
                                               ("per stream", [med(sw[k]["per_stream_decode"]) for k in ks])], note=note))
    pf = {k: v for k, v in r.get("prefill", {}).items() if "prefill_tok_s" in v}
    if pf:
        ks = sorted(pf, key=int)
        charts["prefill"] = (vbars, dict(
            title="Cold prefill (tok/s)", sub="salted prompt, 1 output token; TTFT under each bar",
            cats=[f"{pf[k]['prompt_tokens']:,} tok" for k in ks], vals=[pf[k]["prefill_tok_s"] for k in ks],
            under=[f"TTFT {pf[k]['ttft_s']:.1f} s" for k in ks], note=note))
    return charts


if __name__ == "__main__":
    res = json.load(open(sys.argv[1])); out = sys.argv[2]; os.makedirs(out, exist_ok=True)
    for name, (fn, d) in build(res).items():
        for mode in ("light", "dark"):
            open(os.path.join(out, f"{name}-{mode}.svg"), "w").write(fn(d, THEME[mode]))
            print("wrote", f"{name}-{mode}.svg")
