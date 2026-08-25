class AuthTokens {
  const AuthTokens({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresAt,
    required this.expiresIn,
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final DateTime expiresAt;
  final int expiresIn;

  factory AuthTokens.fromJson(Map<String, dynamic> json) {
    final accessToken = json['access_token'];
    final refreshToken = json['refresh_token'];
    final tokenType = json['token_type'];
    final expiresAt = json['expires_at'];
    final expiresIn = json['expires_in'];

    if (accessToken is! String || accessToken.isEmpty ||
        refreshToken is! String || refreshToken.isEmpty ||
        tokenType is! String || tokenType.isEmpty ||
        expiresAt is! String ||
        expiresIn is! num) {
      throw const FormatException('The authentication response is incomplete.');
    }

    final parsedExpiry = DateTime.tryParse(expiresAt);
    if (parsedExpiry == null) {
      throw const FormatException('The authentication response has an invalid expiry.');
    }

    return AuthTokens(
      accessToken: accessToken,
      refreshToken: refreshToken,
      tokenType: tokenType,
      expiresAt: parsedExpiry,
      expiresIn: expiresIn.toInt(),
    );
  }

  Map<String, dynamic> toJson() => <String, dynamic>{
        'access_token': accessToken,
        'refresh_token': refreshToken,
        'token_type': tokenType,
        'expires_at': expiresAt.toIso8601String(),
        'expires_in': expiresIn,
      };
}
