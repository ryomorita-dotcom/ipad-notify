import json
import os
import importlib
from datetime import datetime
from playwright.sync_api import sync_playwright

def main():
    if not os.path.exists("config.json"):
        print("Error: config.json が見つかりません。")
        return

    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    # "sites" ラッパー構造に対応
    sites = config.get("sites", config)

    all_results = {}
    
    update_time = datetime.now().strftime("%Y-%m-%d %H:%M")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for site_name, site_config in sites.items():
            if not site_config.get("enabled", True):
                print(f"{site_name}: disabled. skipped.")
                continue

            print(f"{site_name}: scraping...", end=" ", flush=True)
            current_time = datetime.now().strftime("%H:%M:%S")
            try:
                scraper = importlib.import_module(f"scrapers.{site_name}")
                result = scraper.scrape(page, site_config)
                all_results[site_name] = result
                print(f"-> DONE ({current_time})")
            except Exception as e:
                print(f"-> FAILED ({e})")
                all_results[site_name] = {"エラー": {"取得失敗": f"× {str(e)}" }}

        browser.close()

    # HTMLセクションの構築
    sections_html = ""
    for site_name, categories in all_results.items():
        title_map = {
            "softbank": "SOFTBANK 在庫状況",
            "hitachi": "HITACHI 在庫状況"
        }
        site_title = title_map.get(site_name, site_name.upper() + " 在庫状況")
        
        url = sites.get(site_name, {}).get("url", "#")

        sections_html += f"""
        <div class="section-title">📊 {site_title}</div>
        <table>
            <thead>
                <tr>
                    <th style="width: 25%;">カテゴリ</th>
                    <th style="width: 55%;">モデル名</th>
                    <th style="width: 20%;">ステータス</th>
                </tr>
            </thead>
            <tbody>
        """
        
        for category, items in categories.items():
            first_row = True
            item_count = len(items)
            for model_name, status in items.items():
                badge_class = "in-stock" if "在庫あり" in status else "out-of-stock"
                
                sections_html += "<tr>"
                if first_row:
                    sections_html += f'<td rowspan="{item_count}" style="vertical-align: middle; font-weight: 500;">{category}</td>'
                    first_row = False
                
                sections_html += f"""
                    <td>{model_name}</td>
                    <td><span class="badge {badge_class}">{status}</span></td>
                </tr>
                """
        
        sections_html += f"""
            </tbody>
        </table>
        <div style="margin-top: 10px; margin-bottom: 25px;">
            <a href="{url}" target="_blank" class="btn-primary">{site_name.upper()}公式ページを開く ↗</a>
        </div>
        """

    # 簡易ステータス要約
    status_summary = "新規在庫: 無し"
    notification_msg = "通知: 無し (前回から新規の在庫復活なし)"

    # HTMLのレンダリング（標準の .replace() を使用）
    if os.path.exists("template.html"):
        with open("template.html", "r", encoding="utf-8") as f:
            template_content = f.read()
        
        rendered_html = template_content.replace("{{ update_time }}", update_time)
        rendered_html = rendered_html.replace("{{ sections_html }}", sections_html)
        rendered_html = rendered_html.replace("{{ status_summary }}", status_summary)
        rendered_html = rendered_html.replace("{{ notification_msg }}", notification_msg)

        with open("index.html", "w", encoding="utf-8") as f:
            f.write(rendered_html)
        print("index.html updated successfully.")

if __name__ == "__main__":
    main()