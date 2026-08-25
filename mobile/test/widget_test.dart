import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app.dart';
import 'package:mobile/features/auth/auth_controller.dart';
import 'package:mobile/models/auth_tokens.dart';
import 'package:mobile/repositories/auth_repository.dart';

void main() {
  testWidgets('renders login when no session is stored', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(controller: AuthController(repository: _FakeAuthRepository())),
    );
    await tester.pumpAndSettle();

    expect(find.text('SecondBrain'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
  });
}

class _FakeAuthRepository implements AuthenticationRepository {
  @override
  Future<AuthTokens> login({required String email, required String password}) {
    throw UnimplementedError();
  }

  @override
  Future<void> logout() async {}

  @override
  Future<AuthTokens> refresh({required String refreshToken}) {
    throw UnimplementedError();
  }

  @override
  Future<AuthTokens> register({
    required String email,
    required String password,
    String? displayName,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<bool> restoreSession() async => false;
}
