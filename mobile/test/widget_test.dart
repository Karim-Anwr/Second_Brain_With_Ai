import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/app.dart';
import 'package:mobile/features/auth/auth_controller.dart';
import 'package:mobile/features/search/search_controller.dart';
import 'package:mobile/models/auth_tokens.dart';
import 'package:mobile/models/search_response.dart';
import 'package:mobile/repositories/auth_repository.dart';
import 'package:mobile/repositories/search_repository.dart';

void main() {
  testWidgets('renders login when no session is stored', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(
        controller: AuthController(
          repository: _FakeAuthRepository(),
        ),
        searchController: SearchController(repository: _FakeSearchRepository()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
    expect(find.text('Create an account'), findsOneWidget);
  });

  testWidgets('opens register screen from login', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(
        controller: AuthController(
          repository: _FakeAuthRepository(),
        ),
        searchController: SearchController(repository: _FakeSearchRepository()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Welcome back'), findsOneWidget);

    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();

    expect(find.text('Create your account'), findsOneWidget);
    expect(find.text('Register'), findsOneWidget);
    expect(find.text('Already have an account? Login'), findsOneWidget);
  });

  testWidgets('returns to login from register screen', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(
        controller: AuthController(
          repository: _FakeAuthRepository(),
        ),
        searchController: SearchController(repository: _FakeSearchRepository()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Create an account'));
    await tester.pumpAndSettle();

    await tester.tap(find.text('Already have an account? Login'));
    await tester.pumpAndSettle();

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Login'), findsOneWidget);
  });

  testWidgets('renders Search only after an authenticated session is restored', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(
        controller: AuthController(
          repository: _FakeAuthRepository(hasSession: true),
        ),
        searchController: SearchController(repository: _FakeSearchRepository()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('Search your memory'), findsOneWidget);
    expect(find.text('Welcome back'), findsNothing);
  });

  testWidgets('logout returns the authenticated Search route to login', (WidgetTester tester) async {
    await tester.pumpWidget(
      SecondBrainApp(
        controller: AuthController(
          repository: _FakeAuthRepository(hasSession: true),
        ),
        searchController: SearchController(repository: _FakeSearchRepository()),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byTooltip('Logout'));
    await tester.pumpAndSettle();

    expect(find.text('Welcome back'), findsOneWidget);
    expect(find.text('Search your memory'), findsNothing);
  });
}

class _FakeAuthRepository implements AuthenticationRepository {
  _FakeAuthRepository({this.hasSession = false});

  final bool hasSession;

  @override
  Future<AuthTokens> login({
    required String email,
    required String password,
  }) {
    throw UnimplementedError();
  }

  @override
  Future<void> logout() async {}

  @override
  Future<AuthTokens> refresh({
    required String refreshToken,
  }) {
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
  Future<bool> restoreSession() async => hasSession;
}

class _FakeSearchRepository implements SearchRepository {
  @override
  Future<SearchResponse> search({
    required String query,
    int topK = 5,
    String? category,
    bool? isFavorite,
  }) {
    throw UnimplementedError();
  }
}
