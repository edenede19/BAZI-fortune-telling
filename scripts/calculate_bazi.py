#!/usr/bin/env python3
"""四柱八字全功能排盘脚本（bazi-quanshu）

在 keenone/bazi-skill 的 calculate_bazi.py（MIT License）基础上扩展：
  - 四柱、十神、藏干、纳音、十二长生（星运 + 自坐）、空亡、胎元、命宫、身宫
  - 真太阳时校正（经度或内置城市表）
  - 节气交接提示、月令人元司令
  - 五行力量（简单计数 + 藏干加权，月令加倍）
  - 日主旺衰参考指标（得令 / 得地 / 得势）
  - 天干五合与相冲；地支六合、三合、半合、拱合、三会、六冲、三刑、自刑、六害、相破
  - 神煞（贵人、禄刃、驿马桃花华盖、天月德、魁罡金神等三十余种）
  - 大运（起运精确到年月日）、流年列表及其与原局、大运的刑冲合会

用法:
  python3 calculate_bazi.py --solar 1993-6-18 --hour 10:00 --gender 男
  python3 calculate_bazi.py --solar 1993-6-18 --hour 10:30 --gender 女 --city 成都 --format md
  python3 calculate_bazi.py --lunar 1993-4-29 --hour 巳 --gender 男 --output /tmp/bazi.json
  python3 calculate_bazi.py --solar 1993-6-18 --hour unknown --gender 男   # 时辰不详，只排三柱

依赖: pip install lunar_python
"""
import argparse
import datetime
import json
import math
import re
import sys

try:
    import lunar_python
except ImportError:  # pragma: no cover
    sys.stderr.write("缺少依赖：请先运行  pip install lunar_python\n")
    sys.exit(1)

# ============================================================
# 基础常量
# ============================================================
GAN = "甲乙丙丁戊己庚辛壬癸"
ZHI = "子丑寅卯辰巳午未申酉戌亥"
GAN_WX = dict(zip(GAN, "木木火火土土金金水水"))
ZHI_WX = dict(zip(ZHI, "水土木木土火火土金金土水"))
GAN_YY = {g: ("阳" if i % 2 == 0 else "阴") for i, g in enumerate(GAN)}
ZHI_YY = {z: ("阳" if i % 2 == 0 else "阴") for i, z in enumerate(ZHI)}
SHENG = {"木": "火", "火": "土", "土": "金", "金": "水", "水": "木"}
KE = {"木": "土", "土": "水", "水": "火", "火": "金", "金": "木"}
WX_COLOR = {"木": "#4CAF50", "火": "#F44336", "土": "#A0522D", "金": "#C8A96E", "水": "#42A5F5"}

# 地支藏干（本气、中气、余气）
CANGGAN = {
    "子": ["癸"], "丑": ["己", "癸", "辛"], "寅": ["甲", "丙", "戊"], "卯": ["乙"],
    "辰": ["戊", "乙", "癸"], "巳": ["丙", "庚", "戊"], "午": ["丁", "己"],
    "未": ["己", "丁", "乙"], "申": ["庚", "壬", "戊"], "酉": ["辛"],
    "戌": ["戊", "辛", "丁"], "亥": ["壬", "甲"],
}
CANG_WEIGHT = {1: [1.0], 2: [0.7, 0.3], 3: [0.6, 0.3, 0.1]}

# 月令人元司令（节后天数），各家略有出入，此取通行表
SILING = {
    "寅": [("戊", 7), ("丙", 7), ("甲", 16)], "卯": [("甲", 10), ("乙", 20)],
    "辰": [("乙", 9), ("癸", 3), ("戊", 18)], "巳": [("戊", 5), ("庚", 9), ("丙", 16)],
    "午": [("丙", 10), ("己", 9), ("丁", 11)], "未": [("丁", 9), ("乙", 3), ("己", 18)],
    "申": [("戊", 7), ("壬", 7), ("庚", 16)], "酉": [("庚", 10), ("辛", 20)],
    "戌": [("辛", 9), ("丁", 3), ("戊", 18)], "亥": [("戊", 7), ("甲", 7), ("壬", 16)],
    "子": [("壬", 10), ("癸", 20)], "丑": [("癸", 9), ("辛", 3), ("己", 18)],
}

SHISHEN_NAMES = {
    ("同", True): "比肩", ("同", False): "劫财",
    ("生", True): "食神", ("生", False): "伤官",
    ("克", True): "偏财", ("克", False): "正财",
    ("被克", True): "七杀", ("被克", False): "正官",
    ("被生", True): "偏印", ("被生", False): "正印",
}

SHICHEN_NAMES = list(ZHI)
SHICHEN_RANGES = [
    "23:00-01:00", "01:00-03:00", "03:00-05:00", "05:00-07:00", "07:00-09:00", "09:00-11:00",
    "11:00-13:00", "13:00-15:00", "15:00-17:00", "17:00-19:00", "19:00-21:00", "21:00-23:00",
]

# 十二长生
CHANGSHENG_STATES = ["长生", "沐浴", "冠带", "临官", "帝旺", "衰", "病", "死", "墓", "绝", "胎", "养"]
CHANGSHENG_START = {"甲": "亥", "丙": "寅", "戊": "寅", "庚": "巳", "壬": "申",
                    "乙": "午", "丁": "酉", "己": "酉", "辛": "子", "癸": "卯"}

