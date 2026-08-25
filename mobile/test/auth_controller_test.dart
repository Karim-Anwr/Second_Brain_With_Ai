import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/core/network/api_exception.dart';
import 'package:mobile/features/auth/auth_controller.dart';
import 'package:mobile/features/auth/auth_state.dart';
import 'package:mobile/models/auth_tokens.dart';
import 'package:mobile/repositories/auth_repository.dart';

void main() {
  group('AuthController', () {
    test('restores an existing local session without refreshing it', () async {
      final repository = _FakeAuthRepository(hasSession: true);
      final controller = AuthController(repository: repository);

      await controller.restoreSession();

      expect(controller.state.status, AuthStatus.authenticated);
      expect(repository.refreshCalls, 0);
    });

    test('becomes authenticated after a successful login', () async {
      final repository = _FakeAuthRepository();
      final controller = AuthController(repository: repository);

      await controller.login(email: 'user@example.com', password: 'password');

      expect(controller.state.status, AuthStatus.authenticated);
      expect(repository.loginCalls, 1);
    });

    test('exposes a safe message for authentication errors', () async {
      final repository = _FakeAuthRepository(
        loginError: const ApiException(
          statusCode: 401,
          code: 'invalid_credentials',
          message: 'Email or password is incorrect.',
        ),
      );
      final controller = AuthController(repository: repository);

      await controller.login(email: 'user@example.com', password: 'wrong');

      expect(controller.state.status, AuthStatus.error);
      expect(controller.state.message, 'Email or password is incorrect.');
    });

    test('logout clears credentials and returns to unauthenticated state', () async {
      final repository = _FakeAuthRepository();
      final controller = AuthController(repository: repository);

      await controller.logout();

      expect(controller.state.status, AuthStatus.unauthenticated);
      expect(repository.logoutCalls, 1);
    });

    test('refresh expiry transition returns to unauthenticated state', () async {
      final controller = AuthController(repository: _FakeAuthRepository());

      await controller.handleSessionExpired();

      expect(controller.state.status, AuthStatus.unauthenticated);
    });
  });
}

class _FakeAuthRepository implements AuthenticationRepository {
  _FakeAuthRepository({
    this.hasSession = false,
    this.loginError,
  });

  final bool hasSession;
  final ApiException? loginError;
  int loginCalls = 0;
  int logoutCalls = 0;
  int refreshCalls = 0;

  static final _tokens = AuthTokens.fromJson(<String, dynamic>{
    'access_token': 'access-token',
    'refresh_token': 'refresh-token',
    'token_type': 'bearer',
    'expires_at': '2026-08-25T12:00:00.000Z',
    'expires_in': 900,
  });

  @override
  Future<AuthTokens> login({required String email, required String password}) async {
    loginCalls++;
    final error = loginError;
    if (error != null) {
      throw error;
    }
    return _tokens;
  }

  @override
  Future<void> logout() async {
    logoutCalls++;
  }

  @override
  Future<AuthTokens> refresh({required String refreshToken}) async {
    refreshCalls++;
    return _tokens;
  }

  @override
  Future<AuthTokens> register({
    required String email,
    required String password,
    String? displayName,
  }) async => _tokens;

  @override
  Future<bool> restoreSession() async => hasSession;
}
