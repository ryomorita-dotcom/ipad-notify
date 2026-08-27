def scrape(page, site_config):
    url = site_config.get("url")
    targets_by_category = site_config.get("targets", {})

    # カテゴリ内のすべてのターゲットをリストに抽出
    all_targets = []
    for category, items in targets_by_category.items():
        all_targets.extend(items)

    page.goto(url, wait_until="networkidle")

    # ブラウザ内で在庫確認JSを実行
    raw_results = page.evaluate("""(targets) => {
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
    }""", all_targets)

    # カテゴリ構造を保った辞書形式で返す
    structured_results = {}
    for category, items in targets_by_category.items():
        structured_results[category] = {}
        for item in items:
            structured_results[category][item] = raw_results.get(item, "× 在庫なし")

    return structured_results
