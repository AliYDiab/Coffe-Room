import 'package:caferoom_owner/reports/report_data_service.dart';
import 'package:caferoom_owner/reports/report_models.dart';
import 'package:caferoom_owner/widgets/pdf_report_button.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('loads the selected screen and opens its report', (tester) async {
    ReportDocument? opened;
    final service = ReportDataService(
      documentLoader: (name) async => {
        'today_revenue': 1000,
        'top_items_today': <Map<String, dynamic>>[],
      },
      collectionLoader: (name) async => [],
      requestHistoryLoader: () async => [],
    );

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        appBar: AppBar(actions: [
          PdfReportButton(
            screenIndex: 0,
            dataService: service,
            openReport: (context, report) async => opened = report,
          ),
        ]),
      ),
    ));

    await tester.tap(find.byTooltip('تقرير PDF'));
    await tester.pumpAndSettle();

    expect(opened?.title, 'تقرير لوحة التحكم');
  });

  testWidgets('shows a retryable message when report loading fails',
      (tester) async {
    final service = ReportDataService(
      documentLoader: (name) async => throw StateError('offline'),
      collectionLoader: (name) async => [],
      requestHistoryLoader: () async => [],
    );

    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        appBar: AppBar(actions: [
          PdfReportButton(screenIndex: 0, dataService: service),
        ]),
      ),
    ));

    await tester.tap(find.byTooltip('تقرير PDF'));
    await tester.pumpAndSettle();

    expect(find.textContaining('تعذر إنشاء التقرير'), findsOneWidget);
  });
}
