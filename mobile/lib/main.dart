import 'package:flutter/material.dart';
import 'services/api.dart';
import 'screens/login.dart';
import 'screens/workspace.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(StockApp(api: StockApi()));
}

class StockApp extends StatefulWidget {
  final StockApi api;
  const StockApp({super.key, required this.api});
  @override
  State<StockApp> createState() => _StockAppState();
}

class _StockAppState extends State<StockApp> {
  final navigator = GlobalKey<NavigatorState>();
  bool loading = true;
  String? message;
  @override
  void initState() {
    super.initState();
    widget.api.onExpired = () {
      if (mounted) {
        navigator.currentState?.popUntil((route) => route.isFirst);
        setState(
          () => message =
              'Votre session a expiré. Reconnectez-vous. Les opérations confirmées sont conservées.',
        );
      }
    };
    restore();
  }

  Future<void> restore() async {
    try {
      await widget.api.restore();
    } catch (e) {
      message = 'Impossible de reprendre la session : $e';
    }
    if (mounted) setState(() => loading = false);
  }

  @override
  Widget build(BuildContext context) => MaterialApp(
    navigatorKey: navigator,
    debugShowCheckedModeBanner: false,
    title: 'Smart Stock',
    theme: ThemeData(
      useMaterial3: true,
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff087e76)),
      scaffoldBackgroundColor: const Color(0xfff4f7f8),
      appBarTheme: const AppBarTheme(backgroundColor: Color(0xfff4f7f8)),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: Colors.white,
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
      ),
      cardTheme: CardThemeData(
        color: Colors.white,
        elevation: 0,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
      ),
      navigationBarTheme: const NavigationBarThemeData(height: 72),
    ),
    home: loading
        ? const Scaffold(body: Center(child: CircularProgressIndicator()))
        : widget.api.user == null
        ? LoginScreen(
            api: widget.api,
            message: message,
            onLogin: () => setState(() => message = null),
          )
        : Workspace(
            api: widget.api,
            onLogout: () => setState(() => message = null),
          ),
  );
}
