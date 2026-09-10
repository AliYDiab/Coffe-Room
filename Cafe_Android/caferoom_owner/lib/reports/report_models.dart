class ReportDataBundle {
  final Map<String, Map<String, dynamic>> documents;
  final Map<String, List<Map<String, dynamic>>> collections;

  const ReportDataBundle({
    this.documents = const {},
    this.collections = const {},
  });

  Map<String, dynamic> document(String name) => documents[name] ?? const {};
  List<Map<String, dynamic>> collection(String name) =>
      collections[name] ?? const [];
}

class ReportDocument {
  final String title;
  final String scope;
  final DateTime generatedAt;
  final List<ReportSection> sections;

  ReportDocument({
    required this.title,
    required this.sections,
    this.scope = 'جميع البيانات المتاحة والمتزامنة',
    DateTime? generatedAt,
  }) : generatedAt = generatedAt ?? DateTime.now();
}

class ReportSection {
  final String title;
  final Map<String, String> summaries;
  final List<ReportTable> tables;
  final String? note;

  const ReportSection({
    required this.title,
    this.summaries = const {},
    this.tables = const [],
    this.note,
  });
}

class ReportTable {
  final String title;
  final List<String> headers;
  final List<List<String>> rows;

  const ReportTable({
    required this.title,
    required this.headers,
    required this.rows,
  });
}
