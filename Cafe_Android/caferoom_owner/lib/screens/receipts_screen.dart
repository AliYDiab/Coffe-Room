import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class ReceiptsScreen extends StatefulWidget {
  const ReceiptsScreen({super.key});
  @override
  State<ReceiptsScreen> createState() => _ReceiptsScreenState();
}

class _ReceiptsScreenState extends State<ReceiptsScreen> {
  String _filter = 'الكل'; // الكل / مدفوع / دين / جزئي

  String _fmt(double v) => '${NumberFormat('#,##0', 'ar').format(v)} SYP';

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.receiptsStream(),
      builder: (ctx, snap) {
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
        if (!snap.hasData) return const Center(child: CircularProgressIndicator(color: AppTheme.primary));

        final d    = FirebaseService.docData(snap.data!);
        var list   = FirebaseService.asList(d['list']);

        if (_filter != 'الكل') {
          final map = {'مدفوع': 'paid', 'دين': 'debt', 'جزئي': 'partial'};
          list = list.where((r) => (r['status'] ?? 'paid') == map[_filter]).toList();
        }

        return Column(
          children: [
            // ── filter ──
            Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: ['الكل', 'مدفوع', 'دين', 'جزئي'].map((f) =>
                  Expanded(child: GestureDetector(
                    onTap: () => setState(() => _filter = f),
                    child: Container(
                      margin: const EdgeInsets.only(right: 6),
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      decoration: BoxDecoration(
                        color: _filter == f
                          ? _filterColor(f).withValues(alpha: 0.2)
                          : AppTheme.surface,
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(
                          color: _filter == f ? _filterColor(f) : Colors.transparent),
                      ),
                      child: Text(f,
                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: _filter == f ? _filterColor(f) : AppTheme.textMuted,
                          fontWeight: FontWeight.bold,
                          fontSize: 13,
                        )),
                    ),
                  ))
                ).toList(),
              ),
            ),

            Expanded(
              child: list.isEmpty
                ? const EmptyState(message: 'لا توجد فواتير', icon: Icons.receipt_long)
                : ListView.builder(
                    padding: const EdgeInsets.symmetric(horizontal: 12),
                    itemCount: list.length,
                    itemBuilder: (_, i) => _receiptCard(list[i]),
                  ),
            ),
          ],
        );
      },
    );
  }

  Widget _receiptCard(Map<String, dynamic> r) {
    final id       = FirebaseService.asInt(r['id']);
    final total    = FirebaseService.asDouble(r['total']);
    final status   = r['status'] as String? ?? 'paid';
    final customer = r['customer'] as String?;
    final date     = r['date']    as String? ?? '';
    final items    = FirebaseService.asList(r['items']);

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: ExpansionTile(
        tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
        leading: Container(
          width: 40, height: 40,
          decoration: BoxDecoration(
            color: AppTheme.surface2,
            borderRadius: BorderRadius.circular(10),
          ),
          child: Center(
            child: Text('#$id',
              style: const TextStyle(
                fontWeight: FontWeight.bold, fontSize: 12, color: AppTheme.textMuted)),
          ),
        ),
        title: Row(children: [
          Expanded(
            child: Text(_fmt(total),
              style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15))),
          StatusBadge(status),
        ]),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (customer != null)
              Text('👤 $customer',
                style: const TextStyle(color: AppTheme.warning, fontSize: 12)),
            Text(FirebaseService.formatDate(date, includeTime: true),
              style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
          ],
        ),
        children: [
          const Divider(color: AppTheme.surface2),
          ...items.map((item) => Padding(
            padding: const EdgeInsets.symmetric(vertical: 3),
            child: Row(children: [
              Expanded(
                child: Text(item['name'] ?? '',
                  style: const TextStyle(fontSize: 13))),
              Text('× ${item['qty']}',
                style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
              const SizedBox(width: 12),
              Text(_fmt(FirebaseService.asDouble(item['price'])),
                style: const TextStyle(color: AppTheme.primary, fontSize: 13)),
            ]),
          )),
        ],
      ),
    );
  }

  Color _filterColor(String f) {
    switch (f) {
      case 'دين':   return AppTheme.warning;
      case 'جزئي':  return AppTheme.accent;
      case 'مدفوع': return AppTheme.primary;
      default:      return AppTheme.textMuted;
    }
  }
}