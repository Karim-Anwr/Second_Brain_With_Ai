import 'package:flutter/material.dart';

import 'core/network/api_client.dart';
import 'core/storage/token_storage.dart';
import 'features/auth/auth_controller.dart';
import 'features/auth/auth_gate.dart';
import 'repositories/auth_repository.dart';

class SecondBrainApp extends StatefulWidget {
  const SecondBrainApp({
    super.key,
    this.controller,
  });

  final AuthController? controller;

  @override
  State<SecondBrainApp> createState() => _SecondBrainAppState();
}

class _SecondBrainAppState extends State<SecondBrainApp> {
  late final AuthController _controller;
  late final bool _ownsController;

  @override
  void initState() {
    super.initState();
    _ownsController = widget.controller == null;
    _controller = widget.controller ?? _createController();
    _controller.restoreSession();
  }

  @override
  void dispose() {
    if (_ownsController) {
      _controller.dispose();
    }
    super.dispose();
  }

  AuthController _createController() {
    final tokenStorage = SecureTokenStorage();
    late final AuthController controller;
    final apiClient = ApiClient(
      tokenStorage: tokenStorage,
      onSessionExpired: () => controller.handleSessionExpired(),
    );
    final repository = AuthRepository(
      apiClient: apiClient,
      tokenStorage: tokenStorage,
    );
    controller = AuthController(repository: repository);
    return controller;
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SecondBrain',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xFF315D9B)),
        useMaterial3: true,
      ),
      home: AuthGate(controller: _controller),
    );
  }
}
