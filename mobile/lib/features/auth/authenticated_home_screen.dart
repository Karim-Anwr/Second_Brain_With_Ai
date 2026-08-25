import 'package:flutter/material.dart';

import 'auth_controller.dart';

class AuthenticatedHomeScreen extends StatelessWidget {
  const AuthenticatedHomeScreen({super.key, required this.controller});

  final AuthController controller;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('SecondBrain'),
        actions: [
          IconButton(
            onPressed: controller.isLoading ? null : controller.logout,
            tooltip: 'Logout',
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: const Center(
        child: Padding(
          padding: EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.verified_user_outlined, size: 56),
              SizedBox(height: 16),
              Text('You are authenticated.'),
              SizedBox(height: 8),
              Text(
                'SecondBrain features will be added in a later phase.',
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
