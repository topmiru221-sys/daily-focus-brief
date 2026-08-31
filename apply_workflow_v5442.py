from pathlib import Path
p=Path(".github/workflows/market-close.yml");s=p.read_text(encoding="utf-8")
needle="      - name: Build Decision Engine\n        run: python src/analyzers/build_decision_engine.py"
insert="      - name: Build Technical Chart Intelligence\n        run: python src/analyzers/build_technical_chart.py\n"+needle
if "Build Technical Chart Intelligence" not in s:s=s.replace(needle,insert)
s=s.replace('git commit -m "data: update V5.4.40 priority history coverage"','git commit -m "data: update V5.4.42 technical chart intelligence"')
p.write_text(s,encoding="utf-8");print("workflow wired")
