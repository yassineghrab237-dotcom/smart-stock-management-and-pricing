import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../widgets/common.dart';

class BusinessField {
  final String name, label, initial;
  final bool required, integer;
  const BusinessField(
    this.name,
    this.label, {
    this.initial = '',
    this.required = true,
    this.integer = false,
  });
}

class BusinessMutation extends StatefulWidget {
  final StockApi api;
  final String title, path, impact, method;
  final List<BusinessField> fields;
  final Future<Json> Function(Map<String, String>) prepare;
  const BusinessMutation({
    super.key,
    required this.api,
    required this.title,
    required this.path,
    required this.impact,
    required this.fields,
    required this.prepare,
    this.method = 'POST',
  });
  @override
  State<BusinessMutation> createState() => _BusinessMutationState();
}

class _BusinessMutationState extends State<BusinessMutation> {
  final form = GlobalKey<FormState>();
  late final Map<String, TextEditingController> fields = {
    for (final f in widget.fields)
      f.name: TextEditingController(text: f.initial),
  };
  bool busy = false;
  String? error;
  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (await widget.api.pending() != null) {
        throw ApiException(
          'Une opération est déjà conservée. Revenez à l’accueil pour vérifier et reprendre le brouillon.',
        );
      }
      final body = await widget.prepare({
        for (final f in fields.entries) f.key: f.value.text.trim(),
      });
      if (!mounted) return;
      final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Confirmer cette opération'),
          content: Text(
            '${widget.title}\n\n${widget.impact}\n\n${fields.entries.map((e) => '${widget.fields.firstWhere((f) => f.name == e.key).label} : ${e.value.text}').join('\n')}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Retour'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirmer'),
            ),
          ],
        ),
      );
      if (accepted != true) return;
      await widget.api.prepare(widget.path, widget.method, {
        ...body,
        'idempotency_key': operationKey(),
      }, widget.title);
      final result = await widget.api.sendPending();
      if (mounted) Navigator.pop(context, result);
    } catch (e) {
      if (mounted) {
        setState(
          () => error =
              '$e Après une erreur réseau, le brouillon est accessible depuis l’accueil.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.title)),
    body: Form(
      key: form,
      child: PageBody(
        children: [
          MessageCard(widget.impact),
          ...widget.fields.map(
            (f) => TextFormField(
              controller: fields[f.name],
              enabled: !busy,
              decoration: InputDecoration(labelText: f.label),
              maxLength: f.integer ? 10 : 1000,
              keyboardType: f.integer
                  ? TextInputType.number
                  : TextInputType.text,
              validator: (value) {
                final v = value?.trim() ?? '';
                if (f.required && v.isEmpty) return 'Champ requis.';
                if (f.integer &&
                    (int.tryParse(v) == null ||
                        int.parse(v) < 0 ||
                        int.parse(v) > 2147483647)) {
                  return 'Entier positif ou nul requis.';
                }
                return null;
              },
            ),
          ),
          if (error != null) MessageCard(error!, error: true),
          ActionButton('Vérifier et confirmer', busy: busy, onPressed: submit),
        ],
      ),
    ),
  );
}
