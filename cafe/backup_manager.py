import os
import sqlite3
import sys
from datetime import datetime
from pathlib import Path


MAX_BACKUPS = 14


def base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def backup_dir():
    path = base_dir() / "_automatic_backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_backups():
    return sorted(backup_dir().glob("CafeRoom_*.db"), reverse=True)


def create_backup(source_connection=None, force=False):
    now = datetime.now()
    if not force:
        today_prefix = f"CafeRoom_{now:%Y%m%d}_"
        existing = [p for p in list_backups() if p.name.startswith(today_prefix)]
        if existing:
            return existing[0]

    destination = backup_dir() / f"CafeRoom_{now:%Y%m%d_%H%M%S}.db"
    owns_source = source_connection is None
    source = source_connection or sqlite3.connect(base_dir() / "cafe.db")
    target = sqlite3.connect(destination)
    try:
        source.backup(target)
        check = target.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise RuntimeError(f"فشل فحص النسخة الاحتياطية: {check}")
    finally:
        target.close()
        if owns_source:
            source.close()

    backups = list_backups()
    for old_backup in backups[MAX_BACKUPS:]:
        old_backup.unlink(missing_ok=True)
    return destination


def restore_backup(backup_path, target_connection):
    backup_path = Path(backup_path).resolve()
    allowed_dir = backup_dir().resolve()
    if backup_path.parent != allowed_dir or not backup_path.is_file():
        raise ValueError("مسار النسخة الاحتياطية غير صالح")

    target_connection.commit()
    create_backup(target_connection, force=True)
    source = sqlite3.connect(backup_path)
    try:
        if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise RuntimeError("النسخة الاحتياطية تالفة")
        source.backup(target_connection)
        target_connection.commit()
    finally:
        source.close()


def backup_display_name(path):
    try:
        stamp = Path(path).stem.removeprefix("CafeRoom_")
        parsed = datetime.strptime(stamp, "%Y%m%d_%H%M%S")
        return parsed.strftime("%Y-%m-%d  %H:%M:%S")
    except ValueError:
        return Path(path).name
