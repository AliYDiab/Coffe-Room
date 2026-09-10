import 'package:flutter/material.dart';
import '../services/AppFirebaseService.dart';
import '../services/analytics_service.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class FinancialAnalyticsScreen extends StatefulWidget {
  const FinancialAnalyticsScreen({super.key});

  @override
  State<FinancialAnalyticsScreen> createState() =>
      _FinancialAnalyticsScreenState();
}

class _FinancialAnalyticsScreenState extends State<FinancialAnalyticsScreen> {
  String _period = '30'; // 7, 30, 90 days

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
                const Icon(Icons.error_outline,
                    color: AppTheme.danger, size: 48),
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
              child: CircularProgressIndicator(color: AppTheme.primary));
        }

        final d = FirebaseService.docData(snap.data!);
        final days7 = FirebaseService.asList(d['last_7_days']);
        final days30 = FirebaseService.asList(d['last_30_days']);
        final days90 = FirebaseService.asList(d['last_90_days'] ?? []);

        final days = _period == '7'
            ? days7
            : _period == '30'
                ? days30
                : days90;

        // Calculate financial metrics
        final totalRevenue = days.fold<double>(
            0, (sum, day) => sum + FirebaseService.asDouble(day['revenue']));
        final totalOrders = days.fold<int>(
            0, (sum, day) => sum + FirebaseService.asInt(day['orders']));
        final avgOrderValue = AnalyticsService.calculateAverageOrderValue(
            totalRevenue, totalOrders);
        final dailyAvgRevenue = AnalyticsService.calculateDailyAverageRevenue(
            totalRevenue, days.length);

        // Get trend
        final trend = AnalyticsService.getTrend(days, 'revenue');

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            // Period selector
            _buildPeriodSelector(),

            const SizedBox(height: 20),

            // KPI Cards
            _buildKPISection(totalRevenue, totalOrders, avgOrderValue,
                dailyAvgRevenue, trend, days.length),

            const SizedBox(height: 24),

            // Revenue breakdown
            _buildRevenueBreakdown(days),

            const SizedBox(height: 24),

            // Profit analysis from synchronized item costs and expenses.
            _buildProfitAnalysis(days),

            const SizedBox(height: 24),

            // Financial health indicators
            _buildFinancialHealthIndicators(d),

            const SizedBox(height: 24),

            // Revenue trend chart
            const SectionTitle('📈 اتجاه الإيرادات'),
            _buildRevenueTrendChart(days),
          ],
        );
      },
    );
  }

  Widget _buildPeriodSelector() {
    return Row(
      children: ['7', '30', '90']
          .map((p) => Expanded(
                child: GestureDetector(
                  onTap: () => setState(() => _period = p),
                  child: Container(
                    margin: const EdgeInsets.only(right: 8),
                    padding: const EdgeInsets.symmetric(vertical: 12),
                    decoration: BoxDecoration(
                      color: _period == p
                          ? AppTheme.primary.withValues(alpha: 0.2)
                          : AppTheme.surface,
                      borderRadius: BorderRadius.circular(12),
                      border: Border.all(
                        color: _period == p
                            ? AppTheme.primary
                            : Colors.transparent,
                        width: 2,
                      ),
                    ),
                    child: Text(
                      'آخر $p يوم',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: _period == p
                            ? AppTheme.primary
                            : AppTheme.textMuted,
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                  ),
                ),
              ))
          .toList(),
    );
  }

  Widget _buildKPISection(
      double totalRevenue,
      int totalOrders,
      double avgOrderValue,
      double dailyAvgRevenue,
      String trend,
      int daysCount) {
    return Column(
      children: [
        // Main revenue card
        Container(
          padding: const EdgeInsets.all(20),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [
                AppTheme.primary.withValues(alpha: 0.2),
                AppTheme.primary.withValues(alpha: 0.1)
              ],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: AppTheme.primary.withValues(alpha: 0.3)),
          ),
          child: Column(
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('إجمالي الإيرادات',
                      style:
                          TextStyle(fontSize: 14, color: AppTheme.textMuted)),
                  _buildTrendBadge(trend),
                ],
              ),
              const SizedBox(height: 8),
              Text(
                AnalyticsService.formatCurrency(totalRevenue),
                style: const TextStyle(
                  fontSize: 32,
                  fontWeight: FontWeight.bold,
                  color: AppTheme.primary,
                ),
              ),
              const SizedBox(height: 4),
              Text('خلال آخر $_period يوم',
                  style:
                      const TextStyle(fontSize: 12, color: AppTheme.textMuted)),
            ],
          ),
        ),

        const SizedBox(height: 16),

        // Secondary metrics grid
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.3,
          children: [
            _buildMetricCard(
              'إجمالي الطلبات',
              AnalyticsService.formatNumber(totalOrders),
              Icons.receipt_long,
              AppTheme.accent,
            ),
            _buildMetricCard(
              'متوسط الطلب',
              AnalyticsService.formatCurrency(avgOrderValue),
              Icons.shopping_cart,
              AppTheme.warning,
            ),
            _buildMetricCard(
              'متوسط يومي',
              AnalyticsService.formatCurrency(dailyAvgRevenue),
              Icons.calendar_today,
              AppTheme.textMuted,
            ),
            _buildMetricCard(
              'عدد الأيام',
              AnalyticsService.formatNumber(daysCount),
              Icons.date_range,
              AppTheme.surface2 == const Color(0xFF1f2937)
                  ? Colors.white70
                  : Colors.white,
            ),
          ],
        ),
      ],
    );
  }

  Widget _buildMetricCard(
      String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 20),
          const SizedBox(height: 8),
          Text(
            label,
            style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildTrendBadge(String trend) {
    Color color;
    IconData icon;
    String label;

    switch (trend) {
      case 'increasing':
        color = AppTheme.primary;
        icon = Icons.trending_up;
        label = 'تصاعدي';
        break;
      case 'decreasing':
        color = AppTheme.danger;
        icon = Icons.trending_down;
        label = 'تنازلي';
        break;
      default:
        color = AppTheme.textMuted;
        icon = Icons.trending_flat;
        label = 'مستقر';
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 14, color: color),
          const SizedBox(width: 4),
          Text(
            label,
            style: TextStyle(
                color: color, fontSize: 11, fontWeight: FontWeight.bold),
          ),
        ],
      ),
    );
  }

  Widget _buildRevenueBreakdown(List<Map<String, dynamic>> days) {
    if (days.isEmpty) {
      return const Center(
        child:
            Text('لا توجد بيانات', style: TextStyle(color: AppTheme.textMuted)),
      );
    }

    // Sort days by revenue
    final sortedDays = List<Map<String, dynamic>>.from(days);
    sortedDays.sort((a, b) => FirebaseService.asDouble(b['revenue'])
        .compareTo(FirebaseService.asDouble(a['revenue'])));

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('أفضل الأيام مبيعاً',
                  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              Text('${AnalyticsService.formatNumber(sortedDays.length)} يوم',
                  style:
                      const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 16),
          ...sortedDays.take(5).map((day) {
            final revenue = FirebaseService.asDouble(day['revenue']);
            final orders = FirebaseService.asInt(day['orders']);
            final dateStr = (day['day'] as String? ?? '').length >= 10
                ? (day['day'] as String).substring(5)
                : day['day'] ?? '';

            return Container(
              margin: const EdgeInsets.only(bottom: 12),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Center(
                      child: Text(
                        dateStr,
                        style: const TextStyle(
                          fontSize: 10,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.primary,
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          AnalyticsService.formatCurrency(revenue),
                          style: const TextStyle(
                            fontWeight: FontWeight.bold,
                            fontSize: 14,
                          ),
                        ),
                        Text('$orders طلب',
                            style: const TextStyle(
                              fontSize: 11,
                              color: AppTheme.textMuted,
                            )),
                      ],
                    ),
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _buildProfitAnalysis(List<Map<String, dynamic>> days) {
    final totals = AnalyticsService.calculateFinancialTotals(days);
    final totalRevenue = totals['revenue'] ?? 0;
    final costOfGoods = totals['cost'] ?? 0;
    final grossProfit = totals['gross_profit'] ?? 0;
    final expenses = totals['expenses'] ?? 0;
    final netProfit = totals['net_profit'] ?? 0;
    final hasActual = totals['has_actual'] == 1;
    final profitMargin =
        totalRevenue == 0 ? 0.0 : netProfit / totalRevenue * 100;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(hasActual ? 'تحليل الربح الفعلي' : 'تحليل الربح (تقديري)',
              style:
                  const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 16),
          _buildProfitRow('إجمالي الإيرادات', totalRevenue, AppTheme.primary),
          _buildProfitRow(
            hasActual
                ? 'تكلفة البضائع المباعة'
                : 'تكلفة البضائع المباعة (تقديري)',
            costOfGoods,
            AppTheme.danger,
          ),
          const Divider(color: AppTheme.surface2, height: 24),
          _buildProfitRow(
            hasActual ? 'الربح الإجمالي' : 'الربح الإجمالي (تقديري)',
            grossProfit,
            AppTheme.primary,
            isBold: true,
          ),
          if (hasActual) ...[
            _buildProfitRow('المصروفات', expenses, AppTheme.warning),
            _buildProfitRow('صافي الربح', netProfit, AppTheme.primary,
                isBold: true),
          ],
          const SizedBox(height: 12),
          Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: profitMargin > 30
                  ? AppTheme.primary.withValues(alpha: 0.1)
                  : AppTheme.warning.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                const Text('هامش الربح',
                    style: TextStyle(fontWeight: FontWeight.w600)),
                Text(
                  AnalyticsService.formatPercentage(profitMargin),
                  style: TextStyle(
                    fontWeight: FontWeight.bold,
                    color:
                        profitMargin > 30 ? AppTheme.primary : AppTheme.warning,
                    fontSize: 18,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 12),
          Text(
            profitMargin > 30
                ? '✅ هامش ربح جيد (>30%)'
                : profitMargin > 20
                    ? '⚠️ هامش ربح متوسط (20-30%)'
                    : '⚠️ هامش ربح منخفض (<20%)',
            style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
          ),
        ],
      ),
    );
  }

  Widget _buildProfitRow(String label, double value, Color color,
      {bool isBold = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(
            label,
            style: TextStyle(
              fontSize: 13,
              color: AppTheme.textMuted,
              fontWeight: isBold ? FontWeight.bold : FontWeight.normal,
            ),
          ),
          Text(
            AnalyticsService.formatCurrency(value),
            style: TextStyle(
              fontSize: 14,
              color: color,
              fontWeight: isBold ? FontWeight.bold : FontWeight.w600,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFinancialHealthIndicators(Map<String, dynamic> dashboardData) {
    // Get additional data for health indicators
    final debtRemaining =
        FirebaseService.asDouble(dashboardData['debt_remaining'] ?? 0);
    final wasteTodayCount =
        FirebaseService.asInt(dashboardData['waste_today_count'] ?? 0);

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('مؤشرات الصحة المالية',
              style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
          const SizedBox(height: 16),
          _buildHealthIndicator(
            'إدارة الديون',
            debtRemaining == 0,
            debtRemaining == 0
                ? 'لا توجد ديون متبقية'
                : 'ديون متبقية: ${AnalyticsService.formatCurrency(debtRemaining)}',
            debtRemaining == 0 ? AppTheme.primary : AppTheme.warning,
          ),
          _buildHealthIndicator(
            'معدل الهدر',
            wasteTodayCount <= 3,
            wasteTodayCount <= 3 ? 'معدل هدر طبيعي' : 'معدل هدر مرتفع',
            wasteTodayCount <= 3 ? AppTheme.primary : AppTheme.danger,
          ),
          _buildHealthIndicator(
            'سيولة الإيرادات',
            true, // Assuming good if data exists
            'تدفق نقدي نشط',
            AppTheme.primary,
          ),
        ],
      ),
    );
  }

  Widget _buildHealthIndicator(
      String title, bool isGood, String status, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          Icon(
            isGood ? Icons.check_circle : Icons.warning,
            color: color,
            size: 20,
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  title,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textMuted,
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  status,
                  style: TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.bold,
                    color: color,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRevenueTrendChart(List<Map<String, dynamic>> days) {
    if (days.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text('لا توجد بيانات',
              style: TextStyle(color: AppTheme.textMuted)),
        ),
      );
    }

    final maxRevenue = days.fold<double>(
        0,
        (max, day) => FirebaseService.asDouble(day['revenue']) > max
            ? FirebaseService.asDouble(day['revenue'])
            : max);

    return Container(
      height: 200,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: days.map((day) {
          final revenue = FirebaseService.asDouble(day['revenue']);
          final percentage = maxRevenue > 0 ? (revenue / maxRevenue) : 0.0;
          final dateStr = (day['day'] as String? ?? '').length >= 10
              ? (day['day'] as String).substring(8)
              : '';

          return Expanded(
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  Flexible(
                    child: FractionallySizedBox(
                      heightFactor: percentage.clamp(0.05, 1.0),
                      child: Container(
                        decoration: BoxDecoration(
                          gradient: LinearGradient(
                            colors: [
                              AppTheme.primary.withValues(alpha: 0.8),
                              AppTheme.primary.withValues(alpha: 0.4),
                            ],
                            begin: Alignment.bottomCenter,
                            end: Alignment.topCenter,
                          ),
                          borderRadius: BorderRadius.circular(6),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    dateStr,
                    style: const TextStyle(
                      color: AppTheme.textMuted,
                      fontSize: 8,
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
          );
        }).toList(),
      ),
    );
  }
}
