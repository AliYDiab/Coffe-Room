import 'package:flutter/material.dart';
import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class FlexibleFirestoreScreen extends StatefulWidget {
  const FlexibleFirestoreScreen({super.key});

  @override
  State<FlexibleFirestoreScreen> createState() => _FlexibleFirestoreScreenState();
}

class _FlexibleFirestoreScreenState extends State<FlexibleFirestoreScreen> with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  final _collections = const [
    _CollectionSpec('workers', 'العمال', Icons.people_outline, 'لا يوجد عمال'),
    _CollectionSpec('shift_schedules', 'الورديات', Icons.schedule_outlined, 'لا توجد ورديات'),
    _CollectionSpec('shift_sessions', 'الجلسات', Icons.playlist_add_check_outlined, 'لا توجد جلسات'),
    _CollectionSpec('worker_ratings', 'التقييمات', Icons.star_outline, 'لا توجد تقييمات'),
    _CollectionSpec('shift_handover', 'التسليم', Icons.swap_horiz_outlined, 'لا يوجد تسليم ورديات'),
  ];

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: _collections.length, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(bottom: BorderSide(color: AppTheme.surface2)),
          ),
          child: TabBar(
            controller: _tabs,
            isScrollable: true,
            indicatorColor: AppTheme.primary,
            labelColor: AppTheme.primary,
            unselectedLabelColor: AppTheme.textMuted,
            tabs: _collections.map((spec) => Tab(text: spec.title, icon: Icon(spec.icon, size: 18))).toList(),
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabs,
            children: _collections.map(_buildCollectionView).toList(),
          ),
        ),
      ],
    );
  }

  Widget _buildCollectionView(_CollectionSpec spec) {
    return StreamBuilder<List<Map<String, dynamic>>>(
      stream: FirebaseService.collectionDataStream(spec.collection),
      builder: (context, snap) {
        if (snap.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: AppTheme.danger, size: 48),
                const SizedBox(height: 16),
                Text('خطأ في الاتصال: ${snap.error}',
                  style: const TextStyle(color: AppTheme.textMuted),
                  textAlign: TextAlign.center),
              ],
            ),
          );
        }

        if (!snap.hasData) {
          return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
        }

        final docs = snap.data!;

        if (docs.isEmpty) {
          return EmptyState(message: spec.emptyMessage, icon: spec.icon);
        }

        return ListView.builder(
          padding: const EdgeInsets.all(16),
          itemCount: docs.length,
          itemBuilder: (_, index) => _collectionCard(docs[index], spec),
        );
      },
    );
  }

  Widget _collectionCard(Map<String, dynamic> doc, _CollectionSpec spec) {
    final title = _primaryTitle(doc, spec.collection);
    final subtitle = _primarySubtitle(doc, spec.collection);
    final extras = FirebaseService.extraFields(doc, reservedKeys: {'id'});

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      child: Material(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        clipBehavior: Clip.antiAlias,
        child: Container(
          decoration: BoxDecoration(
            border: Border.all(color: AppTheme.surface2),
            borderRadius: BorderRadius.circular(16),
          ),
          child: ExpansionTile(
            tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            leading: CircleAvatar(
              backgroundColor: AppTheme.primary.withValues(alpha: 0.15),
              child: Icon(spec.icon, color: AppTheme.primary, size: 20),
            ),
            title: Text(title, style: const TextStyle(fontWeight: FontWeight.bold)),
            subtitle: subtitle.isEmpty
              ? null
              : Text(subtitle, style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
            children: [
              if (extras.isNotEmpty) ...[
                const Align(
                  alignment: Alignment.centerLeft,
                  child: Text('الحقول', style: TextStyle(fontWeight: FontWeight.bold, color: Colors.white)),
                ),
                const SizedBox(height: 10),
                ...extras.entries.map((entry) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: InfoRow(
                    entry.key,
                    FirebaseService.smartText(entry.value),
                    valueColor: AppTheme.primary,
                  ),
                )),
              ],
              if (extras.isEmpty)
                const Text('لا توجد حقول إضافية', style: TextStyle(color: AppTheme.textMuted)),
            ],
          ),
        ),
      ),
    );
  }

  String _primaryTitle(Map<String, dynamic> doc, String collection) {
    switch (collection) {
      case 'workers':
        return doc['name'] as String? ?? 'عامل #${doc['id'] ?? ''}';
      case 'shift_schedules':
        return doc['name'] as String? ?? 'وردية #${doc['id'] ?? ''}';
      case 'shift_sessions':
        return '${doc['worker_name'] ?? 'جلسة'} - ${doc['schedule_name'] ?? ''}'.trim();
      case 'worker_ratings':
        return doc['worker_name'] as String? ?? 'تقييم #${doc['id'] ?? ''}';
      case 'shift_handover':
        return '${doc['from_cashier_name'] ?? 'وردية'} → ${doc['to_cashier_name'] ?? ''}'.trim();
      default:
        return 'وثيقة';
    }
  }

  String _primarySubtitle(Map<String, dynamic> doc, String collection) {
    switch (collection) {
      case 'workers':
        return 'التقييم: ${FirebaseService.asDouble(doc['rating']).toStringAsFixed(1)} • ${FirebaseService.asInt(doc['total_ratings'])} تقييم';
      case 'shift_schedules':
        return 'من ${doc['start_hour']} إلى ${doc['end_hour']} • ${doc['shift_type'] ?? ''}';
      case 'shift_sessions':
        return '${doc['date'] ?? ''} • ${doc['status'] ?? ''} • ${FirebaseService.asDouble(doc['total_revenue']).toStringAsFixed(0)} SYP';
      case 'worker_ratings':
        return 'التقييم: ${FirebaseService.asInt(doc['rating'])} نجوم • ${doc['created_by'] ?? ''}';
      case 'shift_handover':
        return 'المبلغ: ${FirebaseService.asDouble(doc['cash_handover']).toStringAsFixed(0)} SYP';
      default:
        return '';
    }
  }
}

class _CollectionSpec {
  final String collection;
  final String title;
  final IconData icon;
  final String emptyMessage;

  const _CollectionSpec(this.collection, this.title, this.icon, this.emptyMessage);
}