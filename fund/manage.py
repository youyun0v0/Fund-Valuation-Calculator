# 文件名: manage.py
import os
import json
import sys

CONFIG_FILE = "config.json"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {"my_funds": [], "proxy_map": {}, "manual_data": {}}
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def add_fund_ui():
    print("\n" + "="*30)
    print("   ➕ 添加新基金向导")
    print("="*30)
    
    code = input("请输入基金代码 (例如 005827): ").strip()
    if not code: return
    
    cfg = load_config()
    if code in cfg["my_funds"]:
        print("⚠️ 该基金已存在，无需重复添加。")
    else:
        cfg["my_funds"].append(code)
        print(f"✅ 已添加代码: {code}")

    # 询问是否设置替身
    print("-" * 30)
    use_proxy = input("❓ 是否需要设置【替身/映射】？(y/n) [默认n]: ").strip().lower()
    if use_proxy == 'y':
        proxy_code = input(f"请输入 {code} 的替身代码 (例如A类代码): ").strip()
        if proxy_code:
            cfg["proxy_map"][code] = proxy_code
            print(f"✅ 已设置映射: {code} -> {proxy_code}")

    # 询问是否手动录入持仓
    print("-" * 30)
    use_manual = input("❓ 是否需要【手动录入持仓】？(y/n) [默认n]: ").strip().lower()
    if use_manual == 'y':
        print("📝 请依次输入持仓，格式: 代码 名称 权重")
        print("👉 输入 'q' 结束录入")
        holdings = []
        while True:
            line = input("   > ").strip()
            if line.lower() == 'q': break
            parts = line.split()
            if len(parts) >= 3:
                s_code, s_name, s_weight = parts[0], parts[1], parts[2]
                holdings.append([s_code, s_name, float(s_weight)])
                print(f"     已记录: {s_name}")
            else:
                print("     ❌ 格式错误，请重新输入 (例如: 600519 茅台 5.5)")
        
        if holdings:
            cfg["manual_data"][code] = holdings
            print(f"✅ 已保存 {len(holdings)} 条持仓数据")

    save_config(cfg)
    print("\n💾 配置已保存！建议稍后执行一次【更新持仓】。")
    input("\n按回车返回主菜单...")

def delete_fund_ui():
    print("\n" + "="*30)
    print("   🗑️ 删除基金向导")
    print("="*30)
    
    cfg = load_config()
    current_list = cfg.get("my_funds", [])
    
    if not current_list:
        print("⚠️ 当前列表为空，没有什么可删的。")
        input("\n按回车返回...")
        return

    # 打印当前列表，方便查看
    print("当前已关注:")
    count = 0
    for code in current_list:
        print(f"[{code}]", end="\t")
        count += 1
        if count % 5 == 0: print("") # 每5个换行
    print("\n" + "-"*30)
    
    del_code = input("👉 请输入要删除的基金代码: ").strip()
    
    if del_code in current_list:
        # 1. 从主列表删除
        cfg["my_funds"].remove(del_code)
        
        # 2. 清理关联数据 (替身和手动数据)
        extras = []
        if del_code in cfg.get("proxy_map", {}):
            del cfg["proxy_map"][del_code]
            extras.append("替身映射")
        
        if del_code in cfg.get("manual_data", {}):
            del cfg["manual_data"][del_code]
            extras.append("手动持仓")
            
        save_config(cfg)
        print(f"✅ 成功删除 {del_code}！")
        if extras:
            print(f"   (同时自动清理了关联的: {', '.join(extras)})")
            
        print("⚠️ 提示：删除后，该基金在下次运行【更新持仓】后才会从网页消失。")
    else:
        print("❌ 找不到该代码，取消操作。")
        
    input("\n按回车返回主菜单...")

def main_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print("\n" + "="*40)
        print("      💰 养基宝 - 控制中心")
        print("="*40)
        print("  [1] 🔄 一键更新持仓 (运行爬虫)")
        print("  [2] ➕ 导入新基金")
        print("  [3] 🚀 打开网页看盘")
        print("  [4] 🗑️ 删除基金")
        print("  [0] ❌ 退出")
        print("="*40)
        
        choice = input("👉 请输入选项: ").strip()
        
        if choice == '1':
            os.system("python step1_get_data.py")
            input("\n按回车键继续...")
        elif choice == '2':
            add_fund_ui()
        elif choice == '3':
            print("正在启动网页...")
            os.system("streamlit run step2_run_app.py")
        elif choice == '4':
            delete_fund_ui()
        elif choice == '0':
            sys.exit()
        else:
            print("输入无效")

if __name__ == "__main__":
    main_menu()