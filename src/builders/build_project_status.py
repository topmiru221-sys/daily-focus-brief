from pathlib import Path
import shutil
SRC=Path("config/project_status.json"); DST=Path("public/data/project_status.json")
def main():
    DST.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(SRC,DST); return 0
if __name__=="__main__": raise SystemExit(main())
