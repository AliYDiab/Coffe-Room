# CafeRoom

CafeRoom is a cafe point-of-sale system with a Windows desktop application and a Flutter owner application for Android.

## Projects

- `cafe/` — Windows POS, SQLite database logic, worker shifts, Firebase synchronization, backups, and desktop updater.
- `Cafe_Android/caferoom_owner/` — Android owner dashboard, mobile entry requests, analytics, PDF reports, and APK updater.

## Development checks

```powershell
cd cafe
python -m unittest discover -s tests -v

cd ..\Cafe_Android\caferoom_owner
flutter test
flutter analyze --no-fatal-infos
```

## Releases

GitHub releases contain both platform artifacts using stable names:

- `CafeRoom-PC-vX.Y.Z.exe`
- `CafeRoom-Mobile-vX.Y.Z.apk`

The installed applications read the latest GitHub release, compare their runtime version, and select only the compatible platform asset.

Android release builds require `CAFEROOM_SIGNING_PROPERTIES` or the local
`~/.caferoom/release-signing.properties` file. Keep that keystore and properties
file backed up securely: every future APK must use the same certificate for
in-place updates.
