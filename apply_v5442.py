from pathlib import Path
p=Path("public/decision.html");s=p.read_text(encoding="utf-8")
css='<link rel="stylesheet" href="./assets/technical-chart-v5442.css">'
js='<script src="./assets/technical-chart-v5442.js"></script>'
if css not in s:s=s.replace('<link rel="stylesheet" href="./assets/styles.css">','<link rel="stylesheet" href="./assets/styles.css">'+css)
if js not in s:s=s.replace('<script src="./assets/global-stock-name.js"></script>',js+'\n<script src="./assets/global-stock-name.js"></script>')
p.write_text(s,encoding="utf-8");print("decision.html wired")