# 常用城市经度（真太阳时用）
CITY_LONGITUDE = {
    "北京": 116.40, "天津": 117.20, "上海": 121.47, "重庆": 106.55, "哈尔滨": 126.63, "长春": 125.32,
    "沈阳": 123.43, "大连": 121.61, "丹东": 124.38, "呼和浩特": 111.67, "石家庄": 114.48, "太原": 112.55,
    "济南": 117.00, "青岛": 120.38, "郑州": 113.65, "西安": 108.95, "兰州": 103.82, "银川": 106.27,
    "西宁": 101.78, "乌鲁木齐": 87.62, "拉萨": 91.11, "成都": 104.07, "贵阳": 106.71, "昆明": 102.73,
    "南宁": 108.33, "广州": 113.26, "深圳": 114.06, "珠海": 113.58, "汕头": 116.68, "海口": 110.35,
    "三亚": 109.51, "长沙": 112.94, "武汉": 114.31, "南昌": 115.89, "合肥": 117.27, "南京": 118.78,
    "苏州": 120.62, "无锡": 120.30, "杭州": 120.15, "宁波": 121.55, "温州": 120.70, "福州": 119.30,
    "厦门": 118.09, "泉州": 118.68, "台北": 121.56, "高雄": 120.30, "香港": 114.17, "澳门": 113.54,
    "徐州": 117.18, "洛阳": 112.45, "桂林": 110.29, "大理": 100.23, "延吉": 129.51, "吉林": 126.55,
    "齐齐哈尔": 123.97, "包头": 109.84, "唐山": 118.18, "保定": 115.46, "烟台": 121.45, "潍坊": 119.16,
    "临沂": 118.35, "绵阳": 104.74, "宜昌": 111.29, "襄阳": 112.14, "赣州": 114.93, "佛山": 113.12,
    "东莞": 113.75, "湛江": 110.36, "喀什": 75.99, "新加坡": 103.82, "吉隆坡": 101.69,
}

# ============================================================
# 关系表
# ============================================================
GAN_HE = {frozenset("甲己"): "土", frozenset("乙庚"): "金", frozenset("丙辛"): "水",
          frozenset("丁壬"): "木", frozenset("戊癸"): "火"}
GAN_CHONG = [frozenset("甲庚"), frozenset("乙辛"), frozenset("丙壬"), frozenset("丁癸")]
ZHI_LIUHE = {frozenset("子丑"): "土", frozenset("寅亥"): "木", frozenset("卯戌"): "火",
             frozenset("辰酉"): "金", frozenset("巳申"): "水", frozenset("午未"): "火土"}
SANHE = [("申子辰", "水"), ("亥卯未", "木"), ("寅午戌", "火"), ("巳酉丑", "金")]
SANHUI = [("寅卯辰", "木"), ("巳午未", "火"), ("申酉戌", "金"), ("亥子丑", "水")]
ZHI_CHONG = [frozenset(p) for p in ["子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"]]
ZHI_HAI = [frozenset(p) for p in ["子未", "丑午", "寅巳", "卯辰", "申亥", "酉戌"]]
ZHI_PO = [frozenset(p) for p in ["子酉", "卯午", "辰丑", "未戌", "寅亥", "巳申"]]
XING_PAIRS = {frozenset("寅巳"): "寅巳相刑（无恩之刑）", frozenset("巳申"): "巳申相刑（无恩之刑）",
              frozenset("寅申"): "寅申相刑（无恩之刑）", frozenset("丑戌"): "丑戌相刑（恃势之刑）",
              frozenset("戌未"): "戌未相刑（恃势之刑）", frozenset("丑未"): "丑未相刑（恃势之刑）",
              frozenset("子卯"): "子卯相刑（无礼之刑）"}
ZIXING = set("辰午酉亥")

# ============================================================
# 神煞表
# ============================================================
TIANYI = {"甲": "丑未", "戊": "丑未", "庚": "丑未", "乙": "子申", "己": "子申",
          "丙": "亥酉", "丁": "亥酉", "辛": "寅午", "壬": "卯巳", "癸": "卯巳"}
TAIJI = {"甲": "子午", "乙": "子午", "丙": "卯酉", "丁": "卯酉", "戊": "辰戌丑未",
         "己": "辰戌丑未", "庚": "寅亥", "辛": "寅亥", "壬": "巳申", "癸": "巳申"}
