import 'package:intl/intl.dart';

import 'report_models.dart';

class ReportCatalog {
  static final NumberFormat _number = NumberFormat('#,##0.##', 'en_US');

  static ReportDocument fromScreen(int screenIndex, ReportDataBundle data) {
    switch (screenIndex) {
      case 0:
        return _dashboard(data.document('dashboard'));
      case 1:
        return _inventory(data.document('inventory'),
            title: 'تقرير المخزون الكامل');
      case 2:
        return _receipts(data.document('receipts'));
      case 3:
        return _debts(data.document('debts'));
      case 4:
        return _waste(data.document('waste'));
      case 5:
        return _salesAnalytics(data.document('analytics'));
      case 6:
        return _finance(data.document('analytics'));
      case 7:
        return _inventory(data.document('inventory'),
            title: 'تقرير ذكاء المخزون');
      case 8:
        return _customers(data.document('receipts'), data.document('debts'));
      case 9:
        return _operations(data);
      case 10:
        return _entryData(
            data.document('ingredients'), data.document('expenses'));
      case 11:
        return _requests(data);
      default:
        throw RangeError.range(screenIndex, 0, 11, 'screenIndex');
    }
  }

  static ReportDocument _dashboard(Map<String, dynamic> d) {
    final top = _maps(d['top_items_today']);
    return ReportDocument(title: 'تقرير لوحة التحكم', sections: [
      ReportSection(
        title: 'الملخص التنفيذي',
        summaries: {
          'إيراد اليوم': _money(d['today_revenue']),
          'طلبات اليوم': _text(d['today_orders']),
          'إجمالي الإيراد': _money(d['total_revenue']),
          'الدين المتبقي': _money(d['debt_remaining']),
          'مخزون منخفض': _text(d['low_stock_count']),
          'نافد من المخزون': _text(d['out_stock_count']),
          'هدر اليوم': _text(d['waste_today_count']),
        },
        tables: [
          _table(
            'الأصناف الأفضل اليوم',
            ['الصنف', 'الكمية', 'الإيراد'],
            top,
            ['name', 'qty', 'revenue'],
            moneyKeys: const {'revenue'},
          ),
        ],
      ),
    ]);
  }

  static ReportDocument _inventory(Map<String, dynamic> d,
      {required String title}) {
    final items = _maps(d['items']);
    final rows = items.map((item) {
      final price = _double(item['price']);
      final cost = _double(item['cost']);
      final stock = _double(item['stock']);
      final margin = price == 0 ? 0 : ((price - cost) / price) * 100;
      return [
        _text(item['id']),
        _text(item['barcode_value']),
        _text(item['name']),
        _text(item['category']),
        _text(item['type']),
        _format(price),
        _format(cost),
        _format(price - cost),
        '${margin.toStringAsFixed(1)}%',
        _format(stock),
        _format(cost * stock),
        _format(price * stock),
        _text(item['total_sold']),
        _bool(item['available']),
        _stockStatus(stock),
      ];
    }).toList();

    final totalCost = items.fold<double>(
        0, (sum, item) => sum + _double(item['cost']) * _double(item['stock']));
    final totalRetail = items.fold<double>(0,
        (sum, item) => sum + _double(item['price']) * _double(item['stock']));

    return ReportDocument(title: title, sections: [
      ReportSection(
        title: 'ملخص المخزون',
        summaries: {
          'عدد الأصناف': '${items.length}',
          'قيمة التكلفة': _format(totalCost),
          'قيمة البيع': _format(totalRetail),
          'الربح المتوقع': _format(totalRetail - totalCost),
        },
        tables: [
          ReportTable(
            title: 'جميع الأصناف والتكاليف والأسعار',
            headers: const [
              'المعرف',
              'الباركود',
              'الصنف',
              'الفئة',
              'النوع',
              'سعر البيع',
              'التكلفة',
              'ربح الوحدة',
              'هامش الربح',
              'المخزون',
              'قيمة التكلفة',
              'قيمة البيع',
              'إجمالي المباع',
              'متاح',
              'الحالة',
            ],
            rows: rows,
          ),
        ],
      ),
    ]);
  }

