import 'package:flutter/material.dart';
import '../services/AppFirebaseService.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class InventoryScreen extends StatefulWidget {
  const InventoryScreen({super.key});
  @override
  State<InventoryScreen> createState() => _InventoryScreenState();
}

class _InventoryScreenState extends State<InventoryScreen> {
  String _search = '';
  String _category = 'All';
  String _filter = 'All';

  @override
  Widget build(BuildContext context) {
    return StreamBuilder(
      stream: FirebaseService.inventoryStream(),
      builder: (ctx, snap) {
        if (snap.hasError) {
          return Center(
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                const Icon(Icons.error_outline,
                    color: AppTheme.danger, size: 48),
                const SizedBox(height: 16),
                Text('Connection error: ${snap.error}',
                    style: const TextStyle(color: AppTheme.textMuted),
                    textAlign: TextAlign.center),
              ],
            ),
          );
        }
        if (!snap.hasData) {
          return const Center(
              child: CircularProgressIndicator(color: AppTheme.primary));
        }

        final d = FirebaseService.docData(snap.data!);
        final allItems = FirebaseService.asList(d['items']);
        final categories = [
          'All',
          ...(d['categories'] as List<dynamic>? ?? []).cast<String>()
        ];

        // filter
        var items = allItems.where((item) {
          final name = (item['name'] as String? ?? '').toLowerCase();
          final cat = item['category'] as String? ?? '';
          final stock = FirebaseService.asInt(item['stock']);
          final type = item['type'] as String? ?? 'fixed';

          if (_search.isNotEmpty && !name.contains(_search.toLowerCase())) {
            return false;
          }
          if (_category != 'All' && cat != _category) {
            return false;
          }
          if (_filter == 'Low' &&
              !(type == 'fixed' && stock > 0 && stock <= 10)) {
            return false;
          }
          if (_filter == 'Out' && !(type == 'fixed' && stock == 0)) {
            return false;
          }
          return true;
        }).toList();

        return Column(
          children: [
            // Search
            Padding(
              padding: const EdgeInsets.all(12),
              child: TextField(
                onChanged: (v) => setState(() => _search = v),
                style: const TextStyle(color: Colors.white),
                decoration: InputDecoration(
                  hintText: 'Search...',
                  hintStyle: const TextStyle(color: AppTheme.textMuted),
                  prefixIcon:
                      const Icon(Icons.search, color: AppTheme.textMuted),
                  filled: true,
                  fillColor: AppTheme.surface,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                ),
              ),
            ),

            // Category chips
            SizedBox(
              height: 40,
              child: ListView.builder(
                scrollDirection: Axis.horizontal,
                padding: const EdgeInsets.symmetric(horizontal: 12),
                itemCount: categories.length,
                itemBuilder: (_, i) => _chip(
                  categories[i],
                  _category == categories[i],
                  () => setState(() => _category = categories[i]),
                ),
              ),
            ),

            const SizedBox(height: 8),

            // Filter chips
            Row(
              mainAxisAlignment: MainAxisAlignment.center,
              children: ['All', 'Low', 'Out']
                  .map((f) =>
                      _chip(f, _filter == f, () => setState(() => _filter = f),
                          color: f == 'Out'
                              ? AppTheme.danger
                              : f == 'Low'
                                  ? AppTheme.warning
                                  : AppTheme.accent))
                  .toList(),
            ),

            const SizedBox(height: 8),

            // Items list
            Expanded(
              child: items.isEmpty
                  ? const EmptyState(
                      message: 'No items found', icon: Icons.inventory_2)
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      itemCount: items.length,
                      itemBuilder: (_, i) =>
                          _itemCard(items[i], categories.skip(1).toList()),
                    ),
            ),
          ],
        );
      },
    );
  }

  Widget _itemCard(Map<String, dynamic> item, List<String> categories) {
    final name = item['name'] as String? ?? '';
    final category = item['category'] as String? ?? '';
    final price = FirebaseService.asDouble(item['price']);
    final cost = FirebaseService.asDouble(item['cost']);
    final stock = item['stock'];
    final type = item['type'] as String? ?? 'fixed';
    final sold = FirebaseService.asInt(item['total_sold']);

    String stockText;
    Color stockColor;

    if (type == 'recipe') {
      stockText = 'Infinite recipe';
      stockColor = AppTheme.accent;
    } else {
      final s = FirebaseService.asInt(stock);
      if (s == 0) {
        stockText = 'Out';
        stockColor = AppTheme.danger;
      } else if (s <= 10) {
        stockText = '$s low';
        stockColor = AppTheme.warning;
      } else {
        stockText = '$s';
        stockColor = AppTheme.textMuted;
      }
    }

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
      ),
      child: Row(children: [
        Expanded(
            child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(name,
                style:
                    const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
            const SizedBox(height: 4),
            Text(category,
                style:
                    const TextStyle(color: AppTheme.textMuted, fontSize: 12)),
            const SizedBox(height: 4),
            Text('Sold: $sold',
                style: const TextStyle(color: AppTheme.warning, fontSize: 12)),
          ],
        )),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              if (type == 'fixed' && stock != null)
                IconButton(
                  onPressed: () => _openAddStockSheet(item),
                  icon: const Icon(Icons.add_box_outlined,
                      color: AppTheme.primary, size: 22),
                  tooltip: 'إضافة كمية',
                ),
              IconButton(
                onPressed: () => _openEditItemSheet(item, categories),
                icon: const Icon(Icons.edit_outlined,
                    color: AppTheme.accent, size: 20),
                tooltip: 'Edit',
              ),
            ],
          ),
          Text('${price.toStringAsFixed(0)} SYP',
              style: const TextStyle(
                  color: AppTheme.primary, fontWeight: FontWeight.bold)),
          Text('Cost ${cost.toStringAsFixed(0)}',
              style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
          const SizedBox(height: 6),
          Text(stockText,
              style: TextStyle(color: stockColor, fontWeight: FontWeight.bold)),
        ]),
      ]),
    );
  }

  void _openAddStockSheet(Map<String, dynamic> item) {
    final currentStock = FirebaseService.asInt(item['stock']);
    final quantityController = TextEditingController(text: '10');
    var quantityToAdd = 10;
    var isSending = false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
      builder: (sheetContext) {
        return StatefulBuilder(
          builder: (context, setSheetState) {
            void setQuantity(int value) {
              setSheetState(() {
                quantityToAdd = value;
                quantityController.text = value.toString();
              });
            }

            return Padding(
              padding: EdgeInsets.only(
                left: 16,
                right: 16,
                top: 16,
                bottom: MediaQuery.of(context).viewInsets.bottom + 16,
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: Text(
                          'إضافة كمية إلى ${item['name'] as String? ?? ''}',
                          style: const TextStyle(
                              fontSize: 18, fontWeight: FontWeight.bold),
                        ),
                      ),
                      IconButton(
                        onPressed: isSending
                            ? null
                            : () => Navigator.pop(sheetContext),
                        icon:
                            const Icon(Icons.close, color: AppTheme.textMuted),
                      ),
                    ],
                  ),
                  const SizedBox(height: 8),
                  Text('الكمية الحالية: $currentStock',
                      style: const TextStyle(color: AppTheme.textMuted)),
                  const SizedBox(height: 14),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [1, 5, 10, 25, 50].map((amount) {
                      return ChoiceChip(
                        label: Text('+$amount'),
                        selected: quantityToAdd == amount,
                        selectedColor: AppTheme.primary.withValues(alpha: 0.25),
                        backgroundColor: AppTheme.surface2,
                        onSelected:
                            isSending ? null : (_) => setQuantity(amount),
                      );
                    }).toList(),
                  ),
                  const SizedBox(height: 14),
                  TextField(
                    controller: quantityController,
                    enabled: !isSending,
                    keyboardType: TextInputType.number,
                    autofocus: true,
                    decoration: const InputDecoration(
                      labelText: 'كمية أخرى',
                      prefixIcon: Icon(Icons.add),
                      border: OutlineInputBorder(),
                    ),
                    onChanged: (value) => setSheetState(
                      () => quantityToAdd = int.tryParse(value) ?? 0,
                    ),
                  ),
                  const SizedBox(height: 12),
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: AppTheme.primary.withValues(alpha: 0.12),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Text(
                      'بعد الإضافة: ${currentStock + quantityToAdd}',
                      textAlign: TextAlign.center,
                      style: const TextStyle(
                          color: AppTheme.primary, fontWeight: FontWeight.bold),
                    ),
                  ),
                  const SizedBox(height: 14),
                  ElevatedButton.icon(
                    onPressed: isSending || quantityToAdd <= 0
                        ? null
                        : () async {
                            setSheetState(() => isSending = true);
                            try {
                              await FirebaseService.submitMobileInventoryItem({
                                'action': 'increment_stock',
                                'item_id': FirebaseService.asInt(item['id']),
                                'quantity_delta': quantityToAdd,
                              });
                              if (mounted && sheetContext.mounted) {
                                Navigator.pop(sheetContext);
                                _toast('تم إرسال إضافة $quantityToAdd وحدة');
                              }
                            } catch (_) {
                              if (mounted && sheetContext.mounted) {
                                setSheetState(() => isSending = false);
                                _toast('تعذر إرسال الكمية، حاول مرة أخرى');
                              }
                            }
                          },
                    icon: isSending
                        ? const SizedBox(
                            width: 18,
                            height: 18,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )
                        : const Icon(Icons.add_box_outlined),
                    label: Text(isSending ? 'جارٍ الإرسال...' : 'إضافة الكمية'),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: AppTheme.primary,
                      foregroundColor: Colors.white,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    ).whenComplete(quantityController.dispose);
  }

  void _openEditItemSheet(Map<String, dynamic> item, List<String> categories) {
    final nameController =
        TextEditingController(text: item['name'] as String? ?? '');
    final categoryController =
        TextEditingController(text: item['category'] as String? ?? '');
    final priceController = TextEditingController(
        text: FirebaseService.asDouble(item['price']).toStringAsFixed(0));
    final costController = TextEditingController(
        text: FirebaseService.asDouble(item['cost']).toStringAsFixed(0));
    final stockValue = item['stock'];
    final stockController = TextEditingController(
        text: stockValue == null
            ? ''
            : FirebaseService.asInt(stockValue).toString());
    final barcodeController =
        TextEditingController(text: item['barcode_value'] as String? ?? '');
    var itemType = item['type'] as String? ?? 'fixed';
    var available = item['available'] == true ||
        item['available'] == 1 ||
        item['available'] == null;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surface,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(18)),
      ),
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
                        const Expanded(
                          child: Text('Edit Item',
                              style: TextStyle(
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
                    _editField(nameController, 'Name', Icons.label_outline),
                    const SizedBox(height: 10),
                    _editField(categoryController, 'Category',
                        Icons.category_outlined),
                    if (categories.isNotEmpty) ...[
                      const SizedBox(height: 10),
                      Wrap(
                        spacing: 8,
                        runSpacing: 8,
                        children: categories.map((cat) {
                          final selected =
                              categoryController.text.trim() == cat;
                          return ChoiceChip(
                            label: Text(cat),
                            selected: selected,
                            selectedColor:
                                AppTheme.primary.withValues(alpha: 0.25),
                            backgroundColor: AppTheme.surface2,
                            onSelected: (_) => setSheetState(
                                () => categoryController.text = cat),
                          );
                        }).toList(),
                      ),
                    ],
                    const SizedBox(height: 10),
                    Row(
                      children: [
                        Expanded(
                            child: _editField(priceController, 'Price',
                                Icons.payments_outlined,
                                keyboardType: TextInputType.number)),
                        const SizedBox(width: 10),
                        Expanded(
                            child: _editField(costController, 'Cost',
                                Icons.account_balance_wallet_outlined,
                                keyboardType: TextInputType.number)),
                      ],
                    ),
                    const SizedBox(height: 10),
                    _editField(
                        stockController, 'Stock', Icons.inventory_2_outlined,
                        keyboardType: TextInputType.number,
                        hint: 'Empty means unlimited'),
                    const SizedBox(height: 10),
                    _editField(
                        barcodeController, 'Barcode', Icons.qr_code_2_outlined),
                    const SizedBox(height: 10),
                    DropdownButtonFormField<String>(
                      initialValue: itemType,
                      dropdownColor: AppTheme.surface,
                      items: const [
                        DropdownMenuItem(
                            value: 'fixed', child: Text('Fixed stock')),
                        DropdownMenuItem(
                            value: 'recipe', child: Text('Recipe')),
                      ],
                      onChanged: (value) =>
                          setSheetState(() => itemType = value ?? 'fixed'),
                      decoration: const InputDecoration(
                          border: OutlineInputBorder(), labelText: 'Type'),
                    ),
                    SwitchListTile(
                      value: available,
                      onChanged: (value) =>
                          setSheetState(() => available = value),
                      title: const Text('Available'),
                      activeThumbColor: AppTheme.primary,
                      contentPadding: EdgeInsets.zero,
                    ),
                    const SizedBox(height: 12),
                    OutlinedButton.icon(
                      onPressed: () async {
                        final confirm = await showDialog<bool>(
                          context: sheetContext,
                          builder: (dialogContext) => AlertDialog(
                            backgroundColor: AppTheme.surface,
                            title: const Text('Delete Item'),
                            content: Text(
                                'Delete ${item['name'] as String? ?? 'this item'} from inventory?'),
                            actions: [
                              TextButton(
                                onPressed: () =>
                                    Navigator.pop(dialogContext, false),
                                child: const Text('Cancel'),
                              ),
                              TextButton(
                                onPressed: () =>
                                    Navigator.pop(dialogContext, true),
                                child: const Text('Delete',
                                    style: TextStyle(color: AppTheme.danger)),
                              ),
                            ],
                          ),
                        );

                        if (confirm != true) return;

                        await FirebaseService.submitMobileInventoryItem({
                          'action': 'delete',
                          'item_id': FirebaseService.asInt(item['id']),
                          'name': item['name'],
                        });

                        if (mounted && sheetContext.mounted) {
                          Navigator.pop(sheetContext);
                          _toast('Item delete sent');
                        }
                      },
                      icon: const Icon(Icons.delete_outline),
                      label: const Text('Delete Item'),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: AppTheme.danger,
                        side: const BorderSide(color: AppTheme.danger),
                        padding: const EdgeInsets.symmetric(vertical: 14),
                      ),
                    ),
                    const SizedBox(height: 10),
                    ElevatedButton.icon(
                      onPressed: () async {
                        final name = nameController.text.trim();
                        final category = categoryController.text.trim();
                        final price =
                            double.tryParse(priceController.text.trim());
                        final cost =
                            double.tryParse(costController.text.trim()) ?? 0;
                        final stockText = stockController.text.trim();
                        final stock =
                            stockText.isEmpty ? null : int.tryParse(stockText);
                        if (name.isEmpty || category.isEmpty || price == null) {
                          _toast('Complete name, category, and price');
                          return;
                        }

                        await FirebaseService.submitMobileInventoryItem({
                          'action': 'update',
                          'item_id': FirebaseService.asInt(item['id']),
                          'name': name,
                          'category': category,
                          'price': price,
                          'cost': cost,
                          'stock': stock,
                          'available': available,
                          'type': itemType,
                          'barcode_value': barcodeController.text.trim().isEmpty
                              ? null
                              : barcodeController.text.trim(),
                        });

                        if (mounted && sheetContext.mounted) {
                          Navigator.pop(sheetContext);
                          _toast('Item edit sent');
                        }
                      },
                      icon: const Icon(Icons.cloud_upload_outlined),
                      label: const Text('Send Edit'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primary,
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

  Widget _editField(
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
        fillColor: AppTheme.surface2,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(12),
          borderSide: BorderSide.none,
        ),
      ),
    );
  }

  void _toast(String message) {
    ScaffoldMessenger.of(context)
        .showSnackBar(SnackBar(content: Text(message)));
  }

  Widget _chip(String label, bool selected, VoidCallback onTap,
          {Color color = AppTheme.primary}) =>
      GestureDetector(
        onTap: onTap,
        child: Container(
          margin: const EdgeInsets.only(right: 8),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
          decoration: BoxDecoration(
            color: selected ? color.withValues(alpha: 0.2) : AppTheme.surface2,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: selected ? color : Colors.transparent),
          ),
          child: Text(label,
              style: TextStyle(
                color: selected ? color : AppTheme.textMuted,
                fontWeight: selected ? FontWeight.bold : FontWeight.normal,
                fontSize: 13,
              )),
        ),
      );
}
