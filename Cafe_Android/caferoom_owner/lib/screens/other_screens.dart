import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class DebtsScreen extends StatelessWidget {
  const DebtsScreen({super.key});
  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.debtsStream(),
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
        if (!snap.hasData) {
          return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
        }

        final d = FirebaseService.docData(snap.data!);
        final debts = FirebaseService.asList(d['list']);

        return debts.isEmpty
          ? const Center(child: Text('لا توجد ديون', style: TextStyle(color: AppTheme.textMuted)))
          : ListView.builder(
              padding: const EdgeInsets.all(16),
              itemCount: debts.length,
              itemBuilder: (_, i) => _debtCard(debts[i]),
            );
      },
    );
  }

  Widget _debtCard(Map<String, dynamic> d) {
    final customer = d['customer'] as String? ?? '';
    final amount = FirebaseService.asDouble(d['amount']);
    final paid = FirebaseService.asDouble(d['paid']);
    final remaining = FirebaseService.asDouble(d['remaining']);
    final note = d['note'] as String?;
    final date = d['created_at'] as String? ?? '';
    final receiptId = d['receipt_id'];
    final payments = FirebaseService.asList(d['payments']);
    final isSettled = remaining <= 0;
    final pct = amount > 0 ? (paid / amount).clamp(0.0, 1.0) : 0.0;

    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      child: Material(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        clipBehavior: Clip.antiAlias,
        child: Container(
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(14),
            border: Border.all(
              color: isSettled ? AppTheme.primary.withValues(alpha: 0.3) : Colors.transparent,
            ),
          ),
          child: ExpansionTile(
            tilePadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
            leading: CircleAvatar(
              backgroundColor: isSettled
                  ? AppTheme.primary.withValues(alpha: 0.2)
                  : AppTheme.warning.withValues(alpha: 0.2),
              child: Text(
                customer.isNotEmpty ? customer[0] : '؟',
                style: TextStyle(
                  color: isSettled ? AppTheme.primary : AppTheme.warning,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
            title: Text(customer, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            subtitle: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: pct,
                    minHeight: 6,
                    backgroundColor: AppTheme.surface2,
                    valueColor: AlwaysStoppedAnimation(
                      isSettled ? AppTheme.primary : AppTheme.warning,
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  isSettled ? '✅ مسدد بالكامل' : 'متبقي: ${_fmt(remaining)}  من  ${_fmt(amount)}',
                  style: TextStyle(
                    color: isSettled ? AppTheme.primary : AppTheme.danger,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
            trailing: isSettled ? const Icon(Icons.check_circle, color: AppTheme.primary) : null,
            children: [
              if (receiptId != null) InfoRow('فاتورة', '#$receiptId', valueColor: AppTheme.accent),
              InfoRow('تاريخ الدين', FirebaseService.formatDate(date), valueColor: AppTheme.textMuted),
              if (note != null && note.isNotEmpty) InfoRow('ملاحظة', note, valueColor: AppTheme.textMuted),
              InfoRow('المبلغ الكلي', _fmt(amount), valueColor: AppTheme.textMuted),
              InfoRow('المدفوع', _fmt(paid), valueColor: AppTheme.primary),
              if (!isSettled) InfoRow('المتبقي', _fmt(remaining), valueColor: AppTheme.danger),
              if (payments.isNotEmpty) ...[
                const SizedBox(height: 8),
                const Text('سجل الدفعات:', style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                const SizedBox(height: 4),
                ...payments.map((p) {
                  final pAmt = FirebaseService.asDouble(p['amount']);
                  final pDate = p['paid_at'] as String? ?? '';
                  final pNote = p['note'] as String?;
                  return Padding(
                    padding: const EdgeInsets.symmetric(vertical: 2),
                    child: Row(
                      children: [
                        const Icon(Icons.arrow_forward_ios, size: 10, color: AppTheme.primary),
                        const SizedBox(width: 6),
                        Text(
                          FirebaseService.formatDate(pDate, includeTime: true),
                          style: const TextStyle(color: AppTheme.textMuted, fontSize: 12),
                        ),
                        const Spacer(),
                        Text(_fmt(pAmt), style: const TextStyle(color: AppTheme.primary, fontSize: 12)),
                        if (pNote != null && pNote.isNotEmpty) ...[
                          const SizedBox(width: 6),
                          Text('($pNote)', style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                        ],
                      ],
                    ),
                  );
                }),
              ],
            ],
          ),
        ),
      ),
    );
  }

  String _fmt(double value) => value.toStringAsFixed(0);
}


// =====================================================
// WASTE SCREEN
// =====================================================
class WasteScreen extends StatefulWidget {
  const WasteScreen({super.key});
  @override
  State<WasteScreen> createState() => _WasteScreenState();
}

class _WasteScreenState extends State<WasteScreen>
    with SingleTickerProviderStateMixin {
  late TabController _tabs;

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 2, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.wasteStream(),
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

        final d        = FirebaseService.docData(snap.data!);
        final log      = FirebaseService.asList(d['log']);
        final topItems = FirebaseService.asList(d['top_items']);
        final byReason = FirebaseService.asList(d['by_reason']);
        final maxQty   = topItems.isNotEmpty
          ? FirebaseService.asDouble(topItems.first['total_qty'])
          : 1.0;

        return Column(
          children: [
            TabBar(
              controller: _tabs,
              indicatorColor: AppTheme.danger,
              labelColor: AppTheme.danger,
              unselectedLabelColor: AppTheme.textMuted,
              tabs: const [
                Tab(text: 'سجل الهدر'),
                Tab(text: 'إحصائيات'),
              ],
            ),
            Expanded(
              child: TabBarView(
                controller: _tabs,
                children: [
                  // ── LOG TAB ──
                  log.isEmpty
                    ? const EmptyState(message: 'لا يوجد هدر', icon: Icons.delete_forever)
                    : ListView.builder(
                        padding: const EdgeInsets.all(12),
                        itemCount: log.length,
                        itemBuilder: (_, i) {
                          final w    = log[i];
                          final name = w['item_name'] as String? ?? '';
                          final qty  = FirebaseService.asDouble(w['quantity']);
                          final reason = w['reason'] as String? ?? '—';
                          final date   = w['logged_at'] as String? ?? '';
                          return Container(
                            margin: const EdgeInsets.only(bottom: 8),
                            padding: const EdgeInsets.all(14),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(12),
                            ),
                            child: Row(children: [
                              const Icon(Icons.delete_outline,
                                color: AppTheme.danger, size: 20),
                              const SizedBox(width: 10),
                              Expanded(child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(name,
                                    style: const TextStyle(
                                      fontWeight: FontWeight.bold)),
                                  Text(reason,
                                    style: const TextStyle(
                                      color: AppTheme.textMuted, fontSize: 12)),
                                  Text(FirebaseService.formatDate(date, includeTime: true),
                                    style: const TextStyle(
                                      color: AppTheme.textMuted, fontSize: 11)),
                                ],
                              )),
                              Text('${qty.toStringAsFixed(qty.truncateToDouble() == qty ? 0 : 1)} وحدة',
                                style: const TextStyle(
                                  color: AppTheme.warning,
                                  fontWeight: FontWeight.bold)),
                            ]),
                          );
                        }),

                  // ── STATS TAB ──
                  ListView(
                    padding: const EdgeInsets.all(12),
                    children: [
                      const SectionTitle('🏆 أكثر العناصر هدراً'),
                      ...topItems.asMap().entries.map((e) {
                        final i    = e.key;
                        final item = e.value;
                        final qty  = FirebaseService.asDouble(item['total_qty']);
                        final pct  = maxQty > 0 ? qty / maxQty : 0.0;
                        return Container(
                          margin: const EdgeInsets.only(bottom: 8),
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: AppTheme.surface,
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(children: [
                                Text('#${i + 1} ',
                                  style: TextStyle(
                                    color: i == 0 ? AppTheme.danger : AppTheme.warning,
                                    fontWeight: FontWeight.bold,
                                  )),
                                Expanded(
                                  child: Text(item['item_name'] ?? '',
                                    style: const TextStyle(fontWeight: FontWeight.w600))),
                                Text('${qty.toStringAsFixed(0)} وحدة',
                                  style: const TextStyle(
                                    color: AppTheme.warning, fontSize: 13)),
                              ]),
                              const SizedBox(height: 8),
                              ClipRRect(
                                borderRadius: BorderRadius.circular(4),
                                child: LinearProgressIndicator(
                                  value: pct.toDouble(),
                                  minHeight: 6,
                                  backgroundColor: AppTheme.surface2,
                                  valueColor: AlwaysStoppedAnimation(
                                    i == 0 ? AppTheme.danger : AppTheme.warning),
                                ),
                              ),
                            ],
                          ),
                        );
                      }),

                      const SectionTitle('📝 الأسباب'),
                      ...byReason.map((r) => Container(
                        margin: const EdgeInsets.only(bottom: 6),
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: AppTheme.surface,
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Row(children: [
                          Expanded(
                            child: Text(r['reason'] ?? '—',
                              style: const TextStyle(fontSize: 13))),
                          Text('${r['count']} مرة',
                            style: const TextStyle(
                              color: AppTheme.textMuted, fontSize: 12)),
                          const SizedBox(width: 10),
                          Text('${FirebaseService.asDouble(r['total_qty']).toStringAsFixed(0)} وحدة',
                            style: const TextStyle(
                              color: AppTheme.warning, fontSize: 12)),
                        ]),
                      )),
                    ],
                  ),
                ],
              ),
            ),
          ],
        );
      },
    );
  }
}


