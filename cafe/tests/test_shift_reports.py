import sqlite3
from zipfile import ZipFile

import adb
from modules.shift_reports import drinks_sold, pending_reports, session_receipts
import firebase_sync


def test_shift_close_exports_individual_prices_and_stages_owner_report(monkeypatch, tmp_path):
    with sqlite3.connect(":memory:") as db:
        db.executescript("""
            CREATE TABLE workers(id, name);
            CREATE TABLE worker_sessions(id, worker_id, start_time, end_time, status,
                total_receipts, total_items, total_revenue, held_revenue, updated_at);
            CREATE TABLE receipts(id, date, total, status, worker_session_id);
            CREATE TABLE receipt_items(id, receipt_id, item_id, name, qty, price);
            CREATE TABLE items(id, category);
            INSERT INTO workers VALUES(1, 'Ali');
            INSERT INTO worker_sessions VALUES(1, 1, '2026-11-18T08:00', NULL, 'active', 0, 0, 0, 0, NULL);
            INSERT INTO receipts VALUES
                (1, '2026-11-18T07:59', 300, 'paid', 1),
                (2, '2026-11-18T10:00', 700, 'paid', 1),
                (3, '2026-11-18T10:00', 800, 'paid', 2),
                (4, '2026-11-18T18:01', 900, 'paid', 1);
            INSERT INTO items VALUES(1, 'مشروبات'), (2, 'أغذية');
            INSERT INTO receipt_items VALUES
                (1, 1, 1, 'Old', 10, 30),
                (2, 2, 1, 'Coffee', 2, 250),
                (3, 2, 2, 'Cake', 1, 200),
                (4, 3, 1, 'Other worker', 4, 200),
                (5, 4, 1, 'After closing', 3, 300);
        """)
        from datetime import datetime

        start, end = "2026-11-18T08:00", "2026-11-18T18:00"
        assert [row[0] for row in session_receipts(db, 1, start, end)] == [2]
        assert drinks_sold(db, 1, start, end) == 2
        monkeypatch.setattr(adb, "conn", db)
        monkeypatch.setattr(adb, "cur", db.cursor())
        file = adb.end_worker_session(1, datetime.fromisoformat(end), export_dir=tmp_path)
        assert file.exists()
        with ZipFile(file) as archive:
            cells = archive.read("xl/worksheets/sheet1.xml").decode()
            strings = archive.read("xl/sharedStrings.xml").decode()
            assert "Coffee" in strings and "Cake" in strings
            assert "<v>250</v>" in cells and "<v>200</v>" in cells
            assert "<v>700</v>" not in cells and "<f" not in cells
            assert "Other worker" not in strings and "After closing" not in strings
        [(key, report)] = pending_reports(db)
        assert report["drinks"] == 2
        assert report["sections"]["sales"][0][-1] == 500
        assert report["sections"]["receipts"][0][2] == 700
        assert adb.end_worker_session(1, datetime.fromisoformat(end), export_dir=tmp_path) is None
        assert [report_id for report_id, _ in pending_reports(db)] == [key]

        class FakeCloud:
            def __init__(self):
                self.writes = {}

            def collection(self, name):
                assert name == "cafe"
                return self

            def document(self, name):
                class Document:
                    def set(_, data):
                        self.writes[name] = data
                return Document()

        cloud = FakeCloud()
        notifications = []
        monkeypatch.setattr(firebase_sync, "send_notification",
                            lambda title, body, **kwargs: notifications.append(title))
        firebase_sync.sync_closed_shift_reports(db, cloud)
        manifest = cloud.writes[f"shift_report_{key}"]
        assert manifest["entity"] == "closed_shift_report"
        [sales] = manifest["sections"]["sales"]
        assert cloud.writes[sales]["rows"][0]["values"][-1] == 500
        assert list(cloud.writes)[-1] == f"shift_report_{key}"
        firebase_sync.sync_closed_shift_reports(db, cloud)
        assert len(notifications) == 1
