import 'AppFirebaseService.dart';
import 'analytics_service.dart';

/// Smart Alerts and Recommendations Service
/// Provides actionable insights and alerts for the shop owner
class AlertsService {
  
  /// Generate all alerts and recommendations
  static List<Map<String, dynamic>> generateAllAlerts(Map<String, dynamic> dashboardData) {
    final alerts = <Map<String, dynamic>>[];
    
    // Inventory alerts
    alerts.addAll(_generateInventoryAlerts(dashboardData));
    
    // Financial alerts
    alerts.addAll(_generateFinancialAlerts(dashboardData));
    
    // Operational alerts
    alerts.addAll(_generateOperationalAlerts(dashboardData));
    
    // Sort by priority
    alerts.sort((a, b) {
      final priorityOrder = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3};
      return priorityOrder[a['priority']]!.compareTo(priorityOrder[b['priority']]!);
    });
    
    return alerts;
  }
  
  /// Generate inventory-related alerts
  static List<Map<String, dynamic>> _generateInventoryAlerts(Map<String, dynamic> dashboardData) {
    final alerts = <Map<String, dynamic>>[];
    
    final outStockCount = FirebaseService.asInt(dashboardData['out_stock_count'] ?? 0);
    final lowStockCount = FirebaseService.asInt(dashboardData['low_stock_count'] ?? 0);
    
    // Critical: Out of stock items
    if (outStockCount > 0) {
      alerts.add({
        'id': 'inv_out_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'inventory',
        'priority': 'critical',
        'title': 'نفاد المخزون',
        'message': '$outStockCount منتج نفد من المخزون بالكامل',
        'action': 'عرض المخزون',
        'recommendation': 'قم بإعادة طلب هذه المنتجات فوراً لتجنب خسارة المبيعات',
        'icon': 'inventory_2',
        'color': 'danger',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    // High: Low stock items
    if (lowStockCount > 0) {
      alerts.add({
        'id': 'inv_low_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'inventory',
        'priority': lowStockCount > 5 ? 'high' : 'medium',
        'title': 'مخزون منخفض',
        'message': '$lowStockCount منتج وصل للحد الأدنى',
        'action': 'عرض التفاصيل',
        'recommendation': 'راجع مستويات المخزون وخطط لإعادة الطلب قريباً',
        'icon': 'warning',
        'color': 'warning',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    return alerts;
  }
  
  /// Generate financial-related alerts
  static List<Map<String, dynamic>> _generateFinancialAlerts(Map<String, dynamic> dashboardData) {
    final alerts = <Map<String, dynamic>>[];
    
    final todayRevenue = FirebaseService.asDouble(dashboardData['today_revenue'] ?? 0);
    final debtRemaining = FirebaseService.asDouble(dashboardData['debt_remaining'] ?? 0);
    
    // High debt
    if (debtRemaining > 1000000) { // More than 1M SYP
      alerts.add({
        'id': 'fin_debt_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'financial',
        'priority': 'high',
        'title': 'ديون متبقية كبيرة',
        'message': 'إجمالي الديون المتبقية: ${AnalyticsService.formatCurrency(debtRemaining)}',
        'action': 'عرض الديون',
        'recommendation': 'تواصل مع العملاء المدينين لتحصيل الديون المتأخرة',
        'icon': 'account_balance',
        'color': 'warning',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    // Low daily revenue (assuming daily target of 200K SYP)
    if (todayRevenue > 0 && todayRevenue < 100000) {
      alerts.add({
        'id': 'fin_rev_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'financial',
        'priority': 'medium',
        'title': 'إيرادات منخفضة اليوم',
        'message': 'إيرادات اليوم: ${AnalyticsService.formatCurrency(todayRevenue)}',
        'action': 'عرض التحليل',
        'recommendation': 'راجع أسباب انخفاض المبيعات وفكر في عروض ترويجية',
        'icon': 'trending_down',
        'color': 'warning',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    // Good performance
    if (todayRevenue > 300000) {
      alerts.add({
        'id': 'fin_good_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'financial',
        'priority': 'low',
        'title': 'أداء ممتاز اليوم',
        'message': 'إيرادات اليوم: ${AnalyticsService.formatCurrency(todayRevenue)}',
        'action': null,
        'recommendation': 'استمر في الاستراتيجية الحالية',
        'icon': 'trending_up',
        'color': 'primary',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    return alerts;
  }
  
  /// Generate operational-related alerts
  static List<Map<String, dynamic>> _generateOperationalAlerts(Map<String, dynamic> dashboardData) {
    final alerts = <Map<String, dynamic>>[];
    
    final wasteTodayCount = FirebaseService.asInt(dashboardData['waste_today_count'] ?? 0);
    final todayOrders = FirebaseService.asInt(dashboardData['today_orders'] ?? 0);
    
    // High waste
    if (wasteTodayCount > 5) {
      alerts.add({
        'id': 'ops_waste_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'operational',
        'priority': wasteTodayCount > 10 ? 'high' : 'medium',
        'title': 'معدل هدر مرتفع',
        'message': '$wasteTodayCount تسجيل هدر اليوم',
        'action': 'عرض سجل الهدر',
        'recommendation': 'راجع أسباب الهدر واتخذ تدابير لتقليل الفاقد',
        'icon': 'delete_outline',
        'color': 'danger',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    // Low orders (assuming normal day has at least 10 orders)
    if (todayOrders > 0 && todayOrders < 5) {
      alerts.add({
        'id': 'ops_orders_${DateTime.now().millisecondsSinceEpoch}',
        'type': 'operational',
        'priority': 'medium',
        'title': 'عدد طلبات منخفض',
        'message': '$todayOrders طلب فقط حتى الآن',
        'action': null,
        'recommendation': 'فكر في عروض خاصة لزيادة عدد الطلبات',
        'icon': 'receipt_long',
        'color': 'warning',
        'created_at': DateTime.now().toIso8601String(),
      });
    }
    
    return alerts;
  }
  
  /// Generate recommendations based on data trends
  static List<String> generateRecommendations(Map<String, dynamic> dashboardData, Map<String, dynamic> analyticsData) {
    final recommendations = <String>[];
    
    final todayRevenue = FirebaseService.asDouble(dashboardData['today_revenue'] ?? 0);
    final todayOrders = FirebaseService.asInt(dashboardData['today_orders'] ?? 0);
    final lowStockCount = FirebaseService.asInt(dashboardData['low_stock_count'] ?? 0);
    final outStockCount = FirebaseService.asInt(dashboardData['out_stock_count'] ?? 0);
    final wasteTodayCount = FirebaseService.asInt(dashboardData['waste_today_count'] ?? 0);
    
    // Revenue optimization
    if (todayOrders > 0) {
      final avgOrderValue = todayRevenue / todayOrders;
      if (avgOrderValue < 30000) {
        recommendations.add('💡 لزيادة متوسط قيمة الطلب (${AnalyticsService.formatCurrency(avgOrderValue)})، فكر في عرض "اشترِ واحصل على خصم" أو عروض的组合');
      } else if (avgOrderValue > 50000) {
        recommendations.add('✅ متوسط قيمة الطلب ممتاز! حافظ على هذا الأداء من خلال جودة الخدمة');
      }
    }
    
    // Inventory management
    if (outStockCount > 0) {
      recommendations.add('📦 قم بمراجعة سجلات المبيعات للمنتجات النافدة لتحسين التنبؤ بالطلب');
    }
    
    if (lowStockCount > 3) {
      recommendations.add('📦 نفذ نظام إعادة طلب تلقائي للمنتجات التي تصل للحد الأدنى');
    }
    
    // Waste reduction
    if (wasteTodayCount > 3) {
      recommendations.add('🗑️ راجع أوقات التحضير وأحجام الم portions لتقليل الهدر');
      recommendations.add('🗑️ فكر في عروض "Happy Hour" لبيع المنتجات القريبة من الانتهاء');
    }
    
    // General business insights
    if (todayRevenue > 200000) {
      recommendations.add('📈 اليوم يوم مبيعات جيد! وثق العوامل الناجحة لتكرارها');
    }
    
    // Add periodic recommendations
    final now = DateTime.now();
    if (now.hour >= 18) { // Evening
      recommendations.add('🌆 في وقت متأخر من اليوم، راجع المخزون للمساء وخطط ليوم الغد');
    } else if (now.hour >= 12 && now.hour <= 14) { // Lunch peak
      recommendations.add('🍽️ وقت الذروة الغدائي! تأكد من كفاية الموظفين والمخزون');
    }
    
    return recommendations;
  }
  
  /// Get alert priority color
  static String getPriorityColor(String priority) {
    switch (priority) {
      case 'critical':
        return 'danger';
      case 'high':
        return 'warning';
      case 'medium':
        return 'accent';
      default:
        return 'textMuted';
    }
  }
  
  /// Check if alert should be shown (avoid spamming)
  static bool shouldShowAlert(Map<String, dynamic> alert, List<Map<String, dynamic>> shownAlerts) {
    final alertId = alert['id'] as String?;
    if (alertId == null) return true;
    
    // Check if alert was shown in the last hour
    final now = DateTime.now();
    for (final shown in shownAlerts) {
      if (shown['id'] == alertId) {
        final shownAt = DateTime.tryParse(shown['shown_at'] as String? ?? '');
        if (shownAt != null && now.difference(shownAt).inHours < 1) {
          return false;
        }
      }
    }
    
    return true;
  }
  
  /// Mark alert as shown
  static void markAlertAsShown(Map<String, dynamic> alert, List<Map<String, dynamic>> shownAlerts) {
    final alertId = alert['id'] as String?;
    if (alertId == null) return;
    
    shownAlerts.removeWhere((a) => a['id'] == alertId);
    shownAlerts.add({
      'id': alertId,
      'shown_at': DateTime.now().toIso8601String(),
    });
  }
}