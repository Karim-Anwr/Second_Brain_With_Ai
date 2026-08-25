enum AuthStatus {
  initializing,
  authenticated,
  unauthenticated,
  loading,
  error,
}

class AuthState {
  const AuthState({
    required this.status,
    this.message,
  });

  const AuthState.initializing() : this(status: AuthStatus.initializing);

  const AuthState.authenticated() : this(status: AuthStatus.authenticated);

  const AuthState.unauthenticated() : this(status: AuthStatus.unauthenticated);

  const AuthState.loading() : this(status: AuthStatus.loading);

  const AuthState.error(String message)
      : this(status: AuthStatus.error, message: message);

  final AuthStatus status;
  final String? message;

  bool get isAuthenticated => status == AuthStatus.authenticated;
  bool get isLoading => status == AuthStatus.loading;
}