// =====================================================
// ANALYTICS SCREEN
// =====================================================
class AnalyticsScreen extends StatefulWidget {
  const AnalyticsScreen({super.key});
  @override
  State<AnalyticsScreen> createState() => _AnalyticsScreenState();
}

class _AnalyticsScreenState extends State<AnalyticsScreen> {
  String _period = '7';
  String _fmt(double v) => '${NumberFormat('#,##0', 'ar').format(v)} SYP';

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.analyticsStream(),
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

        final d          = FirebaseService.docData(snap.data!);
        final days7      = FirebaseService.asList(d['last_7_days']);
        final days30     = FirebaseService.asList(d['last_30_days']);
        final topItems   = FirebaseService.asList(d['top_items']);
        final hourly     = FirebaseService.asList(d['hourly']);
        final byCategory = FirebaseService.asList(d['by_category']);

        final days     = _period == '7' ? days7 : days30;
        final totalRev = days.fold<double>(
          0, (s, d) => s + FirebaseService.asDouble(d['revenue']));
        final totalOrd = days.fold<int>(
          0, (s, d) => s + FirebaseService.asInt(d['orders']));

        // peak hour
        String peakHour = '—';
        if (hourly.isNotEmpty) {
          final peak = hourly.reduce((a, b) =>
            FirebaseService.asInt(a['orders']) >= FirebaseService.asInt(b['orders']) ? a : b);
          final h = FirebaseService.asInt(peak['hour']);
          peakHour = '${h.toString().padLeft(2, '0')}:00';
        }