WENCHANG = dict(zip(GAN, "巳午申酉申酉亥子寅卯"))
LUSHEN = dict(zip(GAN, "寅卯巳午巳午申酉亥子"))
YANGREN = {"甲": "卯", "丙": "午", "戊": "午", "庚": "酉", "壬": "子"}
YINREN = {"乙": "辰", "丁": "未", "己": "未", "辛": "戌", "癸": "丑"}  # 部分流派称阴刃
JINYU = dict(zip(GAN, "辰巳未申未申戌亥丑寅"))
XUETANG = {g: CHANGSHENG_START[g] for g in GAN}  # 学堂：日干长生之地
HONGYAN = dict(zip(GAN, "午午寅未辰辰戌酉子申"))
GUOYIN = dict(zip(GAN, "戌亥丑寅丑寅辰巳未申"))
SANHE_SHA = {  # 以年支或日支三合局取：驿马、桃花(咸池)、华盖、将星、劫煞、亡神、灾煞
    "申子辰": dict(驿马="寅", 桃花="酉", 华盖="辰", 将星="子", 劫煞="巳", 亡神="亥", 灾煞="午"),
    "寅午戌": dict(驿马="申", 桃花="卯", 华盖="戌", 将星="午", 劫煞="亥", 亡神="巳", 灾煞="子"),
    "巳酉丑": dict(驿马="亥", 桃花="午", 华盖="丑", 将星="酉", 劫煞="寅", 亡神="申", 灾煞="卯"),
    "亥卯未": dict(驿马="巳", 桃花="子", 华盖="未", 将星="卯", 劫煞="申", 亡神="寅", 灾煞="酉"),
}
GUCHEN_GUASU = {"亥子丑": ("寅", "戌"), "寅卯辰": ("巳", "丑"), "巳午未": ("申", "辰"), "申酉戌": ("亥", "未")}
TIANDE = dict(zip("寅卯辰巳午未申酉戌亥子丑", ["丁", "申", "壬", "辛", "亥", "甲", "癸", "寅", "丙", "乙", "巳", "庚"]))
YUEDE = {"寅": "丙", "午": "丙", "戌": "丙", "申": "壬", "子": "壬", "辰": "壬",
         "亥": "甲", "卯": "甲", "未": "甲", "巳": "庚", "酉": "庚", "丑": "庚"}
KUIGANG = {"庚辰", "庚戌", "壬辰", "壬戌", "戊戌"}
JINSHEN = {"乙丑", "己巳", "癸酉"}
SHIE_DABAI = {"甲辰", "乙巳", "丙申", "丁亥", "戊戌", "己丑", "庚辰", "辛巳", "壬申", "癸亥"}
YINCHA_YANGCUO = {"丙子", "丁丑", "戊寅", "辛卯", "壬辰", "癸巳", "丙午", "丁未", "戊申", "辛酉", "壬戌", "癸亥"}
LIUXIU = {"丙午", "丁未", "戊子", "戊午", "己丑", "己未"}
RIDE = {"甲寅", "丙辰", "戊辰", "庚辰", "壬戌"}
RIGUI = {"丁酉", "丁亥", "癸巳", "癸卯"}
RIREN = {"丙午", "戊午", "壬子"}
TIANSHE = {"春": "戊寅", "夏": "甲午", "秋": "戊申", "冬": "甲子"}
SEASON_OF_MONTH = {"寅": "春", "卯": "春", "辰": "春", "巳": "夏", "午": "夏", "未": "夏",
                   "申": "秋", "酉": "秋", "戌": "秋", "亥": "冬", "子": "冬", "丑": "冬"}
PILLAR_CN = {"year": "年", "month": "月", "day": "日", "time": "时"}


# ============================================================
# 工具函数
# ============================================================
def wx_relation(day_wx, other_wx):
    if day_wx == other_wx:
        return "同"
    if SHENG[day_wx] == other_wx:
        return "生"
    if KE[day_wx] == other_wx:
        return "克"
    if KE[other_wx] == day_wx:
        return "被克"
    return "被生"


def get_shishen(day_gan, other_gan):
    """other_gan 对日干的十神（七杀即偏官）"""
    if other_gan not in GAN_WX:
        return "—"
    rel = wx_relation(GAN_WX[day_gan], GAN_WX[other_gan])
    return SHISHEN_NAMES[(rel, GAN_YY[day_gan] == GAN_YY[other_gan])]


def zhi_shishen(day_gan, zhi):
    """地支以本气论十神"""
    return get_shishen(day_gan, CANGGAN[zhi][0])


def changsheng(gan, zhi):
    start = ZHI.index(CHANGSHENG_START[gan])
    idx = ZHI.index(zhi)
    step = (idx - start) % 12 if GAN_YY[gan] == "阳" else (start - idx) % 12
    return CHANGSHENG_STATES[step]


def sanhe_group(zhi):
    for grp in SANHE_SHA:
        if zhi in grp:
            return grp
    return None


def equation_of_time(day_of_year):
    b = 2 * math.pi * (day_of_year - 81) / 364
    return 9.87 * math.sin(2 * b) - 7.53 * math.cos(b) - 1.5 * math.sin(b)


