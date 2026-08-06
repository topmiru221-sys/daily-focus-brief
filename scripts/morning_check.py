from common import ROOT, load_json, save_json, now_tw
import subprocess, sys
status_path = ROOT / "data" / "status.json"
status = load_json(status_path, {})
status["last_morning_check_run"] = now_tw().isoformat()
save_json(status_path, status)
subprocess.check_call([sys.executable, str(ROOT / "scripts" / "build_site.py")])
print("morning completeness check finished")
