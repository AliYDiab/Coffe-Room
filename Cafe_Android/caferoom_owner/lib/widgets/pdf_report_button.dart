import 'package:flutter/material.dart';

import '../reports/report_catalog.dart';
import '../reports/report_data_service.dart';
import '../reports/report_models.dart';
import '../screens/report_preview_screen.dart';

typedef ReportOpener = Future<void> Function(
    BuildContext context, ReportDocument report);

class PdfReportButton extends StatefulWidget {
  final int screenIndex;
  final ReportDataService? dataService;
  final ReportOpener? openReport;

  const PdfReportButton({
    super.key,
    required this.screenIndex,
    this.dataService,
    this.openReport,
  });

  @override
  State<PdfReportButton> createState() => _PdfReportButtonState();
}

class _PdfReportButtonState extends State<PdfReportButton> {
  bool _loading = false;

  @override
  Widget build(BuildContext context) {
    return IconButton(
      tooltip: 'تقرير PDF',
      onPressed: _loading ? null : _open,
      icon: _loading
          ? const SizedBox(
              width: 18,
              height: 18,
              child: CircularProgressIndicator(strokeWidth: 2),
            )
          : const Icon(Icons.picture_as_pdf_outlined),
    );
  }

  Future<void> _open() async {
    setState(() => _loading = true);
    try {
      final bundle = await (widget.dataService ?? ReportDataService())
          .loadForScreen(widget.screenIndex);
      final report = ReportCatalog.fromScreen(widget.screenIndex, bundle);
      if (!mounted) return;
      final opener = widget.openReport ?? _openPreview;
      await opener(context, report);
    } catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(
                'تعذر إنشاء التقرير. تحقق من الاتصال وحاول مجدداً.\n$error'),
            action: SnackBarAction(label: 'إعادة', onPressed: _open),
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _openPreview(BuildContext context, ReportDocument report) async {
    await Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => ReportPreviewScreen(report: report),
    ));
  }
}
