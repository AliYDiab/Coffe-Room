import 'dart:async';
import 'dart:io';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter/foundation.dart';
import 'package:intl/intl.dart';
import 'demo_data_service.dart';

class FirebaseService {
  static final _db = FirebaseFirestore.instance;
  static final _fcm = FirebaseMessaging.instance;
  static StreamSubscription<String>? _tokenRefreshSubscription;

  static bool _useDemoMode = false;

  /// Enable demo mode when Firebase is not available
  static void setDemoMode(bool enabled) {
    _useDemoMode = enabled;
  }

  // Streams
  static Stream<Map<String, dynamic>> dashboardDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getDashboardData());
    }
    return _db
        .collection('cafe')
        .doc('dashboard')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> inventoryDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getInventoryData());
    }
    return _db
        .collection('cafe')
        .doc('inventory')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> receiptsDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getReceiptsData());
    }
    return _db
        .collection('cafe')
        .doc('receipts')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> debtsDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getDebtsData());
    }
    return _db
        .collection('cafe')
        .doc('debts')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> wasteDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getWasteData());
    }
    return _db
        .collection('cafe')
        .doc('waste')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> analyticsDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getAnalyticsData());
    }
    return _db
        .collection('cafe')
        .doc('analytics')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> ingredientsDataStream() {
    if (_useDemoMode) {
      return Stream.value(DemoDataService.getIngredientsData());
    }
    return _db
        .collection('cafe')
        .doc('ingredients')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<Map<String, dynamic>> expensesDataStream() {
    if (_useDemoMode) {
      return Stream.value(const {'list': <Map<String, dynamic>>[]});
    }
    return _db
        .collection('cafe')
        .doc('expenses')
        .snapshots()
        .map((snap) => snap.data() ?? {});
  }

  static Stream<List<Map<String, dynamic>>> collectionDataStream(
      String collection) {
    if (_useDemoMode) {
      switch (collection) {
        case 'workers':
          return Stream.value(DemoDataService.getWorkersData());
        case 'shift_schedules':
          return Stream.value(DemoDataService.getShiftSchedulesData());
        case 'shift_sessions':
          return Stream.value(DemoDataService.getShiftSessionsData());
        case 'worker_ratings':
          return Stream.value(DemoDataService.getWorkerRatingsData());
        case 'shift_handover':
          return Stream.value(DemoDataService.getShiftHandoverData());
        default:
          return Stream.value(const <Map<String, dynamic>>[]);
      }
    }

    return _db.collection(collection).snapshots().map((snap) {
      return snap.docs.map((doc) {
        final data = doc.data();
        return {
          'id': doc.id,
          ...data,
        };
      }).toList();
    });
  }

  // Streams for backward compatibility
  static Stream<dynamic> dashboardStream() {
    if (_useDemoMode) {
      // Create a wrapper stream that returns mock snapshots
      return dashboardDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('dashboard').snapshots();
  }

  static Stream<dynamic> inventoryStream() {
    if (_useDemoMode) {
      return inventoryDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('inventory').snapshots();
  }

  static Stream<dynamic> receiptsStream() {
    if (_useDemoMode) {
      return receiptsDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('receipts').snapshots();
  }

  static Stream<dynamic> debtsStream() {
    if (_useDemoMode) {
      return debtsDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('debts').snapshots();
  }

  static Stream<dynamic> wasteStream() {
    if (_useDemoMode) {
      return wasteDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('waste').snapshots();
  }

  static Stream<dynamic> analyticsStream() {
    if (_useDemoMode) {
      return analyticsDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('analytics').snapshots();
  }

  static Stream<dynamic> ingredientsStream() {
    if (_useDemoMode) {
      return ingredientsDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('ingredients').snapshots();
  }

  static Stream<dynamic> expensesStream() {
    if (_useDemoMode) {
      return expensesDataStream().map((data) => _MockDocumentSnapshot(data));
    }
    return _db.collection('cafe').doc('expenses').snapshots();
  }

  // FCM setup
  static Future<String?> setupNotifications() async {
    if (_useDemoMode) return 'demo_token';

    await _fcm.requestPermission(alert: true, badge: true, sound: true);
    final token = await _fcm.getToken();
    if (token != null) {
      await _saveNotificationToken(token);
    }

    await _tokenRefreshSubscription?.cancel();
    _tokenRefreshSubscription = _fcm.onTokenRefresh.listen(
      (refreshedToken) async {
        try {
          await _saveNotificationToken(refreshedToken);
        } catch (error) {
          debugPrint('[FCM] Could not save refreshed token: $error');
        }
      },
      onError: (Object error) {
        debugPrint('[FCM] Token refresh failed: $error');
      },
    );
    return token;
  }

  static Future<void> _saveNotificationToken(String token) async {
    // Save the current token where the desktop sync service can read it.
    await _db.collection('cafe').doc('device_token').set({
      'token': token,
      'updated_at': FieldValue.serverTimestamp(),
      'platform': Platform.operatingSystem,
    });
    debugPrint('[FCM] Token saved');
  }

  static Future<String> submitMobileInventoryItem(
      Map<String, dynamic> data) async {
    if (_useDemoMode) return 'demo';

    return _submitReliableRequest('mobile_inventory_requests', {
      ...data,
      'entity': 'mobile_inventory_request',
    });
  }

  static Future<String> submitMobileReceiptRequest(
      Map<String, dynamic> data) async {
    if (_useDemoMode) return 'demo';

    return _submitReliableRequest('mobile_receipt_requests', {
      ...data,
      'entity': 'mobile_receipt_request',
    });
  }

  static Future<String> submitMobileExpenseRequest(
      Map<String, dynamic> data) async {
    if (_useDemoMode) return 'demo';

    return _submitReliableRequest('mobile_expense_requests', {
      ...data,
      'entity': 'mobile_expense_request',
    });
  }

  static Future<String> _submitReliableRequest(
      String collection, Map<String, dynamic> data) async {
    final reference = _db.collection(collection).doc();
    await reference.set({
      ...data,
      'operation_id': reference.id,
      'status': 'pending',
      'request_status': 'pending',
      'schema_version': 2,
      'source': 'flutter',
      'offline_capable': true,
      'retry_count': 0,
      'created_at': FieldValue.serverTimestamp(),
      'updated_at': FieldValue.serverTimestamp(),
    });
    return reference.id;
  }

  static Stream<Map<String, dynamic>> syncHealthStream() {
    if (_useDemoMode) {
      return Stream.value({
        'status': 'demo',
        'last_seen': DateTime.now().toIso8601String(),
        'pending_count': 0,
        'failed_count': 0,
      });
    }
    return _db.collection('cafe').doc('sync_health').snapshots().map(
          (snapshot) => snapshot.data() ?? {},
        );
  }

  static Future<List<Map<String, dynamic>>> loadMobileRequestHistory() async {
    if (_useDemoMode) return const [];
    const collections = [
      'mobile_inventory_requests',
      'mobile_receipt_requests',
      'mobile_expense_requests',
    ];
    final results = <Map<String, dynamic>>[];
    for (final collection in collections) {
      QuerySnapshot<Map<String, dynamic>> snapshot;
      try {
        snapshot = await _db.collection(collection).limit(50).get();
      } catch (_) {
        snapshot = await _db
            .collection(collection)
            .limit(50)
            .get(const GetOptions(source: Source.cache));
      }
      for (final doc in snapshot.docs) {
        results.add({
          'document_id': doc.id,
          'collection': collection,
          ...doc.data(),
        });
      }
    }
    results.sort((a, b) => _requestMillis(b).compareTo(_requestMillis(a)));
    return results.take(100).toList();
  }

  static int _requestMillis(Map<String, dynamic> request) {
    final value = request['created_at'];
    if (value is Timestamp) return value.millisecondsSinceEpoch;
    return DateTime.tryParse(value?.toString() ?? '')?.millisecondsSinceEpoch ??
        0;
  }

  static Future<void> retryMobileRequest(
      String collection, String documentId) async {
    await _db.collection(collection).doc(documentId).set({
      'status': 'pending',
      'request_status': 'pending',
      'error_message': FieldValue.delete(),
      'retry_count': FieldValue.increment(1),
      'updated_at': FieldValue.serverTimestamp(),
    }, SetOptions(merge: true));
  }

  // Helpers
  static Map<String, dynamic> docData(dynamic snap) {
    if (snap is DocumentSnapshot) {
      return snap.exists ? (snap.data() as Map<String, dynamic>? ?? {}) : {};
    }
    if (snap is _MockDocumentSnapshot) {
      return snap.data;
    }
    return {};
  }

  static List<Map<String, dynamic>> asList(dynamic val) {
    if (val == null) return [];
    if (val is List) return val.cast<Map<String, dynamic>>();
    return [];
  }

  static double asDouble(dynamic v) {
    if (v == null) return 0;
    if (v is double) return v;
    if (v is int) return v.toDouble();
    if (v is String) return double.tryParse(v) ?? 0;
    return 0;
  }

  static int asInt(dynamic v) {
    if (v == null) return 0;
    if (v is int) return v;
    if (v is double) return v.toInt();
    if (v is String) return int.tryParse(v) ?? 0;
    return 0;
  }

  static List<Map<String, dynamic>> uiSections(Map<String, dynamic>? data) {
    final raw = data?['ui_sections'];
    if (raw is! List) return const [];

    return raw.whereType<Map>().map((section) {
      return Map<String, dynamic>.from(section);
    }).toList();
  }

  static Map<String, dynamic> extraFields(
    Map<String, dynamic> data, {
    Set<String> reservedKeys = const {},
  }) {
    final extras = <String, dynamic>{};

    for (final entry in data.entries) {
      if (reservedKeys.contains(entry.key)) continue;
      if (entry.key == 'ui_sections' ||
          entry.key == 'schema_version' ||
          entry.key == 'entity' ||
          entry.key == 'last_updated') {
        continue;
      }
      extras[entry.key] = entry.value;
    }

    return extras;
  }

  static String smartText(dynamic value) {
    if (value == null) return '-';
    if (value is Timestamp) {
      return value.toDate().toIso8601String();
    }
    if (value is bool) return value ? 'Yes' : 'No';
    if (value is num) return value.toString();
    if (value is String) return value;
    if (value is List) {
      return value.map(smartText).join(', ');
    }
    if (value is Map) {
      return value.entries
          .map((e) => '${e.key}: ${smartText(e.value)}')
          .join(' | ');
    }
    return value.toString();
  }

  static String formatDate(String? date, {bool includeTime = false}) {
    if (date == null || date.isEmpty) return '';

    try {
      final dateTime = DateTime.parse(date);
      final formatter =
          DateFormat(includeTime ? 'yyyy-MM-dd HH:mm' : 'yyyy-MM-dd');
      return formatter.format(dateTime);
    } catch (e) {
      // If parsing fails, return a safe substring
      if (date.length >= 10) {
        return includeTime && date.length >= 16
            ? date.substring(0, 16)
            : date.substring(0, 10);
      }
      return date;
    }
  }

  static String formatTime(String? date) {
    if (date == null || date.isEmpty) return '';

    try {
      final dateTime = DateTime.parse(date);
      final formatter = DateFormat('HH:mm');
      return formatter.format(dateTime);
    } catch (e) {
      // If parsing fails, try to extract time portion
      if (date.length >= 16) {
        return date.substring(11, 16);
      } else if (date.length >= 5) {
        return date.substring(date.length - 5);
      }
      return date;
    }
  }
}

/// Mock DocumentSnapshot for demo mode
class _MockDocumentSnapshot {
  final Map<String, dynamic> _data;

  _MockDocumentSnapshot(this._data);

  Map<String, dynamic> get data => _data;
  bool get exists => true;
}