  static ReportDocument _receipts(Map<String, dynamic> d) {
    final receipts = _maps(d['list']);
    final receiptRows = <List<String>>[];
    final itemRows = <List<String>>[];
    for (final receipt in receipts) {
      final items = _maps(receipt['items']);
      final itemCost = items.fold<double>(
          0, (sum, item) => sum + _double(item['qty']) * _double(item['cost']));
      final total = _double(receipt['total']);
      final profit = receipt['profit'] == null
          ? total - itemCost
          : _double(receipt['profit']);
      receiptRows.add([
        _text(receipt['id']),
        _date(receipt['income_date'] ?? receipt['date']),
        _text(receipt['customer']),
        _status(receipt['status']),
        _text(receipt['worker_name'] ?? receipt['worker_id']),
        _text(receipt['worker_session_id'] ?? receipt['session_id']),
        _format(total),
        _format(itemCost),
        _format(profit),
      ]);
      for (final item in items) {
        final qty = _double(item['qty']);
        final price = _double(item['price']);
        final cost = _double(item['cost']);
        itemRows.add([
          _text(receipt['id']),
          _text(item['item_id']),
          _text(item['name']),
          _format(qty),
          _format(qty * price),
          _format(qty * cost),
          _format(qty * (price - cost)),
        ]);
      }
    }
    return ReportDocument(title: 'تقرير الفواتير والمبيعات', sections: [
      ReportSection(title: 'الفواتير', tables: [
        ReportTable(
          title: 'ملخص الفواتير',
          headers: const [
            'الفاتورة',
            'التاريخ',
            'العميل',
            'الحالة',
            'العامل',
            'الجلسة',
            'الإجمالي',
            'التكلفة',
            'الربح'
          ],
          rows: receiptRows,
        ),
      ]),
      ReportSection(title: 'تفاصيل الأصناف', tables: [
        ReportTable(
          title: 'أصناف الفواتير',
          headers: const [
            'الفاتورة',
            'معرف الصنف',
            'الصنف',
            'الكمية',
            'الإيراد',
            'التكلفة',
            'الربح'
          ],
          rows: itemRows,
        ),
      ]),
    ]);
  }

  static ReportDocument _debts(Map<String, dynamic> d) {
    final debts = _maps(d['list']);
    final paymentRows = <List<String>>[];
    for (final debt in debts) {
      for (final payment in _maps(debt['payments'])) {
        paymentRows.add([
          _text(debt['customer']),
          _money(payment['amount']),
          _date(payment['paid_at']),
          _text(payment['note']),
        ]);
      }
    }
    return ReportDocument(title: 'تقرير الديون والتحصيل', sections: [
      ReportSection(
        title: 'الديون',
        summaries: {
          'إجمالي المتبقي': _money(d['total_remaining']),
          'عدد السجلات': '${debts.length}',
        },
        tables: [
          _table(
              'سجل الديون',
              [
                'العميل',
                'المبلغ',
                'المدفوع',
                'المتبقي',
                'الملاحظة',
                'تاريخ الإنشاء',
                'الفاتورة'
              ],
              debts,
              [
                'customer',
                'amount',
                'paid',
                'remaining',
                'note',
                'created_at',
                'receipt_id'
              ],
              moneyKeys: const {'amount', 'paid', 'remaining'},
              dateKeys: const {'created_at'}),
          ReportTable(
              title: 'سجل الدفعات',
              headers: const ['العميل', 'المبلغ', 'التاريخ', 'الملاحظة'],
              rows: paymentRows),
        ],
      ),
    ]);
  }

  static ReportDocument _waste(Map<String, dynamic> d) => ReportDocument(
        title: 'تقرير الهدر',
        sections: [
          ReportSection(title: 'الهدر', tables: [
            _table(
                'سجل الهدر',
                ['الصنف', 'الكمية', 'السبب', 'التاريخ'],
                _maps(d['log']),
                ['item_name', 'quantity', 'reason', 'logged_at'],
                dateKeys: const {'logged_at'}),
            _table('الهدر حسب الصنف', ['الصنف', 'عدد العمليات', 'الكمية'],
                _maps(d['top_items']), ['item_name', 'entries', 'total_qty']),
            _table('الهدر حسب السبب', ['السبب', 'عدد العمليات', 'الكمية'],
                _maps(d['by_reason']), ['reason', 'count', 'total_qty']),
          ])
        ],
      );

