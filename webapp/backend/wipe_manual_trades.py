"""One-off cleanup: delete every manually-logged trade so a fresh CSV import
has no overlap with old hand-entered rows.

Wipes:
  - trade_logs rows where source IS 'manual' or NULL (legacy rows from before
    the source column was introduced are treated as manual).
  - cascaded plans / notes / attachment rows via the ORM relationships.
  - on-disk attachment directories under uploads/<trade_id>/.

Run from the webapp/backend/ directory:

    python wipe_manual_trades.py            # asks for confirmation
    python wipe_manual_trades.py --yes      # skips the prompt

CSV-imported rows (source='ibkr') are NOT touched.
"""
from __future__ import annotations

import argparse
import sys

from sqlalchemy import or_

import models
from database import SessionLocal
from routers.journal import wipe_trade_uploads


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        manual_trades = (
            db.query(models.TradeLog)
            .filter(or_(models.TradeLog.source == "manual", models.TradeLog.source.is_(None)))
            .all()
        )
        ibkr_count = (
            db.query(models.TradeLog)
            .filter(models.TradeLog.source == "ibkr")
            .count()
        )

        if not manual_trades:
            print(f"No manual trades to wipe. (IBKR-sourced rows preserved: {ibkr_count})")
            return 0

        print(f"About to delete {len(manual_trades)} manual trade(s).")
        print(f"IBKR-sourced rows that will be preserved: {ibkr_count}")
        print()
        print("Sample of what will be deleted:")
        for t in manual_trades[:10]:
            print(f"  id={t.id}  {t.opening_date}  {t.ticker}  qty={t.quantity}  pnl={t.pnl}")
        if len(manual_trades) > 10:
            print(f"  ... and {len(manual_trades) - 10} more")
        print()

        if not args.yes:
            answer = input("Proceed? [y/N] ").strip().lower()
            if answer not in ("y", "yes"):
                print("Aborted.")
                return 1

        trade_ids = [t.id for t in manual_trades]
        for t in manual_trades:
            db.delete(t)
        db.commit()

        for tid in trade_ids:
            wipe_trade_uploads(tid)

        print(f"Done. Deleted {len(trade_ids)} manual trade(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
