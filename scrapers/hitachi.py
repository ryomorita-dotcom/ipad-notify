def scrape(page, site_config):
    url = site_config.get("url")
    exclude_words = site_config.get("exclude_words", [])

    page.goto(url, wait_until="networkidle")

    # 「もっと見る」ボタンを消えるまで連打して全件展開
    max_clicks = 15
    for _ in range(max_clicks):
        try:
            load_more_btn = page.locator("text=もっと見る")
            if load_more_btn.count() > 0 and load_more_btn.first.is_visible():
                load_more_btn.first.click()
                page.wait_for_timeout(1200)
            else:
                break
        except Exception:
            break

    # 「タテ型」と「BW-」を含み、ドラム式を含まないカードブロックを直接抽出する
    raw_results = page.evaluate("""() => {
        const results = [];
        const elements = Array.from(document.querySelectorAll('div, li, article, section'));
        
        elements.forEach(el => {
            const text = el.innerText || '';
            
            if (text.includes('タテ型') && !text.includes('ドラム式') && text.includes('BW-') && text.length < 600) {
                const hasChildCard = elements.some(other => {
                    if (other === el) return false;
                    const otherText = other.innerText || '';
                    return otherText.includes('タテ型') && !otherText.includes('ドラム式') && otherText.includes('BW-') && el.contains(other);
                });

                if (!hasChildCard) {
                    const lines = text.split('\\n').map(l => l.trim()).filter(l => l.length > 0);
                    
                    let name = lines.find(l => l.includes('【日立整備済み品】') || l.includes('BW-')) || 'タテ型洗濯機';
                    
                    const modelMatch = text.match(/BW-[A-Z0-9]+\s*[A-Z]?/);
                    if (modelMatch && !name.includes(modelMatch[0])) {
                        name = `${name} ${modelMatch[0]}`;
                    }

                    results.push({
                        name: name,
                        card_text: text,
                        status: '〇 在庫あり'
                    });
                }
            }
        });

        return results;
    }""")

    cleaned_results = {}
    for item in raw_results:
        name = item["name"]
        card_text = item.get("card_text", "")
        
        # 除外ワードのチェック（「乾燥機」など）
        excluded = False
        for word in exclude_words:
            if word in name or word in card_text:
                excluded = True
                break
        if excluded:
            continue

        if name not in cleaned_results:
            cleaned_results[name] = item["status"]

    structured_results = {
        "洗濯機": cleaned_results if cleaned_results else {"(該当なし)": "× 在庫なし"}
    }

    return structured_results