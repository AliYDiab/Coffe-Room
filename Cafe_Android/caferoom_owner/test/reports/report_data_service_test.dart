import 'package:caferoom_owner/reports/report_data_service.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('customer report loads receipts and debts only', () async {
    final requestedDocuments = <String>[];
    final service = ReportDataService(
      documentLoader: (name) async {
        requestedDocuments.add(name);
        return {'source': name};
      },
      collectionLoader: (name) async => [],
      requestHistoryLoader: () async => [],
    );

    final bundle = await service.loadForScreen(8);

    expect(requestedDocuments, unorderedEquals(['receipts', 'debts']));
    expect(bundle.document('receipts')['source'], 'receipts');
    expect(bundle.document('debts')['source'], 'debts');
  });

  test('operations report loads every displayed dynamic collection', () async {
    final requestedCollections = <String>[];
    final service = ReportDataService(
      documentLoader: (name) async => {},
      collectionLoader: (name) async {
        requestedCollections.add(name);
        return [
          {'id': name}
        ];
      },
      requestHistoryLoader: () async => [],
    );

    final bundle = await service.loadForScreen(9);

    expect(
        requestedCollections,
        unorderedEquals([
          'workers',
          'shift_schedules',
          'shift_sessions',
          'worker_ratings',
          'shift_handover',
        ]));
    expect(bundle.collection('shift_sessions').single['id'], 'shift_sessions');
  });

  test('request report combines sync health and request history', () async {
    final service = ReportDataService(
      documentLoader: (name) async => {'status': 'online'},
      collectionLoader: (name) async => [],
      requestHistoryLoader: () async => [
        {'document_id': 'r1', 'request_status': 'failed'}
      ],
    );

    final bundle = await service.loadForScreen(11);

    expect(bundle.document('sync_health')['status'], 'online');
    expect(bundle.collection('mobile_requests').single['document_id'], 'r1');
  });
}
