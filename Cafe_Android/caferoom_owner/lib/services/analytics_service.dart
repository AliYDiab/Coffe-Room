import 'package:intl/intl.dart';

/// Advanced Analytics Service for CafeRoom Owner
/// Provides business intelligence and insights
class AnalyticsService {
  /// Sum synchronized financial fields without applying a guessed margin.
  static Map<String, double> calculateFinancialTotals(
      List<Map<String, dynamic>> days) {
    var revenue = 0.0;
    var cost = 0.0;
    var grossProfit = 0.0;
    var expenses = 0.0;
    var netProfit = 0.0;
    var hasActual = false;

    for (final day in days) {
      final dayRevenue = (day['revenue'] as num?)?.toDouble() ?? 0;
      final dayGross = (day['gross_profit'] as num?)?.toDouble();
      final dayCost = (day['cost'] as num?)?.toDouble();
      final dayExpenses = (day['expenses'] as num?)?.toDouble() ?? 0;
      final dayNet = (day['net_profit'] as num?)?.toDouble();
      final resolvedGross = dayGross ??
          (dayCost == null ? dayRevenue * 0.35 : dayRevenue - dayCost);
      final resolvedCost = dayCost ?? dayRevenue - resolvedGross;
      final resolvedNet = dayNet ?? resolvedGross - dayExpenses;
      hasActual =
          hasActual || dayGross != null || dayCost != null || dayNet != null;
      revenue += dayRevenue;
      cost += resolvedCost;
      grossProfit += resolvedGross;
      expenses += dayExpenses;
      netProfit += resolvedNet;
    }

    return {
      'revenue': revenue,
      'cost': cost,
      'gross_profit': grossProfit,
      'expenses': expenses,
      'net_profit': netProfit,
      'has_actual': hasActual ? 1 : 0,
    };
  }

  // ── Financial Metrics ──

  /// Calculate average order value
  static double calculateAverageOrderValue(
      double totalRevenue, int totalOrders) {
    if (totalOrders == 0) return 0.0;
    return totalRevenue / totalOrders;
  }

  /// Calculate daily average revenue
  static double calculateDailyAverageRevenue(double totalRevenue, int days) {
    if (days == 0) return 0.0;
    return totalRevenue / days;
  }

  /// Calculate revenue growth percentage
  static double calculateRevenueGrowth(
      double currentRevenue, double previousRevenue) {
    if (previousRevenue == 0) return currentRevenue > 0 ? 100.0 : 0.0;
    return ((currentRevenue - previousRevenue) / previousRevenue) * 100;
  }

  /// Calculate profit margin (if cost data available)
  static double calculateProfitMargin(double revenue, double costs) {
    if (revenue == 0) return 0.0;
    return ((revenue - costs) / revenue) * 100;
  }

  // ── Inventory Metrics ──

  /// Calculate inventory turnover rate
  static double calculateInventoryTurnover(
      double cogs, double averageInventoryValue) {
    if (averageInventoryValue == 0) return 0.0;
    return cogs / averageInventoryValue;
  }

  /// Calculate days of inventory remaining
  static int calculateDaysOfInventory(int currentStock, double dailyUsage) {
    if (dailyUsage == 0) return 999; // Infinite if no usage
    return (currentStock / dailyUsage).floor();
  }

  /// Calculate total inventory value
  static double calculateInventoryValue(List<Map<String, dynamic>> items) {
    return items.fold<double>(0.0, (sum, item) {
      final price = (item['price'] as num?)?.toDouble() ?? 0.0;
      final stock = (item['stock'] as num?)?.toInt() ?? 0;
      return sum + (price * stock);
    });
  }

  // ── Customer Metrics ──

  /// Calculate customer lifetime value
  static double calculateCustomerLifetimeValue(double averageOrderValue,
      int frequencyPerYear, int customerLifespanYears) {
    return averageOrderValue * frequencyPerYear * customerLifespanYears;
  }

  /// Calculate customer retention rate
  static double calculateRetentionRate(
      int returningCustomers, int totalCustomers) {
    if (totalCustomers == 0) return 0.0;
    return (returningCustomers / totalCustomers) * 100;
  }

  // ── Operational Metrics ──

  /// Calculate waste percentage
  static double calculateWastePercentage(
      double wasteValue, double totalInventoryValue) {
    if (totalInventoryValue == 0) return 0.0;
    return (wasteValue / totalInventoryValue) * 100;
  }

  /// Calculate debt collection rate
  static double calculateDebtCollectionRate(
      double collectedAmount, double totalDebt) {
    if (totalDebt == 0) return 100.0;
    return (collectedAmount / totalDebt) * 100;
  }

  // ── Time-based Analysis ──

  /// Get peak hours from hourly data
  static List<Map<String, dynamic>> getPeakHours(
      List<Map<String, dynamic>> hourlyData) {
    if (hourlyData.isEmpty) return [];

    final sorted = List<Map<String, dynamic>>.from(hourlyData);
    sorted.sort((a, b) {
      final ordersA = (a['orders'] as num?)?.toInt() ?? 0;
      final ordersB = (b['orders'] as num?)?.toInt() ?? 0;
      return ordersB.compareTo(ordersA);
    });

    return sorted.take(3).toList();
  }

