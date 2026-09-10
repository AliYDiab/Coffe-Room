import 'dart:async';

import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';

class RequestHistoryScreen extends StatefulWidget {
  const RequestHistoryScreen({super.key});

  @override
  State<RequestHistoryScreen> createState() => _RequestHistoryScreenState();
}

class _RequestHistoryScreenState extends State<RequestHistoryScreen> {
  List<Map<String, dynamic>> _requests = const [];
  bool _loading = true;
  String? _error;
  Timer? _refreshTimer;

  @override
  void initState() {
    super.initState();
    _load();
    _refreshTimer = Timer.periodic(const Duration(seconds: 15), (_) => _load());
  }

  @override
  void dispose() {
    _refreshTimer?.cancel();
    super.dispose();
  }

  Future<void> _load() async {
    try {
      final requests = await FirebaseService.loadMobileRequestHistory();
      if (!mounted) return;
      setState(() {
        _requests = requests;
        _loading = false;
        _error = null;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = 'تعذر تحميل سجل الطلبات. تحقق من الاتصال.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _healthCard(),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _load,
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? ListView(children: [
                        const SizedBox(height: 100),
                        Center(child: Text(_error!)),
                      ])
                    : _requests.isEmpty
                        ? ListView(children: const [
                            SizedBox(height: 100),
                            Center(child: Text('لا توجد طلبات من الهاتف بعد')),
                          ])
                        : ListView.builder(
                            padding: const EdgeInsets.all(12),
                            itemCount: _requests.length,
                            itemBuilder: (_, index) =>
                                _requestCard(_requests[index]),
                          ),
          ),
        ),
      ],
    );
  }

  Widget _healthCard() {
    return StreamBuilder<Map<String, dynamic>>(
      stream: FirebaseService.syncHealthStream(),
      builder: (context, snapshot) {
        final data = snapshot.data ?? const <String, dynamic>{};
        final lastSeen = _asDate(data['last_seen']);
        final age =
            lastSeen == null ? null : DateTime.now().difference(lastSeen);
        final connected = snapshot.hasData &&
            !snapshot.hasError &&
            age != null &&
            age.inMinutes < 2 &&
            data['status'] != 'error';
        final color = connected ? AppTheme.primary : AppTheme.danger;
        final pending = FirebaseService.asInt(data['pending_count']);
        final failed = FirebaseService.asInt(data['failed_count']);

        return Container(
          margin: const EdgeInsets.fromLTRB(12, 12, 12, 0),
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.12),
            borderRadius: BorderRadius.circular(14),
            border: Border.all(color: color.withValues(alpha: 0.4)),
          ),
          child: Row(children: [
            Icon(connected ? Icons.cloud_done : Icons.cloud_off, color: color),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    connected
                        ? 'المزامنة مع الكمبيوتر تعمل'
                        : 'تنبيه: الكمبيوتر غير متصل بالمزامنة',
                    style: TextStyle(color: color, fontWeight: FontWeight.bold),
                  ),
                  Text('قيد الانتظار: $pending  •  فاشلة: $failed',
                      style: const TextStyle(
                          color: AppTheme.textMuted, fontSize: 12)),
                ],
              ),
            ),
          ]),
        );
      },
    );
  }

  Widget _requestCard(Map<String, dynamic> request) {
    final status = (request['request_status'] ?? request['status'] ?? 'pending')
        .toString();
    final color = status == 'synced'
        ? AppTheme.primary
        : status == 'error'
            ? AppTheme.danger
            : AppTheme.warning;
    final statusText = status == 'synced'
        ? 'تمت المزامنة'
        : status == 'error'
            ? 'فشل'
            : 'قيد الانتظار';
    final collection = request['collection']?.toString() ?? '';
    final type = collection.contains('inventory')
        ? 'المخزون'
        : collection.contains('receipt')
            ? 'فاتورة'
            : 'مصروف';
    final date = _asDate(request['created_at']);

    return Card(
      color: AppTheme.surface,
      margin: const EdgeInsets.only(bottom: 8),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(children: [
          Icon(Icons.circle, size: 10, color: color),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('$type — $statusText',
                    style: const TextStyle(fontWeight: FontWeight.bold)),
                if (date != null)
                  Text(
                    '${date.year}-${date.month.toString().padLeft(2, '0')}-${date.day.toString().padLeft(2, '0')} '
                    '${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}',
                    style: const TextStyle(
                        color: AppTheme.textMuted, fontSize: 11),
                  ),
                if (status == 'error')
                  Text(request['error_message_ar']?.toString() ??
                      'تعذر تنفيذ الطلب على الكمبيوتر'),
              ],
            ),
          ),
          if (status == 'error')
            TextButton.icon(
              onPressed: () async {
                await FirebaseService.retryMobileRequest(
                  collection,
                  request['document_id'].toString(),
                );
                await _load();
              },
              icon: const Icon(Icons.refresh),
              label: const Text('إعادة المحاولة'),
            ),
        ]),
      ),
    );
  }

  DateTime? _asDate(dynamic value) {
    if (value is Timestamp) return value.toDate();
    return DateTime.tryParse(value?.toString() ?? '');
  }
}
