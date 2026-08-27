import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/search_response.dart';

void main() {
  final validResponse = <String, dynamic>{
    'query': 'laptop price',
    'total': 1,
    'results': [
      {
        'memory_id': 'mem_123',
        'file_name': 'receipt.pdf',
        'summary': 'Laptop receipt',
        'matched_text': 'The price was 1200.',
        'tags': ['shopping', 'laptop'],
        'created_at': '2026-08-27T10:00:00Z',
        'scores': {'final': 0.9, 'semantic': 0.8, 'recency': 0.7, 'importance': 0.6},
      },
    ],
    'llm_answer': 'The laptop cost 1200.',
  };

  test('parses the verified public search response contract', () {
    final response = SearchResponse.fromJson(validResponse);

    expect(response.query, 'laptop price');
    expect(response.total, 1);
    expect(response.llmAnswer, 'The laptop cost 1200.');
    expect(response.results.single.memoryId, 'mem_123');
    expect(response.results.single.scores.finalScore, 0.9);
  });

  test('accepts nullable llm answer and an empty result set', () {
    final response = SearchResponse.fromJson({
      'query': 'unknown',
      'total': 0,
      'results': [],
      'llm_answer': null,
    });

    expect(response.results, isEmpty);
    expect(response.llmAnswer, isNull);
  });

  test('rejects malformed public response payloads', () {
    expect(
      () => SearchResponse.fromJson({...validResponse, 'results': 'not-a-list'}),
      throwsFormatException,
    );
    expect(
      () => SearchResponse.fromJson({...validResponse, 'llm_answer': 42}),
      throwsFormatException,
    );
  });
}
