from common import ROOT, load_json, save_json, now_tw
from build_site import *  # noqa

status_path = ROOT / "data" / "status.json"
status = load_json(status_path, {})
now = now_tw()
# V2.0 safety: weekends are skipped. Official Taiwan trading-calendar logic arrives in V2.1.
if now.weekday() >= 5:
    print("Weekend: skip normal market-close report")
else:
    status["last_market_close_run"] = now.isoformat()
    status["data_status"] = "waiting_for_v2.1_data_connectors"
    save_json(status_path, status)
    import subprocess, sys
    subprocess.check_call([sys.executable, str(ROOT / "scripts" / "build_site.py")])
