from common import ROOT, PUBLIC, load_json, now_tw

status = load_json(ROOT / "data" / "status.json", {})
PUBLIC.mkdir(parents=True, exist_ok=True)
updated = now_tw().strftime("%Y-%m-%d %H:%M:%S Asia/Taipei")
html = f'''<!doctype html>
<html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Focus Brief</title><style>
body{{font-family:system-ui,-apple-system,"Noto Sans TC",sans-serif;background:#0b1020;color:#eef2ff;margin:0}}
main{{max-width:1000px;margin:auto;padding:40px 20px}} .card{{background:#151c32;border:1px solid #29324f;border-radius:18px;padding:24px;margin:16px 0}}
.badge{{display:inline-block;padding:6px 10px;border-radius:999px;background:#26314f}} small{{color:#aeb8d4}} h1{{font-size:36px}}
</style></head><body><main><span class="badge">V2.0 Automation Skeleton</span><h1>Daily Focus Brief</h1>
<div class="card"><h2>自動化狀態</h2><p>17:30 盤後更新與 08:00 補漏檢查工作流程已建立。</p><p>資料引擎：{status.get('data_status','待更新')}</p><small>網站建置時間：{updated}</small></div>
<div class="card"><h2>V2.1 下一階段</h2><p>接入 TWSE、TPEx、TAIFEX、法人、融資融券、權證與族群資料；未取得可靠資料時一律顯示「待更新」。</p></div>
</main></body></html>'''
(PUBLIC / "index.html").write_text(html, encoding="utf-8")
print("site built", updated)
