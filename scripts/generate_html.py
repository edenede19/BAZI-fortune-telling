#!/usr/bin/env python3
"""八字命盘 HTML 生成脚本

读取排盘数据 JSON + 解读文字 JSON，生成可视化命盘 HTML 文件。

用法:
    python3 generate_html.py --chart /tmp/bazi_chart.json --reading /tmp/bazi_reading.json --output /tmp/bazi.html
    python3 generate_html.py --chart /tmp/bazi_chart.json --output /tmp/bazi.html  # 无解读，仅排盘
"""
import argparse
import json
import sys

WUXING_COLORS = {
    "木": "#4CAF50", "火": "#F44336", "土": "#A0522D",
    "金": "#C8A96E", "水": "#42A5F5",
}

GAN_WUXING = {
    "甲": "木", "乙": "木", "丙": "火", "丁": "火", "戊": "土",
    "己": "土", "庚": "金", "辛": "金", "壬": "水", "癸": "水",
}

CN_NUMS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]


def stem_color(gan):
    return WUXING_COLORS.get(GAN_WUXING.get(gan, ""), "#C8A96E")


def wuxing_label(value, max_val):
    if value == 0:
        return "缺"
    if value == max_val:
        return "最旺"
    if value >= max_val * 0.7:
        return "旺"
    if value <= max_val * 0.3:
        return "弱"
    return ""


def build_header(chart):
    name = chart.get("name", "")
    gender = chart.get("gender", "男")
    lunar = chart.get("lunar_date", "")
    hour = chart.get("hour", "")
    title_text = f"八字命盘 · {name}" if name else "八字命盘"
    sub_parts = [p for p in [name, f"{gender}命", lunar, hour.split("(")[0].strip() if "(" in hour else hour] if p]
    sub_text = " · ".join(sub_parts)

    return f'''  <div class="header">
    <div class="header-eyebrow">四柱八字 · 命理分析</div>
    <div class="header-title">{title_text}</div>
    <div class="header-sub">{sub_text}</div>
  </div>'''


def build_info_bar(chart):
    dm = chart.get("day_master", "")
    geju = chart.get("geju", "") or "—"
    riqiang = chart.get("riqiang", "") or "—"
    xiyong = chart.get("xiyong", "") or "—"

    return f'''  <div class="info-bar">
    <div class="info-cell">
      <div class="info-cell-label">日 主</div>
      <div class="info-cell-value">{dm}</div>
    </div>
    <div class="info-cell">
      <div class="info-cell-label">格 局</div>
      <div class="info-cell-value">{geju}</div>
    </div>
    <div class="info-cell">
      <div class="info-cell-label">强 弱</div>
      <div class="info-cell-value">{riqiang}</div>
    </div>
    <div class="info-cell">
      <div class="info-cell-label">喜 用</div>
      <div class="info-cell-value">{xiyong}</div>
    </div>
  </div>'''


def build_pillars_table(chart):
    pillars = chart["pillars"]
    keys = ["year", "month", "day", "time"]
    labels = ["年 柱", "月 柱", "日 柱", "时 柱"]

    headers = ""
    for lbl in [""] + labels:
        headers += f'    <div class="pillars-header">{lbl}</div>\n'

    stems = ""
    branches = ""
    shishens = ""
    canggans = ""

    for k in keys:
        p = pillars[k]
        cls = ' day-master' if k == "day" else ""
        color = stem_color(p["stem"])

        stems += f'    <div class="pillars-cell{cls}"><div class="stem" style="color:{color}">{p["stem"]}</div></div>\n'
        branches += f'    <div class="pillars-cell{cls}"><div class="branch" style="color:{color}">{p["branch"]}</div></div>\n'
        shishens += f'    <div class="pillars-cell{cls}"><div class="shishen">{p["shishen"]}</div></div>\n'

        cg_lines = []
        for cg in p["canggan"]:
            if "(" in cg:
                g = cg[0]
                rest = cg[1:]
                cg_lines.append(f'<span style="color:{stem_color(g)}">{g}</span>{rest}')
            else:
                cg_lines.append(cg)
        canggans += f'    <div class="pillars-cell{cls}"><div class="canggan">{"<br>".join(cg_lines)}</div></div>\n'

    return f'''  <div class="section-title">四柱排盘</div>
  <div class="pillars-table">
{headers}
    <div class="pillars-row-label">天 干</div>
{stems}
    <div class="pillars-row-label">地 支</div>
{branches}
    <div class="pillars-row-label">十 神</div>
{shishens}
    <div class="pillars-row-label">藏 干</div>
{canggans}
  </div>'''


