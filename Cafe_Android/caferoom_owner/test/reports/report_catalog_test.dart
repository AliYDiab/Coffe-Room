import 'package:caferoom_owner/reports/report_catalog.dart';
import 'package:caferoom_owner/reports/report_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('ReportCatalog', () {
    test('inventory report exposes price cost margin stock and value', () {
      final report = ReportCatalog.fromScreen(
        1,
        ReportDataBundle(documents: {
          'inventory': {
            'items': [
              {
                'id': 7,
                'name': 'قهوة',
                'category': 'مشروبات',
                'barcode_value': '123',
                'price': 7000,
                'cost': 3000,
                'stock': 5,
                'total_sold': 12,
                'available': true,
                'type': 'fixed',
              },
            ],
          },
        }),
      );

      final table = report.sections.single.tables.single;
      expect(
          table.headers,
          containsAll([
            'سعر البيع',
            'التكلفة',
            'ربح الوحدة',
            'هامش الربح',
            'المخزون',
            'قيمة التكلفة',
            'قيمة البيع',
          ]));
      expect(table.rows.single,
          containsAll(['4,000', '57.1%', '15,000', '35,000']));
    });

    test('receipt report contains worker profit and line-item detail', () {
      final report = ReportCatalog.fromScreen(
        2,
        ReportDataBundle(documents: {
          'receipts': {
            'list': [
              {
                'id': 11,
                'date': '2026-09-01T10:30:00',
                'customer': 'أحمد',
                'status': 'paid',
                'worker_id': 3,
                'worker_name': 'ليلى',
                'worker_session_id': 42,
                'total': 14000,
                'profit': 8000,
                'items': [
                  {'name': 'قهوة', 'qty': 2, 'price': 7000, 'cost': 3000},
                ],
              },
            ],
          },
        }),
      );

      expect(report.sections.expand((s) => s.tables).length, 2);
      expect(report.sections[0].tables[0].headers,
          containsAll(['العامل', 'الجلسة', 'الربح']));
      expect(report.sections[1].tables[0].rows.single,
          containsAll(['قهوة', '2', '14,000', '6,000', '8,000']));
    });

    test('finance report uses actual monthly profit fields', () {
      final report = ReportCatalog.fromScreen(
        6,
        ReportDataBundle(documents: {
          'analytics': {
            'monthly': [
              {
                'period': '2026-08',
                'orders': 20,
                'revenue': 100000,
                'cost': 40000,
                'gross_profit': 60000,
                'expenses': 10000,
                'net_profit': 50000,
              },
            ],
          },
        }),
      );

      final table = report.sections.single.tables.single;
      expect(
          table.headers,
          containsAll([
            'الإيراد',
            'تكلفة المبيعات',
            'الربح الإجمالي',
            'المصروفات',
            'صافي الربح'
          ]));
      expect(table.rows.single,
          containsAll(['100,000', '40,000', '60,000', '10,000', '50,000']));
    });

    test('shift report keeps shift total and worker subtotals', () {
      final report = ReportCatalog.fromScreen(
        9,
        ReportDataBundle(collections: {
          'shift_sessions': [
            {
              'id': 8,
              'schedule_name': 'المساء',
              'total_sales': 30,
              'total_revenue': 210000,
              'workers': [
                {'worker_name': 'A', 'items_sold': 10, 'revenue': 70000},
                {'worker_name': 'B', 'items_sold': 20, 'revenue': 140000},
              ],
            },
          ],
        }),
      );

      final tables = report.sections.expand((s) => s.tables).toList();
      final shifts = tables.firstWhere((t) => t.title == 'جلسات الورديات');
      final workers =
          tables.firstWhere((t) => t.title == 'تفصيل العامل داخل الوردية');
      expect(shifts.rows.single, containsAll(['30', '210,000']));
      expect(workers.rows, hasLength(2));
      expect(workers.rows[0], containsAll(['A', '10', '70,000']));
      expect(workers.rows[1], containsAll(['B', '20', '140,000']));
    });

    test('all twelve navigation screens have a report definition', () {
      const bundle = ReportDataBundle();
      for (var index = 0; index < 12; index++) {
        final report = ReportCatalog.fromScreen(index, bundle);
        expect(report.title, isNotEmpty, reason: 'screen $index');
        expect(report.sections, isNotEmpty, reason: 'screen $index');
      }
    });
  });
}
