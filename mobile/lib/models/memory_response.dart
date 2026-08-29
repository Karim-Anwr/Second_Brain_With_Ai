enum MemoryFileType { image, pdf, note, link, text }

enum MemoryCategory {
  technology,
  science,
  business,
  education,
  health,
  religion,
  personal,
  entertainment,
  sports,
  programming,
  finance,
  news,
  social,
  research,
  product,
  other,
}

class MemoryResponse {
  const MemoryResponse({
    required this.memoryId,
    required this.fileName,
    required this.fileType,
    required this.summary,
    required this.tags,
    required this.category,
    required this.importance,
    required this.totalChunks,
    required this.status,
  });

  final String memoryId;
  final String fileName;
  final MemoryFileType fileType;
  final String summary;
  final List<String> tags;
  final MemoryCategory category;
  final double importance;
  final int totalChunks;
  final String status;

  factory MemoryResponse.fromJson(Map<String, dynamic> json) {
    return MemoryResponse(
      memoryId: _requiredString(json, 'memory_id'),
      fileName: _requiredString(json, 'file_name'),
      fileType: _parseFileType(json['file_type']),
      summary: _requiredString(json, 'summary'),
      tags: _requiredStringList(json, 'tags'),
      category: _parseCategory(json['category']),
      importance: _requiredNumber(json, 'importance'),
      totalChunks: _requiredInt(json, 'total_chunks'),
      status: _requiredString(json, 'status'),
    );
  }
}

MemoryFileType _parseFileType(dynamic value) {
  return MemoryFileType.values.firstWhere(
    (item) => item.name == value,
    orElse: () =>
        throw FormatException('The memory response has an invalid file_type.'),
  );
}

MemoryCategory _parseCategory(dynamic value) {
  return MemoryCategory.values.firstWhere(
    (item) => item.name == value,
    orElse: () =>
        throw FormatException('The memory response has an invalid category.'),
  );
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String) {
    throw FormatException('The memory response has an invalid $key.');
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) {
    throw FormatException('The memory response has an invalid $key.');
  }
  return value;
}

double _requiredNumber(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) {
    throw FormatException('The memory response has an invalid $key.');
  }
  return value.toDouble();
}

List<String> _requiredStringList(Map<String, dynamic> json, String key) {
  final value = json[key];

  if (value is! List || value.any((item) => item is! String)) {
    throw FormatException('The memory response has an invalid $key.');
  }

  return List<String>.unmodifiable(value);
}
