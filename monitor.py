import os, json, time, math, urllib.parse, urllib.request
WEBHOOK=os.environ.get("FEISHU_WEBHOOK","")
now=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

ranges = {
  "USDCNH=X": {"name":"离岸人民币", "low":7.05, "high":7.15, "pivot":None},
  "USDHKD=X": {"name":"港币", "low":7.77, "high":7.79, "pivot":None},
  "%5ETNX":   {"name":"美 10 年收益率 (%)", "low":3.9, "high":4.2, "pivot":None},
  "CN10Y":    {"name":"中国 10 年国债 (%)", "low":1.75, "high":1.90, "pivot":1.85},
  "XAUUSD=X": {"name":"国际黄金", "low":3900, "high":4200, "pivot":4050},
  "AU9999":   {"name":"国内黄金", "low":900, "high":950, "pivot":930},
  "BINANCE:BTCUSDT": {"name":"比特币 (USDT)", "low":85000, "high":95000, "pivot":90000},
  "000300.SS": {"name":"沪深 300", "low":4380, "high":4600, "pivot":4550},
  "000905.SS": {"name":"中证 500", "low":5360, "high":5700, "pivot":5450},
  "399006.SZ": {"name":"创业板指", "low":2950, "high":3200, "pivot":3050},
  "000688.SS": {"name":"科创 50", "low":1280, "high":1350, "pivot":1300},
  "000015.SS": {"name":"上证红利", "low":3000, "high":3150, "pivot":3050},
  "%5EHSI":   {"name":"恒生指数", "low":25200, "high":26400, "pivot":26000},
  "%5EHSTECH":{"name":"恒生科技", "low":5600, "high":6200, "pivot":5800},
  "%5EIXIC":  {"name":"纳指综合", "low":22500, "high":23500, "pivot":23000},
  "%5EGSPC":  {"name":"标普 500", "low":6500, "high":6850, "pivot":6800},
  "%5EN225":  {"name":"日经 225", "low":48000, "high":51000, "pivot":50000},
}

def yahoo_quote(symbols):
    url = "https://query1.finance.yahoo.com/v7/finance/quote?symbols=" + ",".join(symbols)
    with urllib.request.urlopen(url, timeout=12) as r:
        data = json.loads(r.read().decode())
    out = {}
    for itm in data.get("quoteResponse",{}).get("result",[]):
        sym = itm.get("symbol")
        price = itm.get("regularMarketPrice") or itm.get("postMarketPrice") or itm.get("preMarketPrice")
        out[sym] = price
    return out

def binance_ticker(symbol="BTCUSDT"):
    url = "https://api.binance.com/api/v3/ticker/price?symbol="+symbol
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = json.loads(r.read().decode())
            return float(data["price"])
    except Exception:
        return None

yahoo_syms = []
for k in ranges.keys():
    if k.startswith("BINANCE:"): continue
    if k in ("CN10Y","AU9999"): continue
    yahoo_syms.append(k)
yahoo_syms.append("3067.HK")  # HSTECH 备用 ETF

yahoo_prices = {}
try:
    yahoo_prices = yahoo_quote(yahoo_syms)
except Exception:
    yahoo_prices = {}

def get_price(symbol):
    if symbol=="%5ETNX":
        v = yahoo_prices.get("^TNX") or yahoo_prices.get("%5ETNX")
        if v is not None: return float(v)/100.0, "高", "Yahoo(^TNX÷100)"
        return None, "低", "Yahoo 不可用"
    if symbol=="%5EHSTECH":
        v = yahoo_prices.get("^HSTECH") or yahoo_prices.get("%5EHSTECH")
        if v is not None: return float(v), "中", "Yahoo(^HSTECH) 不稳定"
        v2 = yahoo_prices.get("3067.HK")
        if v2 is not None: return float(v2)*100.0, "中", "以 3067.HK*100 近似"
        return None, "低", "无可用替代"
    if symbol=="CN10Y":
        return None, "中", "建议 Wind/Tushare；当前以缺失标注"
    if symbol=="AU9999":
        return None, "中", "建议上金所/Tushare；当前以缺失标注"
    if symbol.startswith("BINANCE:"):
        v = binance_ticker(symbol.split(":")[1])
        if v is not None: return float(v), "高", "Binance"
        return None, "低", "Binance 不可用"
    raw = yahoo_prices.get(symbol) or yahoo_prices.get(urllib.parse.unquote(symbol))
    if raw is not None: return float(raw), "高", "Yahoo"
    return None, "低", "Yahoo 不可用"

def position_and_advice(px, low, high, pivot):
    if px is None or low is None or high is None:
        return "数据缺失", "提示：数据不足，建议复核"
    width = high - low
    if width<=0:
        return "区间异常", "提示：区间设定需检查"
    rel = (px - low)/width
    if rel >= 0.95: return "靠近上沿", "建议：逢高降仓"
    if rel >= 0.70: return "中枢偏上", "建议：减仓/控制仓位"
    if rel <= 0.05: return "靠近下沿", "建议：分批布局/抄底"
    if rel <= 0.30: return "中枢偏下", "建议：轻仓试探/观察"
    return "中枢区", "建议：持有/观察"

card_md = []
issues = []
for sym, meta in ranges.items():
    px, conf, src = get_price(sym)
    pos, sug = position_and_advice(px, meta["low"], meta["high"], meta.get("pivot"))
    px_str = "—" if px is None else (f"{px:.4f}" if px<1000 else f"{px:.0f}")
    line = f"- {meta['name']}：{meta['low']}–{meta['high']}（现：{px_str}｜{pos}） \n  {sug}"
    if conf!="高": line += f"  \n  置信：{conf}（来源：{src}）"
    card_md.append(line)
    if conf!="高": issues.append(f"{meta['name']}｜{px_str}｜{src}｜置信:{conf}")

card = {
  "msg_type": "interactive",
  "card": {
    "config": {"wide_screen_mode": True},
    "header": {"template": "blue", "title": {"tag":"plain_text","content": f"12 月资产监控｜实时报告 {now}"}},
    "elements": [
      {"tag":"div","text":{"tag":"lark_md","content":"** 结果摘要 **（对照 12 月区间，自动生成操作倾向）"}},
      {"tag":"hr"},
      {"tag":"div","text":{"tag":"lark_md","content":"\n".join(card_md[:12])}},
    ]
  }
}
if len(card_md) > 12:
    card["card"]["elements"].append({"tag":"div","text":{"tag":"lark_md","content":"…其余标的已记录（为控制卡片长度，此处省略）"}})
if issues:
    card["card"]["elements"] += [{"tag":"hr"},{"tag":"div","text":{"tag":"lark_md","content":"** 数据不置信标注 **（建议复核）：\n- "+"\n- ".join(issues)}}]

def post_webhook(payload):
    if not WEBHOOK: return False, "Webhook 未配置"
    req = urllib.request.Request(WEBHOOK, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(req, timeout=12) as r:
            return True, r.read().decode()
    except Exception as e:
        return False, str(e)

ok, resp = post_webhook(card)
print("FEISHU_POST_OK=", ok)
print("FEISHU_RESP=", resp)