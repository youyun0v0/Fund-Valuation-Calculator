# 文件名: step2_run_app.py
import streamlit as st
import json
import requests
import pandas as pd

# === 核心功能：多市场价格获取 ===
def get_multi_market_prices(stock_list):
    """
    输入: [{'market': 'sh', 'code': '600519'}, {'market': 'hk', 'code': '00700'}, ...]
    输出: {'sh600519': 1.23, 'hk00700': -0.5, ...} (返回涨跌幅)
    """
    if not stock_list: return {}
    
    # 1. 拆分不同市场的查询字符串
    query_map = {
        'a_share': [], # sh/sz/bj
        'hk_share': [],
        'us_share': []
    }
    
    # 构建查询ID
    id_map = {} # 记录 "sina_query_id" -> "our_id" 的映射
    
    for s in stock_list:
        m = s['market']
        c = s['code']
        full_id = f"{m}{c}"
        
        sina_query = ""
        if m in ['sh', 'sz']:
            sina_query = f"{m}{c}"
            query_map['a_share'].append(sina_query)
        elif m == 'bj':
            sina_query = f"bj{c}" # 北交所 bj83xxxx
            query_map['a_share'].append(sina_query)
        elif m == 'hk':
            sina_query = f"rt_hk{c}" # 港股 rt_hk00700
            query_map['hk_share'].append(sina_query)
        elif m == 'us':
            sina_query = f"gb_{c.lower()}" # 美股 gb_aapl
            query_map['us_share'].append(sina_query)
            
        if sina_query:
            id_map[sina_query] = full_id

    # 2. 统一请求函数
    prices_change = {} # 结果字典
    headers = {"Referer": "http://finance.sina.com.cn"}
    
    # --- 处理 A股 & 北交所 ---
    if query_map['a_share']:
        try:
            url = f"http://hq.sinajs.cn/list={','.join(query_map['a_share'])}"
            resp = requests.get(url, headers=headers, timeout=3)
            # 解析: var hq_str_sh600519="...open,prev,price..."
            for line in resp.text.split('\n'):
                if '="' in line:
                    q_id = line.split('="')[0].split('hq_str_')[-1]
                    data = line.split('="')[1].strip('";').split(',')
                    if len(data) > 3:
                        prev = float(data[2])
                        curr = float(data[3])
                        if curr == 0: curr = prev # 停牌或未开盘
                        pct = (curr - prev) / prev * 100 if prev > 0 else 0
                        
                        our_id = id_map.get(q_id)
                        if our_id: prices_change[our_id] = pct
        except: pass

    # --- 处理 港股 (格式完全不同) ---
    if query_map['hk_share']:
        try:
            url = f"http://hq.sinajs.cn/list={','.join(query_map['hk_share'])}"
            resp = requests.get(url, headers=headers, timeout=3)
            # 解析: var hq_str_rt_hk00700="engname,name,open,high,low,last_price,diff,pct,..."
            # 索引: 6 is last_price, 7 is diff, 8 is pct_change(%)
            for line in resp.text.split('\n'):
                if '="' in line:
                    q_id = line.split('="')[0].split('hq_str_')[-1]
                    data = line.split('="')[1].strip('";').split(',')
                    if len(data) > 8:
                        pct = float(data[8]) # 港股直接返回涨跌幅百分比
                        our_id = id_map.get(q_id)
                        if our_id: prices_change[our_id] = pct
        except: pass

    # --- 处理 美股 (白天通常不动) ---
    if query_map['us_share']:
        try:
            url = f"http://hq.sinajs.cn/list={','.join(query_map['us_share'])}"
            resp = requests.get(url, headers=headers, timeout=3)
            # 解析: var hq_str_gb_aapl="name,price,pct,..."
            # 索引: 1 is price, 2 is pct(%)
            for line in resp.text.split('\n'):
                if '="' in line:
                    q_id = line.split('="')[0].split('hq_str_')[-1]
                    data = line.split('="')[1].strip('";').split(',')
                    if len(data) > 2:
                        pct = float(data[2])
                        our_id = id_map.get(q_id)
                        if our_id: prices_change[our_id] = pct
        except: pass

    return prices_change

def main():
    st.set_page_config(page_title="全市场基金看板", layout="wide")
    st.title("🌏 个人全球基金估值   by youyun")
    st.caption("注：美股(QDII)白天休市，涨跌幅通常显示为0或盘前波动，请以晚间为准。")

    try:
        with open("holdings.json", "r", encoding='utf-8') as f:
            FUND_DATA = json.load(f)
    except:
        st.error("请先运行 step1_get_data.py")
        st.stop()

    if st.button("🔄 刷新全市场行情"):
        st.rerun()

    # 1. 收集所有股票
    all_stocks_query = []
    for _, info in FUND_DATA.items():
        for stock in info['holdings']:
            # 排除未知市场
            if stock['market'] in ['sh', 'sz', 'bj', 'hk', 'us']:
                all_stocks_query.append({'market': stock['market'], 'code': stock['code']})
    
    # 2. 获取价格
    prices = get_multi_market_prices(all_stocks_query)
    
    # 3. 计算展示
    results = []
    for f_code, info in FUND_DATA.items():
        val = 0.0
        total_w = 0.0
        details = []
        
        has_hk = False
        has_us = False
        
        for stock in info['holdings']:
            mid = f"{stock['market']}{stock['code']}"
            w = stock['weight']
            p = prices.get(mid, 0.0)
            
            val += p * (w / 100)
            total_w += w
            
            # 标记市场类型
            if stock['market'] == 'hk': has_hk = True
            if stock['market'] == 'us': has_us = True
            
            # 详情
            mk_tag = ""
            if stock['market'] == 'hk': mk_tag = "(港)"
            elif stock['market'] == 'us': mk_tag = "(美)"
            elif stock['market'] == 'bj': mk_tag = "(北)"
            
            details.append(f"{mk_tag}{stock['name']}{p:+.2f}%")

        # 估值修正
        if total_w > 0:
            # 港股和美股基金仓位通常很高(90%+)，A股通常80-90%
            ratio = 0.95 if (has_hk or has_us) else 0.85 
            final_val = (val / total_w) * 100 * ratio
        else:
            final_val = 0
            
        # 针对美股的特殊提示
        msg = ", ".join(details[:10])
        if has_us:
            msg = "💤(美股休市中) " + msg
        
        results.append({
            "名称": info.get('name', f_code),
            "代码": f_code,
            "类型": "QDII/港" if (has_hk or has_us) else "A股",
            "估算涨跌": final_val,
            "重仓透视": msg
        })

    # 4. 渲染
    if results:
        df = pd.DataFrame(results)
        df = df[['名称', '类型', '估算涨跌', '代码', '重仓透视']] # 调整顺序
        
        def highlight(val):
            if val > 0: return 'color: red; font-weight: bold'
            if val < 0: return 'color: green; font-weight: bold'
            return 'color: gray'

        st.dataframe(
            df.style.map(highlight, subset=['估算涨跌'])
              .format({'估算涨跌': "{:+.2f}%"}), 
            height=1000, 
            use_container_width=True
        )

if __name__ == "__main__":
    main()