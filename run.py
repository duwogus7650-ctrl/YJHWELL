"""YJHWell — offline launcher.

Run with the project virtual-env Python (fully offline once set up):
    .venv\\Scripts\\python run.py          (console + logs)
    .venv\\Scripts\\pythonw run.py         (window only)
or just double-click run.bat.

First time only (needs internet that one time): run setup.bat, or
    py -3.12 -m venv .venv
    .venv\\Scripts\\python -m pip install -r requirements.txt
"""
import sys


def _main():
    try:
        from litemaxwell.app import main
    except ImportError as exc:
        print("[YJHWell] A dependency is missing:", exc)
        print("Run setup.bat once (creates .venv and installs requirements),")
        print(r"then launch with:  .venv\Scripts\python run.py")
        sys.exit(1)
    main()


if __name__ == "__main__":
    _main()
