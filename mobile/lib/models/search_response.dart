class SearchScores {
  const SearchScores({
    required this.finalScore,
    required this.semantic,
    required this.recency,
    required this.importance,
  });

  final double finalScore;
  final double semantic;
  final double recency;
  final double importance;

  factory SearchScores.fromJson(Map<String, dynamic> json) {
    return SearchScores(
      finalScore: _requiredNumber(json, 'final'),
      semantic: _requiredNumber(json, 'semantic'),
      recency: _requiredNumber(json, 'recency'),
      importance: _requiredNumber(json, 'importance'),
    );
  }
}

class SearchResult {
  const SearchResult({
    required this.memoryId,
    required this.fileName,
    required this.summary,
    required this.matchedText,
    required this.tags,
    required this.createdAt,
    required this.scores,
  });

  final String memoryId;
  final String fileName;
  final String summary;
  final String matchedText;
  final List<String> tags;
  final String createdAt;
  final SearchScores scores;

  factory SearchResult.fromJson(Map<String, dynamic> json) {
    return SearchResult(
      memoryId: _requiredString(json, 'memory_id'),
      fileName: _requiredString(json, 'file_name'),
      summary: _requiredString(json, 'summary'),
      matchedText: _requiredString(json, 'matched_text'),
      tags: _requiredStringList(json, 'tags'),
      createdAt: _requiredString(json, 'created_at'),
      scores: SearchScores.fromJson(_requiredMap(json, 'scores')),
    );
  }
}

class SearchResponse {
  const SearchResponse({
    required this.query,
    required this.total,
    required this.results,
    required this.llmAnswer,
  });

  final String query;
  final int total;
  final List<SearchResult> results;
  final String? llmAnswer;

  factory SearchResponse.fromJson(Map<String, dynamic> json) {
    final rawAnswer = json['llm_answer'];
    if (rawAnswer != null && rawAnswer is! String) {
      throw const FormatException('The search response has an invalid llm_answer.');
    }
    final rawResults = json['results'];
    if (rawResults is! List) {
      throw const FormatException('The search response has invalid results.');
    }

    return SearchResponse(
      query: _requiredString(json, 'query'),
      total: _requiredInt(json, 'total'),
      results: rawResults
          .map((item) {
            if (item is! Map) {
              throw const FormatException('The search response has an invalid result.');
            }
            return SearchResult.fromJson(Map<String, dynamic>.from(item));
          })
          .toList(growable: false),
      llmAnswer: rawAnswer,
    );
  }
}

String _requiredString(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! String) {
    throw FormatException('The search response has an invalid $key.');
  }
  return value;
}

int _requiredInt(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! int) {
    throw FormatException('The search response has an invalid $key.');
  }
  return value;
}

double _requiredNumber(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! num) {
    throw FormatException('The search response has an invalid $key.');
  }
  return value.toDouble();
}

Map<String, dynamic> _requiredMap(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! Map) {
    throw FormatException('The search response has an invalid $key.');
  }
  return Map<String, dynamic>.from(value);
}

List<String> _requiredStringList(Map<String, dynamic> json, String key) {
  final value = json[key];
  if (value is! List || value.any((item) => item is! String)) {
    throw FormatException('The search response has an invalid $key.');
  }
  return List<String>.unmodifiable(value);
}
