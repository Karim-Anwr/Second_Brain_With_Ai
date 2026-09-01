import 'package:flutter/material.dart';

import 'auth_controller.dart';
import 'auth_state.dart';
import 'authenticated_home_screen.dart';
import 'login_screen.dart';
import 'register_screen.dart';
import '../search/search_controller.dart';
import '../upload/upload_controller.dart';

class AuthGate extends StatefulWidget {
  const AuthGate({
    super.key,
    required this.controller,
    required this.searchController,
    required this.uploadController,
  });

  final AuthController controller;
  final MemorySearchController searchController;
  final UploadController uploadController;

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  bool _showRegister = false;

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.controller,
      builder: (context, _) {
        final state = widget.controller.state;
        if (state.status == AuthStatus.initializing) {
          return const _LoadingScreen(message: 'Restoring your session…');
        }
        if (state.isAuthenticated) {
          return AuthenticatedHomeScreen(
            controller: widget.controller,
            searchController: widget.searchController,
            uploadController: widget.uploadController,
          );
        }

        final showRegister = _showRegister;
        if (showRegister) {
          return RegisterScreen(
            controller: widget.controller,
            message: state.status == AuthStatus.error ? state.message : null,
            onShowLogin: () => setState(() => _showRegister = false),
          );
        }

        return LoginScreen(
          controller: widget.controller,
          message: state.status == AuthStatus.error ? state.message : null,
          onShowRegister: () => setState(() => _showRegister = true),
        );
      },
    );
  }
}

class _LoadingScreen extends StatelessWidget {
  const _LoadingScreen({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 16),
            Text(message),
          ],
        ),
      ),
    );
  }
}
