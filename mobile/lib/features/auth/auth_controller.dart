import 'package:flutter/foundation.dart';

import '../../core/network/api_exception.dart';
import '../../repositories/auth_repository.dart';
import 'auth_state.dart';

class AuthController extends ChangeNotifier {
  AuthController({required AuthenticationRepository repository})
      : _repository = repository;

  final AuthenticationRepository _repository;
  AuthState _state = const AuthState.initializing();

  AuthState get state => _state;
  bool get isAuthenticated => _state.isAuthenticated;
  bool get isLoading => _state.isLoading;

  Future<void> restoreSession() async {
    _setState(const AuthState.initializing());
    try {
      final hasSession = await _repository.restoreSession();
      _setState(
        hasSession
            ? const AuthState.authenticated()
            : const AuthState.unauthenticated(),
      );
    } catch (_) {
      _setState(const AuthState.error('Your saved session could not be restored.'));
    }
  }

  Future<void> login({
    required String email,
    required String password,
  }) {
    return _authenticate(
      () => _repository.login(email: email, password: password),
    );
  }

  Future<void> register({
    required String email,
    required String password,
    String? displayName,
  }) {
    return _authenticate(
      () => _repository.register(
        email: email,
        password: password,
        displayName: displayName,
      ),
    );
  }

  Future<void> logout() async {
    _setState(const AuthState.loading());
    try {
      await _repository.logout();
      _setState(const AuthState.unauthenticated());
    } catch (_) {
      _setState(const AuthState.error('Your local credentials could not be cleared.'));
    }
  }

  Future<void> handleSessionExpired() async {
    _setState(const AuthState.unauthenticated());
  }

  Future<void> _authenticate(Future<Object?> Function() action) async {
    if (isLoading) {
      return;
    }

    _setState(const AuthState.loading());
    try {
      await action();
      _setState(const AuthState.authenticated());
    } on ApiException catch (error) {
      _setState(AuthState.error(error.message));
    } catch (_) {
      _setState(const AuthState.error('Authentication could not be completed.'));
    }
  }

  void _setState(AuthState state) {
    _state = state;
    notifyListeners();
  }
}
