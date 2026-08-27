import json
import os
import importlib
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
PUSHOVER_USER = os.getenv("PUSHOVER_USER")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")

STATE_FILE = "state.json"
TEMPLATE_FILE = "template.html"
HTML_FILE = "index.html"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            data = json.loads(content) if content else {}
            
            # 旧state.json（フラット構造）からの移行対応
            migrated = {}
            for k, v in data.items():
                if isinstance(v, dict):
                    migrated[k] = v
                else:
                    if "softbank" not in migrated:
                        migrated["softbank"] = {}
                    migrated["softbank"][k] = v
            return migrated
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def generate_html(all_site_results, site_configs, newly_available, notification_msg):
    now_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M (JST)")
    
    sections_html = ""
    for site_key, categories in all_site_results.items():
        site_url = site_configs.get(site_key, {}).get("url", "#")
        site_name = site_key.upper()

        rows_html = ""
        for category, items in categories.items():
            for model, status in items.items():
                is_available = "〇" in status
                badge_class = "in-stock" if is_available else "out-of-stock"
                rows_html += f"""
                    <tr>
                        <td>{category}</td>
                        <td>{model}</td>
                        <td><span class="badge {badge_class}">{status}</span></td>
                    </tr>
                """

        sections_html += f"""
            <div class="section-title">📊 {site_name} 在庫状況</div>
            <table>
                <thead>
                    <tr>
                        <th>カテゴリ</th>
                        <th>モデル名</th>
                        <th>ステータス</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
            <div style="margin-top: 10px; margin-bottom: 25px;">
                <a class="btn-primary" href="{site_url}" target="_blank">{site_name}公式ページを開く ↗</a>
            </div>
        """

    status_summary = f"新規在庫: 有り ({', '.join(newly_available)})" if newly_available else "新規在庫: 無し"

    if os.path.exists(TEMPLATE_FILE):
        with open(TEMPLATE_FILE, "r", encoding="utf-8") as f:
            template_content = f.read()

        html_content = template_content.replace("{{ update_time }}", now_str) \
                                       .replace("{{ sections_html }}", sections_html) \
                                       .replace("{{ status_summary }}", status_summary) \
                                       .replace("{{ notification_msg }}", notification_msg)
    else:
        print(f"Warning: {TEMPLATE_FILE} が見つかりません。")
        return

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html_content)

def send_pushover_notification(message):
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        return

    url = "https://api.pushover.net/1/messages.json"
    data = urllib.parse.urlencode({
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "message": message,
        "title": "在庫更新通知",
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req)
    except Exception:
        pass

def check_all_stocks():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)

    site_configs = config.get("sites", {})
    state = load_state()

    all_site_results = {}
    newly_available = []
    reasons = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for site_key, site_info in site_configs.items():
            if not site_info.get("enabled", False):
                continue

            # 動的な進捗表示
            print(f"{site_key}: scraping...", end="", flush=True)

            try:
                scraper_module = importlib.import_module(f"scrapers.{site_key}")
                site_results = scraper_module.scrape(page, site_info)
                all_site_results[site_key] = site_results
                
                # 完了時のタイムスタンプ取得（HH:MM:SS）
                time_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M:%S")
                print(f" -> DONE ({time_str})")
            except ModuleNotFoundError:
                print(" -> FAILED (Module not found)")
                continue
            except Exception as e:
                print(f" -> FAILED ({e})")
                continue

            site_state = state.setdefault(site_key, {})
            for category, items in site_results.items():
                for model, status in items.items():
                    prev_status = site_state.get(model)
                    if status == "〇 在庫あり" and prev_status != "〇 在庫あり":
                        newly_available.append(f"[{site_key}] {model}")
                        if prev_status is None:
                            reasons.append(f"[{site_key}] {model}: 初回検出（在庫あり）")
                        else:
                            reasons.append(f"[{site_key}] {model}: 在庫なし({prev_status}) → 在庫あり に変化")
                    site_state[model] = status

        browser.close()

    save_state(state)

    status_msg = f"新規在庫: 有り ({', '.join(newly_available)})" if newly_available else "新規在庫: 無し"
    notification_msg = f"通知: 有り ({', '.join(reasons)})" if newly_available else "通知: 無し (前回から新規の在庫復活なし)"

    generate_html(all_site_results, site_configs, newly_available, notification_msg)

    print(f"\n[新規在庫有無]\n{status_msg}\n\n[通知]\n{notification_msg}")

    if newly_available:
        send_pushover_notification(f"{status_msg}\n\n{notification_msg}")

if __name__ == "__main__":
    check_all_stocks()