  static ReportDocument _salesAnalytics(Map<String, dynamic> d) {
    final tables = <ReportTable>[];
    for (final period in const [
      ('last_7_days', 'آخر 7 أيام'),
      ('last_30_days', 'آخر 30 يوماً'),
      ('last_90_days', 'آخر 90 يوماً')
    ]) {
      final rows = _maps(d[period.$1]);
      if (rows.isNotEmpty) tables.add(_financeTable(period.$2, rows));
    }
    tables.addAll([
      _table(
          'أفضل الأصناف',
          ['الصنف', 'الكمية', 'الإيراد', 'التكلفة'],
          _maps(d['top_items']),
          ['name', 'total_qty', 'total_revenue', 'total_cost'],
          moneyKeys: const {'total_revenue', 'total_cost'}),
      _table('المبيعات حسب الفئة', ['الفئة', 'الإيراد'],
          _maps(d['by_category']), ['category', 'revenue'],
          moneyKeys: const {'revenue'}),
      _table('الطلبات حسب الساعة', ['الساعة', 'الطلبات'], _maps(d['hourly']),
          ['hour', 'orders']),
    ]);
    return ReportDocument(
        title: 'تقرير تحليلات المبيعات',
        sections: [ReportSection(title: 'التحليلات', tables: tables)]);
  }

  static ReportDocument _finance(Map<String, dynamic> d) {
    final tables = <ReportTable>[];
    for (final period in const [
      ('monthly', 'الدخل الشهري'),
      ('yearly', 'الدخل السنوي'),
      ('last_90_days', 'الدخل اليومي - 90 يوماً'),
      ('last_30_days', 'الدخل اليومي - 30 يوماً'),
      ('last_7_days', 'الدخل اليومي - 7 أيام')
    ]) {
      final rows = _maps(d[period.$1]);
      if (rows.isNotEmpty) tables.add(_financeTable(period.$2, rows));
    }
    if (tables.isEmpty) tables.add(_financeTable('البيانات المالية', const []));
    return ReportDocument(title: 'تقرير الدخل والأرباح', sections: [
      ReportSection(
        title: 'الدخل اليومي والشهري والسنوي',
        tables: tables,
        note:
            'الأرباح تعتمد على تكاليف الأصناف المسجلة. أي تكلفة مفقودة تُحسب صفراً وتظهر ضمن نطاق البيانات المتزامنة.',
      ),
    ]);
  }

  static ReportTable _financeTable(
      String title, List<Map<String, dynamic>> rows) {
    return ReportTable(
      title: title,
      headers: const [
        'الفترة',
        'الطلبات',
        'الإيراد',
        'تكلفة المبيعات',
        'الربح الإجمالي',
        'المصروفات',
        'صافي الربح',
        'متوسط الطلب',
        'الهامش'
      ],
      rows: rows.map((row) {
        final revenue = _double(row['revenue']);
        final gross = _double(row['gross_profit']);
        final cost =
            row['cost'] == null ? revenue - gross : _double(row['cost']);
        final expenses = _double(row['expenses']);
        final net = row['net_profit'] == null
            ? gross - expenses
            : _double(row['net_profit']);
        final orders = _double(row['orders']);
        return [
          _text(row['period'] ?? row['day'] ?? row['month'] ?? row['year']),
          _format(orders),
          _format(revenue),
          _format(cost),
          _format(gross),
          _format(expenses),
          _format(net),
          _format(orders == 0 ? 0 : revenue / orders),
          '${(revenue == 0 ? 0 : net / revenue * 100).toStringAsFixed(1)}%',
        ];
      }).toList(),
    );
  }

