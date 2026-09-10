/// Demo Data Service
/// Provides sample data for testing when Firebase is not configured
class DemoDataService {
  
  /// Get demo dashboard data
  static Map<String, dynamic> getDashboardData() {
    return {
      'today_orders': 24,
      'today_revenue': 485000.0,
      'total_orders': 1247,
      'total_revenue': 12500000.0,
      'debt_remaining': 350000.0,
      'low_stock_count': 3,
      'out_stock_count': 1,
      'top_items_today': [
        {'name': 'قهوة تركي', 'qty': 12, 'revenue': 84000.0},
        {'name': 'لاتيه', 'qty': 8, 'revenue': 56000.0},
        {'name': 'شاي', 'qty': 15, 'revenue': 37500.0},
        {'name': 'كيكة', 'qty': 6, 'revenue': 48000.0},
        {'name': 'ساندوتش', 'qty': 10, 'revenue': 150000.0},
      ],
      'waste_today_count': 2,
      'waste_today_qty': 3.5,
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo inventory data
  static Map<String, dynamic> getInventoryData() {
    return {
      'items': [
        {
          'id': 1,
          'name': 'قهوة تركي',
          'category': 'مشروبات',
          'price': 7000.0,
          'cost': 3000.0,
          'stock': 45,
          'type': 'fixed',
          'available': true,
          'total_sold': 156,
        },
        {
          'id': 2,
          'name': 'لاتيه',
          'category': 'مشروبات',
          'price': 7000.0,
          'cost': 3500.0,
          'stock': 32,
          'type': 'fixed',
          'available': true,
          'total_sold': 98,
        },
        {
          'id': 3,
          'name': 'شاي',
          'category': 'مشروبات',
          'price': 2500.0,
          'cost': 1000.0,
          'stock': 0,
          'type': 'fixed',
          'available': true,
          'total_sold': 234,
        },
        {
          'id': 4,
          'name': 'كيكة شوكولاتة',
          'category': 'حلويات',
          'price': 8000.0,
          'cost': 4000.0,
          'stock': 8,
          'type': 'fixed',
          'available': true,
          'total_sold': 67,
        },
        {
          'id': 5,
          'name': 'ساندوتش تونة',
          'category': 'وجبات',
          'price': 15000.0,
          'cost': 8000.0,
          'stock': 15,
          'type': 'fixed',
          'available': true,
          'total_sold': 89,
        },
        {
          'id': 6,
          'name': 'مياه معدنية',
          'category': 'مشروبات',
          'price': 1000.0,
          'cost': 500.0,
          'stock': 100,
          'type': 'fixed',
          'available': true,
          'total_sold': 312,
        },
      ],
      'categories': ['مشروبات', 'حلويات', 'وجبات', 'خفيفات'],
      'count': 6,
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo receipts data
  static Map<String, dynamic> getReceiptsData() {
    return {
      'list': [
        {
          'id': 1001,
          'total': 45000.0,
          'date': DateTime.now().toIso8601String(),
          'status': 'paid',
          'customer': 'أحمد محمد',
          'items': [
            {'name': 'قهوة تركي', 'qty': 3, 'price': 7000.0},
            {'name': 'لاتيه', 'qty': 2, 'price': 7000.0},
            {'name': 'كيكة', 'qty': 1, 'price': 8000.0},
          ],
        },
        {
          'id': 1000,
          'total': 35000.0,
          'date': DateTime.now().subtract(Duration(hours: 2)).toIso8601String(),
          'status': 'debt',
          'customer': 'سارة علي',
          'items': [
            {'name': 'ساندوتش تونة', 'qty': 1, 'price': 15000.0},
            {'name': 'مياه معدنية', 'qty': 2, 'price': 1000.0},
          ],
        },
        {
          'id': 999,
          'total': 22000.0,
          'date': DateTime.now().subtract(Duration(hours: 5)).toIso8601String(),
          'status': 'partial',
          'customer': 'خالد حسن',
          'items': [
            {'name': 'شاي', 'qty': 5, 'price': 2500.0},
            {'name': 'كيكة شوكولاتة', 'qty': 1, 'price': 8000.0},
          ],
        },
      ],
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo debts data
  static Map<String, dynamic> getDebtsData() {
    return {
      'list': [
        {
          'id': 1,
          'customer': 'سارة علي',
          'amount': 35000.0,
          'paid': 20000.0,
          'remaining': 15000.0,
          'note': 'ستدفع الأسبوع القادم',
          'created_at': DateTime.now().subtract(Duration(days: 3)).toIso8601String(),
          'receipt_id': 1000,
          'payments': [
            {'amount': 10000.0, 'paid_at': DateTime.now().subtract(Duration(days: 2)).toIso8601String(), 'note': 'دفعة أولى'},
          ],
        },
        {
          'id': 2,
          'customer': 'محمد أحمد',
          'amount': 80000.0,
          'paid': 30000.0,
          'remaining': 50000.0,
          'note': null,
          'created_at': DateTime.now().subtract(Duration(days: 7)).toIso8601String(),
          'receipt_id': 998,
          'payments': [
            {'amount': 30000.0, 'paid_at': DateTime.now().subtract(Duration(days: 5)).toIso8601String(), 'note': null},
          ],
        },
      ],
      'total_remaining': 65000.0,
      'count': 2,
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo waste data
  static Map<String, dynamic> getWasteData() {
    return {
      'log': [
        {
          'item_name': 'قهوة تركي',
          'quantity': 2.0,
          'reason': 'احترق',
          'logged_at': DateTime.now().subtract(Duration(hours: 1)).toIso8601String(),
        },
        {
          'item_name': 'كيكة',
          'quantity': 1.5,
          'reason': 'انتهت صلاحيتها',
          'logged_at': DateTime.now().subtract(Duration(hours: 4)).toIso8601String(),
        },
      ],
      'top_items': [
        {'item_name': 'قهوة تركي', 'entries': 8, 'total_qty': 12.0},
        {'item_name': 'كيكة شوكولاتة', 'entries': 5, 'total_qty': 7.5},
      ],
      'by_reason': [
        {'reason': 'احترق', 'count': 10, 'total_qty': 15.0},
        {'reason': 'انتهت صلاحيتها', 'count': 5, 'total_qty': 8.0},
        {'reason': 'خطأ في التحضير', 'count': 3, 'total_qty': 4.5},
      ],
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo analytics data
  static Map<String, dynamic> getAnalyticsData() {
    final today = DateTime.now();
    final last7Days = List.generate(7, (i) {
      final date = today.subtract(Duration(days: 6 - i));
      return {
        'day': date.toIso8601String().split('T')[0],
        'orders': 15 + (i * 3),
        'revenue': 250000.0 + (i * 50000.0),
      };
    });
    
    final last30Days = List.generate(30, (i) {
      final date = today.subtract(Duration(days: 29 - i));
      return {
        'day': date.toIso8601String().split('T')[0],
        'orders': 10 + (i % 10),
        'revenue': 150000.0 + ((i % 5) * 100000.0),
      };
    });
    
    final hourly = List.generate(24, (i) {
      return {
        'hour': i,
        'orders': (i >= 8 && i <= 10) ? 25 : (i >= 12 && i <= 14) ? 30 : (i >= 18 && i <= 20) ? 20 : 5 + (i % 3),
      };
    });
    
    return {
      'last_7_days': last7Days,
      'last_30_days': last30Days,
      'last_90_days': last30Days,
      'top_items': [
        {'name': 'قهوة تركي', 'total_qty': 450, 'total_revenue': 3150000.0, 'total_cost': 1350000.0},
        {'name': 'لاتيه', 'qty': 320, 'total_revenue': 2240000.0, 'total_cost': 1120000.0},
        {'name': 'شاي', 'total_qty': 680, 'total_revenue': 1700000.0, 'total_cost': 680000.0},
        {'name': 'كيكة شوكولاتة', 'total_qty': 245, 'total_revenue': 1960000.0, 'total_cost': 980000.0},
        {'name': 'ساندوتش تونة', 'total_qty': 180, 'total_revenue': 2700000.0, 'total_cost': 1440000.0},
      ],
      'hourly': hourly,
      'by_category': [
        {'category': 'مشروبات', 'revenue': 8500000.0},
        {'category': 'حلويات', 'revenue': 3200000.0},
        {'category': 'وجبات', 'revenue': 4500000.0},
        {'category': 'خفيفات', 'revenue': 1200000.0},
      ],
      'last_updated': DateTime.now().toIso8601String(),
    };
  }
  
  /// Get demo ingredients data
  static Map<String, dynamic> getIngredientsData() {
    return {
      'list': [
        {'id': 1, 'name': 'بن', 'quantity': 15.0, 'cost': 45000.0},
        {'id': 2, 'name': 'حليب', 'quantity': 20.0, 'cost': 60000.0},
        {'id': 3, 'name': 'سكر', 'quantity': 30.0, 'cost': 9000.0},
        {'id': 4, 'name': 'دقيق', 'quantity': 25.0, 'cost': 25000.0},
      ],
      'last_updated': DateTime.now().toIso8601String(),
    };
  }

  static List<Map<String, dynamic>> getWorkersData() {
    return [
      {'id': 1, 'name': 'أحمد', 'active': true, 'rating': 4.6, 'total_ratings': 12, 'created_at': DateTime.now().subtract(const Duration(days: 12)).toIso8601String()},
      {'id': 2, 'name': 'سارة', 'active': true, 'rating': 4.9, 'total_ratings': 18, 'created_at': DateTime.now().subtract(const Duration(days: 20)).toIso8601String()},
      {'id': 3, 'name': 'خالد', 'active': false, 'rating': 4.1, 'total_ratings': 7, 'created_at': DateTime.now().subtract(const Duration(days: 32)).toIso8601String()},
    ];
  }

  static List<Map<String, dynamic>> getShiftSchedulesData() {
    return [
      {'id': 1, 'name': 'وردية صباحية', 'shift_type': 'morning', 'start_hour': 6, 'end_hour': 14, 'allowed_workers': ['1', '2'], 'is_active': true, 'created_at': DateTime.now().subtract(const Duration(days: 30)).toIso8601String(), 'updated_at': DateTime.now().toIso8601String()},
      {'id': 2, 'name': 'وردية مسائية', 'shift_type': 'night', 'start_hour': 14, 'end_hour': 22, 'allowed_workers': ['2', '3'], 'is_active': true, 'created_at': DateTime.now().subtract(const Duration(days: 30)).toIso8601String(), 'updated_at': DateTime.now().toIso8601String()},
    ];
  }

  static List<Map<String, dynamic>> getShiftSessionsData() {
    return [
      {'id': 101, 'schedule_name': 'وردية صباحية', 'worker_name': 'أحمد', 'date': DateTime.now().toIso8601String().split('T')[0], 'start_time': DateTime.now().subtract(const Duration(hours: 4)).toIso8601String(), 'end_time': null, 'status': 'active', 'total_sales': 12, 'total_revenue': 245000.0},
      {'id': 102, 'schedule_name': 'وردية مسائية', 'worker_name': 'سارة', 'date': DateTime.now().subtract(const Duration(days: 1)).toIso8601String().split('T')[0], 'start_time': DateTime.now().subtract(const Duration(days: 1, hours: 8)).toIso8601String(), 'end_time': DateTime.now().subtract(const Duration(days: 1, hours: 1)).toIso8601String(), 'status': 'completed', 'total_sales': 19, 'total_revenue': 412000.0},
    ];
  }

  static List<Map<String, dynamic>> getWorkerRatingsData() {
    return [
      {'id': 201, 'worker_name': 'أحمد', 'rating': 5, 'notes': 'أداء ممتاز وسرعة عالية', 'created_by': 'النظام', 'created_at': DateTime.now().subtract(const Duration(days: 2)).toIso8601String()},
      {'id': 202, 'worker_name': 'سارة', 'rating': 4, 'notes': 'دقيقة في التسليم', 'created_by': 'المالك', 'created_at': DateTime.now().subtract(const Duration(days: 5)).toIso8601String()},
    ];
  }

  static List<Map<String, dynamic>> getShiftHandoverData() {
    return [
      {'id': 301, 'from_cashier_name': 'أحمد', 'to_cashier_name': 'سارة', 'notes': 'تم تسليم الصندوق بشكل كامل', 'cash_handover': 125000.0, 'created_at': DateTime.now().subtract(const Duration(hours: 3)).toIso8601String()},
    ];
  }
}