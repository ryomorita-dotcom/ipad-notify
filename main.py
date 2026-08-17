import json
import os
import requests
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()
PUSHOVER_USER = os.getenv("PUSHOVER_USER")
PUSHOVER_TOKEN = os.getenv("PUSHOVER_TOKEN")

STATE_FILE = "state.json"

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

def send_pushover_notification(message):
    if not PUSHOVER_USER or not PUSHOVER_TOKEN:
        return

    payload = {
        "token": PUSHOVER_TOKEN,
        "user": PUSHOVER_USER,
        "message": message,
        "title": "iPad在庫更新通知",
    }
    
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload)
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

    # 新規在庫有無のテキスト
    if newly_available:
        status_msg = f"新規在庫: 有り ({', '.join(newly_available)})"
    else:
        status_msg = "新規在庫: 無し"

    # 指定モデルの在庫状況のテキスト
    details_msg = "\n".join([f"{model.ljust(20)} : {status}" for model, status in stock_results.items()])

    # 通知判定のテキスト
    if newly_available:
        notification_msg = f"通知: 有り ({', '.join(reasons)})"
    else:
        notification_msg = "通知: 無し (前回から新規の在庫復活なし)"

    # 画面（ターミナル）に出力
    console_output = f"[新規在庫有無]\n{status_msg}\n\n[指定モデルの在庫状況]\n{details_msg}\n\n[通知]\n{notification_msg}"
    print(console_output)

    # 新規在庫がある（通知すべき）ときだけ Pushover へ送信する
    if newly_available:
        full_message = f"[新規在庫有無]\n{status_msg}\n\n[指定モデルの在庫状況]\n{details_msg}\n\n[通知]\n{notification_msg}\n\n[URL]\nhttps://www.softbank.jp/online-shop/products/stock/?device=ipad"
        send_pushover_notification(full_message)

if __name__ == "__main__":
    check_ipad_stock()