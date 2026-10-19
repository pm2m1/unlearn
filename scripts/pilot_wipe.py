"""Wipe ALL pilot data: every row in the pilot log and every pilot class graph this machine's FalkorDB holds.

    PILOT_DATABASE_URL=... PYTHONPATH=api .venv/bin/python scripts/pilot_wipe.py --yes

The live service keeps an in-memory copy of its pilot graphs until it restarts. To clear the live copy too,
either restart the service after running this, or call the live wipe instead:

    curl -X POST https://<host>/pilot/api/admin/wipe -H "X-Pilot-Admin: <admin key>" \\
         -H "Content-Type: application/json" -d '{"confirm": "WIPE"}'
"""

import argparse
import os
import sys

from unlearn.pilot.engine import wipe_all
from unlearn.pilot.store import SCHEMA, Store


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="really delete everything")
    args = ap.parse_args()
    url = os.getenv("PILOT_DATABASE_URL")
    if not url:
        sys.exit("PILOT_DATABASE_URL is not set")
    store = Store(url)
    store.init()
    before = {t: store.count(t) for t in SCHEMA}
    print("rows now:", before)
    if not args.yes:
        print("nothing deleted (pass --yes to wipe)")
        return 0
    dropped = wipe_all(store)
    after = {t: store.count(t) for t in SCHEMA}
    print(f"deleted; rows now: {after}; pilot graphs dropped here: {dropped}")
    print("Restart the live service (or call /pilot/api/admin/wipe) so its in-memory copy goes too.")
    return 0 if not any(after.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
