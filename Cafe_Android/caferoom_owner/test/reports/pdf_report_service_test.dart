import 'dart:convert';
import 'dart:io';

import 'package:caferoom_owner/reports/pdf_report_service.dart';
import 'package:caferoom_owner/reports/report_models.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('builds a valid multi-page PDF for a long Arabic table', () async {
    final rows = List.generate(
        180,
        (index) => [
              '${index + 1}',
              'قهوة عربية رقم ${index + 1}',
              '${(index + 1) * 1000}',
            ]);
    final report = ReportDocument(
      title: 'تقرير اختبار عربي',
      sections: [
        ReportSection(
          title: 'المخزون',
          summaries: const {'عدد الأصناف': '180'},
          tables: [
            ReportTable(
              title: 'الأصناف',
              headers: const ['المعرف', 'الصنف', 'القيمة'],
              rows: rows,
            ),
          ],
        ),
      ],
    );

    final bytes = await PdfReportService().build(report);
    final qaOutput = Platform.environment['REPORT_QA_OUTPUT'];
    if (qaOutput != null && qaOutput.isNotEmpty) {
      final output = File(qaOutput);
      await output.parent.create(recursive: true);
      await output.writeAsBytes(bytes);
    }
    final source = latin1.decode(bytes, allowInvalid: true);

    expect(bytes.length, greaterThan(1000));
    expect(source.startsWith('%PDF-'), isTrue);
    expect(
        RegExp(r'/Type\s*/Page\b').allMatches(source).length, greaterThan(1));
  });
}
