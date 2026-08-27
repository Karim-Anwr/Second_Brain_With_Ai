import '../../models/search_response.dart';

enum SearchStatus {
  initial,
  loading,
  success,
  empty,
  error,
}

class SearchState {
  const SearchState({
    required this.status,
    this.query,
    this.response,
    this.message,
  });

  const SearchState.initial() : this(status: SearchStatus.initial);

  const SearchState.loading(String query)
      : this(status: SearchStatus.loading, query: query);

  const SearchState.success({
    required String query,
    required SearchResponse response,
  }) : this(status: SearchStatus.success, query: query, response: response);

  const SearchState.empty({
    required String query,
    required SearchResponse response,
  }) : this(status: SearchStatus.empty, query: query, response: response);

  const SearchState.error({
    required String query,
    required String message,
  }) : this(status: SearchStatus.error, query: query, message: message);

  final SearchStatus status;
  final String? query;
  final SearchResponse? response;
  final String? message;

  bool get isLoading => status == SearchStatus.loading;
}
