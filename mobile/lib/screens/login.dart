import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/common.dart';

class LoginScreen extends StatefulWidget {
  final StockApi api;
  final VoidCallback onLogin;
  final String? message;
  const LoginScreen({
    super.key,
    required this.api,
    required this.onLogin,
    this.message,
  });
  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final form = GlobalKey<FormState>();
  final address = TextEditingController(
    text: const String.fromEnvironment('API_URL', defaultValue: 'https://'),
  );
  final email = TextEditingController(), password = TextEditingController();
  bool busy = false, visible = false;
  String? error;
  @override
  void dispose() {
    address.dispose();
    email.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> login() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.login(address.text, email.text.trim(), password.text);
      if (mounted) {
        password.clear();
        widget.onLogin();
      }
    } catch (e) {
      if (mounted) setState(() => error = e.toString());
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    body: SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: PageBody(
            children: [
              const Icon(
                Icons.inventory_2_outlined,
                size: 56,
                color: Color(0xff087e76),
              ),
              Text(
                'Smart Stock',
                style: Theme.of(context).textTheme.headlineLarge,
              ),
              const Text(
                'Votre stock, à portée de main. Connectez-vous avec le compte créé sur votre ordinateur.',
              ),
              if (widget.message != null) MessageCard(widget.message!),
              Form(
                key: form,
                child: Column(
                  children: [
                    TextFormField(
                      controller: address,
                      enabled: !busy,
                      keyboardType: TextInputType.url,
                      autocorrect: false,
                      decoration: const InputDecoration(
                        labelText: 'Adresse du service',
                        hintText: 'https://votre-service',
                      ),
                      validator: (v) {
                        try {
                          validateEndpoint(v ?? '');
                          return null;
                        } catch (e) {
                          return e.toString();
                        }
                      },
                    ),
                    const SizedBox(height: 18),
                    TextFormField(
                      controller: email,
                      enabled: !busy,
                      keyboardType: TextInputType.emailAddress,
                      autofillHints: const [AutofillHints.username],
                      decoration: const InputDecoration(
                        labelText: 'Adresse e-mail',
                      ),
                      validator: (v) => v == null || !v.contains('@')
                          ? 'Indiquez votre adresse e-mail.'
                          : null,
                    ),
                    const SizedBox(height: 18),
                    TextFormField(
                      controller: password,
                      enabled: !busy,
                      obscureText: !visible,
                      autofillHints: const [AutofillHints.password],
                      decoration: InputDecoration(
                        labelText: 'Mot de passe',
                        suffixIcon: IconButton(
                          tooltip: visible
                              ? 'Masquer le mot de passe'
                              : 'Afficher le mot de passe',
                          onPressed: () => setState(() => visible = !visible),
                          icon: Icon(
                            visible ? Icons.visibility_off : Icons.visibility,
                          ),
                        ),
                      ),
                      validator: (v) => v == null || v.isEmpty
                          ? 'Indiquez votre mot de passe.'
                          : null,
                    ),
                  ],
                ),
              ),
              if (error != null) MessageCard(error!, error: true),
              ActionButton('Se connecter', busy: busy, onPressed: login),
              const MessageCard(
                'Pour le test local Android, reliez le téléphone au PC par USB. Le guide technique explique le tunnel sécurisé au câble. Un accès à distance nécessite un service HTTPS configuré.',
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
