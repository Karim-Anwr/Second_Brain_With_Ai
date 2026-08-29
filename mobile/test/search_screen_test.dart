import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/features/search/search_controller.dart';
import 'package:mobile/features/search/search_screen.dart';
import 'package:mobile/models/search_response.dart';
import 'package:mobile/repositories/search_repository.dart';

void main() {
  testWidgets('submits a query and renders the verified result fields', (tester) async {
    final repository = _FakeSearchRepository(response: _response());
    final controller = MemorySearchController(repository: repository);

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: SearchScreen(controller: controller))),
    );
    await tester.enterText(find.byType(TextField), 'laptop');
    await tester.tap(find.byTooltip('Search'));
    await tester.pump();
    await tester.pumpAndSettle();

    expect(repository.queries, ['laptop']);
    expect(find.text('receipt.pdf'), findsOneWidget);
    expect(find.text('Laptop receipt'), findsOneWidget);
    expect(find.text('The laptop cost 1200.'), findsOneWidget);
  });

  testWidgets('renders an empty-state message and retry action', (tester) async {
    final controller = MemorySearchController(
      repository: _FakeSearchRepository(
        response: const SearchResponse(query: 'missing', total: 0, results: [], llmAnswer: null),
      ),
    );

    await tester.pumpWidget(
      MaterialApp(home: Scaffold(body: SearchScreen(controller: controller))),
    );
    await tester.enterText(find.byType(TextField), 'missing');
    await tester.tap(find.byTooltip('Search'));
    await tester.pumpAndSettle();

    expect(find.text('No memories found'), findsOneWidget);
    expect(find.text('Retry search'), findsOneWidget);
  });
}

class _FakeSearchRepository implements SearchRepository {
  _FakeSearchRepository({required this.response});

  final SearchResponse response;
  final List<String> queries = [];

  @override
  Future<SearchResponse> search({
    required String query,
    int topK = 5,
    String? category,
    bool? isFavorite,
  }) async {
    queries.add(query);
    return response;
  }
}

SearchResponse _response() => const SearchResponse(
      query: 'laptop',
      total: 1,
      results: [
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
