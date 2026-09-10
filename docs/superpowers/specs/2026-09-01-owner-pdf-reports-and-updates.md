# CafeRoom Owner PDF Reports and Cross-Platform Updates

## Approved product behavior

- Keep every existing dashboard/widget and add one PDF action for the active data screen or tab.
- Generate Arabic RTL table reports for dashboard, inventory, receipts, debts, waste, sales/finance analytics, inventory intelligence, customer insights, workers, schedules, shift sessions, ratings, handovers, ingredients, expenses, mobile requests, and sync health.
- Reports include the complete available fields, totals, filters/period labels, generated time, repeating headers, page numbers, and native preview/share/print.
- Income reports support daily, monthly, and yearly summaries using real revenue, COGS, gross profit, expenses, and net profit. Estimated values must be explicitly labelled.
- Shift reports keep the shift total and attribute each receipt/item to its worker session, so returning workers continue their totals and newly joining workers start at zero.
- Release both Android APK and Windows EXE together. Both installed apps must detect a newer GitHub release, select only their own platform asset, download it, and continue the installation flow.

## Architecture

- Flutter owns a reusable report model/catalog, Firestore report loader, Arabic PDF renderer, preview screen, and one app-bar report action keyed by the active screen.
- Desktop sync publishes compact 90-day/monthly/yearly aggregates; raw receipts remain bounded to avoid Firestore document-size failures.
- Update parsing and version comparison are pure/testable. Runtime code obtains its version from package metadata on Flutter and `version.py` on desktop.
- GitHub releases use semantic tags and stable asset names: `CafeRoom-Mobile-vX.Y.Z.apk` and `CafeRoom-PC-vX.Y.Z.exe`.

## Release constraints

- Target release: v1.6.0.
- Do not claim all-time receipt detail beyond the bounded synced receipt list; clearly label report scope.
- Preserve the current Android signing identity so existing sideloaded installations can update in place.
- Release only after desktop tests, Flutter tests/analyze, APK build, EXE build, updater contract checks, and artifact checksums pass.
