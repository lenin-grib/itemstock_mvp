import argparse
import sys
from pathlib import Path
from datetime import date

from sqlalchemy import func

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database import SessionLocal, UploadedFile, Sale, Supply, Balance, Spoil


def _min_max_for_logs(session, file_id: int):
    mins = [
        session.query(func.min(Sale.date)).filter(Sale.source_file_id == file_id).scalar(),
        session.query(func.min(Supply.date)).filter(Supply.source_file_id == file_id).scalar(),
        session.query(func.min(Balance.date)).filter(Balance.source_file_id == file_id).scalar(),
    ]
    maxs = [
        session.query(func.max(Sale.date)).filter(Sale.source_file_id == file_id).scalar(),
        session.query(func.max(Supply.date)).filter(Supply.source_file_id == file_id).scalar(),
        session.query(func.max(Balance.date)).filter(Balance.source_file_id == file_id).scalar(),
    ]

    valid_mins = [d for d in mins if d is not None]
    valid_maxs = [d for d in maxs if d is not None]

    if not valid_mins or not valid_maxs:
        return None, None

    return min(valid_mins), max(valid_maxs)


def _min_max_for_spoils(session, file_id: int):
    date_from = session.query(func.min(Spoil.date)).filter(Spoil.source_file_id == file_id).scalar()
    date_to = session.query(func.max(Spoil.date)).filter(Spoil.source_file_id == file_id).scalar()
    return date_from, date_to


def _format_date(value: date | None):
    return value.isoformat() if value else "None"


def backfill(recompute_all: bool = False, dry_run: bool = False):
    session = SessionLocal()
    try:
        files = session.query(UploadedFile).all()

        updated = 0
        skipped = 0
        without_data = 0

        for f in files:
            needs_update = recompute_all or f.date_from is None or f.date_to is None
            if not needs_update:
                skipped += 1
                continue

            is_spoils = str(f.filename).startswith("spoils::")
            if is_spoils:
                new_from, new_to = _min_max_for_spoils(session, f.id)
            else:
                new_from, new_to = _min_max_for_logs(session, f.id)

            if new_from is None or new_to is None:
                without_data += 1
                print(f"[NO DATA] id={f.id} file={f.filename}")
                continue

            if dry_run:
                print(
                    f"[DRY] id={f.id} file={f.filename} "
                    f"{_format_date(f.date_from)}..{_format_date(f.date_to)} -> "
                    f"{_format_date(new_from)}..{_format_date(new_to)}"
                )
            else:
                f.date_from = new_from
                f.date_to = new_to
                updated += 1
                print(
                    f"[UPDATED] id={f.id} file={f.filename} "
                    f"=> {_format_date(new_from)}..{_format_date(new_to)}"
                )

        if not dry_run:
            session.commit()

        print("\nSummary:")
        print(f"  updated: {updated}")
        print(f"  skipped: {skipped}")
        print(f"  no_data: {without_data}")
        print(f"  mode: {'dry-run' if dry_run else 'apply'}")

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main():
    parser = argparse.ArgumentParser(
        description="Backfill uploaded_files.date_from/date_to from existing movement tables."
    )
    parser.add_argument(
        "--recompute-all",
        action="store_true",
        help="Recompute range for all uploaded files, not only missing ones.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would change without writing to DB.",
    )
    args = parser.parse_args()

    backfill(recompute_all=args.recompute_all, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
