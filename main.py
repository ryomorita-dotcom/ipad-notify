import json
import os
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
HTML_FILE = "index.html"

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def generate_html(stock_results, newly_available, notification_msg):
    # JST（Asia/Tokyo）の現在時刻を明示的に取得
    now_str = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y-%m-%d %H:%M (JST)")
    
    rows_html = ""
    for model, status in stock_results.items():
        is_available = "〇" in status
        badge_class = "in-stock" if is_available else "out-of-stock"
        rows_html += f"""
            <tr>
                <td>{model}</td>
                <td><span class="badge {badge_class}">{status}</span></td>
            </tr>
        """

    status_summary = f"新規在庫: 有り ({', '.join(newly_available)})" if newly_available else "新規在庫: 無し"

    html_content = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>iPad 在庫チェッカー</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 680px;
            margin: 40px auto;
            padding: 0 20px;
            color: #2c3e50;
            background: #f8f9fa;
        }}
        h1 {{
            font-size: 1.4rem;
            margin: 0 0 5px 0;
            color: #1a1a1a;
        }}
        .update-time {{
            font-size: 0.85rem;
            color: #666;
            margin-bottom: 20px;
        }}
        .section-title {{
            font-size: 1.05rem;
            font-weight: bold;
            margin: 25px 0 10px 0;
            display: flex;
            align-items: center;
            gap: 6px;
            border-bottom: 2px solid #eaeaea;
            padding-bottom: 6px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: #fff;
            border-radius: 6px;
            overflow: hidden;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            margin-top: 5px;
        }}
        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #edf2f7;
            font-size: 0.95rem;
        }}
        th {{
            background: #f1f5f9;
            font-weight: 600;
            color: #475569;
        }}
        tr:last-child td {{
            border-bottom: none;
        }}
        .badge {{
            padding: 4px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 0.9rem;
            display: inline-block;
        }}
        .in-stock {{
            background: #eff6ff;
            color: #2563eb;
        }}
        .out-of-stock {{
            background: #fef2f2;
            color: #dc2626;
        }}
        .notification-box {{
            background: #fff;
            padding: 14px 16px;
            border-radius: 6px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            font-size: 0.9rem;
            margin-top: 5px;
        }}
        .btn-primary {{
            display: inline-block;
            background: #2563eb;
            color: #fff;
            padding: 10px 20px;
            border-radius: 6px;
            text-decoration: none;
            font-weight: bold;
            font-size: 0.95rem;
            box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
            transition: background 0.2s;
            margin-top: 5px;
        }}
        .btn-primary:hover {{
            background: #1d4ed8;
        }}
    </style>
</head>
<body>

    <h1>iPad 在庫状況</h1>
    <div class="update-time">最終更新: {now_str}</div>

    <div class="section-title">📊 指定モデルの在庫状況</div>
    <table>
        <thead>
            <tr>
                <th>モデル名</th>
                <th>ステータス</th>
            </tr>
        </thead>
        <tbody>
            {rows_html}
        </tbody>
    </table>

    <div class="section-title">🔔 通知ステータス</div>
    <div class="notification-box">
        <strong>{status_summary}</strong><br>
        <span style="color: #555; font-size: 0.85rem;">{notification_msg}</span>
    </div>

    <div class="section-title">🔗 購入ページ</div>
    <a class="btn-primary" href="https://www.softbank.jp/online-shop/products/stock/?device=ipad" target="_blank">公式購入ページを開く ↗</a>

</body>
</html>
"""
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
        "title": "iPad在庫更新通知",
    }).encode("utf-8")
    
    try:
        req = urllib.request.Request(url, data=data, method="POST")
        urllib.request.urlopen(req)
    except Exception:
        pass

def check_ipad_stock():
    with open("config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    target_models = config.get("target_models", [])
    state = load_state()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto("https://www.softbank.jp/online-shop/products/stock/?device=ipad", wait_until="networkidle")

        stock_results = page.evaluate("""(targets) => {
            const results = {};
            targets.forEach(target => {
                let status = "× 在庫なし";
                const allElements = Array.from(document.querySelectorAll('*'));
                for (let el of allElements) {
                    if (el.childNodes.length > 0) {
                        for (let node of el.childNodes) {
                            if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes(target)) {
                                let cardContainer = el;
                                for (let i = 0; i < 2; i++) if (cardContainer.parentElement) cardContainer = cardContainer.parentElement;
                                if (cardContainer.innerText.includes("在庫あり")) status = "〇 在庫あり";
                                else if (cardContainer.innerText.includes("在庫なし")) status = "× 在庫なし";
                            }
                        }
                    }
                }
                results[target] = status;
            });
            return results;
        }""", target_models)
        browser.close()

    newly_available = []
    reasons = []

    for model, status in stock_results.items():
        prev_status = state.get(model)
        if status == "〇 在庫あり" and prev_status != "〇 在庫あり":
            newly_available.append(model)
            if prev_status is None:
                reasons.append(f"{model}: 初回検出（在庫あり）")
            else:
                reasons.append(f"{model}: 在庫なし({prev_status}) → 在庫あり に変化")
        state[model] = status

    save_state(state)

    if newly_available:
        status_msg = f"新規在庫: 有り ({', '.join(newly_available)})"
    else:
        status_msg = "新規在庫: 無し"

    details_msg = "\n".join([f"{model.ljust(20)} : {status}" for model, status in stock_results.items()])

    if newly_available:
        notification_msg = f"通知: 有り ({', '.join(reasons)})"
    else:
        notification_msg = "通知: 無し (前回から新規の在庫復活なし)"

    generate_html(stock_results, newly_available, notification_msg)

    console_output = f"[新規在庫有無]\n{status_msg}\n\n[指定モデルの在庫状況]\n{details_msg}\n\n[通知]\n{notification_msg}"
    print(console_output)

    if newly_available:
        full_message = f"{console_output}\n\n[URL]\nhttps://www.softbank.jp/online-shop/products/stock/?device=ipad"
        send_pushover_notification(full_message)

if __name__ == "__main__":
    check_ipad_stock()