def build_detail_table(chart):
    pillars = chart["pillars"]
    keys = ["year", "month", "day", "time"]
    nayin = chart.get("nayin", {})
    kongwang = chart.get("kongwang", {})
    rows = ""

    rows += '    <div class="detail-row-label">纳 音</div>\n'
    for k in keys:
        val = nayin.get(k, pillars[k].get("nayin", ""))
        rows += f'    <div class="detail-cell"><span class="gold">{val}</span></div>\n'

    rows += '    <div class="detail-row-label">空 亡</div>\n'
    for k in keys:
        rows += f'    <div class="detail-cell">{kongwang.get(k, "")}</div>\n'

    rows += '    <div class="detail-row-label">地 势</div>\n'
    for k in keys:
        val = pillars[k].get("dishi", "")
        span = f'<span class="teal">{val}</span>' if val in ("长生", "帝旺", "冠带", "临官") else val
        rows += f'    <div class="detail-cell">{span}</div>\n'

    return f'''  <div class="detail-table">
{rows}
  </div>'''


def build_wuxing_chart(chart):
    wuxing = chart.get("wuxing", {})
    max_val = max(wuxing.values()) if wuxing else 1
    bars = ""

    for wx in ["木", "火", "土", "金", "水"]:
        val = wuxing.get(wx, 0)
        pct = max(val / max_val * 100, 4) if max_val > 0 else 4
        color = WUXING_COLORS[wx]
        label = wuxing_label(val, max_val)
        label_html = f'<div class="wuxing-element">{label}</div>' if label else ""
        bars += f'''    <div class="wuxing-bar-group">
      <div class="wuxing-bar" style="height:{pct}%;background:{color};">
        <div class="bar-value" style="color:{color}">{val}</div>
      </div>
      <div class="wuxing-label" style="color:{color}">{wx}</div>
      {label_html}
    </div>\n'''

    return f'''  <div class="section-title">五行力量分布</div>
  <div class="wuxing-chart">
{bars}
  </div>'''


def build_dayun_timeline(chart):
    dayun = chart.get("dayun", [])
    cells = ""

    for dy in dayun:
        ganzhi = dy.get("ganzhi", "")
        if not ganzhi:
            continue

        cls = ""
        if dy.get("current"):
            cls = " current"
        elif dy.get("next"):
            cls = " next"

        if len(ganzhi) == 2:
            g_html = f'<span style="color:{stem_color(ganzhi[0])}">{ganzhi[0]}</span>'
            z_html = f'<span style="color:{stem_color(ganzhi[0])}">{ganzhi[1]}</span>'
            ganzhi_html = g_html + z_html
        else:
            ganzhi_html = ganzhi

        badge = ""
        if dy.get("current"):
            badge = '\n      <div class="dayun-badge badge-current">当前大运</div>'
        elif dy.get("next"):
            badge = '\n      <div class="dayun-badge badge-next">下一步</div>'

        cells += f'''    <div class="dayun-cell{cls}">
      <div class="dayun-range">{dy["range"]}岁</div>
      <div class="dayun-ganzhi">{ganzhi_html}</div>
      <div class="dayun-shishen">{dy.get("shishen", "")}</div>{badge}
    </div>\n'''

    return f'''  <div class="section-title">大运排列</div>
  <div class="dayun-timeline">
{cells}
  </div>'''


def build_reading_cards(reading):
    cards = reading.get("cards", [])
    if not cards:
        return ""

    grid = ""
    for i, card in enumerate(cards):
        num = CN_NUMS[i] if i < len(CN_NUMS) else str(i + 1)
        classes = ["reading-card"]
        if card.get("full"):
            classes.append("full")
        if card.get("highlight"):
            classes.append("highlight")
        if card.get("teal"):
            classes.append("teal-highlight")

        prob_html = ""
        for pb in card.get("probabilities", []):
            prob_html += f'''<div class="prob-bar">
          <span class="prob-label">{pb["label"]}</span>
          <div class="prob-track"><div class="prob-fill" style="width:{pb["pct"]}%"></div></div>
          <span class="prob-pct">{pb["pct"]}%</span>
        </div>\n'''
        prob_wrap = f'<div style="margin-top:16px;">{prob_html}</div>' if prob_html else ""

        grid += f'''    <div class="{' '.join(classes)}" data-num="{num}">
      <div class="card-title">{card["title"]}</div>
      <div class="card-stars-badge">{card.get("badge", "")}</div>
      <div class="card-body">{card["body"]}</div>
      {prob_wrap}
    </div>\n'''

    return f'''  <div class="section-title">命盘解读</div>
  <div class="reading-grid">
{grid}
  </div>'''


