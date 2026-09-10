import 'package:flutter/material.dart';
import 'package:printing/printing.dart';

import '../reports/pdf_report_service.dart';
import '../reports/report_models.dart';

class ReportPreviewScreen extends StatelessWidget {
  final ReportDocument report;

  const ReportPreviewScreen({super.key, required this.report});

  @override
  Widget build(BuildContext context) {
    final service = PdfReportService();
    final safeName =
        report.title.replaceAll(RegExp(r'[^\w\u0600-\u06FF-]+'), '_');
    return Scaffold(
      appBar: AppBar(title: Text(report.title)),
      body: PdfPreview(
        pdfFileName: '$safeName.pdf',
        build: (_) => service.build(report),
        canChangeOrientation: false,
        canChangePageFormat: false,
        canDebug: false,
        allowPrinting: true,
        allowSharing: true,
        loadingWidget: const Center(child: CircularProgressIndicator()),
        onError: (context, error) => Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child:
                Text('تعذر عرض ملف PDF\n$error', textAlign: TextAlign.center),
          ),
        ),
      ),
    );
  }
}
