# Cross-Platform Updater and Release Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make both the installed Android APK and Windows EXE reliably discover, download, and continue installing a newer GitHub release, then publish v1.6.0 with both artifacts.

**Architecture:** Pure parsers select a platform-specific asset from GitHub release JSON and compare semantic versions. Android resumes installation after unknown-source permission is granted. Windows exposes a manual check button and uses a bounded replacement script with an error log. One release contract validates names, versions, and checksums before upload.

**Tech Stack:** Dart/Flutter, Android Kotlin MethodChannel, Python/Tkinter, PyInstaller, GitHub CLI/Releases.

**Spec:** `docs/superpowers/specs/2026-09-01-owner-pdf-reports-and-updates.md`

## Global Constraints

- Target version/tag: `1.6.0` / `v1.6.0`.
- Release assets: `CafeRoom-Mobile-v1.6.0.apk` and `CafeRoom-PC-v1.6.0.exe`.
- Preserve Android signing identity used by existing installations.
- Never report “up to date” when a newer release exists but its APK/EXE asset is missing.

---

### Task 1: Reproduce and protect release parsing

**Files:**
- Modify: `Cafe_Android/caferoom_owner/lib/services/update_service.dart`
- Create: `Cafe_Android/caferoom_owner/test/services/update_service_test.dart`
- Modify: `cafe/updater.py`
- Create: `cafe/tests/test_updater.py`

- [ ] Add failing tests using the real v1.5.0 release shape (newer tag with EXE but no APK) and assert “missing compatible asset,” not “up to date.”
- [ ] Add platform asset selection, malformed response, prerelease, and semantic-version cases.
- [ ] Run focused Dart and Python tests and confirm expected failures.
- [ ] Implement pure release parsers and explicit update statuses, then re-run tests.

### Task 2: Android version and permission-resume flow

**Files:**
- Modify: `Cafe_Android/caferoom_owner/pubspec.yaml`
- Modify: `Cafe_Android/caferoom_owner/lib/services/update_service.dart`
- Modify: `Cafe_Android/caferoom_owner/lib/main.dart`
- Modify: `Cafe_Android/caferoom_owner/android/app/src/main/kotlin/com/CoffeShop/MainActivity.kt`
- Test: `Cafe_Android/caferoom_owner/test/services/update_install_coordinator_test.dart`

- [ ] Write failing tests proving runtime package version is used and a downloaded APK remains pending while permission settings are open.
- [ ] Implement runtime version lookup and resume installation without re-downloading when the app returns to foreground.
- [ ] Display distinct Arabic messages for no update, missing APK, network error, permission required, and installer opened.
- [ ] Run focused tests and full Flutter tests.

### Task 3: Windows manual and bounded update flow

**Files:**
- Modify: `cafe/main.py`
- Modify: `cafe/updater.py`
- Modify: `cafe/version.py`
- Test: `cafe/tests/test_updater.py`

- [ ] Write failing tests for exact EXE preference, retry exhaustion, protected-data preservation, and generated restart command.
- [ ] Add a visible manual “check for update” owner control while retaining startup checks.
- [ ] Replace infinite copy loops with bounded retries and a readable failure log/message.
- [ ] Set desktop version to `1.6.0` and run the desktop suite.

### Task 4: Version, signing, and release contract

**Files:**
- Modify: `Cafe_Android/caferoom_owner/pubspec.yaml`
- Modify: `Cafe_Android/caferoom_owner/android/app/build.gradle.kts` only if an existing persistent keystore is available.
- Create: `scripts/verify_release.py`
- Test: `tests/test_verify_release.py`

- [ ] Verify the previous APK certificate and the local signing certificate match before building.
- [ ] Set Flutter version to `1.6.0+6`.
- [ ] Write a failing contract test for artifact names, embedded/app versions, non-zero sizes, and SHA-256 output.
- [ ] Implement the release verifier and re-run it against controlled fixtures.

### Task 5: Build and publish v1.6.0

**Files:**
- Create: `RELEASE_NOTES_v1.6.0.md`
- Create during build: `release-v1.6.0/CafeRoom-Mobile-v1.6.0.apk`
- Create during build: `release-v1.6.0/CafeRoom-PC-v1.6.0.exe`
- Create during build: `release-v1.6.0/SHA256SUMS-v1.6.0.txt`

- [ ] Run full Python tests and compile checks.
- [ ] Run Flutter tests/analyze and build the release APK.
- [ ] Build the PyInstaller EXE from `cafe/CafeRoom.spec` and smoke-launch it in a controlled process.
- [ ] Run release contract verification and calculate checksums.
- [ ] Commit/push source to the repository’s `main` branch without overwriting remote history.
- [ ] Create GitHub release `v1.6.0`, upload both artifacts plus checksums, and query the published release JSON to verify both update clients can select their asset.
