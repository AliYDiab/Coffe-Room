# CafeRoom v1.6.0

## Owner APK

- Added a PDF report action to every data screen while preserving all existing widgets.
- Added Arabic RTL PDF preview, sharing, printing, repeated table headers, pagination, summaries, and full-detail tables.
- Added reports for dashboard, inventory, receipts, debts, waste, sales and finance, smart inventory, customers, workers and shifts, ingredients, expenses, mobile requests, and sync health.
- Added real 90-day, monthly, and yearly income/profit data.
- Replaced estimated profit widgets with synchronized item-cost, expense, gross-profit, and net-profit values when available.

## Updates

- Fixed Android update detection when a newer GitHub release is missing its APK.
- Android now resumes installation automatically after unknown-source permission is granted, without downloading the APK again.
- Added a visible manual update check to the Windows app.
- Windows now selects the correct EXE from releases containing both APK and EXE assets and stops safely with an error log if replacement remains locked.
- Android releases now use a persistent CafeRoom signing certificate so v1.6.0 and later can update each other directly.

> Android installations from before v1.6.0 used a debug certificate whose private key is no longer available. Android requires a one-time uninstall before installing v1.6.0; future CafeRoom updates will install directly from the app.

## Worker and shift reporting

- Shift totals remain attached to the shift.
- Sales and item quantities remain attached to the worker session that sold them.
- Reconnecting workers continue the same daily worker log; another worker starts with an independent zero subtotal.
