import 'package:flutter_test/flutter_test.dart';
import 'package:mobile/models/auth_tokens.dart';

void main() {
  test('AuthTokens parses and serializes the backend token response', () {
    final tokens = AuthTokens.fromJson(<String, dynamic>{
      'access_token': 'access-token',
      'refresh_token': 'refresh-token',
      'token_type': 'bearer',
      'expires_at': '2026-08-25T12:00:00.000Z',
      'expires_in': 900,
    });

    expect(tokens.accessToken, 'access-token');
    expect(tokens.refreshToken, 'refresh-token');
    expect(tokens.tokenType, 'bearer');
    expect(tokens.expiresIn, 900);
    expect(tokens.toJson()['refresh_token'], 'refresh-token');
  });

  test('AuthTokens rejects an incomplete backend response', () {
    expect(
      () => AuthTokens.fromJson(<String, dynamic>{}),
      throwsFormatException,
    );
  });
}
