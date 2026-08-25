class ApiError {
  const ApiError({required this.code, required this.message});

  final String code;
  final String message;

  factory ApiError.fromJson(Map<String, dynamic> json) {
    final code = json['code'];
    final message = json['message'];
    if (code is! String || message is! String) {
      throw const FormatException('The API error envelope is malformed.');
    }
    return ApiError(code: code, message: message);
  }
}
