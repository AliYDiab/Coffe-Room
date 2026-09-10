# Owner PDF Reports Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add accurate Arabic PDF table reports for every data domain displayed by the owner APK without removing existing widgets.

**Architecture:** A pure report catalog converts normalized Firestore payloads into report sections. A single PDF renderer handles RTL layout, pagination, totals, and preview; the main shell provides the active-screen report action. Desktop sync adds compact aggregates required for accurate long-range finance reports.

**Tech Stack:** Flutter/Dart, Firebase Firestore, `pdf`, `printing`, bundled Noto Arabic font, Python/SQLite sync.

**Spec:** `docs/superpowers/specs/2026-09-01-owner-pdf-reports-and-updates.md`

## Global Constraints

- Keep all existing widgets.
- One PDF action per active screen/tab; no repeated action on each KPI card.
- Arabic RTL, page numbers, repeated table headers, generated timestamp, and explicit report scope.
- Daily/monthly/yearly finance uses actual synchronized values where present.

---

### Task 1: Report domain model and catalog

**Files:**
- Create: `Cafe_Android/caferoom_owner/lib/reports/report_models.dart`
- Create: `Cafe_Android/caferoom_owner/lib/reports/report_catalog.dart`
- Test: `Cafe_Android/caferoom_owner/test/reports/report_catalog_test.dart`

**Interfaces:**
- Produces: `ReportDocument`, `ReportSection`, `ReportTable`, and `ReportCatalog.fromScreen(int, ReportDataBundle)`.

- [ ] Write failing tests for inventory full-field columns, receipt item details, finance periods, and shift/worker totals.
- [ ] Run `flutter test test/reports/report_catalog_test.dart` and confirm missing-symbol failures.
- [ ] Implement immutable report models plus deterministic formatters and catalog builders.
- [ ] Re-run the focused tests and the full Flutter suite.

### Task 2: Firestore report data loader

**Files:**
- Create: `Cafe_Android/caferoom_owner/lib/reports/report_data_service.dart`
- Modify: `Cafe_Android/caferoom_owner/lib/services/AppFirebaseService.dart`
- Test: `Cafe_Android/caferoom_owner/test/reports/report_data_service_test.dart`

**Interfaces:**
- Produces: `Future<ReportDataBundle> loadForScreen(int screenIndex)` and normalization helpers that accept missing/dynamic fields safely.

- [ ] Write failing tests for missing documents, numeric normalization, dynamic collection rows, and screen-to-source mapping.
- [ ] Run focused tests and confirm expected failures.
- [ ] Implement the loader using existing document/collection streams and bounded timeouts.
- [ ] Re-run focused and full tests.

### Task 3: Arabic PDF renderer and preview

**Files:**
- Modify: `Cafe_Android/caferoom_owner/pubspec.yaml`
- Create: `Cafe_Android/caferoom_owner/assets/fonts/NotoSansArabic-Regular.ttf`
- Create: `Cafe_Android/caferoom_owner/assets/fonts/NotoSansArabic-Bold.ttf`
- Create: `Cafe_Android/caferoom_owner/lib/reports/pdf_report_service.dart`
- Create: `Cafe_Android/caferoom_owner/lib/screens/report_preview_screen.dart`
- Test: `Cafe_Android/caferoom_owner/test/reports/pdf_report_service_test.dart`

**Interfaces:**
- Produces: `Future<Uint8List> PdfReportService.build(ReportDocument report)` and `ReportPreviewScreen(report:)`.

- [ ] Add a failing renderer test that parses a multi-page PDF and verifies page count/non-empty bytes.
- [ ] Resolve `pdf` and `printing`, register bundled Arabic fonts, and confirm the test still fails because renderer is absent.
- [ ] Implement RTL header, summaries, paged tables, orientation selection, headers/footers, and native preview/share/print.
- [ ] Render representative inventory and finance PDFs to images and visually check Arabic/order/table boundaries.

### Task 4: Report action in the APK

**Files:**
- Create: `Cafe_Android/caferoom_owner/lib/widgets/pdf_report_button.dart`
- Modify: `Cafe_Android/caferoom_owner/lib/main.dart`
- Test: `Cafe_Android/caferoom_owner/test/widgets/pdf_report_button_test.dart`

**Interfaces:**
- Consumes: `ReportDataService.loadForScreen`, `ReportCatalog.fromScreen`, `ReportPreviewScreen`.

- [ ] Write failing widget tests for loading, success navigation, empty-data message, and error retry.
- [ ] Implement one Arabic PDF action in the app bar, keyed to the selected screen.
- [ ] Verify every navigable data screen has a non-empty catalog entry and mobile-entry maps to ingredients/expenses/request summaries.
- [ ] Run widget tests, full tests, and `flutter analyze --no-fatal-infos`.

### Task 5: Accurate long-range sync aggregates

**Files:**
- Modify: `cafe/firebase_sync.py`
- Test: `cafe/tests/test_firebase_sync_analytics.py`

**Interfaces:**
- Produces Firestore analytics keys `last_90_days`, `monthly`, and `yearly`, each containing orders, revenue, gross_profit, expenses, and net_profit.

- [ ] Write failing SQLite fixture tests for 90-day, month-boundary, year-boundary, expense, and missing-cost behavior.
- [ ] Extract pure aggregate query helpers and publish compact results from `sync_analytics`.
- [ ] Confirm the old 7/30-day contracts remain compatible.
- [ ] Run `python -m unittest discover -s cafe/tests -v`.

### Task 6: End-to-end report verification

**Files:**
- Update tests above only if a discovered contract gap requires it.

- [ ] Run all desktop and Flutter tests.
- [ ] Run Flutter analyze.
- [ ] Generate representative reports for every catalog domain.
- [ ] Confirm worker subtotals reconcile with shift totals and finance period totals reconcile across daily/monthly/yearly data.