def build_calibration(reading):
    questions = reading.get("calibration_questions", [])
    if not questions:
        return ""

    qs = ""
    for i, q in enumerate(questions[:5]):
        num = CN_NUMS[i] if i < len(CN_NUMS) else str(i + 1)
        hint = f'<span>{q["hint"]}</span>' if q.get("hint") else ""
        qs += f'''      <div class="cal-q">
        <div class="cal-num">{num}</div>
        <div class="cal-text">{q["text"]}{hint}</div>
      </div>\n'''

    return f'''  <div class="calibration">
    <div class="cal-title">校准问答</div>
    <div class="cal-desc">当前盘准确度约 68-75%。以下问题的反馈可以把它推到 85% 以上。</div>
    <div class="cal-questions">
{qs}
    </div>
  </div>'''


def build_footer():
    return '''  <div class="footer">
    <div class="footer-quote">命盘显示可能性<br>行动决定现实</div>
    <div class="footer-note">命理分析仅供参考 · 人生在于自身的努力和选择</div>
  </div>'''


def build_css():
    return ''':root {
    --gold: #C8A96E; --gold-light: #E8C97E; --gold-dim: #8B7245;
    --crimson: #9B2335; --crimson-bright: #C42B3F;
    --ink: #0A0A0F; --ink-mid: #12121A; --ink-light: #1C1C2A;
    --ivory: #F2EBD9; --ivory-dim: #B8AA90;
    --teal: #3B7A85; --teal-light: #5BA8B5;
  }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    background: var(--ink); color: var(--ivory);
    font-family: 'Noto Serif SC', 'Songti SC', 'STSong', serif;
    min-height: 100vh; overflow-x: hidden;
  }
  body::before {
    content: ''; position: fixed; inset: 0;
    background:
      radial-gradient(ellipse at 20% 20%, rgba(60,40,100,0.3) 0%, transparent 60%),
      radial-gradient(ellipse at 80% 80%, rgba(40,20,60,0.4) 0%, transparent 60%),
      radial-gradient(ellipse at 50% 0%, rgba(155,35,53,0.1) 0%, transparent 50%);
    pointer-events: none; z-index: 0;
  }
  body::after {
    content: ''; position: fixed; inset: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.04'/%3E%3C/svg%3E");
    opacity: 0.4; pointer-events: none; z-index: 0;
  }
  .container { position: relative; z-index: 1; max-width: 900px; margin: 0 auto; padding: 40px 24px 80px; }
  .header { text-align: center; padding: 60px 0 40px; animation: fadeDown 1s ease both; }
  .header-eyebrow { font-size: 11px; letter-spacing: 6px; color: var(--gold-dim); text-transform: uppercase; margin-bottom: 16px; }
  .header-title { font-size: clamp(36px, 6vw, 58px); color: var(--gold); line-height: 1.2; margin-bottom: 8px; text-shadow: 0 0 40px rgba(200,169,110,0.3); }
  .header-sub { font-size: 13px; color: var(--ivory-dim); letter-spacing: 3px; margin-top: 12px; }
  .info-bar { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px; background: rgba(200,169,110,0.15); border: 1px solid rgba(200,169,110,0.2); border-radius: 2px; margin-bottom: 48px; animation: fadeUp 1s 0.2s ease both; }
  .info-cell { background: var(--ink-mid); padding: 20px 16px; text-align: center; }
  .info-cell-label { font-size: 10px; letter-spacing: 3px; color: var(--gold-dim); margin-bottom: 8px; }
  .info-cell-value { font-size: 16px; color: var(--gold); font-weight: 600; }
  .section-title { font-size: 11px; letter-spacing: 5px; color: var(--gold-dim); text-transform: uppercase; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; }
  .section-title::after { content: ''; flex: 1; height: 1px; background: rgba(200,169,110,0.2); }
  .pillars-table { display: grid; grid-template-columns: 80px repeat(4, 1fr); gap: 1px; background: rgba(200,169,110,0.15); border: 1px solid rgba(200,169,110,0.2); margin-bottom: 16px; animation: fadeUp 1s 0.3s ease both; }
  .pillars-header { background: rgba(200,169,110,0.08); padding: 14px 12px; text-align: center; font-size: 11px; letter-spacing: 3px; color: var(--gold-dim); }
  .pillars-row-label { background: var(--ink-mid); padding: 14px 12px; text-align: center; font-size: 10px; letter-spacing: 2px; color: var(--ivory-dim); display: flex; align-items: center; justify-content: center; }
  .pillars-cell { background: var(--ink-mid); padding: 14px 12px; text-align: center; }
  .pillars-cell .stem, .pillars-cell .branch { font-size: 28px; font-weight: 700; color: var(--gold); line-height: 1.2; }
  .pillars-cell .shishen { font-size: 11px; color: var(--crimson-bright); margin-top: 4px; letter-spacing: 1px; }
  .pillars-cell .canggan { font-size: 10px; color: var(--ivory-dim); margin-top: 6px; line-height: 1.8; }
  .pillars-cell.day-master { background: rgba(155,35,53,0.1); border: 1px solid rgba(155,35,53,0.3); margin: -1px; z-index: 2; }
  .detail-table { display: grid; grid-template-columns: 80px repeat(4, 1fr); gap: 1px; background: rgba(200,169,110,0.1); border: 1px solid rgba(200,169,110,0.15); margin-bottom: 48px; animation: fadeUp 1s 0.35s ease both; }
  .detail-row-label { background: var(--ink-mid); padding: 10px 8px; text-align: center; font-size: 9px; letter-spacing: 2px; color: var(--ivory-dim); display: flex; align-items: center; justify-content: center; }
  .detail-cell { background: var(--ink-mid); padding: 10px 8px; text-align: center; font-size: 11px; color: var(--ivory-dim); line-height: 1.6; }
  .detail-cell .gold { color: var(--gold); }
  .detail-cell .crimson { color: var(--crimson-bright); }
  .detail-cell .teal { color: var(--teal-light); }
  .wuxing-chart { display: flex; align-items: flex-end; justify-content: center; gap: 24px; height: 200px; padding: 20px 40px; background: var(--ink-mid); border: 1px solid rgba(200,169,110,0.1); margin-bottom: 48px; animation: fadeUp 1s 0.4s ease both; }
  .wuxing-bar-group { display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1; }
  .wuxing-bar { width: 100%; max-width: 60px; border-radius: 2px 2px 0 0; transition: height 1s ease; position: relative; }
  .wuxing-bar .bar-value { position: absolute; top: -20px; left: 50%; transform: translateX(-50%); font-size: 14px; font-weight: 600; color: var(--gold); }
  .wuxing-label { font-size: 13px; color: var(--ivory); font-weight: 600; }
  .wuxing-element { font-size: 10px; color: var(--ivory-dim); letter-spacing: 1px; }
  .dayun-timeline { display: grid; grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); gap: 1px; background: rgba(200,169,110,0.1); border: 1px solid rgba(200,169,110,0.15); margin-bottom: 48px; animation: fadeUp 1s 0.5s ease both; }
  .dayun-cell { background: var(--ink-mid); padding: 16px 12px; text-align: center; position: relative; transition: background 0.3s; }
  .dayun-cell:hover { background: var(--ink-light); }
  .dayun-cell.current { background: rgba(59,122,133,0.12); border: 1px solid rgba(91,168,181,0.3); margin: -1px; z-index: 2; }
  .dayun-cell.next { background: rgba(200,169,110,0.05); border: 1px dashed rgba(200,169,110,0.2); margin: -1px; z-index: 2; }
  .dayun-range { font-size: 10px; color: var(--ivory-dim); letter-spacing: 1px; margin-bottom: 6px; }
  .dayun-ganzhi { font-size: 22px; font-weight: 700; color: var(--gold); line-height: 1.2; }
  .dayun-shishen { font-size: 10px; color: var(--crimson-bright); margin-top: 4px; letter-spacing: 1px; }
  .dayun-badge { display: inline-block; font-size: 9px; padding: 2px 6px; border-radius: 1px; margin-top: 6px; letter-spacing: 1px; }
  .badge-current { background: rgba(59,122,133,0.3); color: var(--teal-light); border: 1px solid rgba(59,122,133,0.5); }
  .badge-next { background: rgba(200,169,110,0.15); color: var(--gold-dim); border: 1px solid rgba(200,169,110,0.3); }
  .reading-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 48px; animation: fadeUp 1s 0.6s ease both; }
  .reading-card { background: var(--ink-mid); border: 1px solid rgba(200,169,110,0.1); padding: 24px; position: relative; overflow: hidden; }
  .reading-card::before { content: attr(data-num); position: absolute; right: 16px; top: 12px; font-size: 48px; color: var(--gold); opacity: 0.06; }
  .reading-card.full { grid-column: 1 / -1; }
  .reading-card.highlight { border-color: rgba(155,35,53,0.3); background: rgba(155,35,53,0.05); }
  .reading-card.teal-highlight { border-color: rgba(59,122,133,0.3); background: rgba(59,122,133,0.05); }
  .card-title { font-size: 11px; letter-spacing: 4px; color: var(--gold-dim); margin-bottom: 16px; text-transform: uppercase; }
  .card-stars-badge { font-size: 18px; color: var(--gold); font-weight: 600; margin-bottom: 12px; }
  .card-body { font-size: 13.5px; line-height: 2; color: var(--ivory-dim); }
  .card-body strong { color: var(--ivory); font-weight: 600; }
  .card-body em { color: var(--gold); font-style: normal; }
  .card-body .warn { color: #FF8C60; }
  .card-body .good { color: #7CCC60; }
  .prob-bar { display: flex; align-items: center; gap: 12px; margin-top: 12px; }
  .prob-label { font-size: 11px; color: var(--ivory-dim); width: 80px; flex-shrink: 0; }
  .prob-track { flex: 1; height: 3px; background: rgba(200,169,110,0.1); border-radius: 2px; }
  .prob-fill { height: 100%; background: linear-gradient(to right, var(--gold-dim), var(--gold)); border-radius: 2px; }
  .prob-pct { font-size: 12px; color: var(--gold); width: 36px; text-align: right; flex-shrink: 0; }
  .calibration { border: 1px solid rgba(200,169,110,0.25); padding: 32px; background: linear-gradient(135deg, rgba(200,169,110,0.03), rgba(59,122,133,0.05)); margin-bottom: 48px; animation: fadeUp 1s 0.7s ease both; }
  .cal-title { font-size: 22px; color: var(--gold); margin-bottom: 8px; }
  .cal-desc { font-size: 12px; color: var(--ivory-dim); margin-bottom: 24px; letter-spacing: 1px; }
  .cal-questions { display: flex; flex-direction: column; gap: 16px; }
  .cal-q { display: flex; gap: 16px; align-items: flex-start; }
  .cal-num { font-size: 18px; color: rgba(200,169,110,0.3); font-weight: 700; flex-shrink: 0; width: 28px; }
  .cal-text { font-size: 14px; color: var(--ivory); line-height: 1.8; padding-top: 2px; }
  .cal-text span { font-size: 11px; color: var(--ivory-dim); display: block; margin-top: 4px; }
  .footer { text-align: center; padding: 40px 0; animation: fadeUp 1s 0.8s ease both; }
  .footer-quote { font-size: 18px; color: rgba(200,169,110,0.4); letter-spacing: 4px; line-height: 2; }
  .footer-note { font-size: 11px; color: rgba(200,169,110,0.2); margin-top: 12px; letter-spacing: 2px; }
  @keyframes fadeDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
  @keyframes fadeUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
  @media (max-width: 620px) {
    .reading-grid { grid-template-columns: 1fr; }
    .info-bar { grid-template-columns: 1fr 1fr; }
    .pillars-table { grid-template-columns: 60px repeat(4, 1fr); }
    .pillars-cell .stem, .pillars-cell .branch { font-size: 22px; }
    .detail-table { grid-template-columns: 60px repeat(4, 1fr); }
    .dayun-timeline { grid-template-columns: repeat(auto-fill, minmax(80px, 1fr)); }
    .wuxing-chart { gap: 12px; padding: 20px 16px; }
  }'''