        return ListView(
          padding: const EdgeInsets.all(12),
          children: [
            // period toggle
            Row(
              children: ['7', '30'].map((p) => Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _period = p),
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.symmetric(vertical: 10),
                    decoration: BoxDecoration(
                      color: _period == p
                        ? AppTheme.accent.withValues(alpha: 0.2)
                        : AppTheme.surface,
                      borderRadius: BorderRadius.circular(10),
                      border: Border.all(
                        color: _period == p ? AppTheme.accent : Colors.transparent),
                    ),
                    child: Text('آخر $p أيام',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: _period == p ? AppTheme.accent : AppTheme.textMuted,
                        fontWeight: FontWeight.bold,
                      )),
                  ),
                ),
              )).toList(),
            ),

            const SizedBox(height: 16),

            // summary
            Row(children: [
              Expanded(child: StatCard(
                label: 'الإيرادات',
                value: _fmt(totalRev),
                icon: Icons.attach_money,
                color: AppTheme.primary,
              )),
              const SizedBox(width: 12),
              Expanded(child: StatCard(
                label: 'الطلبات',
                value: '$totalOrd',
                icon: Icons.receipt,
                color: AppTheme.accent,
                sub: 'ساعة الذروة: $peakHour',
              )),
            ]),

            const SizedBox(height: 16),

            // daily chart (simple bar)
            const SectionTitle('📈 المبيعات اليومية'),
            _barChart(days),

            // top items
            const SectionTitle('🏆 الأكثر مبيعاً (الكل)'),
            ...topItems.asMap().entries.map((e) {
              final i    = e.key;
              final item = e.value;
              final rev  = FirebaseService.asDouble(item['total_revenue']);
              final qty  = FirebaseService.asInt(item['total_qty']);
              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(14),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(children: [
                  SizedBox(
                    width: 30,
                    child: Text('#${i + 1}',
                      style: TextStyle(
                        color: i == 0 ? AppTheme.warning : AppTheme.textMuted,
                        fontWeight: FontWeight.bold,
                      )),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(item['name'] ?? '',
                      style: const TextStyle(fontWeight: FontWeight.w600))),
                  Text('$qty وحدة',
                    style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                  const SizedBox(width: 10),
                  Text(_fmt(rev),
                    style: const TextStyle(
                      color: AppTheme.primary, fontWeight: FontWeight.bold, fontSize: 13)),
                ]),
              );
            }),

            // category
            if (byCategory.isNotEmpty) ...[
              const SectionTitle('📂 حسب الفئة'),
              ...byCategory.map((c) {
                final rev = FirebaseService.asDouble(c['revenue']);
                return Container(
                  margin: const EdgeInsets.only(bottom: 6),
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    color: AppTheme.surface,
                    borderRadius: BorderRadius.circular(10),
                  ),
                  child: Row(children: [
                    Expanded(
                      child: Text(c['category'] ?? '—',
                        style: const TextStyle(fontWeight: FontWeight.w600))),
                    Text(_fmt(rev),
                      style: const TextStyle(color: AppTheme.primary)),
                  ]),
                );
              }),
            ],
          ],
        );
      },
    );
  }

  Widget _barChart(List<Map<String, dynamic>> days) {
    if (days.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text('لا توجد بيانات',
            style: TextStyle(color: AppTheme.textMuted)),
        ),
      );
    }

    final maxRev = days.fold<double>(
      0, (m, d) => FirebaseService.asDouble(d['revenue']) > m
        ? FirebaseService.asDouble(d['revenue']) : m);

    return Container(
      height: 160,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: days.map((d) {
          final rev = FirebaseService.asDouble(d['revenue']);
          final pct = maxRev > 0 ? rev / maxRev : 0.0;
          final day = (d['day'] as String? ?? '').length >= 10
            ? (d['day'] as String).substring(5) : d['day'] ?? '';

          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Flexible(
                    child: FractionallySizedBox(
                      heightFactor: pct.toDouble().clamp(0.02, 1.0),
                      child: Container(
                        decoration: BoxDecoration(
                          color: AppTheme.primary.withValues(alpha: 0.7),
                          borderRadius: BorderRadius.circular(4),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(day,
                    style: const TextStyle(
                      color: AppTheme.textMuted, fontSize: 9),
                    overflow: TextOverflow.ellipsis),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}