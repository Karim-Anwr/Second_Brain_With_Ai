import 'package:flutter/material.dart';

import 'auth_controller.dart';
import 'auth_form_scaffold.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({
    super.key,
    required this.controller,
    required this.onShowLogin,
    this.message,
  });

  final AuthController controller;
  final VoidCallback onShowLogin;
  final String? message;

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController = TextEditingController();
  final _passwordController = TextEditingController();
  final _displayNameController = TextEditingController();

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    _displayNameController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (widget.controller.isLoading || !_formKey.currentState!.validate()) {
      return;
    }
    final displayName = _displayNameController.text.trim();
    await widget.controller.register(
      email: _emailController.text.trim(),
      password: _passwordController.text,
      displayName: displayName.isEmpty ? null : displayName,
    );
  }

  @override
  Widget build(BuildContext context) {
    final isLoading = widget.controller.isLoading;
    return AuthFormScaffold(
      title: 'Create your account',
      subtitle: 'Start with a secure SecondBrain session.',
      form: Form(
        key: _formKey,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            TextFormField(
              controller: _emailController,
              enabled: !isLoading,
              keyboardType: TextInputType.emailAddress,
              autofillHints: const [AutofillHints.newUsername],
              decoration: const InputDecoration(labelText: 'Email'),
              validator: emailValidator,
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _passwordController,
              enabled: !isLoading,
              obscureText: true,
              autofillHints: const [AutofillHints.newPassword],
              decoration: const InputDecoration(labelText: 'Password'),
              validator: (value) => requiredFieldValidator(value, 'Password'),
              onFieldSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _displayNameController,
              enabled: !isLoading,
              textCapitalization: TextCapitalization.words,
              decoration: const InputDecoration(labelText: 'Display name (optional)'),
            ),
            if (widget.message != null) ...[
              const SizedBox(height: 16),
              Text(
                widget.message!,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const SizedBox(height: 24),
            FilledButton(
              onPressed: isLoading ? null : _submit,
              child: isLoading
                  ? const SizedBox(
                      height: 20,
                      width: 20,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Text('Register'),
            ),
          ],
        ),
      ),
      footer: TextButton(
        onPressed: isLoading ? null : widget.onShowLogin,
        child: const Text('Already have an account? Login'),
      ),
    );
  }
}
