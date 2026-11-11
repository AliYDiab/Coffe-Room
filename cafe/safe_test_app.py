"""Launch source UI against a private DB copy, with network and Firebase disabled."""
import os
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile


def blocked(*args, **kwargs):
    raise RuntimeError("Network/Firebase is disabled in this offline test copy")


def main():
    source_dir = Path(__file__).resolve().parent
    test_dir = Path(tempfile.mkdtemp(prefix="CafeRoom-offline-test-"))
    with sqlite3.connect((source_dir / "cafe.db").as_uri() + "?mode=ro", uri=True) as source:
        with sqlite3.connect(test_dir / "cafe.db") as target:
            source.backup(target)
    os.chdir(test_dir)
    socket.socket.connect = blocked
    socket.socket.connect_ex = blocked
    socket.create_connection = blocked
    import firebase_admin
    firebase_admin.initialize_app = blocked
    import backup_manager
    backup_manager.base_dir = lambda: test_dir
    import firebase_sync
    firebase_sync.DB_PATH = str(test_dir / "cafe.db")
    firebase_sync.init_firebase = blocked
    firebase_sync.main = blocked
    import main as cafe
    if "--self-check" in sys.argv:
        import adb
        assert Path(adb.conn.execute("PRAGMA database_list").fetchone()[2]).parent == test_dir
        for action in (lambda: socket.create_connection(("127.0.0.1", 443)),
                       lambda: firebase_admin.initialize_app(), firebase_sync.init_firebase):
            try:
                action()
            except RuntimeError:
                pass
            else:
                raise AssertionError("Offline guard did not block access")
        print("PASS: private database copy; network and Firebase initialization blocked")
        return
    root = cafe.main()
    root.title("CafeRoom - OFFLINE TEST - private database copy")
    # Deliberately run only the UI: no updater and no sync thread.
    root.mainloop()


if __name__ == "__main__":
    main()