  static ReportDocument _customers(
      Map<String, dynamic> receiptDoc, Map<String, dynamic> debtDoc) {
    final customers = <String, Map<String, dynamic>>{};
    for (final receipt in _maps(receiptDoc['list'])) {
      final name = _text(receipt['customer']).trim().isEmpty
          ? 'عميل نقدي'
          : _text(receipt['customer']);
      final row = customers.putIfAbsent(
          name, () => {'orders': 0, 'spent': 0.0, 'last': ''});
      row['orders'] = (row['orders'] as int) + 1;
      row['spent'] = (row['spent'] as double) + _double(receipt['total']);
      final date = _date(receipt['date']);
      if (date.compareTo(row['last'] as String) > 0) row['last'] = date;
    }
    final rows = customers.entries.map((entry) {
      final orders = entry.value['orders'] as int;
      final spent = entry.value['spent'] as double;
      return [
        entry.key,
        '$orders',
        _format(spent),
        _format(orders == 0 ? 0 : spent / orders),
        _text(entry.value['last'])
      ];
    }).toList()
      ..sort((a, b) => b[2].compareTo(a[2]));
    return ReportDocument(title: 'تقرير العملاء', sections: [
      ReportSection(
          title: 'قيمة وولاء العملاء',
          tables: [
            ReportTable(
                title: 'العملاء',
                headers: const [
                  'العميل',
                  'الطلبات',
                  'إجمالي الإنفاق',
                  'متوسط الطلب',
                  'آخر شراء'
                ],
                rows: rows),
            _table(
                'ديون العملاء',
                ['العميل', 'المبلغ', 'المدفوع', 'المتبقي'],
                _maps(debtDoc['list']),
                ['customer', 'amount', 'paid', 'remaining'],
                moneyKeys: const {'amount', 'paid', 'remaining'}),
          ],
          note:
              'المبيعات المسجلة دون اسم عميل مجمعة تحت «عميل نقدي» ولا تمثل شخصاً واحداً.'),
    ]);
  }

  static ReportDocument _operations(ReportDataBundle data) {
    final tables = <ReportTable>[];
    tables.add(_dynamicTable('العمال', data.collection('workers')));
    tables.add(
        _dynamicTable('جداول الورديات', data.collection('shift_schedules')));
    final sessions = data.collection('shift_sessions');
    tables.add(_table(
        'جلسات الورديات',
        [
          'المعرف',
          'الوردية',
          'العامل',
          'التاريخ',
          'الحالة',
          'إجمالي المباع',
          'إجمالي الإيراد'
        ],
        sessions,
        [
          'id',
          'schedule_name',
          'worker_name',
          'date',
          'status',
          'total_sales',
          'total_revenue'
        ],
        moneyKeys: const {'total_revenue'},
        dateKeys: const {'date'}));
    final workerRows = <List<String>>[];
    for (final session in sessions) {
      for (final worker in _maps(session['workers'])) {
        workerRows.add([
          _text(session['id']),
          _text(session['schedule_name']),
          _text(worker['worker_name'] ?? worker['name']),
          _text(worker['items_sold'] ?? worker['total_sales']),
          _money(worker['revenue'] ?? worker['total_revenue']),
        ]);
      }
    }
    tables.add(ReportTable(
        title: 'تفصيل العامل داخل الوردية',
        headers: const ['الجلسة', 'الوردية', 'العامل', 'المباع', 'الإيراد'],
        rows: workerRows));
    tables.add(
        _dynamicTable('تقييمات العمال', data.collection('worker_ratings')));
    tables.add(
        _dynamicTable('تسليم الورديات', data.collection('shift_handover')));
    return ReportDocument(
        title: 'تقرير العمال والورديات',
        sections: [ReportSection(title: 'بيانات التشغيل', tables: tables)]);
  }

