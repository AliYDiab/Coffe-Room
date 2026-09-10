import 'package:caferoom_owner/services/analytics_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('financial totals use synchronized cost profit and expenses', () {
    final totals = AnalyticsService.calculateFinancialTotals([
      {
        'revenue': 100,
        'cost': 40,
        'gross_profit': 60,
        'expenses': 10,
        'net_profit': 50,
      },
      {
        'revenue': 200,
        'cost': 80,
        'gross_profit': 120,
        'expenses': 20,
        'net_profit': 100,
      },
    ]);

    expect(totals['revenue'], 300);
    expect(totals['cost'], 120);
    expect(totals['gross_profit'], 180);
    expect(totals['expenses'], 30);
    expect(totals['net_profit'], 150);
  });
}
