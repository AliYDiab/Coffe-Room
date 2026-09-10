import 'package:flutter/material.dart';
import '../services/AppFirebaseService.dart';
import '../services/analytics_service.dart';
import '../theme/app_theme.dart';
import '../widgets/shared_widgets.dart';

class InventoryIntelligenceScreen extends StatefulWidget {
  const InventoryIntelligenceScreen({super.key});
  
  @override
  State<InventoryIntelligenceScreen> createState() => _InventoryIntelligenceScreenState();
}

class _InventoryIntelligenceScreenState extends State<InventoryIntelligenceScreen> {
  String _view = 'overview'; // overview, reorder, analysis
  
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
                const Icon(Icons.error_outline, color: AppTheme.danger, size: 48),
                const SizedBox(height: 16),
                Text('خطأ في الاتصال: ${snap.error}',
                  style: const TextStyle(color: AppTheme.textMuted),
                  textAlign: TextAlign.center),
              ],
            ),
          );
        }
        if (!snap.hasData) return const Center(child: CircularProgressIndicator(color: AppTheme.primary));
        
        final d = FirebaseService.docData(snap.data!);
        final items = FirebaseService.asList(d['items']);
        final categories = (d['categories'] as List<dynamic>? ?? []).cast<String>();
        
        // Calculate inventory metrics
        final totalItems = items.length;
        final outOfStock = items.where((item) => FirebaseService.asInt(item['stock']) == 0).length;
        final lowStock = items.where((item) {
          final stock = FirebaseService.asInt(item['stock']);
          final type = item['type'] as String? ?? 'fixed';
          return type == 'fixed' && stock > 0 && stock <= 10;
        }).length;
        final totalValue = AnalyticsService.calculateInventoryValue(items);
        
        // Generate reorder suggestions (simulated daily usage)
        final dailyUsage = _generateDailyUsageMap(items);
        final reorderSuggestions = AnalyticsService.generateReorderSuggestions(items, dailyUsage);
        
        return Column(
          children: [
            // View selector
            _buildViewSelector(),
            
            Expanded(
              child: _buildSelectedView(
                items, 
                categories, 
                totalItems, 
                outOfStock, 
                lowStock, 
                totalValue,
                reorderSuggestions,
                dailyUsage,
              ),
            ),
          ],
        );
      },
    );
  }
  
  Widget _buildViewSelector() {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        border: Border(bottom: BorderSide(color: AppTheme.surface2)),
      ),
      child: Row(
        children: [
          _buildViewTab('نظرة عامة', 'overview', Icons.dashboard),
          _buildViewTab('اقتراحات الطلب', 'reorder', Icons.shopping_cart),
          _buildViewTab('التحليل المتقدم', 'analysis', Icons.analytics),
        ],
      ),
    );
  }
  
  Widget _buildViewTab(String label, String value, IconData icon) {
    final isSelected = _view == value;
    return Expanded(
      child: GestureDetector(
        onTap: () => setState(() => _view = value),
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            color: isSelected ? AppTheme.primary.withValues(alpha: 0.1) : Colors.transparent,
            border: Border(
              bottom: BorderSide(
                color: isSelected ? AppTheme.primary : Colors.transparent,
                width: 2,
              ),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                icon,
                size: 18,
                color: isSelected ? AppTheme.primary : AppTheme.textMuted,
              ),
              const SizedBox(width: 8),
              Text(
                label,
                style: TextStyle(
                  color: isSelected ? AppTheme.primary : AppTheme.textMuted,
                  fontWeight: isSelected ? FontWeight.bold : FontWeight.normal,
                  fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
  
  Widget _buildSelectedView(
    List<Map<String, dynamic>> items,
    List<String> categories,
    int totalItems,
    int outOfStock,
    int lowStock,
    double totalValue,
    List<Map<String, dynamic>> reorderSuggestions,
    Map<String, double> dailyUsage,
  ) {
    switch (_view) {
      case 'reorder':
        return _buildReorderView(reorderSuggestions);
      case 'analysis':
        return _buildAnalysisView(items, categories, dailyUsage);
      default:
        return _buildOverviewView(
          items, 
          totalItems, 
          outOfStock, 
          lowStock, 
          totalValue,
        );
    }
  }
  
  Widget _buildOverviewView(
    List<Map<String, dynamic>> items,
    int totalItems,
    int outOfStock,
    int lowStock,
    double totalValue,
  ) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Summary cards
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.4,
          children: [
            _buildSummaryCard('إجمالي المنتجات', totalItems.toString(), Icons.inventory_2, AppTheme.primary),
            _buildSummaryCard('قيمة المخزون', AnalyticsService.formatCurrency(totalValue), Icons.account_balance_wallet, AppTheme.accent),
            _buildSummaryCard('نفد المخزون', outOfStock.toString(), Icons.error_outline, AppTheme.danger),
            _buildSummaryCard('منخفض المخزون', lowStock.toString(), Icons.warning, AppTheme.warning),
          ],
        ),
        
        const SizedBox(height: 20),
        
        // Stock status distribution
        const SectionTitle('📊 توزيع حالة المخزون'),
        _buildStockDistribution(items),
        
        const SizedBox(height: 20),
        
        // Category breakdown
        if (items.isNotEmpty) _buildCategoryBreakdown(items),
        
        const SizedBox(height: 20),
        
        // Top value items
        const SectionTitle('💰 المنتجات الأعلى قيمة'),
        _buildTopValueItems(items),
      ],
    );
  }
  
  Widget _buildSummaryCard(String label, String value, IconData icon, Color color) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: color.withValues(alpha: 0.2)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: color, size: 24),
          const SizedBox(height: 12),
          Text(
            label,
            style: const TextStyle(fontSize: 12, color: AppTheme.textMuted),
          ),
          const SizedBox(height: 4),
          Text(
            value,
            style: TextStyle(
              fontSize: 20,
              fontWeight: FontWeight.bold,
              color: color,
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildStockDistribution(List<Map<String, dynamic>> items) {
    final inStock = items.where((item) => FirebaseService.asInt(item['stock']) > 10).length;
    final low = items.where((item) {
      final stock = FirebaseService.asInt(item['stock']);
      final type = item['type'] as String? ?? 'fixed';
      return type == 'fixed' && stock > 0 && stock <= 10;
    }).length;
    final out = items.where((item) => FirebaseService.asInt(item['stock']) == 0).length;
    final total = items.length;
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          // Progress bars
          _buildStockBar('متوفر', inStock, total, AppTheme.primary),
          _buildStockBar('منخفض', low, total, AppTheme.warning),
          _buildStockBar('نفد', out, total, AppTheme.danger),
          
          const SizedBox(height: 16),
          
          // Legend
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: [
              _buildLegend('متوفر', AppTheme.primary, inStock),
              _buildLegend('منخفض', AppTheme.warning, low),
              _buildLegend('نفد', AppTheme.danger, out),
            ],
          ),
        ],
      ),
    );
  }
  
  Widget _buildStockBar(String label, int count, int total, Color color) {
    final percentage = total > 0 ? (count / total * 100) : 0.0;
    
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(label, style: const TextStyle(fontSize: 12)),
            Text('$count (${percentage.toStringAsFixed(1)}%)',
              style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: percentage / 100,
            backgroundColor: AppTheme.surface2,
            valueColor: AlwaysStoppedAnimation(color),
            minHeight: 8,
          ),
        ),
        const SizedBox(height: 8),
      ],
    );
  }
  
  Widget _buildLegend(String label, Color color, int count) {
    return Row(
      children: [
        Container(
          width: 12,
          height: 12,
          decoration: BoxDecoration(
            color: color,
            shape: BoxShape.circle,
          ),
        ),
        const SizedBox(width: 6),
        Text('$label ($count)', style: const TextStyle(fontSize: 11)),
      ],
    );
  }
  
  Widget _buildCategoryBreakdown(List<Map<String, dynamic>> items) {
    final categoryMap = <String, List<Map<String, dynamic>>>{};
    
    for (final item in items) {
      final category = item['category'] as String? ?? 'غير مصنف';
      if (!categoryMap.containsKey(category)) {
        categoryMap[category] = [];
      }
      categoryMap[category]!.add(item);
    }
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text('توزيع الفئات',
            style: TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
          const SizedBox(height: 16),
          ...categoryMap.entries.map((entry) {
            final categoryValue = AnalyticsService.calculateInventoryValue(entry.value);
            return Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(entry.key, style: const TextStyle(fontSize: 13)),
                  Row(
                    children: [
                      Text('${entry.value.length} منتج',
                        style: const TextStyle(
                          fontSize: 12,
                          color: AppTheme.textMuted,
                        )),
                      const SizedBox(width: 12),
                      Text(AnalyticsService.formatCurrency(categoryValue),
                        style: const TextStyle(
                          fontWeight: FontWeight.w600,
                          fontSize: 13,
                        )),
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
  
  Widget _buildTopValueItems(List<Map<String, dynamic>> items) {
    final sortedItems = List<Map<String, dynamic>>.from(items);
    sortedItems.sort((a, b) {
      final priceA = FirebaseService.asDouble(a['price']);
      final stockA = FirebaseService.asInt(a['stock']);
      final valueA = priceA * stockA;
      
      final priceB = FirebaseService.asDouble(b['price']);
      final stockB = FirebaseService.asInt(b['stock']);
      final valueB = priceB * stockB;
      
      return valueB.compareTo(valueA);
    });
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: sortedItems.take(5).map((item) {
          final name = item['name'] as String? ?? '';
          final price = FirebaseService.asDouble(item['price']);
          final stock = FirebaseService.asInt(item['stock']);
          final totalValue = price * stock;
          
          return Container(
            margin: const EdgeInsets.only(bottom: 12),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface2,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(name, style: const TextStyle(fontWeight: FontWeight.w600)),
                      Text('$stock × ${AnalyticsService.formatCurrency(price)}',
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.textMuted,
                        )),
                    ],
                  ),
                ),
                Text(
                  AnalyticsService.formatCurrency(totalValue),
                  style: const TextStyle(
                    fontWeight: FontWeight.bold,
                    color: AppTheme.primary,
                  ),
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
  
  Widget _buildReorderView(List<Map<String, dynamic>> suggestions) {
    if (suggestions.isEmpty) {
      return const Center(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(Icons.check_circle, color: AppTheme.primary, size: 64),
            SizedBox(height: 16),
            Text('لا توجد اقتراحات طلب حالياً',
              style: TextStyle(color: AppTheme.textMuted)),
          ],
        ),
      );
    }
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        const SectionTitle('🛒 اقتراحات إعادة الطلب'),
        const SizedBox(height: 8),
        ...suggestions.map((suggestion) => _buildSuggestionCard(suggestion)),
      ],
    );
  }
  
  Widget _buildSuggestionCard(Map<String, dynamic> suggestion) {
    final priority = suggestion['priority'] as String? ?? 'medium';
    final itemName = suggestion['item'] as String? ?? '';
    final currentStock = suggestion['current_stock'] as int? ?? 0;
    final daysRemaining = suggestion['days_remaining'] as int? ?? 0;
    final suggestedQty = suggestion['suggested_order_quantity'] as int? ?? 0;
    
    Color priorityColor;
    String priorityLabel;
    
    switch (priority) {
      case 'critical':
        priorityColor = AppTheme.danger;
        priorityLabel = 'حرج';
        break;
      case 'high':
        priorityColor = AppTheme.warning;
        priorityLabel = 'عالي';
        break;
      default:
        priorityColor = AppTheme.primary;
        priorityLabel = 'متوسط';
    }
    
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: priorityColor.withValues(alpha: 0.3), width: 2),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                itemName,
                style: const TextStyle(
                  fontWeight: FontWeight.bold,
                  fontSize: 16,
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: priorityColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  priorityLabel,
                  style: TextStyle(
                    color: priorityColor,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildSuggestionDetail('المخزون الحالي', currentStock.toString()),
              ),
              Expanded(
                child: _buildSuggestionDetail('أيام متبقية', daysRemaining.toString()),
              ),
              Expanded(
                child: _buildSuggestionDetail('الكمية المقترحة', suggestedQty.toString()),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              color: priorityColor.withValues(alpha: 0.1),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Text(
              daysRemaining <= 1 
                ? '⚠️ يحتاج إعادة طلب فوري!'
                : daysRemaining <= 2 
                  ? '⚠️ يُنصح بالطلب خلال 24 ساعة'
                  : 'ℹ️ يمكن الطلب خلال الأيام القليلة القادمة',
              textAlign: TextAlign.center,
              style: TextStyle(
                color: priorityColor,
                fontWeight: FontWeight.w600,
                fontSize: 12,
              ),
            ),
          ),
        ],
      ),
    );
  }
  
  Widget _buildSuggestionDetail(String label, String value) {
    return Column(
      children: [
        Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
        const SizedBox(height: 4),
        Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
      ],
    );
  }
  
  Widget _buildAnalysisView(List<Map<String, dynamic>> items, List<String> categories, Map<String, double> dailyUsage) {
    // Calculate additional metrics
    final totalValue = AnalyticsService.calculateInventoryValue(items);
    final avgPricePerItem = items.isNotEmpty ? totalValue / items.length : 0.0;
    
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // KPI cards
        GridView.count(
          crossAxisCount: 2,
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          crossAxisSpacing: 12,
          mainAxisSpacing: 12,
          childAspectRatio: 1.5,
          children: [
            _buildAnalysisCard('متوسط سعر المنتج', AnalyticsService.formatCurrency(avgPricePerItem), Icons.price_check),
            _buildAnalysisCard('إجمالي الفئات', categories.length.toString(), Icons.category),
            _buildAnalysisCard('منتجات نشطة', items.where((i) => FirebaseService.asInt(i['total_sold']) > 0).length.toString(), Icons.trending_up),
            _buildAnalysisCard('منتجات راكدة', items.where((i) => FirebaseService.asInt(i['total_sold']) == 0).length.toString(), Icons.trending_down),
          ],
        ),
        
        const SizedBox(height: 20),
        
        // Slow moving items
        const SectionTitle('📉 المنتجات الراكدة (لا مبيعات)'),
        _buildSlowMovingItems(items),
        
        const SizedBox(height: 20),
        
        // Fast moving items
        const SectionTitle('📈 المنتجات سريعة الحركة'),
        _buildFastMovingItems(items),
      ],
    );
  }
  
  Widget _buildAnalysisCard(String label, String value, IconData icon) {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, color: AppTheme.accent, size: 20),
          const SizedBox(height: 8),
          Text(label, style: const TextStyle(fontSize: 11, color: AppTheme.textMuted)),
          const SizedBox(height: 4),
          Text(value, style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16)),
        ],
      ),
    );
  }
  
  Widget _buildSlowMovingItems(List<Map<String, dynamic>> items) {
    final slowMoving = items.where((item) => FirebaseService.asInt(item['total_sold']) == 0).toList();
    
    if (slowMoving.isEmpty) {
      return const Center(
        child: Padding(
          padding: EdgeInsets.all(20),
          child: Text('لا توجد منتجات راكدة',
            style: TextStyle(color: AppTheme.textMuted)),
        ),
      );
    }
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: slowMoving.take(5).map((item) {
          final name = item['name'] as String? ?? '';
          final stock = FirebaseService.asInt(item['stock']);
          final price = FirebaseService.asDouble(item['price']);
          
          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface2,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(child: Text(name, style: const TextStyle(fontSize: 13))),
                Row(
                  children: [
                    Text('$stock في المخزون',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textMuted,
                      )),
                    const SizedBox(width: 8),
                    Text(AnalyticsService.formatCurrency(price),
                      style: const TextStyle(
                        fontWeight: FontWeight.w600,
                        fontSize: 12,
                      )),
                  ],
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
  
  Widget _buildFastMovingItems(List<Map<String, dynamic>> items) {
    final fastMoving = List<Map<String, dynamic>>.from(items);
    fastMoving.sort((a, b) => FirebaseService.asInt(b['total_sold']).compareTo(FirebaseService.asInt(a['total_sold'])));
    
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: fastMoving.take(5).map((item) {
          final name = item['name'] as String? ?? '';
          final sold = FirebaseService.asInt(item['total_sold']);
          final stock = FirebaseService.asInt(item['stock']);
          
          return Container(
            margin: const EdgeInsets.only(bottom: 8),
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: AppTheme.surface2,
              borderRadius: BorderRadius.circular(10),
            ),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Expanded(child: Text(name, style: const TextStyle(fontSize: 13))),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      decoration: BoxDecoration(
                        color: AppTheme.primary.withValues(alpha: 0.15),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text('$sold مباع',
                        style: const TextStyle(
                          fontSize: 11,
                          color: AppTheme.primary,
                          fontWeight: FontWeight.bold,
                        )),
                    ),
                    const SizedBox(width: 8),
                    Text('$stock متوفر',
                      style: const TextStyle(
                        fontSize: 11,
                        color: AppTheme.textMuted,
                      )),
                  ],
                ),
              ],
            ),
          );
        }).toList(),
      ),
    );
  }
  
  // Simulated daily usage map (in real app, this would come from actual sales data)
  Map<String, double> _generateDailyUsageMap(List<Map<String, dynamic>> items) {
    final usageMap = <String, double>{};
    
    for (final item in items) {
      final name = item['name'] as String? ?? '';
      final sold = FirebaseService.asInt(item['total_sold']);
      // Assume sales over 30 days for daily average
      usageMap[name] = sold / 30.0;
    }
    
    return usageMap;
  }
}