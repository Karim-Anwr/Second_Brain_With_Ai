/// Compile-time configuration for values that must never be embedded in API code.
class AppConfig {
  AppConfig._();

  static const String _rawApiBaseUrl = String.fromEnvironment('API_BASE_URL');

  static String get apiBaseUrl {
    final value = _rawApiBaseUrl.trim();
    final uri = Uri.tryParse(value);
    if (value.isEmpty || uri == null || !uri.hasScheme || !uri.hasAuthority) {
      throw StateError(
        'API_BASE_URL is required. Launch with '
        '--dart-define=API_BASE_URL=<environment-url>',
      );
    }

    return value.endsWith('/') ? value.substring(0, value.length - 1) : value;
  }

  static void validate() {
    // Parsing forces evaluation of the validated compile-time value at startup.
    Uri.parse(apiBaseUrl);
  }
}