  /// Get slowest hours
  static List<Map<String, dynamic>> getSlowestHours(
      List<Map<String, dynamic>> hourlyData) {
    if (hourlyData.isEmpty) return [];

    final sorted = List<Map<String, dynamic>>.from(hourlyData);
    sorted.sort((a, b) {
      final ordersA = (a['orders'] as num?)?.toInt() ?? 0;
      final ordersB = (b['orders'] as num?)?.toInt() ?? 0;
      return ordersA.compareTo(ordersB);
    });

    return sorted.take(3).toList();
  }

  /// Get trend analysis (increasing, decreasing, stable)
  static String getTrend(List<Map<String, dynamic>> data, String key) {
    if (data.length < 2) return 'stable';

    final recent = data.take(3).toList();
    final previous = data.skip(3).take(3).toList();

    if (previous.isEmpty) return 'stable';

    final recentSum = recent.fold<double>(
        0, (sum, item) => sum + ((item[key] as num?)?.toDouble() ?? 0));
    final previousSum = previous.fold<double>(
        0, (sum, item) => sum + ((item[key] as num?)?.toDouble() ?? 0));

    final change = ((recentSum - previousSum) / previousSum) * 100;

    if (change > 5) return 'increasing';
    if (change < -5) return 'decreasing';
    return 'stable';
  }

  // ── Smart Recommendations ──

  /// Generate inventory reorder suggestions
  static List<Map<String, dynamic>> generateReorderSuggestions(
      List<Map<String, dynamic>> items, Map<String, double> dailyUsage) {
    final suggestions = <Map<String, dynamic>>[];

    for (final item in items) {
      final name = item['name'] as String? ?? '';
      final stock = (item['stock'] as num?)?.toInt() ?? 0;
      final type = item['type'] as String? ?? 'fixed';

      if (type == 'recipe') continue; // Skip recipe items

      final usage = dailyUsage[name] ?? 0.0;
      if (usage > 0) {
        final daysRemaining = calculateDaysOfInventory(stock, usage);

        if (daysRemaining <= 3) {
          suggestions.add({
            'item': name,
            'current_stock': stock,
            'daily_usage': usage,
            'days_remaining': daysRemaining,
            'priority': daysRemaining <= 1
                ? 'critical'
                : daysRemaining <= 2
                    ? 'high'
                    : 'medium',
            'suggested_order_quantity': (usage * 7).ceil(), // Order for 1 week
          });
        }
      }
    }

    suggestions.sort((a, b) {
      final priorityOrder = {'critical': 0, 'high': 1, 'medium': 2};
      return priorityOrder[a['priority']]!
          .compareTo(priorityOrder[b['priority']]!);
    });

    return suggestions;
  }

  /// Generate performance insights
  static List<String> generatePerformanceInsights(
      Map<String, dynamic> dashboardData) {
    final insights = <String>[];

    final todayRevenue =
        (dashboardData['today_revenue'] as num?)?.toDouble() ?? 0.0;
    final todayOrders = (dashboardData['today_orders'] as num?)?.toInt() ?? 0;
    final lowStockCount =
        (dashboardData['low_stock_count'] as num?)?.toInt() ?? 0;
    final outStockCount =
        (dashboardData['out_stock_count'] as num?)?.toInt() ?? 0;
    final wasteCount =
        (dashboardData['waste_today_count'] as num?)?.toInt() ?? 0;

    // Revenue insights
    if (todayOrders > 0) {
      final avgOrder = todayRevenue / todayOrders;
      insights
          .add('متوسط قيمة الطلب اليوم: ${avgOrder.toStringAsFixed(0)} SYP');
    }

    // Stock insights
    if (outStockCount > 0) {
      insights.add(
          'تنبيه: $outStockCount منتج نفد من المخزون - يحتاج إعادة طلب فوري');
    }
    if (lowStockCount > 0) {
      insights.add('تحذير: $lowStockCount منتج وصل للحد الأدنى');
    }

    // Waste insights
    if (wasteCount > 5) {
      insights.add('معدل هدر مرتفع اليوم: $wasteCount تسجيلات - راجع الأسباب');
    }

    // General performance
    if (todayRevenue > 0) {
      insights.add(
          'الأداء الجيد: إيرادات اليوم ${todayRevenue.toStringAsFixed(0)} SYP');
    }

    return insights;
  }

  // ── Formatters ──

  static String formatCurrency(double value) {
    return '${NumberFormat('#,##0', 'ar').format(value)} SYP';
  }

  static String formatPercentage(double value) {
    return '${value.toStringAsFixed(1)}%';
  }

  static String formatNumber(int value) {
    return NumberFormat('#,##0', 'ar').format(value);
  }
}
