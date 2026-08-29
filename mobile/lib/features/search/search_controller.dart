import 'package:flutter/foundation.dart';

import '../../core/network/api_exception.dart';
import '../../repositories/search_repository.dart';
import 'search_state.dart';

class MemorySearchController extends ChangeNotifier {
  MemorySearchController({required SearchRepository repository}) : _repository = repository;

  final SearchRepository _repository;
  SearchState _state = const SearchState.initial();
  String? _lastCompletedQuery;
  int _requestVersion = 0;

  SearchState get state => _state;

  Future<void> search(String value, {bool force = false}) async {
    final query = value.trim();
    if (query.isEmpty) {
      _setState(
        const SearchState.error(
          query: '',
          message: 'Enter a search query before submitting.',
        ),
      );
      return;
    }
    if (_state.isLoading || (!force && query == _lastCompletedQuery)) {
      return;
    }

    final requestVersion = ++_requestVersion;
    _setState(SearchState.loading(query));
    try {
      final response = await _repository.search(query: query);
      if (requestVersion != _requestVersion) {
        return;
      }
      _lastCompletedQuery = query;
      _setState(
        response.results.isEmpty
            ? SearchState.empty(query: query, response: response)
            : SearchState.success(query: query, response: response),
      );
    } on ApiException catch (error) {
      if (requestVersion == _requestVersion) {
        _setState(SearchState.error(query: query, message: _messageFor(error)));
      }
    } catch (_) {
      if (requestVersion == _requestVersion) {
        _setState(
          SearchState.error(
            query: query,
            message: 'Search could not be completed. Please try again.',
          ),
        );
      }
    }
  }

  Future<void> retry() async {
    final query = _state.query;
    if (query == null || query.isEmpty || _state.isLoading) {
      return;
    }
    await search(query, force: true);
  }

  void _setState(SearchState state) {
    _state = state;
    notifyListeners();
  }

  String _messageFor(ApiException error) {
    switch (error.code) {
      case 'validation_error':
        return 'Check your search query and try again.';
      case 'authentication_required':
      case 'authentication_failed':
        return 'Your session has expired. Please sign in again.';
      case 'network_error':
      case 'request_timeout':
        return 'A network connection could not be established. Please try again.';
      case 'malformed_response':
        return 'The server returned an unexpected response.';
      default:
        return 'Search could not be completed. Please try again.';
    }
  }
}
