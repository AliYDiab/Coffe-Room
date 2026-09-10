import 'package:caferoom_owner/services/update_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('MobileReleaseParser', () {
    test('newer release without APK is not reported as up to date', () {
      final release = {
        'tag_name': 'v1.5.0',
        'assets': [
          {
            'name': 'CafeRoom-PC-v1.5.0.exe',
            'browser_download_url': 'https://example/exe'
          }
        ],
      };

      expect(
        () => MobileReleaseParser.parse(release, currentVersion: '1.4.0'),
        throwsA(isA<MissingCompatibleAssetException>()),
      );
    });

    test('selects the APK asset from a combined platform release', () {
      final release = {
        'tag_name': 'v1.6.0',
        'assets': [
          {
            'name': 'CafeRoom-PC-v1.6.0.exe',
            'browser_download_url': 'https://example/exe'
          },
          {
            'name': 'CafeRoom-Mobile-v1.6.0.apk',
            'browser_download_url': 'https://example/apk'
          },
        ],
      };

      final update =
          MobileReleaseParser.parse(release, currentVersion: '1.5.0');

      expect(update?.version, '1.6.0');
      expect(update?.assetName, 'CafeRoom-Mobile-v1.6.0.apk');
      expect(update?.downloadUrl, 'https://example/apk');
    });

    test('handles different semantic version lengths', () {
      expect(MobileReleaseParser.isNewer('1.6.0', '1.5'), isTrue);
      expect(MobileReleaseParser.isNewer('1.6.0+6', '1.6.0'), isFalse);
      expect(MobileReleaseParser.isNewer('1.5.9', '1.6.0'), isFalse);
    });
  });

  test('permission-required APK is retried on resume without downloading again',
      () async {
    final calls = <String>[];
    var first = true;
    final coordinator = UpdateInstallCoordinator(installer: (path) async {
      calls.add(path);
      if (first) {
        first = false;
        return 'permission_required';
      }
      return 'installer_opened';
    });

    expect(await coordinator.install('update.apk'), 'permission_required');
    expect(coordinator.pendingApkPath, 'update.apk');
    expect(await coordinator.resumePendingInstall(), 'installer_opened');
    expect(coordinator.pendingApkPath, isNull);
    expect(calls, ['update.apk', 'update.apk']);
  });
}
