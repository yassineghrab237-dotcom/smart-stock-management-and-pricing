import 'package:flutter/material.dart';
import '../services/api.dart';
import '../widgets/common.dart';

class ProductCreateScreen extends StatefulWidget {
  final StockApi api;
  const ProductCreateScreen({super.key, required this.api});
  @override
  State<ProductCreateScreen> createState() => _ProductCreateScreenState();
}

class _ProductCreateScreenState extends State<ProductCreateScreen> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController(), sku = TextEditingController();
  bool busy = false;
  String? error;
  @override
  void dispose() {
    name.dispose();
    sku.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      await widget.api.request(
        '/products',
        method: 'POST',
        body: {'name': name.text.trim(), 'sku': sku.text.trim()},
      );
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(
          () => error =
              '$e Si la réponse a été perdue, recherchez ce SKU avant de réessayer. Un SKU ne peut être créé qu’une fois.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: Scaffold(
      appBar: AppBar(title: const Text('Ajouter un produit')),
      body: PageBody(
        children: [
          const Text(
            'Créez le produit, puis enregistrez une entrée pour ajouter son stock. Les seuils et les options avancées se règlent sur le web.',
          ),
          Form(
            key: form,
            child: Column(
              children: [
                TextFormField(
                  controller: name,
                  enabled: !busy,
                  maxLength: 180,
                  decoration: const InputDecoration(
                    labelText: 'Nom du produit',
                  ),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Indiquez le nom du produit.'
                      : null,
                ),
                const SizedBox(height: 18),
                TextFormField(
                  controller: sku,
                  enabled: !busy,
                  maxLength: 80,
                  decoration: const InputDecoration(
                    labelText: 'Référence / SKU',
                  ),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Indiquez une référence unique.'
                      : null,
                ),
              ],
            ),
          ),
          if (error != null) MessageCard(error!, error: true),
          ActionButton('Créer le produit', busy: busy, onPressed: submit),
        ],
      ),
    ),
  );
}