  static ReportDocument _entryData(
          Map<String, dynamic> ingredients, Map<String, dynamic> expenses) =>
      ReportDocument(
        title: 'تقرير المكونات والمصروفات',
        sections: [
          ReportSection(title: 'بيانات الإدخال المتزامنة', tables: [
            _table('المكونات', ['المعرف', 'المكون', 'الكمية', 'التكلفة'],
                _maps(ingredients['list']), ['id', 'name', 'quantity', 'cost'],
                moneyKeys: const {'cost'}),
            _table(
                'المصروفات',
                [
                  'المعرف',
                  'التاريخ',
                  'الفئة',
                  'المبلغ',
                  'المورد',
                  'الملاحظة',
                  'المصدر'
                ],
                _maps(expenses['list']),
                [
                  'id',
                  'date',
                  'category',
                  'amount',
                  'vendor',
                  'note',
                  'source'
                ],
                moneyKeys: const {'amount'},
                dateKeys: const {'date'}),
            _table('المصروفات حسب الفئة', ['الفئة', 'المبلغ'],
                _maps(expenses['by_category']), ['category', 'amount'],
                moneyKeys: const {'amount'}),
          ])
        ],
      );

  static ReportDocument _requests(ReportDataBundle data) => ReportDocument(
        title: 'تقرير الطلبات والمزامنة',
        sections: [
          ReportSection(
            title: 'الحالة التشغيلية',
            summaries: data
                .document('sync_health')
                .map((key, value) => MapEntry(key, _text(value))),
            tables: [
              _dynamicTable(
                  'سجل طلبات الهاتف', data.collection('mobile_requests'))
            ],
          )
        ],
      );

  static ReportTable _dynamicTable(
      String title, List<Map<String, dynamic>> rows) {
    final keys = <String>[];
    for (final row in rows) {
      for (final key in row.keys) {
        if (!_metadataKeys.contains(key) &&
            !keys.contains(key) &&
            row[key] is! List &&
            row[key] is! Map) {
          keys.add(key);
        }
      }
    }
    if (keys.isEmpty) keys.add('البيانات');
    return ReportTable(
      title: title,
      headers: keys.map(_fieldLabel).toList(),
      rows: rows
          .map((row) => keys.map((key) => _text(row[key])).toList())
          .toList(),
    );
  }

  static ReportTable _table(String title, List<String> headers,
      List<Map<String, dynamic>> rows, List<String> keys,
      {Set<String> moneyKeys = const {}, Set<String> dateKeys = const {}}) {
    return ReportTable(
      title: title,
      headers: headers,
      rows: rows
          .map((row) => keys.map((key) {
                if (moneyKeys.contains(key)) return _money(row[key]);
                if (dateKeys.contains(key)) return _date(row[key]);
                return _text(row[key]);
              }).toList())
          .toList(),
    );
  }

  static const _metadataKeys = {
    'ui_sections',
    'schema_version',
    'entity',
    'last_updated'
  };
  static String _fieldLabel(String value) => value.replaceAll('_', ' ');
  static List<Map<String, dynamic>> _maps(dynamic value) => value is List
      ? value.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList()
      : const [];
  static double _double(dynamic value) => value is num
      ? value.toDouble()
      : double.tryParse(value?.toString() ?? '') ?? 0;
  static String _format(num value) => _number.format(value);
  static String _money(dynamic value) => _format(_double(value));
  static String _text(dynamic value) {
    if (value == null) return '-';
    if (value is bool) return _bool(value);
    if (value is num) return _format(value);
    if (value is List) return value.map(_text).join('، ');
    if (value is Map) {
      return value.entries
          .map((e) => '${e.key}: ${_text(e.value)}')
          .join(' | ');
    }
    return value.toString();
  }

  static String _bool(dynamic value) =>
      value == true || value == 1 ? 'نعم' : 'لا';
  static String _date(dynamic value) {
    final text = value?.toString() ?? '';
    final parsed = DateTime.tryParse(text);
    return parsed == null
        ? (text.isEmpty ? '-' : text)
        : DateFormat('yyyy-MM-dd HH:mm').format(parsed);
  }

  static String _status(dynamic value) {
    switch (value?.toString().toLowerCase()) {
      case 'paid':
        return 'مدفوع';
      case 'debt':
        return 'دين';
      case 'partial':
        return 'جزئي';
      case 'active':
        return 'نشطة';
      case 'completed':
        return 'مكتملة';
      default:
        return _text(value);
    }
  }

  static String _stockStatus(double stock) => stock <= 0
      ? 'نافد'
      : stock <= 5
          ? 'منخفض'
          : 'متوفر';
}
