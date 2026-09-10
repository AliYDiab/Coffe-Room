import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class MobileEntryScreen extends StatefulWidget {
  const MobileEntryScreen({super.key});

  @override
  State<MobileEntryScreen> createState() => _MobileEntryScreenState();
}

class _MobileEntryScreenState extends State<MobileEntryScreen>
    with SingleTickerProviderStateMixin {
  late final TabController _tabs;

  final _itemNameController = TextEditingController();
  final _itemCategoryController = TextEditingController();
  final _itemPriceController = TextEditingController();
  final _itemCostController = TextEditingController();
  final _itemStockController = TextEditingController();
  final _itemBarcodeController = TextEditingController();

  final _customerController = TextEditingController();
  final _expenseAmountController = TextEditingController();
  final _expenseVendorController = TextEditingController();
  final _expenseNoteController = TextEditingController();

  DateTime _receiptDate = DateTime.now();
  DateTime _expenseDate = DateTime.now();
  String _receiptStatus = 'paid';
  String _expenseCategory = 'كهرباء';
  final List<_ReceiptLine> _receiptLines = [];

  @override
  void initState() {
    super.initState();
    _tabs = TabController(length: 3, vsync: this);
  }

  @override
  void dispose() {
    _tabs.dispose();
    _itemNameController.dispose();
    _itemCategoryController.dispose();
    _itemPriceController.dispose();
    _itemCostController.dispose();
    _itemStockController.dispose();
    _itemBarcodeController.dispose();
    _customerController.dispose();
    _expenseAmountController.dispose();
    _expenseVendorController.dispose();
    _expenseNoteController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: AppTheme.surface,
            border: Border(bottom: BorderSide(color: AppTheme.surface2)),
          ),
          child: TabBar(
            controller: _tabs,
            indicatorColor: AppTheme.primary,
            labelColor: AppTheme.primary,
            unselectedLabelColor: AppTheme.textMuted,
            tabs: const [
              Tab(
                  text: 'إضافة عنصر',
                  icon: Icon(Icons.inventory_2_outlined, size: 18)),
              Tab(
                  text: 'إضافة فاتورة',
                  icon: Icon(Icons.receipt_long_outlined, size: 18)),
              Tab(
                  text: 'مصروفات',
                  icon: Icon(Icons.payments_outlined, size: 18)),
            ],
          ),
        ),
        Expanded(
          child: TabBarView(
            controller: _tabs,
            children: [
              _buildItemForm(),
              _buildReceiptForm(),
              _buildExpenseForm(),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildItemForm() {
    return StreamBuilder(
      stream: FirebaseService.inventoryStream(),
      builder: (context, snap) {
        final d = snap.hasData ? FirebaseService.docData(snap.data!) : {};
        final categories = <String>{
          'مشروبات',
          'حلويات',
          'وجبات',
          ...(d['categories'] as List<dynamic>? ?? []).cast<String>()
        }.toList();

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const SectionTitle('📦 إضافة عنصر جديد'),
            const Text(
              'هذا النموذج يضيف عنصرًا جديدًا للمخزون عبر Firestore، ثم يلتقطه sync.python إلى SQLite.',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            _field(_itemNameController, 'اسم العنصر', Icons.label_outline),
            const SizedBox(height: 12),
            _field(_itemCategoryController, 'الفئة', Icons.category_outlined,
                hint: 'يمكن كتابة فئة جديدة'),
            const SizedBox(height: 12),
            _categoryPicker(categories, _itemCategoryController),
            const SizedBox(height: 12),
            Row(children: [
              Expanded(
                  child: _field(_itemPriceController, 'سعر البيع',
                      Icons.payments_outlined,
                      keyboardType: TextInputType.number)),
              const SizedBox(width: 12),
              Expanded(
                  child: _field(_itemCostController, 'التكلفة',
                      Icons.account_balance_wallet_outlined,
                      keyboardType: TextInputType.number)),
            ]),
            const SizedBox(height: 12),
            _field(_itemStockController, 'المخزون', Icons.inventory_2_outlined,
                keyboardType: TextInputType.number,
                hint: 'اتركه فارغًا إذا كان غير محدود'),
            const SizedBox(height: 12),
            _field(_itemBarcodeController, 'الباركود', Icons.qr_code_2_outlined,
                hint: 'اختياري'),
            const SizedBox(height: 8),
            ElevatedButton.icon(
              onPressed: _submitItem,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: const Text('إرسال العنصر'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.primary,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildReceiptForm() {
    return StreamBuilder(
      stream: FirebaseService.inventoryStream(),
      builder: (context, snap) {
        final d = snap.hasData ? FirebaseService.docData(snap.data!) : {};
        final items = FirebaseService.asList(d['items']);

        return ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const SectionTitle('🧾 إضافة فاتورة يدوية'),
            const Text(
              'اختر تاريخًا من الهاتف ثم أضف العناصر التي نسيها الكاشير.',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12),
            ),
            const SizedBox(height: 16),
            _dateCard(),
            const SizedBox(height: 12),
            _field(_customerController, 'اسم الزبون', Icons.person_outline,
                hint: 'اختياري'),
            const SizedBox(height: 12),
            _statusSelector(),
            const SizedBox(height: 16),
            _addReceiptLine(items),
            const SizedBox(height: 16),
            if (_receiptLines.isNotEmpty) _selectedLinesCard(),
            const SizedBox(height: 16),
            _totalCard(),
            const SizedBox(height: 20),
            ElevatedButton.icon(
              onPressed: _submitReceipt,
              icon: const Icon(Icons.cloud_upload_outlined),
              label: const Text('إرسال الفاتورة'),
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.accent,
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget _buildExpenseForm() {
    const categories = [
      'غاز',
      'ماء',
      'كهرباء',
      'إيجار',
      'مستلزمات',
      'صيانة',
      'مكونات',
      'أخرى'
    ];

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const SectionTitle('إضافة مصروف'),
        const SizedBox(height: 16),
        InkWell(
          borderRadius: BorderRadius.circular(14),
          onTap: () async {
            final picked = await showDatePicker(
              context: context,
              initialDate: _expenseDate,
              firstDate: DateTime(2020),
              lastDate: DateTime.now().add(const Duration(days: 365)),
            );
            if (picked != null) {
              setState(() => _expenseDate = picked);
            }
          },
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: BorderRadius.circular(14),
            ),
            child: Row(
              children: [
                const Icon(Icons.event_outlined, color: AppTheme.primary),
                const SizedBox(width: 12),
                Expanded(
                  child: Text(
                    DateFormat('yyyy-MM-dd').format(_expenseDate),
                    style: const TextStyle(fontWeight: FontWeight.bold),
                  ),
                ),
                const Icon(Icons.edit_calendar_outlined,
                    color: AppTheme.textMuted),
              ],
            ),
          ),
        ),
        const SizedBox(height: 12),
        DropdownButtonFormField<String>(
          initialValue: _expenseCategory,
          dropdownColor: AppTheme.surface,
          items: categories.map((category) {
            return DropdownMenuItem<String>(
              value: category,
              child: Text(category),
            );
          }).toList(),
          onChanged: (value) =>
              setState(() => _expenseCategory = value ?? 'أخرى'),
          decoration: const InputDecoration(
              border: OutlineInputBorder(), labelText: 'نوع المصروف'),
        ),
        const SizedBox(height: 12),
        _field(_expenseAmountController, 'المبلغ', Icons.payments_outlined,
            keyboardType: TextInputType.number),
        const SizedBox(height: 12),
        _field(
            _expenseVendorController, 'الجهة / المورد', Icons.store_outlined),
        const SizedBox(height: 12),
        _field(_expenseNoteController, 'ملاحظة', Icons.notes_outlined),
        const SizedBox(height: 20),
        ElevatedButton.icon(
          onPressed: _submitExpense,
          icon: const Icon(Icons.cloud_upload_outlined),
          label: const Text('إرسال المصروف'),
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.warning,
            foregroundColor: Colors.white,
            padding: const EdgeInsets.symmetric(vertical: 14),
          ),
        ),
        const SizedBox(height: 20),
        _expenseHistorySection(),
      ],
    );
  }

  Widget _expenseHistorySection() {
    return StreamBuilder(
      stream: FirebaseService.expensesStream(),
      builder: (context, snap) {
        if (!snap.hasData) {
          return const Center(
              child: CircularProgressIndicator(color: AppTheme.primary));
        }

        final data = FirebaseService.docData(snap.data!);
        final expenses = FirebaseService.asList(data['list']);

        if (expenses.isEmpty) {
          return const Text('لا توجد مصروفات بعد',
              style: TextStyle(color: AppTheme.textMuted));
        }

        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SectionTitle('آخر المصروفات'),
            ...expenses.take(20).map((expense) {
              final id = FirebaseService.asInt(expense['id']);
              final category = expense['category'] as String? ?? 'أخرى';
              final amount = FirebaseService.asDouble(expense['amount']);
              final date = expense['date'] as String? ?? '';
              final vendor = expense['vendor'] as String?;
              final note = expense['note'] as String?;

              return Container(
                margin: const EdgeInsets.only(bottom: 8),
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('$category #$id',
                              style:
                                  const TextStyle(fontWeight: FontWeight.bold)),
                          const SizedBox(height: 4),
                          Text(
                            [FirebaseService.formatDate(date), vendor, note]
                                .whereType<String>()
                                .where((v) => v.isNotEmpty)
                                .join(' | '),
                            style: const TextStyle(
                                color: AppTheme.textMuted, fontSize: 12),
                          ),
                        ],
                      ),
                    ),
                    Text('${NumberFormat('#,##0', 'ar').format(amount)} ل.س',
                        style: const TextStyle(
                            color: AppTheme.warning,
                            fontWeight: FontWeight.bold)),
                    IconButton(
                      onPressed: () => _openEditExpenseSheet(expense),
                      icon: const Icon(Icons.edit_outlined,
                          color: AppTheme.accent),
                    ),
                  ],
                ),
              );
            }),
          ],
        );
      },
    );
  }

  void _openEditExpenseSheet(Map<String, dynamic> expense) {
    const categories = [
      'غاز',
      'ماء',
      'كهرباء',
      'إيجار',
      'مستلزمات',
      'صيانة',
      'مكونات',
      'أخرى'
    ];
    final amountController = TextEditingController(
        text: FirebaseService.asDouble(expense['amount']).toStringAsFixed(0));
    final vendorController =
        TextEditingController(text: expense['vendor'] as String? ?? '');
    final noteController =
        TextEditingController(text: expense['note'] as String? ?? '');
    var category = expense['category'] as String? ?? 'أخرى';
    if (!categories.contains(category)) category = 'أخرى';
    var date =
        DateTime.tryParse(expense['date'] as String? ?? '') ?? DateTime.now();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
          borderRadius: BorderRadius.vertical(top: Radius.circular(18))),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(context).viewInsets.bottom + 16,
              ),
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                              'تعديل مصروف #${FirebaseService.asInt(expense['id'])}',
                              style: const TextStyle(
                                  fontSize: 18, fontWeight: FontWeight.bold)),
                        ),
                        IconButton(
                          onPressed: () => Navigator.pop(sheetContext),
                          icon: const Icon(Icons.close,
                              color: AppTheme.textMuted),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    InkWell(
                      onTap: () async {
                        final picked = await showDatePicker(
                          context: context,
                          initialDate: date,
                          firstDate: DateTime(2020),
                          lastDate:
                              DateTime.now().add(const Duration(days: 365)),
                        );
                        if (picked != null) {
                          setSheetState(() => date = picked);
                        }
                      },
                      child: Container(
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                            color: AppTheme.surface2,
                            borderRadius: BorderRadius.circular(12)),
                        child: Row(
                          children: [
                            const Icon(Icons.event_outlined,
                                color: AppTheme.primary),
                            const SizedBox(width: 12),
                            Expanded(
                                child: Text(
                                    DateFormat('yyyy-MM-dd').format(date))),
                            const Icon(Icons.edit_calendar_outlined,
                                color: AppTheme.textMuted),
                          ],
                        ),
                      ),
                    ),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      initialValue: category,
                      dropdownColor: AppTheme.surface,
                      items: categories
                          .map((value) => DropdownMenuItem(
                              value: value, child: Text(value)))
                          .toList(),
                      onChanged: (value) =>
                          setSheetState(() => category = value ?? 'أخرى'),
                      decoration: const InputDecoration(
                          border: OutlineInputBorder(),
                          labelText: 'نوع المصروف'),
                    ),
                    const SizedBox(height: 10),
                    _field(amountController, 'المبلغ', Icons.payments_outlined,
                        keyboardType: TextInputType.number),
                    const SizedBox(height: 10),
                    _field(vendorController, 'الجهة / المورد',
                        Icons.store_outlined),
                    const SizedBox(height: 10),
                    _field(noteController, 'ملاحظة', Icons.notes_outlined),
                    const SizedBox(height: 14),
                    ElevatedButton.icon(
                      onPressed: () async {
                        final amount =
                            double.tryParse(amountController.text.trim());
                        if (amount == null || amount <= 0) {
                          _toast('أدخل مبلغاً صحيحاً');
                          return;
                        }

                        await FirebaseService.submitMobileExpenseRequest({
                          'action': 'update',
                          'expense_id': FirebaseService.asInt(expense['id']),
                          'date': date.toIso8601String(),
                          'category': category,
                          'amount': amount,
                          'vendor': vendorController.text.trim().isEmpty
                              ? null
                              : vendorController.text.trim(),
                          'note': noteController.text.trim().isEmpty
                              ? null
                              : noteController.text.trim(),
                        });

                        if (mounted && sheetContext.mounted) {
                          Navigator.pop(sheetContext);
                          _toast('تم إرسال تعديل المصروف');
                        }
                      },
                      icon: const Icon(Icons.cloud_upload_outlined),
                      label: const Text('إرسال التعديل'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.warning,
                        foregroundColor: Colors.white,
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                  ],
                ),
              ),
            );
          },
        );
      },
    );
  }

  Widget _categoryPicker(
    List<String> categories,
    TextEditingController controller,
  ) {
    if (categories.isEmpty) return const SizedBox.shrink();

    return Wrap(
      spacing: 8,
      runSpacing: 8,
      children: categories.map((cat) {
        final selected = controller.text.trim() == cat;
        return ChoiceChip(
          label: Text(cat),
          selected: selected,
          selectedColor: AppTheme.primary.withValues(alpha: 0.25),
          backgroundColor: AppTheme.surface2,
          onSelected: (_) => setState(() => controller.text = cat),
        );
      }).toList(),
    );
  }

  Widget _field(
    TextEditingController controller,
    String label,
    IconData icon, {
    String? hint,
    TextInputType keyboardType = TextInputType.text,
  }) {
    return TextField(
      controller: controller,
      keyboardType: keyboardType,
      style: const TextStyle(color: Colors.white),
      decoration: InputDecoration(
        labelText: label,
        hintText: hint,
        prefixIcon: Icon(icon, color: AppTheme.textMuted),
        filled: true,
        fillColor: AppTheme.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(14),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  Widget _dateCard() {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: _receiptDate,
          firstDate: DateTime(2020),
          lastDate: DateTime.now().add(const Duration(days: 365)),
        );
        if (picked != null) {
          setState(() => _receiptDate = picked);
        }
      },
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(14),
        ),
        child: Row(
          children: [
            const Icon(Icons.event_outlined, color: AppTheme.primary),
            const SizedBox(width: 12),
            Expanded(
              child: Text(
                'تاريخ الفاتورة: ${DateFormat('yyyy-MM-dd').format(_receiptDate)}',
                style: const TextStyle(fontWeight: FontWeight.bold),
              ),
            ),
            const Icon(Icons.edit_calendar_outlined, color: AppTheme.textMuted),
          ],
        ),
      ),
    );
  }

  Widget _statusSelector() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        children: [
          const Text('الحالة: ', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(width: 8),
          ChoiceChip(
            label: const Text('مدفوع'),
            selected: _receiptStatus == 'paid',
            onSelected: (_) => setState(() => _receiptStatus = 'paid'),
          ),
          const SizedBox(width: 8),
          ChoiceChip(
            label: const Text('دين'),
            selected: _receiptStatus == 'debt',
            onSelected: (_) => setState(() => _receiptStatus = 'debt'),
          ),
        ],
      ),
    );
  }

  Widget _addReceiptLine(List<Map<String, dynamic>> items) {
    final selectedItem = items.isNotEmpty ? items.first : null;

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('إضافة صنف',
              style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          DropdownButtonFormField<Map<String, dynamic>>(
            initialValue: selectedItem,
            items: items.map((item) {
              return DropdownMenuItem<Map<String, dynamic>>(
                value: item,
                child: Text(item['name'] as String? ?? ''),
              );
            }).toList(),
            onChanged: (item) => setState(() {
              if (item == null) return;
              _receiptLines.add(_ReceiptLine(
                itemId: FirebaseService.asInt(item['id']),
                name: item['name'] as String? ?? '',
                qty: 1,
                price: FirebaseService.asDouble(item['price']),
                cost: FirebaseService.asDouble(item['cost']),
                type: item['type'] as String? ?? 'fixed',
              ));
            }),
            decoration: const InputDecoration(border: OutlineInputBorder()),
          ),
          const SizedBox(height: 8),
          if (items.isEmpty)
            const Text('لا توجد عناصر متاحة في المخزون',
                style: TextStyle(color: AppTheme.textMuted)),
          const SizedBox(height: 8),
          const Text('اضغط على القائمة لإضافة الصنف إلى الفاتورة.',
              style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
        ],
      ),
    );
  }

  Widget _selectedLinesCard() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('العناصر المحددة',
              style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 12),
          ..._receiptLines.asMap().entries.map((entry) {
            final index = entry.key;
            final line = entry.value;
            return Container(
              margin: const EdgeInsets.only(bottom: 10),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                color: AppTheme.surface2,
                borderRadius: BorderRadius.circular(12),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(
                          child: Text(line.name,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold))),
                      IconButton(
                        onPressed: () =>
                            setState(() => _receiptLines.removeAt(index)),
                        icon: const Icon(Icons.close, color: AppTheme.danger),
                      ),
                    ],
                  ),
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          keyboardType: TextInputType.number,
                          controller:
                              TextEditingController(text: line.qty.toString()),
                          decoration:
                              const InputDecoration(labelText: 'الكمية'),
                          onChanged: (v) =>
                              setState(() => line.qty = int.tryParse(v) ?? 1),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: TextField(
                          keyboardType: TextInputType.number,
                          controller: TextEditingController(
                              text: line.price.toString()),
                          decoration: const InputDecoration(labelText: 'السعر'),
                          onChanged: (v) => setState(() =>
                              line.price = double.tryParse(v) ?? line.price),
                        ),
                      ),
                    ],
                  ),
                ],
              ),
            );
          }),
        ],
      ),
    );
  }

  Widget _totalCard() {
    final total = _receiptLines.fold<double>(
        0, (sum, line) => sum + (line.qty * line.price));
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.primary.withValues(alpha: 0.12),
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          const Text('الإجمالي', style: TextStyle(fontWeight: FontWeight.bold)),
          Text('${NumberFormat('#,##0', 'ar').format(total)} ل.س',
              style: const TextStyle(
                  fontWeight: FontWeight.bold, color: AppTheme.primary)),
        ],
      ),
    );
  }

  Future<void> _submitItem() async {
    final name = _itemNameController.text.trim();
    final category = _itemCategoryController.text.trim();
    final price = double.tryParse(_itemPriceController.text.trim());
    final cost = double.tryParse(_itemCostController.text.trim()) ?? 0;
    final stockText = _itemStockController.text.trim();
    final stock = stockText.isEmpty ? null : int.tryParse(stockText);
    final barcode = _itemBarcodeController.text.trim();

    if (name.isEmpty || category.isEmpty || price == null) {
      _toast('أكمل الاسم والفئة والسعر');
      return;
    }

    await FirebaseService.submitMobileInventoryItem({
      'name': name,
      'category': category,
      'price': price,
      'cost': cost,
      'stock': stock,
      'available': true,
      'type': 'fixed',
      if (barcode.isNotEmpty) 'barcode_value': barcode,
    });

    _itemNameController.clear();
    _itemCategoryController.clear();
    _itemPriceController.clear();
    _itemCostController.clear();
    _itemStockController.clear();
    _itemBarcodeController.clear();

    _toast('تم إرسال طلب إضافة العنصر');
  }

  Future<void> _submitReceipt() async {
    final customer = _customerController.text.trim();
    if (_receiptLines.isEmpty) {
      _toast('أضف عناصر للفاتورة');
      return;
    }
    if (_receiptStatus == 'debt' && customer.isEmpty) {
      _toast('أدخل اسم الزبون لفاتورة الدين');
      return;
    }

    final items = _receiptLines.map((line) {
      return {
        'item_id': line.itemId,
        'name': line.name,
        'qty': line.qty,
        'price': line.price,
        'cost': line.cost,
        'type': line.type,
      };
    }).toList();

    final total = _receiptLines.fold<double>(
        0, (sum, line) => sum + (line.qty * line.price));

    await FirebaseService.submitMobileReceiptRequest({
      'date': _receiptDate.toIso8601String(),
      'customer': customer.isEmpty ? null : customer,
      'receipt_status': _receiptStatus,
      'total': total,
      'items': items,
    });

    setState(() {
      _customerController.clear();
      _receiptLines.clear();
      _receiptStatus = 'paid';
      _receiptDate = DateTime.now();
    });

    _toast('تم إرسال الفاتورة اليدوية');
  }

  Future<void> _submitExpense() async {
    final amount = double.tryParse(_expenseAmountController.text.trim());
    if (amount == null || amount <= 0) {
      _toast('أدخل مبلغاً صحيحاً');
      return;
    }

    await FirebaseService.submitMobileExpenseRequest({
      'action': 'create',
      'date': _expenseDate.toIso8601String(),
      'category': _expenseCategory,
      'amount': amount,
      'vendor': _expenseVendorController.text.trim().isEmpty
          ? null
          : _expenseVendorController.text.trim(),
      'note': _expenseNoteController.text.trim().isEmpty
          ? null
          : _expenseNoteController.text.trim(),
    });

    setState(() {
      _expenseAmountController.clear();
      _expenseVendorController.clear();
      _expenseNoteController.clear();
      _expenseCategory = 'كهرباء';
      _expenseDate = DateTime.now();
    });

    _toast('تم إرسال المصروف');
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(message)),
    );
  }
}

class _ReceiptLine {
  final int itemId;
  final String name;
  int qty;
  double price;
  final double cost;
  final String type;

  _ReceiptLine({
    required this.itemId,
    required this.name,
    required this.qty,
    required this.price,
    required this.cost,
    required this.type,
  });
}
