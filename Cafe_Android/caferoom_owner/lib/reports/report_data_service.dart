import '../services/AppFirebaseService.dart';
import 'report_models.dart';

typedef ReportDocumentLoader = Future<Map<String, dynamic>> Function(
    String name);
typedef ReportCollectionLoader = Future<List<Map<String, dynamic>>> Function(
    String name);
typedef RequestHistoryLoader = Future<List<Map<String, dynamic>>> Function();

class ReportDataService {
  final ReportDocumentLoader documentLoader;
  final ReportCollectionLoader collectionLoader;
  final RequestHistoryLoader requestHistoryLoader;

  ReportDataService({
    ReportDocumentLoader? documentLoader,
    ReportCollectionLoader? collectionLoader,
    RequestHistoryLoader? requestHistoryLoader,
  })  : documentLoader = documentLoader ?? _loadDocument,
        collectionLoader = collectionLoader ?? _loadCollection,
        requestHistoryLoader =
            requestHistoryLoader ?? FirebaseService.loadMobileRequestHistory;

  Future<ReportDataBundle> loadForScreen(int screenIndex) async {
    if (screenIndex < 0 || screenIndex > 11) {
      throw RangeError.range(screenIndex, 0, 11, 'screenIndex');
    }

    final documentNames = _documentsForScreen(screenIndex);
    final collectionNames = _collectionsForScreen(screenIndex);
    final documentEntries = await Future.wait(documentNames.map((name) async {
      return MapEntry(name, await documentLoader(name));
    }));
    final collectionEntries =
        await Future.wait(collectionNames.map((name) async {
      return MapEntry(name, await collectionLoader(name));
    }));

    final documents =
        Map<String, Map<String, dynamic>>.fromEntries(documentEntries);
    final collections =
        Map<String, List<Map<String, dynamic>>>.fromEntries(collectionEntries);

    if (screenIndex == 11) {
      collections['mobile_requests'] = await requestHistoryLoader();
    }

    return ReportDataBundle(documents: documents, collections: collections);
  }

  static List<String> _documentsForScreen(int index) {
    switch (index) {
      case 0:
        return const ['dashboard'];
      case 1:
      case 7:
        return const ['inventory'];
      case 2:
        return const ['receipts'];
      case 3:
        return const ['debts'];
      case 4:
        return const ['waste'];
      case 5:
      case 6:
        return const ['analytics'];
      case 8:
        return const ['receipts', 'debts'];
      case 10:
        return const ['ingredients', 'expenses'];
      case 11:
        return const ['sync_health'];
      default:
        return const [];
    }
  }

  static List<String> _collectionsForScreen(int index) => index == 9
      ? const [
          'workers',
          'shift_schedules',
          'shift_sessions',
          'worker_ratings',
          'shift_handover',
        ]
      : const [];

  static Future<Map<String, dynamic>> _loadDocument(String name) {
    switch (name) {
      case 'dashboard':
        return FirebaseService.dashboardDataStream().first;
      case 'inventory':
        return FirebaseService.inventoryDataStream().first;
      case 'receipts':
        return FirebaseService.receiptsDataStream().first;
      case 'debts':
        return FirebaseService.debtsDataStream().first;
      case 'waste':
        return FirebaseService.wasteDataStream().first;
      case 'analytics':
        return FirebaseService.analyticsDataStream().first;
      case 'ingredients':
        return FirebaseService.ingredientsDataStream().first;
      case 'expenses':
        return FirebaseService.expensesDataStream().first;
      case 'sync_health':
        return FirebaseService.syncHealthStream().first;
      default:
        throw ArgumentError.value(name, 'name', 'Unknown report document');
    }
  }

  static Future<List<Map<String, dynamic>>> _loadCollection(String name) =>
      FirebaseService.collectionDataStream(name).first;
}
