import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api.dart';
import '../widgets/common.dart';

class OperationScreen extends StatefulWidget {
  final StockApi api;
  final Product product;
  final bool price;
  const OperationScreen({
    super.key,
    required this.api,
    required this.product,
    this.price = false,
  });
  @override
  State<OperationScreen> createState() => _OperationScreenState();
}

class _OperationScreenState extends State<OperationScreen> {
  final form = GlobalKey<FormState>();
  final quantity = TextEditingController(), reason = TextEditingController();
  String type = 'IN';
  String? error;
  bool busy = false, prepared = false;
  @override
  void dispose() {
    quantity.dispose();
    reason.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    if (!prepared) {
      if (!form.currentState!.validate()) return;
      final target = widget.price ? null : int.parse(quantity.text);
      final after = target == null
          ? null
          : type == 'ADJUSTMENT'
          ? target
          : widget.product.stock + (type == 'IN' ? target : -target);
      if (after != null && (after < 0 || after > 2147483647)) {
        setState(
          () => error =
              'Cette quantité dépasse le stock disponible ou sa limite.',
        );
        return;
      }
      final accepted = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('Vérifier l’opération'),
          content: Text(
            '${widget.product.name}\n${widget.price ? 'Nouveau prix : ${quantity.text}' : '${movementType(type)} : $target\nStock : ${widget.product.stock} → $after'}\nMotif : ${reason.text.trim()}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('Corriger'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('Confirmer'),
            ),
          ],
        ),
      );
      if (accepted != true || !mounted) return;
    }
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (!prepared) {
        final body = <String, dynamic>{
          'reason': reason.text.trim(),
          'expected_version': widget.product.version,
          'idempotency_key': operationKey(),
        };
        if (widget.price) {
          body['price'] = quantity.text;
        } else {
          body.addAll({
            'product_id': widget.product.id,
            'type': type,
            'quantity': int.parse(quantity.text),
          });
        }
        await widget.api.prepare(
          widget.price ? '/products/${widget.product.id}/price' : '/movements',
          widget.price ? 'PATCH' : 'POST',
          body,
          '${widget.product.name} · ${widget.price ? 'Prix' : movementType(type)} · ${quantity.text} · ${reason.text.trim()}',
        );
        prepared = true;
      }
      await widget.api.sendPending();
      if (mounted) Navigator.pop(context, true);
    } catch (e) {
      if (mounted) {
        setState(
          () => error =
              '$e ${prepared ? 'L’opération reste à vérifier. Une réponse perdue ne veut pas dire que l’enregistrement a échoué. Réessayez à l’identique ou consultez l’historique depuis l’accueil.' : ''}',
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
      appBar: AppBar(
        title: Text(widget.price ? 'Changer le prix' : 'Mouvement de stock'),
      ),
      body: PageBody(
        children: [
          Text(
            widget.product.name,
            style: Theme.of(context).textTheme.headlineSmall,
          ),
          Text(
            '${widget.product.sku} · Stock actuel : ${widget.product.stock} ${widget.product.unit ?? ''}',
          ),
          if (widget.price)
            Text(
              'Prix actuel : ${amount(widget.product.price)} · Minimum : ${amount(widget.product.minPrice)}',
            ),
          Form(
            key: form,
            child: Column(
              children: [
                if (!widget.price)
                  DropdownButtonFormField<String>(
                    initialValue: type,
                    decoration: const InputDecoration(
                      labelText: 'Type de mouvement',
                    ),
                    items: ['IN', 'OUT', 'ADJUSTMENT']
                        .map(
                          (v) => DropdownMenuItem(
                            value: v,
                            child: Text(movementType(v)),
                          ),
                        )
                        .toList(),
                    onChanged: busy || prepared
                        ? null
                        : (v) => setState(() => type = v!),
                  ),
                const SizedBox(height: 18),
                TextFormField(
                  controller: quantity,
                  enabled: !busy && !prepared,
                  keyboardType: TextInputType.numberWithOptions(
                    decimal: widget.price,
                  ),
                  decoration: InputDecoration(
                    labelText: widget.price
                        ? 'Nouveau prix'
                        : type == 'ADJUSTMENT'
                        ? 'Stock cible après ajustement'
                        : 'Quantité',
                    helperText: widget.price
                        ? 'Point décimal · maximum 4 décimales'
                        : 'Quantité entière',
                  ),
                  validator: (v) {
                    if (widget.price) {
                      return v != null &&
                              RegExp(r'^\d{1,12}(\.\d{1,4})?$').hasMatch(v)
                          ? null
                          : 'Indiquez un prix positif, avec un point décimal.';
                    }
                    final n = int.tryParse(v ?? '');
                    return n == null ||
                            n < (type == 'ADJUSTMENT' ? 0 : 1) ||
                            n > 2147483647
                        ? 'Indiquez une quantité entière valide.'
                        : null;
                  },
                ),
                const SizedBox(height: 18),
                TextFormField(
                  controller: reason,
                  enabled: !busy && !prepared,
                  maxLength: 1000,
                  maxLines: 2,
                  decoration: const InputDecoration(
                    labelText: 'Motif de l’opération',
                  ),
                  validator: (v) => v == null || v.trim().isEmpty
                      ? 'Expliquez pourquoi vous faites cette opération.'
                      : null,
                ),
              ],
            ),
          ),
          if (error != null) MessageCard(error!, error: true),
          ActionButton(
            prepared
                ? 'Réessayer la même opération'
                : widget.price
                ? 'Vérifier le prix'
                : 'Vérifier le mouvement',
            busy: busy,
            onPressed: submit,
          ),
          const Text(
            'Une confirmation du service est nécessaire. Aucune opération n’est envoyée automatiquement après une coupure réseau.',
          ),
        ],
      ),
    ),
  );
}
