import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../services/AppFirebaseService.dart';
import '../services/analytics_service.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class CustomerInsightsScreen extends StatefulWidget {
  const CustomerInsightsScreen({super.key});
  
  @override
  State<CustomerInsightsScreen> createState() => _CustomerInsightsScreenState();
}

class _CustomerInsightsScreenState extends State<CustomerInsightsScreen> {
  String _view = 'overview'; // overview, loyal, debt, patterns
  
  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.receiptsStream(),
      builder: (ctx, receiptSnap) {
        if (receiptSnap.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline, color: AppTheme.danger, size: 48),
                const SizedBox(height: 16),
                Text('خطأ في الاتصال: ${receiptSnap.error}',
                  style: const TextStyle(color: AppTheme.textMuted),
                  textAlign: TextAlign.center),
              ],
            ),
          );
        }
        if (!receiptSnap.hasData) return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
        
        final receiptData = FirebaseService.docData(receiptSnap.data!);
        final receipts = FirebaseService.asList(receiptData['list']);
        
        return StreamBuilder(
          stream: FirebaseService.debtsStream(),
          builder: (ctx, debtSnap) {
            if (!debtSnap.hasData) return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
            
            final debtData = FirebaseService.docData(debtSnap.data!);
            final debts = FirebaseService.asList(debtData['list']);
            
            // Process customer data
            final customerMetrics = _analyzeCustomerData(receipts, debts);
            
            return Column(
              children: [
                // View selector
                _buildViewSelector(),
                
                Expanded(
                  child: _buildSelectedView(customerMetrics, receipts, debts),
                ),
              ],
            );
          },
        );
      },
    );
  }
  
  Widget _buildViewSelector() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: Border(bottom: BorderSide(color: AppTheme.surface2)),
      ),
      child: Row(
        children: [
          _buildViewTab('نظرة عامة', 'overview', Icons.dashboard),
          _buildViewTab('العملاء المخلصين', 'loyal', Icons.star),
          _buildViewTab('تحليل الديون', 'debt', Icons.account_balance),
          _buildViewTab('أنماط الشراء', 'patterns', Icons.timeline),
        ],
      ),
    );
  }
  
  Widget _buildViewTab(String label, String value, IconData icon) {
    final isSelected = _view == value;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _view = value),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primary.withValues(alpha: 0.1) : Colors.transparent,
            border: Border(
              bottom: BorderSide(
                color: isSelected ? AppTheme.primary : Colors.transparent,
                width: 2,
              ),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 18,
                color: isSelected ? AppTheme.primary : AppTheme.textMuted,
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? AppTheme.primary : AppTheme.textMuted,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  fontSize: 12,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  Widget _buildSelectedView(
    Map<String, dynamic> customerMetrics,
    List<Map<String, dynamic>> receipts,
    List<Map<String, dynamic>> debts,
  ) {
    switch (_view) {
      case 'loyal':
        return _buildLoyalCustomersView(customerMetrics);
      case 'debt':
        return _buildDebtAnalysisView(debts);
      case 'patterns':
        return _buildPurchasePatternsView(receipts);
      default:
        return _buildOverviewView(customerMetrics, receipts, debts);
    }
  }
  
  Map<String, dynamic> _analyzeCustomerData(List<Map<String, dynamic>> receipts, List<Map<String, dynamic>> debts) {
    final customerMap = <String, Map<String, dynamic>>{};
    final totalRevenue = receipts.fold<double>(0, (sum, r) => sum + FirebaseService.asDouble(r['total']));
    
    // Analyze receipts
    for (final receipt in receipts) {
      final customer = receipt['customer'] as String? ?? 'عميل نقدي';
      final total = FirebaseService.asDouble(receipt['total']);
      final items = FirebaseService.asList(receipt['items']);
      
      if (!customerMap.containsKey(customer)) {
        customerMap[customer] = {
          'name': customer,
          'total_spent': 0.0,
          'order_count': 0,
          'avg_order_value': 0.0,
          'items_purchased': <String>[],
          'first_purchase': receipt['date'],
          'last_purchase': receipt['date'],
        };
      }
      
      final custData = customerMap[customer]!;
      custData['total_spent'] = custData['total_spent'] + total;
      custData['order_count'] = custData['order_count'] + 1;
      custData['avg_order_value'] = custData['total_spent'] / custData['order_count'];
      
      // Track items
      for (final item in items) {
        final itemName = item['name'] as String? ?? '';
        if (itemName.isNotEmpty) {
          final items = custData['items_purchased'] as List<String>;
          if (!items.contains(itemName)) {
            items.add(itemName);
          }
        }
      }
    }
    
    // Analyze debts
    final debtCustomers = debts.map((d) => d['customer'] as String? ?? '').toSet();
    
    // Convert to list and sort by total spent
    final customerList = customerMap.values.toList()
      ..sort((a, b) => (b['total_spent'] as double).compareTo(a['total_spent'] as double));
    
    // Calculate metrics
    final uniqueCustomers = customerMap.length;
    final avgCustomerValue = uniqueCustomers > 0 ? totalRevenue / uniqueCustomers : 0.0;
    final avgOrderValue = receipts.isNotEmpty ? totalRevenue / receipts.length : 0.0;
    
    return {
      'customers': customerList,
      'unique_customers': uniqueCustomers,
      'avg_customer_value': avgCustomerValue,
      'avg_order_value': avgOrderValue,
      'total_revenue': totalRevenue,
      'debt_customers': debtCustomers,
    };
  }
  
  Widget _buildOverviewView(
    Map<String, dynamic> customerMetrics,
    List<Map<String, dynamic>> receipts,
    List<Map<String, dynamic>> debts,
  ) {
    final customers = customerMetrics['customers'] as List<Map<String, dynamic>>;
    final uniqueCustomers = customerMetrics['unique_customers'] as int;
    final avgCustomerValue = customerMetrics['avg_customer_value'] as double;
    final avgOrderValue = customerMetrics['avg_order_value'] as double;
    final totalRevenue = customerMetrics['total_revenue'] as double;
    final debtCustomers = customerMetrics['debt_customers'] as Set<String>;
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // KPI cards
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.4,
          children: [
            _buildKPICard('إجمالي العملاء', uniqueCustomers.toString(), Icons.people, AppTheme.primary),
            _buildKPICard('متوسط قيمة العميل', AnalyticsService.formatCurrency(avgCustomerValue), Icons.account_balance_wallet, AppTheme.accent),
            _buildKPICard('متوسط قيمة الطلب', AnalyticsService.formatCurrency(avgOrderValue), Icons.receipt_long, AppTheme.warning),
            _buildKPICard('عملاء مدينةون', debtCustomers.length.toString(), Icons.account_balance, AppTheme.danger),
          ],
        ),
        
        const SizedBox(height: 20),
        
        // Top customers
        const SectionTitle('🏆 أفضل العملاء قيمة'),
        _buildTopCustomers(customers),
        
        const SizedBox(height: 20),
        
        // Customer distribution
        _buildCustomerDistribution(customers),
        
        const SizedBox(height: 20),
        
        // Revenue contribution
        _buildRevenueContribution(customers, totalRevenue),
      ],
    );
  }
  
  Widget _buildKPICard(String label, String value, IconData icon, Color color) {
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
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textMuted)),
          const SizedBox(height: 4),
          Text(value, style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }
  
  Widget _buildTopCustomers(List<Map<String, dynamic>> customers) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: customers.take(5).map((customer) {
          final name = customer['name'] as String? ?? '';
          final totalSpent = customer['total_spent'] as double;
          final orderCount = customer['order_count'] as int;
          final avgOrder = customer['avg_order_value'] as double;
          
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface2,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(
                      name,
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        fontSize: 14,
                      ),
                    ),
                    Text(
                      AnalyticsService.formatCurrency(totalSpent),
                      style: const TextStyle(
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primary,
                        fontSize: 16,
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    _buildCustomerBadge('$orderCount طلب', Icons.shopping_bag, AppTheme.textMuted),
                    const SizedBox(width: 8),
                    _buildCustomerBadge('${AnalyticsService.formatCurrency(avgOrder)}/طلب', Icons.trending_up, AppTheme.accent),
                  ],
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
  
  Widget _buildCustomerBadge(String label, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Icon(icon, size: 12, color: color),
          const SizedBox(width: 4),
          Text(label, style: TextStyle(fontSize: 11, color: color)),
        ],
      ),
    );
  }
  
  Widget _buildCustomerDistribution(List<Map<String, dynamic>> customers) {
    // Categorize customers by spending
    final highValue = customers.where((c) => (c['total_spent'] as double) >= 500000).length;
    final mediumValue = customers.where((c) {
      final spent = c['total_spent'] as double;
      return spent >= 200000 && spent < 500000;
    }).length;
    final lowValue = customers.where((c) => (c['total_spent'] as double) < 200000).length;
    
    final total = customers.length;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('توزيع العملاء حسب الإنفاق',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          const SizedBox(height: 16),
          
          _buildCustomerSegment('عالية القيمة (≥500K SYP)', highValue, total, AppTheme.primary),
          _buildCustomerSegment('متوسطة القيمة (200K-500K SYP)', mediumValue, total, AppTheme.accent),
          _buildCustomerSegment('منخفضة القيمة (<200K SYP)', lowValue, total, AppTheme.textMuted),
        ],
      ),
    );
  }
  
  Widget _buildCustomerSegment(String label, int count, int total, Color color) {
    final percentage = total > 0 ? (count / total * 100) : 0.0;
    
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(label, style: const TextStyle(fontSize: 12)),
              Text('$count (${percentage.toStringAsFixed(1)}%)',
                style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
            ],
          ),
          const SizedBox(height: 4),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: percentage / 100,
              backgroundColor: AppTheme.surface2,
              valueColor: AlwaysStoppedAnimation(color),
              minHeight: 6,
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildRevenueContribution(List<Map<String, dynamic>> customers, double totalRevenue) {
    // Pareto principle: top 20% customers
    final top20Count = (customers.length * 0.2).ceil();
    final top20Revenue = customers.take(top20Count).fold<double>(
      0, (sum, c) => sum + (c['total_spent'] as double));
    final top20Percentage = totalRevenue > 0 ? (top20Revenue / totalRevenue * 100) : 0.0;
    
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
              const Text('مساهمة أفضل 20% عملاء',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
              Text(top20Percentage >= 80 ? '✅ ممتاز' : '⚠️ يمكن تحسينه',
                style: TextStyle(
                  fontSize: 11,
                  color: top20Percentage >= 80 ? AppTheme.primary : AppTheme.warning,
                  fontWeight: FontWeight.bold,
                )),
            ],
          ),
          const SizedBox(height: 16),
          
          Container(
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.primary.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              children: [
                Text(
                  '${top20Percentage.toStringAsFixed(1)}%',
                  style: const TextStyle(
                    fontSize: 32,
                    fontWeight: FontWeight.bold,
                    color: AppTheme.primary,
                  ),
                ),
                const SizedBox(height: 4),
                Text('من إجمالي الإيرادات',
                  style: const TextStyle(fontSize: 12, color: AppTheme.textMuted)),
                const SizedBox(height: 8),
                Text(
                  top20Percentage >= 80 
                    ? 'توزيع جيد - عملاء مخلصون يساهمون بشكل كبير'
                    : 'فكر في برامج ولاء لزيادة قيمة العملاء',
                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildLoyalCustomersView(Map<String, dynamic> customerMetrics) {
    final customers = customerMetrics['customers'] as List<Map<String, dynamic>>;
    
    // Sort by order count and frequency
    final loyalCustomers = List<Map<String, dynamic>>.from(customers);
    loyalCustomers.sort((a, b) => (b['order_count'] as int).compareTo(a['order_count'] as int));
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const SectionTitle('⭐ العملاء الأكثر تكراراً'),
        const SizedBox(height: 8),
        ...loyalCustomers.take(10).map((customer) {
          final name = customer['name'] as String? ?? '';
          final orderCount = customer['order_count'] as int;
          final totalSpent = customer['total_spent'] as double;
          final avgOrder = customer['avg_order_value'] as double;
          
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(16),
            ),
            child: Row(
              children: [
                CircleAvatar(
                  backgroundColor: AppTheme.primary.withValues(alpha: 0.2),
                  child: Text(name.isNotEmpty ? name[0] : '?',
                    style: const TextStyle(
                      color: AppTheme.primary,
                      fontWeight: FontWeight.bold,
                    )),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(fontWeight: FontWeight.bold)),
                      const SizedBox(height: 4),
                      Row(
                        children: [
                          _buildLoyalBadge(orderCount, 'طلب'),
                          const SizedBox(width: 8),
                          _buildLoyalBadge(totalSpent.toInt(), 'SYP', isCurrency: true),
                        ],
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Text('${AnalyticsService.formatCurrency(avgOrder)}/طلب',
                    style: const TextStyle(
                      fontSize: 11,
                      color: AppTheme.primary,
                      fontWeight: FontWeight.bold,
                    )),
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
  
  Widget _buildLoyalBadge(int value, String suffix, {bool isCurrency = false}) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(
        color: AppTheme.surface2,
        borderRadius: BorderRadius.circular(6),
      ),
      child: Text(
        isCurrency ? AnalyticsService.formatCurrency(value.toDouble()) + suffix : '$value $suffix',
        style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
      ),
    );
  }
  
  Widget _buildDebtAnalysisView(List<Map<String, dynamic>> debts) {
    final totalDebt = debts.fold<double>(0, (sum, d) => sum + FirebaseService.asDouble(d['amount']));
    final totalCollected = debts.fold<double>(0, (sum, d) => sum + FirebaseService.asDouble(d['paid']));
    final totalRemaining = debts.fold<double>(0, (sum, d) => sum + FirebaseService.asDouble(d['remaining']));
    final collectionRate = AnalyticsService.calculateDebtCollectionRate(totalCollected, totalDebt);
    
    // Sort by remaining amount
    final highDebtCustomers = List<Map<String, dynamic>>.from(debts);
    highDebtCustomers.sort((a, b) => FirebaseService.asDouble(b['remaining']).compareTo(FirebaseService.asDouble(a['remaining'])));
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Summary cards
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.5,
          children: [
            _buildDebtCard('إجمالي الديون', totalDebt, Icons.account_balance, AppTheme.danger),
            _buildDebtCard('المبلغ المحصّل', totalCollected, Icons.check_circle, AppTheme.primary),
            _buildDebtCard('المتبقي', totalRemaining, Icons.pending, AppTheme.warning),
            _buildDebtCard('نسبة التحصيل', collectionRate, Icons.percent, collectionRate >= 70 ? AppTheme.primary : AppTheme.warning, isPercentage: true),
          ],
        ),
        
        const SizedBox(height: 20),
        
        // High debt customers
        const SectionTitle('⚠️ العملاء الأعلى ديوناً'),
        const SizedBox(height: 8),
        ...highDebtCustomers.take(10).map((debt) {
          final customer = debt['customer'] as String? ?? '';
          final remaining = FirebaseService.asDouble(debt['remaining']);
          final total = FirebaseService.asDouble(debt['amount']);
          final paid = FirebaseService.asDouble(debt['paid']);
          final percentage = total > 0 ? (paid / total * 100) : 0.0;
          
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: remaining > 100000 ? AppTheme.danger.withValues(alpha: 0.3) : Colors.transparent,
                width: remaining > 100000 ? 2 : 1,
              ),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text(customer, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                    Text(AnalyticsService.formatCurrency(remaining),
                      style: TextStyle(
                        fontWeight: FontWeight.bold,
                        color: remaining > 100000 ? AppTheme.danger : AppTheme.warning,
                        fontSize: 16,
                      )),
                  ],
                ),
                const SizedBox(height: 12),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: percentage / 100,
                    backgroundColor: AppTheme.surface2,
                    valueColor: AlwaysStoppedAnimation(percentage >= 100 ? AppTheme.primary : AppTheme.warning),
                    minHeight: 6,
                  ),
                ),
                const SizedBox(height: 8),
                Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('مدفوع: ${AnalyticsService.formatCurrency(paid)}',
                      style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                    Text('الإجمالي: ${AnalyticsService.formatCurrency(total)}',
                      style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
                  ],
                ),
              ],
            ),
          );
        }),
      ],
    );
  }
  
  Widget _buildDebtCard(String label, double value, IconData icon, Color color, {bool isPercentage = false}) {
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
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
          const SizedBox(height: 4),
          Text(
            isPercentage ? '${value.toStringAsFixed(1)}%' : AnalyticsService.formatCurrency(value),
            style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: color),
          ),
        ],
      ),
    );
  }
  
  Widget _buildPurchasePatternsView(List<Map<String, dynamic>> receipts) {
    // Analyze purchase patterns by time
    final hourlyMap = <int, int>{};
    final dayOfWeekMap = <String, int>{};
    
    for (final receipt in receipts) {
      final dateStr = receipt['date'] as String? ?? '';
      try {
        final date = DateTime.parse(dateStr);
        final hour = date.hour;
        final day = DateFormat('EEEE', 'ar').format(date);
        
        hourlyMap[hour] = (hourlyMap[hour] ?? 0) + 1;
        dayOfWeekMap[day] = (dayOfWeekMap[day] ?? 0) + 1;
      } catch (e) {
        // Skip invalid dates
      }
    }
    
    // Find peak times
    final peakHour = hourlyMap.entries.reduce((a, b) => a.value > b.value ? a : b);
    final peakDay = dayOfWeekMap.entries.isNotEmpty 
      ? dayOfWeekMap.entries.reduce((a, b) => a.value > b.value ? a : b)
      : MapEntry('—', 0);
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Peak time cards
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            gradient: LinearGradient(
              colors: [AppTheme.primary.withValues(alpha: 0.2), AppTheme.accent.withValues(alpha: 0.1)],
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
            ),
            borderRadius: BorderRadius.circular(16),
          ),
          child: Column(
            children: [
              const Text('أوقات الذروة',
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
              const SizedBox(height: 16),
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceAround,
                children: [
                  _buildPeakTimeCard('ساعة الذروة', '${peakHour.key}:00', Icons.access_time, peakHour.value),
                  _buildPeakTimeCard('اليوم الأكثر', peakDay.key, Icons.calendar_today, peakDay.value),
                ],
              ),
            ],
          ),
        ),
        
        const SizedBox(height: 20),
        
        // Hourly distribution
        const SectionTitle('📊 التوزيع الساعي'),
        _buildHourlyChart(hourlyMap),
        
        const SizedBox(height: 20),
        
        // Day distribution
        const SectionTitle('📅 التوزيع اليومي'),
        _buildDayChart(dayOfWeekMap),
      ],
    );
  }
  
  Widget _buildPeakTimeCard(String label, String value, IconData icon, int count) {
    return Column(
      children: [
        Icon(icon, color: AppTheme.primary, size: 28),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(fontSize: 12, color: AppTheme.textMuted)),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        Text('$count طلب', style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
      ],
    );
  }
  
  Widget _buildHourlyChart(Map<int, int> hourlyMap) {
    if (hourlyMap.isEmpty) {
      return const Center(
        child: Text('لا توجد بيانات كافية',
          style: TextStyle(color: AppTheme.textMuted)),
      );
    }
    
    final maxCount = hourlyMap.values.reduce((a, b) => a > b ? a : b);
    
    return Container(
      height: 150,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: List.generate(24, (hour) {
          final count = hourlyMap[hour] ?? 0;
          final percentage = maxCount > 0 ? (count / maxCount) : 0.0;
          
          return Expanded(
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 1),
              height: percentage * 100,
              decoration: BoxDecoration(
                color: count > 0 ? AppTheme.primary.withValues(alpha: 0.3 + percentage * 0.5) : AppTheme.surface2,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          );
        }),
      ),
    );
  }
  
  Widget _buildDayChart(Map<String, int> dayOfWeekMap) {
    if (dayOfWeekMap.isEmpty) {
      return const Center(
        child: Text('لا توجد بيانات كافية',
          style: TextStyle(color: AppTheme.textMuted)),
      );
    }
    
    final days = ['السبت', 'الأحد', 'الاثنين', 'الثلاثاء', 'الأربعاء', 'الخميس', 'الجمعة'];
    final maxCount = dayOfWeekMap.values.reduce((a, b) => a > b ? a : b);
    
    return Container(
      height: 120,
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: days.map((day) {
          final count = dayOfWeekMap[day] ?? 0;
          final percentage = maxCount > 0 ? (count / maxCount) : 0.0;
          
          return Expanded(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                Container(
                  width: double.infinity,
                  margin: const EdgeInsets.symmetric(horizontal: 2),
                  height: percentage * 80,
                  decoration: BoxDecoration(
                    color: count > 0 ? AppTheme.accent.withValues(alpha: 0.3 + percentage * 0.5) : AppTheme.surface2,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
                const SizedBox(height: 6),
                Text(
                  day.substring(0, 2),
                  style: const TextStyle(fontSize: 9, color: AppTheme.textMuted),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
}