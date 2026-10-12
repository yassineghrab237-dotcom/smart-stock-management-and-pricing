import 'package:flutter/material.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../widgets/common.dart';

class MarketProduct extends StatefulWidget {
  final StockApi api;
  final int productId;
  const MarketProduct({super.key, required this.api, required this.productId});
  @override
  State<MarketProduct> createState() => _MarketProductState();
}

class _MarketProductState extends State<MarketProduct> {
  late Future<Json> data;
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    data = widget.api.request('/market/products/${widget.productId}');
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Offres concurrentes'),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: () => setState(load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    body: FutureBuilder<Json>(
      future: data,
      builder: (context, s) {
        if (s.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        if (s.hasError) {
          return PageBody(
            children: [
              MessageCard(
                s.error.toString(),
                error: true,
                retry: () => setState(load),
              ),
            ],
          );
        }
        final d = s.data!;
        final items = (d['items'] as List).cast<Json>();
        return PageBody(
          refresh: () async {
            setState(load);
            await data;
          },
          children: [
            Text(
              (d['product'] as Json)['name'] as String,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            const MessageCard(
              'Relevés validés ou manuels. La collecte, les variantes et la validation se gèrent sur le web. Aucune modification du prix interne.',
            ),
            if (items.isEmpty)
              const MessageCard('Aucune offre enregistrée pour ce produit.'),
            ...items.map(
              (o) => Card(
                child: Padding(
                  padding: const EdgeInsets.all(16),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        o['retailer'] as String,
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                      Text(
                        '${amount(o['price'] as String?)} ${o['currency']} · ${o['tax_basis']}',
                      ),
                      Text('${o['manufacturer_ref']} · ${o['variant']}'),
                      Text(
                        '${o['confirmed'] == true ? 'Correspondance confirmée' : 'À vérifier'} · ${o['stale'] == true
                            ? 'Périmé'
                            : o['current'] == true
                            ? 'Actuel'
                            : 'Historique'}',
                      ),
                      Text('Livraison : ${amount(o['delivery'] as String?)}'),
                      Text(
                        o['delta_to_lowest'] == null
                            ? 'Comparaison indisponible'
                            : 'Écart au minimum : ${amount(o['delta_to_lowest'] as String?)} ${o['currency']}',
                      ),
                      Text('Observé le ${o['observed_at']}'),
                      SelectableText(o['source_url'] as String),
                    ],
                  ),
                ),
              ),
            ),
          ],
        );
      },
    ),
  );
}