def generate_html(chart, reading=None):
    if reading is None:
        reading = {}

    name = chart.get("name", "")
    title = f"八字命盘 · {name}" if name else "八字命盘"

    sections = [
        build_header(chart),
        build_info_bar(chart),
        build_pillars_table(chart),
        build_detail_table(chart),
        build_wuxing_chart(chart),
        build_dayun_timeline(chart),
        build_reading_cards(reading),
        build_calibration(reading),
        build_footer(),
    ]

    body = "\n\n".join(s for s in sections if s)

    return f'''<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
{build_css()}
</style>
</head>
<body>
<div class="container">

{body}

</div>
</body>
</html>'''


def main():
    parser = argparse.ArgumentParser(description='八字命盘 HTML 生成')
    parser.add_argument('--chart', required=True, help='排盘数据 JSON 文件')
    parser.add_argument('--reading', help='解读数据 JSON 文件（可选）')
    parser.add_argument('--output', required=True, help='输出 HTML 文件路径')

    args = parser.parse_args()

    with open(args.chart, 'r', encoding='utf-8') as f:
        chart_data = json.load(f)

    reading_data = {}
    if args.reading:
        with open(args.reading, 'r', encoding='utf-8') as f:
            reading_data = json.load(f)

    html = generate_html(chart_data, reading_data)

    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'命盘已生成: {args.output}')


if __name__ == '__main__':
    main()
