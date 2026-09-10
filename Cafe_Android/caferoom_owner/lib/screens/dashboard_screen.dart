import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/AppFirebaseService.dart';
import '../services/alerts_service.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({super.key});

  String _fmt(double v) =>
      '${NumberFormat('#,##0', 'ar').format(v)} SYP';

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.dashboardStream(),
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
          return const Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                CircularProgressIndicator(color: AppTheme.primary),
                SizedBox(height: 16),
                Text('جاري تحميل البيانات...',
                  style: TextStyle(color: AppTheme.textMuted)),
                SizedBox(height: 8),
                Text('إذا استغرق الأمر وقتاً طويلاً، تأكد من اتصال الإنترنت',
                  style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
              ],
            ),
          );
        }

        final d = FirebaseService.docData(snap.data!);
        final todayRev   = FirebaseService.asDouble(d['today_revenue']);
        final todayOrd   = FirebaseService.asInt(d['today_orders']);
        final totalRev   = FirebaseService.asDouble(d['total_revenue']);
        final debtRem    = FirebaseService.asDouble(d['debt_remaining']);
        final lowStock   = FirebaseService.asInt(d['low_stock_count']);
        final outStock   = FirebaseService.asInt(d['out_stock_count']);
        final wasteCount = FirebaseService.asInt(d['waste_today_count']);
        final topItems   = FirebaseService.asList(d['top_items_today']);
        final updated    = FirebaseService.formatTime(d['last_updated'] as String?);

        return RefreshIndicator(
          color: AppTheme.primary,
          onRefresh: () async {
            await Future.delayed(const Duration(seconds: 1));
          },
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // ── last updated ──
              Row(children: [
                const Icon(Icons.circle, size: 8, color: AppTheme.primary),
                const SizedBox(width: 6),
                Text('آخر تحديث: $updated',
                  style: const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
              ]),
              const SizedBox(height: 16),

              // ── today stats ──
              const SectionTitle('☕ اليوم'),
              GridView.count(
                crossAxisCount: 2,
                shrinkWrap: true,
                physics: const NeverScrollableScrollPhysics(),
                crossAxisSpacing: 12,
                mainAxisSpacing: 12,
                childAspectRatio: 1.4,
                children: [
                  StatCard(
                    label: 'إيرادات اليوم',
                    value: _fmt(todayRev),
                    icon: Icons.attach_money,
                    color: AppTheme.primary,
                    sub: '$todayOrd طلب',
                  ),
                  StatCard(
                    label: 'إجمالي الإيرادات',
                    value: _fmt(totalRev),
                    icon: Icons.bar_chart,
                    color: AppTheme.accent,
                  ),
                  StatCard(
                    label: 'الديون المتبقية',
                    value: _fmt(debtRem),
                    icon: Icons.credit_card,
                    color: debtRem > 0 ? AppTheme.warning : AppTheme.primary,
                  ),
                  StatCard(
                    label: 'هدر اليوم',
                    value: '$wasteCount تسجيل',
                    icon: Icons.delete_outline,
                    color: AppTheme.danger,
                  ),
                ],
              ),

              const SizedBox(height: 8),

              // ── stock alerts ──
              if (outStock > 0)
                _alertCard(
                  '🚨 نفاد مخزون',
                  '$outStock عنصر نفد من المخزون',
                  AppTheme.danger,
                ),
              if (lowStock > 0)
                _alertCard(
                  '⚠️ مخزون منخفض',
                  '$lowStock عنصر وصل للحد الأدنى',
                  AppTheme.warning,
                ),

              // ── performance insights ──
              const SectionTitle('💡 رؤى الأداء'),
              _buildPerformanceInsights(d),

              const SizedBox(height: 16),

              // ── top items today ──
              if (topItems.isNotEmpty) ...[
                const SectionTitle('🔥 الأكثر مبيعاً اليوم'),
                ...topItems.asMap().entries.map((e) {
                  final i    = e.key;
                  final item = e.value;
                  final rev  = FirebaseService.asDouble(item['revenue']);
                  final qty  = FirebaseService.asInt(item['qty']);
                  return Container(
                    margin: const EdgeInsets.only(bottom: 8),
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Row(children: [
                      Container(
                        width: 30, height: 30,
                        decoration: BoxDecoration(
                          color: _rankColor(i).withValues(alpha: 0.2),
                          shape: BoxShape.circle,
                        ),
                        child: Center(
                          child: Text('${i + 1}',
                            style: TextStyle(
                              color: _rankColor(i),
                              fontWeight: FontWeight.bold,
                              fontSize: 13,
                            )),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Text(item['name'] ?? '',
                          style: const TextStyle(fontWeight: FontWeight.w600)),
                      ),
                      Text('$qty وحدة',
                        style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
                      const SizedBox(width: 12),
                      Text(_fmt(rev),
                        style: const TextStyle(
                          color: AppTheme.primary, fontWeight: FontWeight.bold)),
                    ]),
                  );
                }),
              ],
            ],
          ),
        );
      },
    );
  }

  Color _rankColor(int i) {
    if (i == 0) return AppTheme.warning;
    if (i == 1) return AppTheme.textMuted;
    if (i == 2) return const Color(0xFFb45309);
    return AppTheme.accent;
  }

  Widget _alertCard(String title, String body, Color color) => Container(
    margin: const EdgeInsets.only(bottom: 8),
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.1),
      borderRadius: BorderRadius.circular(12),
      border: Border.all(color: color.withValues(alpha: 0.3)),
    ),
    child: Row(children: [
      Icon(Icons.warning_amber, color: color),
      const SizedBox(width: 10),
      Expanded(child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: TextStyle(color: color, fontWeight: FontWeight.bold)),
          Text(body,  style: const TextStyle(color: AppTheme.textMuted, fontSize: 13)),
        ],
      )),
    ]),
  );

  Widget _buildPerformanceInsights(Map<String, dynamic> dashboardData) {
    final insights = AlertsService.generateRecommendations(dashboardData, {});
    
    if (insights.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
        ),
        child: const Center(
          child: Text('لا توجد رؤى حالياً',
            style: TextStyle(color: AppTheme.textMuted)),
        ),
      );
    }
    
    return Column(
      children: insights.take(3).map((insight) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: AppTheme.primary.withValues(alpha: 0.2)),
        ),
        child: Row(
          children: [
            Icon(Icons.lightbulb_outline, 
              size: 20, 
              color: AppTheme.accent),
            const SizedBox(width: 10),
            Expanded(
              child: Text(insight,
                style: const TextStyle(fontSize: 13)),
            ),
          ],
        ),
      )).toList(),
    );
  }
}