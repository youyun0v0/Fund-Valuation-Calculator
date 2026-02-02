# 文件名: step2_run_app.py
import streamlit as st
import json
import requests
import pandas as pd
import datetime
import math

# === 辅助功能：列表分块（防止URL过长） ===
def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

# === 核心：多市场价格获取 (修复版) ===
def get_multi_market_prices(stock_list):
    if not stock_list: return {}
    
    # 拆分查询类型
    query_batches = {'a': [], 'hk': [], 'us': []}
    id_map = {} 
    
    for s in stock_list:
        m = s['market']
        c = s['code']
        full_id = f"{m}{c}"
        sina_query = ""
        
        # 构造新浪查询代码
        if m in ['sh', 'sz', 'bj']:
            prefix = "bj" if m == 'bj' else m
            sina_query = f"{prefix}{c}"
            query_batches['a'].append(sina_query)
        elif m == 'hk':
            sina_query = f"rt_hk{c}"
            query_batches['hk'].append(sina_query)
        elif m == 'us':
            sina_query = f"gb_{c.lower()}"
            query_batches['us'].append(sina_query)
            
        if sina_query: 
            id_map[sina_query] = full_id

    prices_change = {}
    
    # 增加 User-Agent 伪装成浏览器，防止被拦截
    headers = {
        "Referer": "http://finance.sina.com.cn",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # === 核心修复：分批请求 (Batching) ===
    # 新浪接口限制URL长度，每次请求不能超过约80个代码
    
    # 1. 处理 A股/北交所
    for batch in chunk_list(query_batches['a'], 80):
        try:
            url = f"http://hq.sinajs.cn/list={','.join(batch)}"
            resp = requests.get(url, headers=headers, timeout=3)
            # 解析响应
            content = resp.text
            for line in content.split('\n'):
                if '="' in line:
                    try:
                        q_id = line.split('="')[0].split('hq_str_')[-1]
                        data = line.split('="')[1].strip('";').split(',')
                        # A股数据格式: Index 2=昨收, Index 3=当前
                        if len(data) > 3:
                            prev = float(data[2])
                            curr = float(data[3])
                            if curr == 0 and prev > 0: curr = prev # 停牌或集合竞价
                            
                            if prev > 0:
                                pct = (curr - prev) / prev * 100 
                                if id_map.get(q_id): prices_change[id_map[q_id]] = pct
                    except: continue
        except Exception as e:
            print(f"A股请求失败: {e}")

    # 2. 处理 港股
    for batch in chunk_list(query_batches['hk'], 80):
        try:
            url = f"http://hq.sinajs.cn/list={','.join(batch)}"
            resp = requests.get(url, headers=headers, timeout=3)
            for line in resp.text.split('\n'):
                if '="' in line:
                    try:
                        q_id = line.split('="')[0].split('hq_str_')[-1]
                        data = line.split('="')[1].strip('";').split(',')
                        # 港股 rt_hk 格式: Index 8 是涨跌幅%
                        if len(data) > 8:
                            pct = float(data[8])
                            if id_map.get(q_id): prices_change[id_map[q_id]] = pct
                    except: continue
        except: pass

    # 3. 处理 美股
    for batch in chunk_list(query_batches['us'], 80):
        try:
            url = f"http://hq.sinajs.cn/list={','.join(batch)}"
            resp = requests.get(url, headers=headers, timeout=3)
            for line in resp.text.split('\n'):
                if '="' in line:
                    try:
                        q_id = line.split('="')[0].split('hq_str_')[-1]
                        data = line.split('="')[1].strip('";').split(',')
                        # 美股 gb_ 格式: Index 2 是涨跌幅%
                        if len(data) > 2:
                            pct = float(data[2])
                            if id_map.get(q_id): prices_change[id_map[q_id]] = pct
                    except: continue
        except: pass

    return prices_change

def main():
    st.set_page_config(page_title="养基宝 Pro", layout="wide", page_icon="📈")
    
    # === 侧边栏 ===
    with st.sidebar:
        st.header("🎮 控制台")
        if st.button("🔄 立即刷新行情"):
            st.rerun()
        
        st.info(f"更新时间: {datetime.datetime.now().strftime('%H:%M:%S')}")
        st.markdown("---")
        st.caption("说明：美股基金(QDII)白天显示0%或盘前波动属于正常现象，因为美股现在休市。")

    st.title("🚀 基金估值 by youyun")

    # 读取数据
    try:
        with open("holdings.json", "r", encoding='utf-8') as f:
            FUND_DATA = json.load(f)
    except:
        st.error("找不到 holdings.json，请先运行 step1_get_data.py")
        st.stop()

    # 1. 准备查询列表
    all_stocks_query = []
    for _, info in FUND_DATA.items():
        for stock in info['holdings']:
            all_stocks_query.append({'market': stock['market'], 'code': stock['code']})
    
    # 2. 获取实时股价 (已修复分批请求)
    prices = get_multi_market_prices(all_stocks_query)
    
    # 3. 计算基金估值
    results = []
    total_change_sum = 0
    valid_funds_count = 0
    
    for f_code, info in FUND_DATA.items():
        val = 0.0
        total_w = 0.0
        details = []
        market_tags = set()
        
        # 遍历持仓
        for stock in info['holdings']:
            mid = f"{stock['market']}{stock['code']}"
            w = stock['weight']
            # 如果没获取到价格，默认为 0
            p = prices.get(mid, 0.0)
            
            # 只有当 w 是有效数字时才计算
            if w and not math.isnan(w):
                val += p * (w / 100)
                total_w += w
            
            # 记录市场
            if stock['market'] == 'hk': market_tags.add('港')
            if stock['market'] == 'us': market_tags.add('美')
            if stock['market'] == 'bj': market_tags.add('北')
            
            # 详情文本
            details.append(f"{stock['name']} {p:+.2f}%")

        # 估值修正逻辑
        # 港美股基金仓位通常较高(95%)，A股通常(88-90%)
        # 如果 total_w 太小(说明数据有问题)，则不放大
        if total_w > 50: 
            ratio = 0.95 if ('港' in market_tags or '美' in market_tags) else 0.88
            final_val = (val / total_w) * 100 * ratio
        else:
            final_val = val # 权重不足时，直接用加权和，不再放大，防止误差过大
            
        total_change_sum += final_val
        valid_funds_count += 1
        
        # 标签生成
        tag_str = "A股"
        if '美' in market_tags: tag_str = "QDII/美"
        elif '港' in market_tags: tag_str = "港股通"
        
        src = info.get('source', '')
        if '手动' in src: tag_str += " | 手动⚡"
        elif '替身' in src or '映射' in src: tag_str += " | 替身🎭"

        results.append({
            "基金名称": info.get('name', f_code),
            "代码": f_code,
            "估算涨跌": final_val,
            "标签": tag_str,
            "持仓透视": " ".join(details[:6]) + "..." 
        })

    if not results:
        st.warning("没有数据。")
        st.stop()

    df = pd.DataFrame(results)

    # === 顶部看板 ===
    avg_change = total_change_sum / valid_funds_count if valid_funds_count > 0 else 0
    best_fund = df.loc[df['估算涨跌'].idxmax()]
    worst_fund = df.loc[df['估算涨跌'].idxmin()]
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📊 监控数量", f"{len(df)} 只")
    col2.metric("⚖️ 平均涨幅", f"{avg_change:+.2f}%", delta_color="normal")
    col3.metric("🔥 领涨", f"{best_fund['基金名称'][:5]}..", f"{best_fund['估算涨跌']:+.2f}%")
    col4.metric("❄️ 领跌", f"{worst_fund['基金名称'][:5]}..", f"{worst_fund['估算涨跌']:+.2f}%")
    
    st.markdown("---")

    # === 列表展示 ===
    tab1, tab2, tab3, tab4 = st.tabs(["📋 全部列表", "📈 赚钱区", "📉 亏钱区", "✈️ 海外/QDII"])
    
    def style_df(dataframe):
        return dataframe.style.map(
            lambda x: f'color: {"#FF4B4B" if x > 0 else "#00CC96" if x < 0 else "gray"}; font-weight: bold', 
            subset=['估算涨跌']
        ).format({'估算涨跌': "{:+.2f}%"})

    with tab1:
        df_sorted = df.sort_values(by='估算涨跌', ascending=False)
        st.dataframe(style_df(df_sorted), width="stretch", height=800, hide_index=True)
        
    with tab2:
        df_red = df[df['估算涨跌'] > 0].sort_values(by='估算涨跌', ascending=False)
        if not df_red.empty:
            st.dataframe(style_df(df_red), width="stretch", hide_index=True)
        else:
            st.info("暂无正收益基金")

    with tab3:
        df_green = df[df['估算涨跌'] < 0].sort_values(by='估算涨跌', ascending=True)
        if not df_green.empty:
            st.dataframe(style_df(df_green), width="stretch", hide_index=True)
        else:
            st.success("全红！没有亏损基金！")

    with tab4:
        df_qdii = df[df['标签'].str.contains('港|美|QDII')]
        if not df_qdii.empty:
            st.dataframe(style_df(df_qdii), width="stretch", hide_index=True)
        else:
            st.info("无海外基金")

if __name__ == "__main__":
    main()
