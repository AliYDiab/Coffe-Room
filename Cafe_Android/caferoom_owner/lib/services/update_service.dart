import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:package_info_plus/package_info_plus.dart';

class MobileUpdateInfo {
  final String version;
  final String downloadUrl;
  final String assetName;

  const MobileUpdateInfo({
    required this.version,
    required this.downloadUrl,
    required this.assetName,
  });
}

class MobileUpdateService {
  static const _repo = 'AliYDiab/Coffe-Room';
  static const _apiUrl = 'https://api.github.com/repos/$_repo/releases/latest';
  static const _channel = MethodChannel('caferoom/update');

  static Future<MobileUpdateInfo?> checkForUpdate() async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(Uri.parse(_apiUrl));
      request.headers
          .set(HttpHeaders.acceptHeader, 'application/vnd.github+json');
      request.headers.set(HttpHeaders.userAgentHeader, 'CafeRoom-Mobile');
      final response = await request.close();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException('GitHub returned ${response.statusCode}');
      }

      final body = await response.transform(utf8.decoder).join();
      final data = jsonDecode(body) as Map<String, dynamic>;
      final package = await PackageInfo.fromPlatform();
      return MobileReleaseParser.parse(data, currentVersion: package.version);
    } finally {
      client.close(force: true);
    }
  }

  static Future<String> downloadApk(
    MobileUpdateInfo update, {
    void Function(int received, int total)? onProgress,
  }) async {
    final client = HttpClient();
    try {
      final request = await client.getUrl(Uri.parse(update.downloadUrl));
      request.headers.set(HttpHeaders.userAgentHeader, 'CafeRoom-Mobile');
      final response = await request.close();
      if (response.statusCode < 200 || response.statusCode >= 300) {
        throw HttpException('Download returned ${response.statusCode}');
      }

      final safeName =
          update.assetName.replaceAll(RegExp(r'[^A-Za-z0-9._-]'), '_');
      final file = File('${Directory.systemTemp.path}/$safeName');
      final sink = file.openWrite();
      var received = 0;
      final total = response.contentLength;

      await for (final chunk in response) {
        received += chunk.length;
        sink.add(chunk);
        onProgress?.call(received, total);
      }

      await sink.close();
      if (total > 0 && received != total) {
        await file.delete();
        throw const HttpException(
            'Downloaded APK size does not match the release asset');
      }
      return file.path;
    } finally {
      client.close(force: true);
    }
  }

  static Future<String?> installApk(String apkPath) async {
    return _channel.invokeMethod<String>('installApk', {'path': apkPath});
  }
}

class MissingCompatibleAssetException implements Exception {
  final String version;

  const MissingCompatibleAssetException(this.version);

  @override
  String toString() =>
      'الإصدار $version موجود، لكن ملف Android APK غير مرفق به.';
}

class MobileReleaseParser {
  static MobileUpdateInfo? parse(
    Map<String, dynamic> data, {
    required String currentVersion,
  }) {
    final tag = (data['tag_name'] as String? ?? '').trim();
    final latestVersion = tag.replaceFirst(RegExp(r'^[vV]'), '');
    if (latestVersion.isEmpty) {
      throw const FormatException(
          'GitHub release does not contain a version tag');
    }
    if (!isNewer(latestVersion, currentVersion)) return null;

    final assets = data['assets'];
    if (assets is List) {
      for (final rawAsset in assets.whereType<Map>()) {
        final asset = Map<String, dynamic>.from(rawAsset);
        final name = (asset['name'] as String? ?? '').trim();
        final url = (asset['browser_download_url'] as String? ?? '').trim();
        if (name.toLowerCase().endsWith('.apk') && url.isNotEmpty) {
          return MobileUpdateInfo(
            version: latestVersion,
            downloadUrl: url,
            assetName: name,
          );
        }
      }
    }
    throw MissingCompatibleAssetException(latestVersion);
  }

  static bool isNewer(String latest, String current) {
    final latestParts = _versionParts(latest);
    final currentParts = _versionParts(current);
    final length = latestParts.length > currentParts.length
        ? latestParts.length
        : currentParts.length;

    for (var i = 0; i < length; i++) {
      final l = i < latestParts.length ? latestParts[i] : 0;
      final c = i < currentParts.length ? currentParts[i] : 0;
      if (l > c) return true;
      if (l < c) return false;
    }

    return false;
  }

  static List<int> _versionParts(String value) {
    final withoutBuild = value.split('+').first;
    return withoutBuild
        .split(RegExp(r'[.-]'))
        .map((part) => int.tryParse(part) ?? 0)
        .toList();
  }
}

typedef ApkInstaller = Future<String?> Function(String apkPath);

class UpdateInstallCoordinator {
  final ApkInstaller installer;
  String? pendingApkPath;

  UpdateInstallCoordinator({ApkInstaller? installer})
      : installer = installer ?? MobileUpdateService.installApk;

  Future<String?> install(String apkPath) async {
    final result = await installer(apkPath);
    pendingApkPath = result == 'permission_required' ? apkPath : null;
    return result;
  }

  Future<String?> resumePendingInstall() async {
    final path = pendingApkPath;
    if (path == null) return null;
    final result = await installer(path);
    if (result != 'permission_required') pendingApkPath = null;
    return result;
  }
}
