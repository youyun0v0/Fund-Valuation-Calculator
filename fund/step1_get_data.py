# 文件名: step1_get_data.py
import akshare as ak
import json
import time
import pandas as pd
import os

print("🚀 正在初始化数据引擎...")

# === 1. 读取配置文件 ===
CONFIG_FILE = "config.json"
if not os.path.exists(CONFIG_FILE):
    print(f"❌ 错误：找不到 {CONFIG_FILE}！请确保文件存在。")
    time.sleep(5)
    exit()

with open(CONFIG_FILE, "r", encoding="utf-8") as f:
    config = json.load(f)

MY_FUNDS = config.get("my_funds", [])
PROXY_MAP = config.get("proxy_map", {})
MANUAL_FALLBACK_DATA = config.get("manual_data", {})

print(f"📋 加载配置成功：关注 {len(MY_FUNDS)} 只基金")

# === 2. 准备基础数据 ===
try:
    print("🌍 正在下载全市场基金名录...")
    all_funds_df = ak.fund_name_em() 
    all_funds_df['基金代码'] = all_funds_df['基金代码'].astype(str)
    fund_name_map = dict(zip(all_funds_df['基金代码'], all_funds_df['基金简称']))
except:
    fund_name_map = {}

data = {}
total = len(MY_FUNDS)

def detect_market(code):
    code = str(code)
    if len(code) == 5 and code.isdigit(): return "hk", code 
    if not code.isdigit(): return "us", code.split('.')[0].lower() 
    if len(code) == 6:
        if code.startswith(('8','4','9')): return "bj", code 
        if code.startswith('6'): return "sh", code 
        return "sz", code 
    return "sz", code

# === 3. 开始循环处理 ===
for i, my_code in enumerate(MY_FUNDS):
    fund_name = fund_name_map.get(my_code, f"基金{my_code}")
    print(f"[{i+1}/{total}] 分析: {fund_name} ({my_code})")
    
    stocks = []
    source_info = "无数据"
    success = False
    
    # --- 阶段1: 爬虫/替身 ---
    target_code = PROXY_MAP.get(my_code, my_code) 
    if target_code != my_code:
        print(f"    ├── 🔄 映射替身: {target_code}")
        
    try:
        df = ak.fund_portfolio_hold_em(symbol=target_code)
        if df is not None and not df.empty:
            for _, row in df.iterrows():
                mkt, clean_code = detect_market(row['股票代码'])
                stocks.append({
                    "code": clean_code, "name": row['股票名称'],
                    "market": mkt, "weight": float(row['占净值比例'])
                })
            success = True
            source_info = f"网络爬虫 ({target_code})"
            print(f"    └── ✅ 爬虫成功! 获取 {len(stocks)} 持仓")
    except: pass

    # --- 阶段2: 手动兜底 ---
    if not success and my_code in MANUAL_FALLBACK_DATA:
        print(f"    ├── ⚠️ 启用手动数据兜底...")
        raw_list = MANUAL_FALLBACK_DATA[my_code]
        stocks = []
        for item in raw_list:
            raw_code, name, weight = item
            mkt, clean_code = detect_market(raw_code)
            stocks.append({
                "code": clean_code, "name": name, 
                "market": mkt, "weight": float(weight)
            })
        success = True
        source_info = "手动兜底"
        print(f"    └── ✅ 兜底成功! 加载 {len(stocks)} 条")

    if not success:
         print(f"    └── ❌ 获取失败")

    data[my_code] = {"name": fund_name, "source": source_info, "holdings": stocks}
    if source_info.startswith("网络"): time.sleep(0.3)

# === 4. 保存结果 ===
with open("holdings.json", "w", encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=4)

print("\n✅ 数据更新完毕！")