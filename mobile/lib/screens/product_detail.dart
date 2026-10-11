import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api.dart';
import '../widgets/common.dart';
import 'operation.dart';

class ProductDetailScreen extends StatefulWidget {
  final StockApi api;
  final int id;
  const ProductDetailScreen({super.key, required this.api, required this.id});
  @override
  State<ProductDetailScreen> createState() => _ProductDetailScreenState();
}

class _ProductDetailScreenState extends State<ProductDetailScreen> {
  late Future<List<Json>> data;
  String? success;
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    data = Future.wait([
      widget.api.request('/products/${widget.id}'),
      widget.api.request('/movements?product_id=${widget.id}'),
      widget.api.request('/products/${widget.id}/prices'),
    ]);
  }

  Future<void> operate(Product p, bool price) async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(
        builder: (_) =>
            OperationScreen(api: widget.api, product: p, price: price),
      ),
    );
    if (mounted) {
      setState(() {
        if (result == true) success = 'Opération enregistrée par le service.';
        load();
      });
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Fiche produit'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: () => setState(load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<List<Json>>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (snapshot.hasError) {
          return PageBody(
            children: [
              MessageCard(
                snapshot.error.toString(),
                error: true,
                retry: () => setState(load),
              ),
            ],
          );
        }
        if (!snapshot.hasData) {
          return const Center(child: CircularProgressIndicator());
        }
        final product = Product.fromJson(snapshot.data![0]);
        final movements = (snapshot.data![1]['items'] as List).cast<Json>();
        final prices = (snapshot.data![2]['items'] as List).cast<Json>();
        return PageBody(
          refresh: () async {
            setState(load);
            await data;
          },
          children: [
            if (success != null) MessageCard(success!),
            Text(
              product.name,
              style: Theme.of(context).textTheme.headlineMedium,
            ),
            Text(product.sku),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      '${product.stock} ${product.unit ?? 'unités'}',
                      style: Theme.of(context).textTheme.headlineLarge,
                    ),
                    Text('Seuil minimum : ${product.minimum}'),
                    Text('Prix actuel : ${amount(product.price)}'),
                    const Text('Montants sans devise ni taxe présumée.'),
                  ],
                ),
              ),
            ),
            if (widget.api.user!.canWrite) ...[
              ActionButton(
                'Enregistrer un mouvement',
                onPressed: () => operate(product, false),
              ),
              OutlinedButton(
                onPressed: () => operate(product, true),
                child: const Text('Changer le prix'),
              ),
            ],
            Text(
              'Derniers mouvements',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (movements.isEmpty)
              const Text(
                'Aucun mouvement. Une entrée permet d’ajouter du stock.',
              ),
            ...movements
                .take(30)
                .map(
                  (m) => Card(
                    child: ListTile(
                      title: Text(
                        '${movementType(m['type'] as String)} · ${m['quantity']}',
                      ),
                      subtitle: Text(
                        '${m['reason']}\n${m['stock_before']} → ${m['stock_after']} · ${m['actor_name']}\n${m['created_at']}',
                      ),
                      isThreeLine: true,
                    ),
                  ),
                ),
            Text(
              'Historique des prix',
              style: Theme.of(context).textTheme.titleLarge,
            ),
            if (prices.isEmpty)
              const Text('Aucun changement de prix enregistré.'),
            ...prices
                .take(30)
                .map(
                  (p) => Card(
                    child: ListTile(
                      title: Text(
                        '${amount(p['old_price'] as String?)} → ${amount(p['new_price'] as String)}',
                      ),
                      subtitle: Text('${p['reason']} · ${p['actor_name']}'),
                    ),
                  ),
                ),
          ],
        );
      },
    ),
  );
}
