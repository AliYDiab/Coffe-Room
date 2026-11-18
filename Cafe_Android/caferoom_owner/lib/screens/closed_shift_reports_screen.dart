import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';

import '../reports/report_models.dart';
import 'report_preview_screen.dart';

class ClosedShiftReportsScreen extends StatefulWidget {
  const ClosedShiftReportsScreen({super.key});

  @override
  State<ClosedShiftReportsScreen> createState() =>
      _ClosedShiftReportsScreenState();
}

class _ClosedShiftReportsScreenState extends State<ClosedShiftReportsScreen> {
  late final _cafe = FirebaseFirestore.instance.collection('cafe');
  late final _reports =
      _cafe.where('entity', isEqualTo: 'closed_shift_report').snapshots();
  String? _opening;

  static const _tables = <String, (String, List<String>)>{
    'receipts': ('الفواتير', ['رقم الفاتورة', 'الوقت', 'الإجمالي', 'الحالة']),
    'sales': (
      'بنود المبيعات',
      ['الفاتورة', 'الوقت', 'الصنف', 'الكمية', 'سعر الوحدة', 'قيمة البند']
    ),
    'expenses': ('المصروفات', ['الوقت', 'الفئة', 'المبلغ', 'الملاحظة']),
    'waste': ('الهدر', ['الوقت', 'الصنف', 'الكمية', 'السبب']),
    'debt_payments': ('تسديد الديون', ['الوقت', 'الدين', 'المبلغ', 'الملاحظة']),
  };

  String _text(Object? value) => value?.toString() ?? '';
  String _time(Object? value) =>
      _text(value).split('.').first.replaceFirst('T', ' ');

  Future<void> _open(QueryDocumentSnapshot<Map<String, dynamic>> doc) async {
    setState(() => _opening = doc.id);
    try {
      final data = doc.data();
      final references = Map<String, dynamic>.from(data['sections'] as Map);
      final tables = <ReportTable>[];
      for (final entry in _tables.entries) {
        final refs = List<String>.from(references[entry.key] as List? ?? []);
        final rows = <List<String>>[];
        for (final ref in refs) {
          final snapshot = await _cafe.doc(ref).get();
          final values = snapshot.data()?['rows'] as List?;
          if (values == null) throw StateError('جزء من التقرير غير متاح');
          for (final row in values) {
            rows.add((row['values'] as List).map(_text).toList());
          }
        }
        tables.add(ReportTable(
          title: entry.value.$1,
          headers: entry.value.$2,
          rows: rows,
        ));
      }
      final report = ReportDocument(
        title: 'وردية ${_text(data['worker'])} - ${_time(data['end'])}',
        scope: '${_time(data['start'])} إلى ${_time(data['end'])}',
        sections: [
          ReportSection(
            title: 'تفاصيل الوردية',
            summaries: {
              'المشروبات المباعة': _text(data['drinks']),
              'عدد الفواتير': _text(data['receipt_count']),
              'قيمة الفواتير المدفوعة': _text(data['paid_total']),
              'قيمة فواتير الدين': _text(data['debt_total']),
            },
            tables: tables,
          ),
        ],
      );
      if (!mounted) return;
      await Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => ReportPreviewScreen(report: report),
      ));
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('تعذر فتح التقرير. حاول مجدداً.')),
      );
    } finally {
      if (mounted) setState(() => _opening = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    return StreamBuilder<QuerySnapshot<Map<String, dynamic>>>(
      stream: _reports,
      builder: (context, snapshot) {
        if (snapshot.hasError) {
          return const Center(child: Text('تعذر تحميل تقارير الورديات'));
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final docs = snapshot.data!.docs.toList()
          ..sort((a, b) =>
              _text(b.data()['end']).compareTo(_text(a.data()['end'])));
        if (docs.isEmpty) {
          return const Center(child: Text('لا توجد تقارير ورديات بعد'));
        }
        return ListView.builder(
          itemCount: docs.length,
          itemBuilder: (context, index) {
            final doc = docs[index];
            final data = doc.data();
            return ListTile(
              leading: _opening == doc.id
                  ? const CircularProgressIndicator()
                  : const Icon(Icons.picture_as_pdf_outlined),
              title: Text(_text(data['worker'])),
              subtitle: Text(_time(data['end'])),
              onTap: _opening == null ? () => _open(doc) : null,
            );
          },
        );
      },
    );
  }
}
