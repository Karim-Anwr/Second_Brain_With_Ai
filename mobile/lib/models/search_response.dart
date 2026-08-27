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
      finalScore: (json['final'] as num).toDouble(),
      semantic: (json['semantic'] as num).toDouble(),
      recency: (json['recency'] as num).toDouble(),
      importance: (json['importance'] as num).toDouble(),
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
      memoryId: json['memory_id'] as String,
      fileName: json['file_name'] as String,
      summary: json['summary'] as String,
      matchedText: json['matched_text'] as String,
      tags: List<String>.from(json['tags'] as List),
      createdAt: json['created_at'] as String,
      scores: SearchScores.fromJson(
        Map<String, dynamic>.from(json['scores'] as Map),
      ),
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
    return SearchResponse(
      query: json['query'] as String,
      total: json['total'] as int,
      results: (json['results'] as List)
          .map(
            (item) => SearchResult.fromJson(
              Map<String, dynamic>.from(item as Map),
            ),
          )
          .toList(),
      llmAnswer: json['llm_answer'] as String?,
    );
  }
}