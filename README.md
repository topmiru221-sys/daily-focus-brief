# Daily Focus Brief V2.0

台股自動化晨報／盤後晚報網站骨架。

## 自動排程
- 交易日 17:30 Asia/Taipei：盤後更新（GitHub Actions cron 09:30 UTC）
- 每日 08:00 Asia/Taipei：前一交易日資料完整性檢查（00:00 UTC）
- push main：GitHub Pages 自動部署

V2.0 先建立無人值守執行、資料狀態與部署骨架；V2.1 接入 TWSE/TPEx/TAIFEX 正式資料源。

## 首次設定
1. 將 ZIP 解壓後的「內容」上傳到 GitHub repository 根目錄。
2. GitHub > Settings > Pages > Source 選 GitHub Actions。
3. GitHub > Actions 確認 workflows 可執行。
4. 手動執行一次 `Deploy GitHub Pages` 驗證網站。

正常運作後不需要每日人工操作。
