import 'package:flutter/services.dart';
import 'package:intl/intl.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;

import 'report_models.dart';

typedef ReportFontLoader = Future<ByteData> Function(String asset);

class PdfReportService {
  static const _regularFont = 'assets/fonts/NotoSansArabic-Regular.ttf';
  static const _boldFont = 'assets/fonts/NotoSansArabic-Bold.ttf';

  final ReportFontLoader fontLoader;

  PdfReportService({ReportFontLoader? fontLoader})
      : fontLoader = fontLoader ?? rootBundle.load;

  Future<Uint8List> build(ReportDocument report) async {
    final regularData = await fontLoader(_regularFont);
    final boldData = await fontLoader(_boldFont);
    final regular = pw.Font.ttf(regularData);
    final bold = pw.Font.ttf(boldData);
    final pdf = pw.Document(
      title: report.title,
      author: 'CafeRoom',
      creator: 'CafeRoom Owner',
      subject: report.scope,
    );
    final wide = report.sections
        .expand((section) => section.tables)
        .any((table) => table.headers.length > 7);
    final format = wide ? PdfPageFormat.a4.landscape : PdfPageFormat.a4;
    final generated = DateFormat('yyyy-MM-dd HH:mm').format(report.generatedAt);

    pdf.addPage(
      pw.MultiPage(
        maxPages: 500,
        pageTheme: pw.PageTheme(
          pageFormat: format,
          margin: const pw.EdgeInsets.fromLTRB(24, 34, 24, 34),
          textDirection: pw.TextDirection.rtl,
          theme: pw.ThemeData.withFont(base: regular, bold: bold),
        ),
        header: (context) => pw.Container(
          padding: const pw.EdgeInsets.only(bottom: 8),
          decoration: const pw.BoxDecoration(
            border: pw.Border(
                bottom: pw.BorderSide(color: PdfColors.amber700, width: 1.5)),
          ),
          child: pw.Row(
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              pw.Text('غرفة القهوة',
                  style: pw.TextStyle(
                      font: bold, fontSize: 12, color: PdfColors.brown900)),
              pw.Text(report.title,
                  style: pw.TextStyle(font: bold, fontSize: 12)),
            ],
          ),
        ),
        footer: (context) => pw.Container(
          padding: const pw.EdgeInsets.only(top: 6),
          decoration: const pw.BoxDecoration(
            border: pw.Border(
                top: pw.BorderSide(color: PdfColors.grey400, width: .5)),
          ),
          child: pw.Row(
            mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
            children: [
              pw.Text('تم الإنشاء: $generated',
                  style: const pw.TextStyle(
                      fontSize: 8, color: PdfColors.grey700)),
              pw.Text('صفحة ${context.pageNumber} من ${context.pagesCount}',
                  style: const pw.TextStyle(
                      fontSize: 8, color: PdfColors.grey700)),
            ],
          ),
        ),
        build: (context) => [
          pw.SizedBox(height: 12),
          pw.Text(report.title,
              style: pw.TextStyle(
                  font: bold, fontSize: 23, color: PdfColors.brown900)),
          pw.SizedBox(height: 5),
          pw.Text('النطاق: ${report.scope}',
              style: const pw.TextStyle(fontSize: 9, color: PdfColors.grey700)),
          pw.SizedBox(height: 16),
          for (final section in report.sections) ..._section(section, bold),
        ],
      ),
    );

    return pdf.save();
  }

  List<pw.Widget> _section(ReportSection section, pw.Font bold) {
    return [
      pw.Header(
        level: 1,
        text: section.title,
        textStyle:
            pw.TextStyle(font: bold, fontSize: 16, color: PdfColors.brown800),
        decoration: const pw.BoxDecoration(
          border: pw.Border(
              bottom: pw.BorderSide(color: PdfColors.amber600, width: 1)),
        ),
      ),
      if (section.summaries.isNotEmpty)
        pw.Wrap(
          spacing: 8,
          runSpacing: 8,
          children: section.summaries.entries.map((entry) {
            return pw.Container(
              width: 145,
              padding: const pw.EdgeInsets.all(8),
              decoration: pw.BoxDecoration(
                color: PdfColors.amber50,
                borderRadius: pw.BorderRadius.circular(4),
                border: pw.Border.all(color: PdfColors.amber300, width: .5),
              ),
              child: pw.Column(
                crossAxisAlignment: pw.CrossAxisAlignment.start,
                children: [
                  pw.Text(entry.key,
                      style: const pw.TextStyle(
                          fontSize: 8, color: PdfColors.grey700)),
                  pw.SizedBox(height: 3),
                  pw.Text(entry.value,
                      style: pw.TextStyle(font: bold, fontSize: 11)),
                ],
              ),
            );
          }).toList(),
        ),
      if (section.note != null) ...[
        pw.SizedBox(height: 8),
        pw.Container(
          width: double.infinity,
          padding: const pw.EdgeInsets.all(7),
          color: PdfColors.grey100,
          child: pw.Text(section.note!,
              style: const pw.TextStyle(fontSize: 8, color: PdfColors.grey800)),
        ),
      ],
      for (final table in section.tables) ...[
        pw.SizedBox(height: 12),
        pw.Text(table.title, style: pw.TextStyle(font: bold, fontSize: 12)),
        pw.SizedBox(height: 5),
        if (table.rows.isEmpty)
          pw.Container(
            width: double.infinity,
            padding: const pw.EdgeInsets.all(10),
            color: PdfColors.grey100,
            child: pw.Text('لا توجد بيانات متاحة لهذا الجدول.',
                style: const pw.TextStyle(fontSize: 9)),
          )
        else
          pw.TableHelper.fromTextArray(
            headers: table.headers,
            data: table.rows,
            headerStyle: pw.TextStyle(
                font: bold,
                fontSize: table.headers.length > 10 ? 6 : 7.5,
                color: PdfColors.white),
            cellStyle:
                pw.TextStyle(fontSize: table.headers.length > 10 ? 5.5 : 7),
            headerDecoration: const pw.BoxDecoration(color: PdfColors.brown800),
            oddRowDecoration: const pw.BoxDecoration(color: PdfColors.amber50),
            border: pw.TableBorder.all(color: PdfColors.grey400, width: .35),
            headerAlignment: pw.Alignment.center,
            cellAlignment: pw.Alignment.center,
            cellPadding:
                const pw.EdgeInsets.symmetric(horizontal: 3, vertical: 4),
          ),
      ],
      pw.SizedBox(height: 14),
    ];
  }
}
