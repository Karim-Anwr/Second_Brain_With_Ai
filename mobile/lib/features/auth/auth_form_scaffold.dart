import 'package:flutter/material.dart';

class AuthFormScaffold extends StatelessWidget {
  const AuthFormScaffold({
    super.key,
    required this.title,
    required this.subtitle,
    required this.form,
    required this.footer,
  });

  final String title;
  final String subtitle;
  final Widget form;
  final Widget footer;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(24),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 440),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Icon(
                    Icons.psychology_alt_outlined,
                    color: Theme.of(context).colorScheme.primary,
                    size: 52,
                  ),
                  const SizedBox(height: 20),
                  Text(
                    title,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.headlineMedium,
                  ),
                  const SizedBox(height: 8),
                  Text(
                    subtitle,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.bodyLarge,
                  ),
                  const SizedBox(height: 32),
                  form,
                  const SizedBox(height: 20),
                  footer,
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

String? requiredFieldValidator(String? value, String label) {
  if (value == null || value.trim().isEmpty) {
    return '$label is required.';
  }
  return null;
}

String? emailValidator(String? value) {
  final requiredError = requiredFieldValidator(value, 'Email');
  if (requiredError != null) {
    return requiredError;
  }
  if (!value!.contains('@')) {
    return 'Enter a valid email address.';
  }
  return null;
}
