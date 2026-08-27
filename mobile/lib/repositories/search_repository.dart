import '../core/network/api_client.dart';
import '../core/network/api_exception.dart';
import '../models/search_response.dart';

abstract interface class SearchRepository {
  Future<SearchResponse> search({
    required String query,
    int topK = 5,
    String? category,
    bool? isFavorite,
  });
}

class ApiSearchRepository implements SearchRepository {
  ApiSearchRepository({required ApiClient apiClient}) : _apiClient = apiClient;

  final ApiClient _apiClient;

  @override
  Future<SearchResponse> search({
    required String query,
    int topK = 5,
    String? category,
    bool? isFavorite,
  }) async {
    final response = await _apiClient.post<dynamic>(
      '/search',
      data: <String, dynamic>{
        'query': query,
        'top_k': topK,
        if (category != null && category.isNotEmpty) 'category': category,
        if (isFavorite != null) 'is_favorite': isFavorite,
      },
    );
    final data = response.data;
    if (data is! Map) {
      throw ApiException.malformedResponse();
    }

    try {
      return SearchResponse.fromJson(Map<String, dynamic>.from(data));
    } on FormatException {
      throw ApiException.malformedResponse();
    } on TypeError {
      throw ApiException.malformedResponse();
    }
  }
}