def parse_hour(hour_str):
    """返回 (hour, minute, 时辰索引, 是否精确时间)；时辰不详返回 None"""
    s = str(hour_str).strip()
    if s.lower() in ("unknown", "未知", "不详", "none", ""):
        return None
    m = re.match(r"^(\d{1,2})[:：](\d{2})$", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if not (0 <= h <= 23 and 0 <= mi <= 59):
            raise ValueError(f"无效时间: {s}")
        return h, mi, ((h + 1) // 2) % 12, True
    s2 = s.rstrip("时")
    if s2 in SHICHEN_NAMES:
        si = SHICHEN_NAMES.index(s2)
        h = 0 if si == 0 else si * 2  # 取时辰中点（子时取 00:00）
        return h, 0, si, False
    si = int(s)
    if 0 <= si <= 11:
        return (0 if si == 0 else si * 2), 0, si, False
    raise ValueError(f"无法解析时间参数: {s}")


# ============================================================
# 关系检测
# ============================================================
def detect_relations(stems, branches):
    """stems / branches: [(位置名, 字)]，返回关系列表"""
    res = []
    n = len(stems)
    for i in range(n):
        for j in range(i + 1, n):
            (pi, a), (pj, b) = stems[i], stems[j]
            key = frozenset((a, b))
            if key in GAN_HE and a != b:
                res.append(f"天干五合：{pi}{a}与{pj}{b}合（合化{GAN_HE[key]}，化否须看月令与透干）")
            if key in GAN_CHONG:
                res.append(f"天干相冲：{pi}{a}冲{pj}{b}")
    m = len(branches)
    for i in range(m):
        for j in range(i + 1, m):
            (pi, a), (pj, b) = branches[i], branches[j]
            key = frozenset((a, b))
            if a == b:
                if a in ZIXING:
                    res.append(f"地支自刑：{pi}{a}与{pj}{b}")
                continue
            if key in ZHI_LIUHE:
                res.append(f"地支六合：{pi}{a}合{pj}{b}（{ZHI_LIUHE[key]}）")
            if key in ZHI_CHONG:
                res.append(f"地支六冲：{pi}{a}冲{pj}{b}")
            if key in XING_PAIRS:
                res.append(f"地支相刑：{pi}{a}与{pj}{b}，{XING_PAIRS[key]}")
            if key in ZHI_HAI:
                res.append(f"地支六害：{pi}{a}害{pj}{b}")
            if key in ZHI_PO:
                res.append(f"地支相破：{pi}{a}破{pj}{b}")
    present = [z for _, z in branches]
    pos = {}
    for p, z in branches:
        pos.setdefault(z, []).append(p)
    for grp, wx in SANHE:
        have = [z for z in grp if z in present]
        if len(have) == 3:
            res.append(f"地支三合：{grp}三合{wx}局（{'、'.join(p + z for z in grp for p in pos[z])}）")
        elif len(have) == 2:
            mid = grp[1]
            kind = "半合" if mid in have else "拱合（缺中神，力弱）"
            res.append(f"地支{kind}：{''.join(have)}，{wx}局")
    for grp, wx in SANHUI:
        have = [z for z in grp if z in present]
        if len(have) == 3:
            res.append(f"地支三会：{grp}会{wx}方")
    for a, b, c in ["寅巳申", "丑戌未"]:
        if all(z in present for z in (a, b, c)):
            res.append(f"地支三刑全：{a}{b}{c}")
    return res


def cross_relations(label, gz, stems, branches):
    """流年/大运干支与原局各柱的关系"""
    g, z = gz[0], gz[1]
    res = []
    for p, s in stems:
        key = frozenset((g, s))
        if key in GAN_HE and g != s:
            res.append(f"{label}{g}合{p}{s}")
        if key in GAN_CHONG:
            res.append(f"{label}{g}冲{p}{s}")
    for p, b in branches:
        key = frozenset((z, b))
        if z == b:
            if z in ZIXING:
                res.append(f"{label}{z}与{p}{b}自刑")
            else:
                res.append(f"{label}{z}与{p}{b}伏吟")
            continue
        if key in ZHI_CHONG:
            res.append(f"{label}{z}冲{p}{b}")
        if key in ZHI_LIUHE:
            res.append(f"{label}{z}合{p}{b}")
        if key in XING_PAIRS:
            res.append(f"{label}{z}刑{p}{b}")
        if key in ZHI_HAI:
            res.append(f"{label}{z}害{p}{b}")
    present = [b for _, b in branches] + [z]
    for grp, wx in SANHE:
        if z in grp and all(x in present for x in grp):
            res.append(f"{label}{z}引动{grp}三合{wx}局")
    for grp, wx in SANHUI:
        if z in grp and all(x in present for x in grp):
            res.append(f"{label}{z}引动{grp}三会{wx}方")
    return res


# ============================================================
# 神煞
# ============================================================
def detect_shensha(pillars, has_time):
    keys = ["year", "month", "day"] + (["time"] if has_time else [])
    day_gan = pillars["day"]["stem"]
    year_gan = pillars["year"]["stem"]
    month_zhi = pillars["month"]["branch"]
    year_zhi = pillars["year"]["branch"]
    day_zhi = pillars["day"]["branch"]
    found = {k: [] for k in keys}

    def mark(name, target_zhis, basis):
        for k in keys:
            if pillars[k]["branch"] in target_zhis:
                found[k].append(f"{name}（{basis}）")

    mark("天乙贵人", TIANYI[day_gan], "日干")
    if TIANYI[year_gan] != TIANYI[day_gan]:
        mark("天乙贵人", TIANYI[year_gan], "年干")
    mark("太极贵人", TAIJI[day_gan], "日干")
    mark("文昌", WENCHANG[day_gan], "日干")
    mark("学堂", XUETANG[day_gan], "日干长生")
    mark("禄神", LUSHEN[day_gan], "日干")
    if day_gan in YANGREN:
        mark("羊刃", YANGREN[day_gan], "日干")
    else:
        mark("阴刃（部分流派用）", YINREN[day_gan], "日干")
    mark("金舆", JINYU[day_gan], "日干")
    mark("红艳", HONGYAN[day_gan], "日干")
    mark("国印", GUOYIN[day_gan], "日干")
    for basis_name, bz in (("年支", year_zhi), ("日支", day_zhi)):
        grp = sanhe_group(bz)
        for name, target in SANHE_SHA[grp].items():
            mark(name, target, basis_name)
    for grp, (gu, gua) in GUCHEN_GUASU.items():
        if year_zhi in grp:
            mark("孤辰", gu, "年支")
            mark("寡宿", gua, "年支")
    mark("天医", ZHI[(ZHI.index(month_zhi) - 1) % 12], "月支")
    td = TIANDE[month_zhi]
    yd = YUEDE[month_zhi]
    for k in keys:
        if pillars[k]["stem"] == td or pillars[k]["branch"] == td:
            found[k].append("天德贵人（月支）")
        if pillars[k]["stem"] == yd:
            found[k].append("月德贵人（月支）")
    for k in keys:
        if pillars[k]["branch"] in "戌亥":
            found[k].append("天罗（戌亥）")
        if pillars[k]["branch"] in "辰巳":
            found[k].append("地网（辰巳）")
    day_gz = pillars["day"]["stem"] + pillars["day"]["branch"]
    day_special = []
    if day_gz in KUIGANG:
        day_special.append("魁罡日")
    if day_gz in SHIE_DABAI:
        day_special.append("十恶大败日")
    if day_gz in YINCHA_YANGCUO:
        day_special.append("阴差阳错日")
    if day_gz in LIUXIU:
        day_special.append("六秀日")
    if day_gz in RIDE:
        day_special.append("日德")
    if day_gz in RIGUI:
        day_special.append("日贵")
    if day_gz in RIREN:
        day_special.append("日刃")
    if day_gz == TIANSHE[SEASON_OF_MONTH[month_zhi]]:
        day_special.append("天赦日")
    for k in ["day"] + (["time"] if has_time else []):
        gz = pillars[k]["stem"] + pillars[k]["branch"]
        if gz in JINSHEN:
            found[k].append("金神")
    found["day"].extend(day_special)
    return found


# ============================================================
# 主排盘
# ============================================================
def build_chart(solar_date=None, lunar_date=None, hour_str="unknown", gender_str="男",
                birthplace="", sect=2, longitude=None, city=None, now=None, years_ahead=3):
    now = now or datetime.datetime.now()
    hp = parse_hour(hour_str)
    has_time = hp is not None
    h, mi = (hp[0], hp[1]) if has_time else (12, 0)
    exact_time = has_time and hp[3]

    if solar_date:
        y, m, d = [int(x) for x in re.split(r"[-/.]", solar_date)]
        clock_dt = datetime.datetime(y, m, d, h, mi)
    elif lunar_date:
        parts = re.split(r"[-/.]", lunar_date)
        y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
        lun = lunar_python.Lunar.fromYmdHms(y, m, d, h, mi, 0)
        s = lun.getSolar()
        clock_dt = datetime.datetime(s.getYear(), s.getMonth(), s.getDay(), h, mi)
    else:
        raise ValueError("必须提供 --solar 或 --lunar")

    # 真太阳时
    tst_note = None
    used_dt = clock_dt
    if longitude is None and city:
        for name, lon in CITY_LONGITUDE.items():
            if name in city:
                longitude = lon
                break
    if longitude is not None and exact_time:
        doy = clock_dt.timetuple().tm_yday
        offset = (longitude - 120.0) * 4 + equation_of_time(doy)
        used_dt = clock_dt + datetime.timedelta(minutes=offset)
        tst_note = (f"经度 {longitude:.2f}°，经度差 {(longitude - 120) * 4:+.1f} 分钟，"
                    f"均时差 {equation_of_time(doy):+.1f} 分钟，真太阳时 {used_dt.strftime('%Y-%m-%d %H:%M')}")
    elif longitude is not None and not exact_time:
        tst_note = "只提供了时辰而非具体钟点，未做真太阳时校正"

    solar = lunar_python.Solar.fromYmdHms(used_dt.year, used_dt.month, used_dt.day,
                                          used_dt.hour, used_dt.minute, 0)
    lunar_obj = solar.getLunar()
    bazi = lunar_obj.getEightChar()
    bazi.setSect(sect)
    day_gan = bazi.getDayGan()
    shichen_idx = ((used_dt.hour + 1) // 2) % 12 if has_time else None

    getters = {
        "year": (bazi.getYearGan, bazi.getYearZhi, bazi.getYearNaYin, bazi.getYearXunKong),
        "month": (bazi.getMonthGan, bazi.getMonthZhi, bazi.getMonthNaYin, bazi.getMonthXunKong),
        "day": (bazi.getDayGan, bazi.getDayZhi, bazi.getDayNaYin, bazi.getDayXunKong),
        "time": (bazi.getTimeGan, bazi.getTimeZhi, bazi.getTimeNaYin, bazi.getTimeXunKong),
    }
    keys = ["year", "month", "day"] + (["time"] if has_time else [])
    pillars = {}
    for k in keys:
        gg, gz, gn, gk = getters[k]
        stem, branch = gg(), gz()
        pillars[k] = {
            "stem": stem, "branch": branch, "ganzhi": stem + branch,
            "shishen": "日主" if k == "day" else get_shishen(day_gan, stem),
            "zhi_shishen": zhi_shishen(day_gan, branch),
            "canggan": [f"{g}({get_shishen(day_gan, g)})" for g in CANGGAN[branch]],
            "nayin": gn(), "xunkong": gk(),
            "dishi": changsheng(day_gan, branch),       # 星运：日干临该支
            "zizuo": changsheng(stem, branch),           # 自坐：本柱天干临本支
            "stem_wx": GAN_WX[stem], "branch_wx": ZHI_WX[branch],
            "stem_color": WX_COLOR[GAN_WX[stem]], "branch_color": WX_COLOR[ZHI_WX[branch]],
        }
    if not has_time:
        pillars["time"] = {"stem": "?", "branch": "?", "ganzhi": "时辰不详", "shishen": "—",
                           "zhi_shishen": "—", "canggan": [], "nayin": "—", "xunkong": "—",
                           "dishi": "—", "zizuo": "—", "stem_color": "#888", "branch_color": "#888"}

    # 空亡（以日柱旬空为主）
    day_kong = pillars["day"]["xunkong"]
    kong_hits = [f"{PILLAR_CN[k]}支{pillars[k]['branch']}" for k in keys
                 if k != "day" and pillars[k]["branch"] in day_kong]

    # 五行力量
    wx_count = {w: 0 for w in "木火土金水"}
    wx_weight = {w: 0.0 for w in "木火土金水"}
    for k in keys:
        p = pillars[k]
        wx_count[GAN_WX[p["stem"]]] += 1
        wx_count[ZHI_WX[p["branch"]]] += 1
        wx_weight[GAN_WX[p["stem"]]] += 1.0
        hidden = CANGGAN[p["branch"]]
        mult = 1.5 if k == "month" else 1.0
        for g, w in zip(hidden, CANG_WEIGHT[len(hidden)]):
            wx_weight[GAN_WX[g]] += round(w * mult, 2)
    wx_weight = {k: round(v, 2) for k, v in wx_weight.items()}
    total = sum(wx_weight.values())
    wx_pct = {k: round(v / total * 100, 1) for k, v in wx_weight.items()}

    # 日主旺衰参考
    dwx = GAN_WX[day_gan]
    yin_wx = [w for w in "木火土金水" if SHENG[w] == dwx][0]
    month_main = CANGGAN[pillars["month"]["branch"]][0]
    deling = GAN_WX[month_main] in (dwx, yin_wx)
    roots = []
    for k in keys:
        for idx, g in enumerate(CANGGAN[pillars[k]["branch"]]):
            if GAN_WX[g] == dwx:
                roots.append(f"{PILLAR_CN[k]}支{pillars[k]['branch']}藏{g}（{['本气', '中气', '余气'][idx]}）")
    helper_stems = [f"{PILLAR_CN[k]}干{pillars[k]['stem']}({pillars[k]['shishen']})" for k in keys
                    if k != "day" and GAN_WX[pillars[k]["stem"]] in (dwx, yin_wx)]
    self_party = wx_weight[dwx] + wx_weight[yin_wx]
    strength = {
        "deling": deling,
        "deling_note": f"月令{pillars['month']['branch']}本气{month_main}{GAN_WX[month_main]}，"
                       f"{'生扶日主，得令' if deling else '不生扶日主，失令'}；日干临月令为「{pillars['month']['dishi']}」",
        "roots": roots,
        "helper_stems": helper_stems,
        "self_party_pct": round(self_party / total * 100, 1),
        "note": "同党（比劫+印）占加权五行比例，约 >50% 偏旺、<35% 偏弱，仅作参考；"
                "最终旺衰须结合格局、调候与《滴天髓》衰旺/从化之论综合判断。",
    }

    # 节气与司令
    prev_jie = lunar_obj.getPrevJie()
    next_jie = lunar_obj.getNextJie()
    pj_s, nj_s = prev_jie.getSolar(), next_jie.getSolar()
    pj_dt = datetime.datetime(pj_s.getYear(), pj_s.getMonth(), pj_s.getDay(), pj_s.getHour(), pj_s.getMinute())
    nj_dt = datetime.datetime(nj_s.getYear(), nj_s.getMonth(), nj_s.getDay(), nj_s.getHour(), nj_s.getMinute())
    days_after = (used_dt - pj_dt).total_seconds() / 86400
    acc = 0
    siling = None
    for g, ds in SILING[pillars["month"]["branch"]]:
        acc += ds
        if days_after < acc:
            siling = g
            break
    siling = siling or SILING[pillars["month"]["branch"]][-1][0]
    jieqi = {
        "prev_jie": f"{prev_jie.getName()} {pj_dt.strftime('%Y-%m-%d %H:%M')}",
        "next_jie": f"{next_jie.getName()} {nj_dt.strftime('%Y-%m-%d %H:%M')}",
        "days_after_jie": round(days_after, 2),
        "siling": f"{siling}（{GAN_WX[siling]}，{get_shishen(day_gan, siling)}）",
        "warning": None,
    }
    if days_after < 1 or (nj_dt - used_dt).total_seconds() < 86400:
        jieqi["warning"] = "出生时间距交节不足 1 天，月柱（及立春前后的年柱）可能不同，务必核实出生时间与真太阳时。"

    # 关系
    stems = [(PILLAR_CN[k] + "干", pillars[k]["stem"]) for k in keys]
    branches = [(PILLAR_CN[k] + "支", pillars[k]["branch"]) for k in keys]
    relations = detect_relations(stems, branches)

    shensha = detect_shensha(pillars, has_time)

    # 大运
    gender_int = 1 if gender_str == "男" else 0
    yun = bazi.getYun(gender_int)
    start = yun.getStartSolar()
    dayun = []
    cur_idx = None
    for i, dy in enumerate(yun.getDaYun()):
        gz = dy.getGanZhi()
        entry = {"seq": i, "range": f"{dy.getStartAge()}-{dy.getEndAge()}",
                 "start_year": dy.getStartYear(), "end_year": dy.getEndYear(), "ganzhi": gz}
        if gz:
            entry.update({
                "shishen": get_shishen(day_gan, gz[0]), "zhi_shishen": zhi_shishen(day_gan, gz[1]),
                "dishi": changsheng(day_gan, gz[1]), "nayin": lunar_python.util.LunarUtil.NAYIN.get(gz, ""),
                "relations": cross_relations("运", gz, stems, branches),
            })
        else:
            entry.update({"ganzhi": "（起运前，以月柱/小运论）", "shishen": ""})
        if dy.getStartYear() <= now.year <= dy.getEndYear():
            entry["current"] = True
            cur_idx = i
        dayun.append(entry)
    if cur_idx is not None and cur_idx + 1 < len(dayun):
        dayun[cur_idx + 1]["next"] = True

    # 流年：当前大运十年 + 未来 years_ahead 年
    liunian = []
    cur_dy = dayun[cur_idx] if cur_idx is not None else None
    y0 = cur_dy["start_year"] if cur_dy else now.year
    y1 = max(cur_dy["end_year"] if cur_dy else now.year, now.year + years_ahead)
    birth_year = solar.getYear()
    for yr in range(y0, y1 + 1):
        ln_lunar = lunar_python.Solar.fromYmd(yr, 6, 1).getLunar()
        gz = ln_lunar.getYearInGanZhiExact()
        dy_for_year = next((d for d in dayun if d["start_year"] <= yr <= d["end_year"]), None)
        rel = cross_relations("岁", gz, stems, branches)
        if dy_for_year and len(dy_for_year.get("ganzhi", "")) == 2:
            dgz = dy_for_year["ganzhi"]
            if frozenset((gz[1], dgz[1])) in ZHI_CHONG:
                rel.append(f"岁{gz[1]}冲运{dgz[1]}（岁运相冲）")
            if gz == dgz:
                rel.append("岁运并临")
        liunian.append({
            "year": yr, "age": yr - birth_year + 1, "ganzhi": gz,
            "shishen": get_shishen(day_gan, gz[0]), "zhi_shishen": zhi_shishen(day_gan, gz[1]),
            "dayun": dy_for_year["ganzhi"] if dy_for_year else "",
            "relations": rel, "current": yr == now.year,
        })

    result = {
        "name": "", "gender": gender_str,
        "input_clock_time": clock_dt.strftime("%Y-%m-%d %H:%M") if has_time else clock_dt.strftime("%Y-%m-%d") + "（时辰不详）",
        "true_solar_time": tst_note,
        "solar_date": f"{solar.getYear()}-{solar.getMonth():02d}-{solar.getDay():02d}",
        "lunar_date": f"{lunar_obj.getYearInChinese()}年{lunar_obj.getMonthInChinese()}月{lunar_obj.getDayInChinese()}",
        "hour": f"{SHICHEN_NAMES[shichen_idx]}时 ({SHICHEN_RANGES[shichen_idx]})" if has_time else "时辰不详",
        "hour_index": shichen_idx, "has_time": has_time, "birthplace": birthplace or (city or ""),
        "zishi_rule": "晚子时（23点后）日柱归次日" if sect == 2 else "子时整个归当日",
        "day_master": f"{day_gan}{GAN_WX[day_gan]}（{GAN_YY[day_gan]}）",
        "geju": "", "riqiang": "", "xiyong": "",
        "pillars": pillars,
        "wuxing": wx_count, "wuxing_weighted": wx_weight, "wuxing_pct": wx_pct,
        "strength_indicators": strength,
        "jieqi": jieqi,
        "nayin": {k: pillars[k]["nayin"] for k in ["year", "month", "day", "time"]},
        "kongwang": {k: pillars[k]["xunkong"] for k in ["year", "month", "day", "time"]},
        "kongwang_hits": kong_hits,
        "taiyuan": bazi.getTaiYuan(), "minggong": bazi.getMingGong() if has_time else "时辰不详",
        "shengong": bazi.getShenGong() if has_time else "时辰不详",
        "relations": relations, "shensha": {PILLAR_CN[k]: v for k, v in shensha.items()},
        "qiyun": {"forward": yun.isForward(),
                  "desc": f"出生后 {yun.getStartYear()} 年 {yun.getStartMonth()} 个月 {yun.getStartDay()} 天起运",
                  "start_date": start.toYmd()},
        "dayun": dayun, "liunian": liunian,
        "current_year": next((l["ganzhi"] for l in liunian if l["current"]), ""),
        "current_year_shishen": next((l["shishen"] for l in liunian if l["current"]), ""),
        "analysis_date": now.strftime("%Y-%m-%d"),
    }
    return result


# ============================================================
# Markdown 输出
# ============================================================
def to_markdown(r):
    P = r["pillars"]
    ks = ["year", "month", "day", "time"]
    L = []
    L.append(f"# 八字排盘 · {r['day_master']}")
    L.append(f"- 性别：{r['gender']}　出生（钟表）：{r['input_clock_time']}")
    if r["true_solar_time"]:
        L.append(f"- 真太阳时：{r['true_solar_time']}")
    L.append(f"- 公历：{r['solar_date']}　农历：{r['lunar_date']}　时辰：{r['hour']}")
    L.append(f"- 节气：上一节 {r['jieqi']['prev_jie']}，下一节 {r['jieqi']['next_jie']}；节后第 {r['jieqi']['days_after_jie']} 天，人元司令 {r['jieqi']['siling']}")
    if r["jieqi"]["warning"]:
        L.append(f"- ⚠️ {r['jieqi']['warning']}")
    L.append("")
    L.append("| | 年柱 | 月柱 | 日柱 | 时柱 |")
    L.append("|---|---|---|---|---|")
    row = lambda name, f: L.append(f"| {name} | " + " | ".join(f(P[k]) for k in ks) + " |")
    row("十神", lambda p: p["shishen"])
    row("天干", lambda p: p["stem"])
    row("地支", lambda p: p["branch"])
    row("藏干", lambda p: " ".join(p["canggan"]) or "—")
    row("星运", lambda p: p["dishi"])
    row("自坐", lambda p: p["zizuo"])
    row("纳音", lambda p: p["nayin"])
    row("旬空", lambda p: p["xunkong"])
    L.append("")
    L.append(f"胎元 {r['taiyuan']}　命宫 {r['minggong']}　身宫 {r['shengong']}　日空 {r['kongwang']['day']}"
             + (f"（落：{'、'.join(r['kongwang_hits'])}）" if r["kongwang_hits"] else ""))
    L.append("")
    L.append("## 五行力量")
    L.append("| | 木 | 火 | 土 | 金 | 水 |\n|---|---|---|---|---|---|")
    L.append("| 计数 | " + " | ".join(str(r["wuxing"][w]) for w in "木火土金水") + " |")
    L.append("| 加权 | " + " | ".join(str(r["wuxing_weighted"][w]) for w in "木火土金水") + " |")
    L.append("| 占比% | " + " | ".join(str(r["wuxing_pct"][w]) for w in "木火土金水") + " |")
    s = r["strength_indicators"]
    L.append(f"\n- 得令：{s['deling_note']}")
    L.append(f"- 得地（通根）：{'；'.join(s['roots']) or '无根'}")
    L.append(f"- 得势（干上比印）：{'、'.join(s['helper_stems']) or '无'}")
    L.append(f"- 同党占比：{s['self_party_pct']}%（{s['note']}）")
    L.append("\n## 刑冲合会")
    L.extend(f"- {x}" for x in (r["relations"] or ["无明显刑冲合会"]))
    L.append("\n## 神煞")
    for k, v in r["shensha"].items():
        if v:
            L.append(f"- {k}柱：{'、'.join(v)}")
    L.append(f"\n## 大运（{r['qiyun']['desc']}，{'顺排' if r['qiyun']['forward'] else '逆排'}）")
    L.append("| 年龄 | 年份 | 大运 | 干十神 | 支十神 | 星运 | 与原局 |\n|---|---|---|---|---|---|---|")
    for d in r["dayun"]:
        flag = " ◀当前" if d.get("current") else ""
        L.append(f"| {d['range']} | {d['start_year']}-{d['end_year']} | {d['ganzhi']}{flag} | {d.get('shishen', '')} | "
                 f"{d.get('zhi_shishen', '')} | {d.get('dishi', '')} | {'；'.join(d.get('relations', [])) or '—'} |")
    L.append("\n## 流年")
    L.append("| 年份 | 虚岁 | 流年 | 干十神 | 支十神 | 大运 | 作用 |\n|---|---|---|---|---|---|---|")
    for l in r["liunian"]:
        flag = " ◀今年" if l["current"] else ""
        L.append(f"| {l['year']} | {l['age']} | {l['ganzhi']}{flag} | {l['shishen']} | {l['zhi_shishen']} | "
                 f"{l['dayun']} | {'；'.join(l['relations']) or '—'} |")
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description="四柱八字全功能排盘")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--solar", help="公历日期 YYYY-M-D")
    g.add_argument("--lunar", help="农历日期 YYYY-M-D（闰月请先换算公历，或按节气确认）")
    ap.add_argument("--hour", default="unknown", help="HH:MM / 时辰名(巳) / 索引0-11 / unknown")
    ap.add_argument("--gender", required=True, choices=["男", "女"])
    ap.add_argument("--birthplace", default="")
    ap.add_argument("--city", help="出生城市（用于真太阳时，内置常用城市经度）")
    ap.add_argument("--longitude", type=float, help="出生地经度（东经为正），优先于 --city")
    ap.add_argument("--sect", type=int, default=2, choices=[1, 2], help="1=子时整个归当日，2=晚子归次日（默认）")
    ap.add_argument("--now", help="分析基准日期 YYYY-M-D（默认今天；已故者可设为去世年份）")
    ap.add_argument("--years-ahead", type=int, default=3, help="流年向后展望年数")
    ap.add_argument("--format", choices=["json", "md"], default="json")
    ap.add_argument("--output")
    a = ap.parse_args()
    now = None
    if a.now:
        yy, mm, dd = [int(x) for x in re.split(r"[-/.]", a.now)]
        now = datetime.datetime(yy, mm, dd)
    r = build_chart(a.solar, a.lunar, a.hour, a.gender, a.birthplace, a.sect,
                    a.longitude, a.city or a.birthplace, now, a.years_ahead)
    out = to_markdown(r) if a.format == "md" else json.dumps(r, ensure_ascii=False, indent=2)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"已写入 {a.output}", file=sys.stderr)
    else:
        print(out)


if __name__ == "__main__":
    main()
