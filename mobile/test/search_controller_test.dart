import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_exception.dart';
import 'package:mobile/features/search/search_controller.dart';
import 'package:mobile/features/search/search_state.dart';
import 'package:mobile/models/search_response.dart';
import 'package:mobile/repositories/search_repository.dart';

void main() {
  group('SearchController', () {
    test('starts in the initial state', () {
      final controller = SearchController(repository: _FakeSearchRepository());

      expect(controller.state.status, SearchStatus.initial);
    });

    test('trims a query and transitions to successful results', () async {
      final repository = _FakeSearchRepository(response: _response());
      final controller = SearchController(repository: repository);
      final states = <SearchStatus>[];
      controller.addListener(() => states.add(controller.state.status));

      await controller.search('  laptop  ');

      expect(repository.queries, ['laptop']);
      expect(states, [SearchStatus.loading, SearchStatus.success]);
      expect(controller.state.response!.results, hasLength(1));
    });

    test('transitions to empty for an empty backend result set', () async {
      final controller = SearchController(
        repository: _FakeSearchRepository(response: _response(results: const [])),
      );

      await controller.search('missing');

      expect(controller.state.status, SearchStatus.empty);
    });

    test('reports an inline validation error without calling the repository', () async {
      final repository = _FakeSearchRepository();
      final controller = SearchController(repository: repository);

      await controller.search('   ');

      expect(controller.state.status, SearchStatus.error);
      expect(controller.state.message, 'Enter a search query before submitting.');
      expect(repository.queries, isEmpty);
    });

    test('maps unauthorized and network errors to safe user-facing states', () async {
      final unauthorized = SearchController(
        repository: _FakeSearchRepository(
          error: const ApiException(
            statusCode: 401,
            code: 'authentication_required',
            message: 'Authentication is required.',
          ),
        ),
      );
      await unauthorized.search('private');
      expect(unauthorized.state.message, 'Your session has expired. Please sign in again.');

      final offline = SearchController(
        repository: _FakeSearchRepository(
          error: const ApiException(code: 'network_error', message: 'offline'),
        ),
      );
      await offline.search('private');
      expect(offline.state.message, 'A network connection could not be established. Please try again.');
    });

    test('does not repeat a completed identical query unless retry is explicit', () async {
      final repository = _FakeSearchRepository(response: _response());
      final controller = SearchController(repository: repository);

      await controller.search('laptop');
      await controller.search(' laptop ');
      expect(repository.queries, ['laptop']);

      await controller.retry();
      expect(repository.queries, ['laptop', 'laptop']);
    });
  });
}

class _FakeSearchRepository implements SearchRepository {
  _FakeSearchRepository({this.response, this.error});

  final SearchResponse? response;
  final Object? error;
  final List<String> queries = [];

  @override
  Future<SearchResponse> search({
    required String query,
    int topK = 5,
    String? category,
    bool? isFavorite,
  }) async {
    queries.add(query);
    final failure = error;
    if (failure != null) {
      throw failure;
    }
    return response ?? _response();
  }
}

SearchResponse _response({List<SearchResult>? results}) {
  return SearchResponse(
    query: 'laptop',
    total: results?.length ?? 1,
    results: results ??
        const [
          SearchResult(
            memoryId: 'mem_123',
            fileName: 'receipt.pdf',
            summary: 'Laptop receipt',
            matchedText: 'The price was 1200.',
            tags: ['shopping'],
            createdAt: '2026-08-27T10:00:00Z',
            scores: SearchScores(finalScore: 0.9, semantic: 0.8, recency: 0.7, importance: 0.6),
          ),
        ],
    llmAnswer: 'The laptop cost 1200.',
  );
}
