import 'package:flutter/material.dart';
import '../../models/business.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../widgets/common.dart';
import 'business_mutation.dart';

class BusinessDetail extends StatefulWidget {
  final StockApi api;
  final BusinessKind kind;
  final int id;
  const BusinessDetail({
    super.key,
    required this.api,
    required this.kind,
    required this.id,
  });
  @override
  State<BusinessDetail> createState() => _BusinessDetailState();
}

class _BusinessDetailState extends State<BusinessDetail> {
  late int id = widget.id;
  late Future<Json> data;
  String? message;
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    data = widget.api.request('${widget.kind.path}/$id');
  }

  Future<void> mutate(
    String title,
    String path,
    String impact,
    List<BusinessField> fields,
    Future<Json> Function(Map<String, String>) prepare, {
    String method = 'POST',
  }) async {
    final result = await Navigator.push<Json>(
      context,
      MaterialPageRoute(
        builder: (_) => BusinessMutation(
          api: widget.api,
          title: title,
          path: path,
          impact: impact,
          fields: fields,
          prepare: prepare,
          method: method,
        ),
      ),
    );
    if (mounted && result != null) {
      setState(() {
        if (widget.kind == BusinessKind.sales && result['id'] is int) {
          id = result['id'] as int;
        }
        message = 'Opération confirmée par le service.';
        load();
      });
    }
  }

  Future<Json> versions(List<Json> lines) async {
    final products = await Future.wait(
      lines.map((l) => widget.api.request('/products/${l['product_id']}')),
    );
    return {for (final p in products) '${p['id']}': p['version']};
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(widget.kind.title),
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
        final d = snapshot.data!;
        final lines = ((d['lines'] as List?) ?? []).cast<Json>();
        final write = widget.api.user!.canWrite;
        return PageBody(
          refresh: () async {
            setState(load);
            await data;
          },
          children: [
            Text(
              (d['reference'] ?? d['title'] ?? d['name']) as String,
              style: Theme.of(context).textTheme.headlineSmall,
            ),
            if (message != null) MessageCard(message!),
            Text(businessStatus((d['status'] ?? d['stage']) as String?)),
            if (widget.kind == BusinessKind.sales) ...[
              Text('Client : ${d['customer_name'] ?? 'Non associé'}'),
              Text(
                'Total TTC : ${amount((d['totals'] as Json)['total_ttc'] as String?)} TND',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                'Montant net après retours : ${amount(d['net_total_ttc'] as String?)} TND',
              ),
              ...lines.map(
                (l) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${l['name']} · ${l['sku']}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          '${l['quantity']} unités · ${amount(l['unit_price_ttc'] as String?)} TND TTC/unité\nTaxe ${amount(l['tax_rate'] as String?)} % · coût ${amount(l['unit_cost_ht'] as String?)} HT\nRetournées : ${l['returned']}',
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              if (write && d['status'] == 'DRAFT')
                ActionButton(
                  d['kind'] == 'QUOTE'
                      ? 'Convertir ce devis en vente'
                      : 'Confirmer la vente',
                  onPressed: () => mutate(
                    'Confirmer ${d['reference']}',
                    '/commerce/documents/$id/confirm',
                    'La vente confirmée déduira les quantités affichées du stock. Total ${amount((d['totals'] as Json)['total_ttc'] as String?)} TND TTC.',
                    [
                      if (d['kind'] == 'QUOTE')
                        const BusinessField(
                          'reference',
                          'Référence de la vente',
                        ),
                    ],
                    (v) async => {
                      'expected_version': d['version'],
                      'product_versions': await versions(lines),
                      if (d['kind'] == 'QUOTE')
                        'sale_reference': v['reference'],
                    },
                  ),
                ),
              const MessageCard(
                'Les retours et documents imprimables sont disponibles sur le web.',
              ),
            ],
            if (widget.kind == BusinessKind.purchases) ...[
              Text(
                'Fournisseur : ${d['supplier_name']}\nAttendu le ${d['expected_on']}',
              ),
              Text('Total : ${amount(d['total_ht'] as String?)} TND HT'),
              ...lines.map(
                (l) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${l['name']} · ${l['sku']}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          'Reçues ${l['received']} / ${l['quantity']} · ${amount(l['unit_cost_ht'] as String?)} TND HT/unité',
                        ),
                        if (write &&
                            [
                              'ORDERED',
                              'PART_RECEIVED',
                            ].contains(d['status']) &&
                            (l['received'] as int) < (l['quantity'] as int))
                          TextButton(
                            onPressed: () => mutate(
                              'Réceptionner ${l['sku']}',
                              '/purchases/orders/$id/receive',
                              'Seule la quantité réceptionnée augmentera le stock. Restant : ${(l['quantity'] as int) - (l['received'] as int)}.',
                              const [
                                BusinessField(
                                  'quantity',
                                  'Quantité reçue',
                                  integer: true,
                                ),
                                BusinessField('reason', 'Motif de réception'),
                              ],
                              (v) async {
                                final qty = int.parse(v['quantity']!);
                                if (qty < 1 ||
                                    qty >
                                        (l['quantity'] as int) -
                                            (l['received'] as int)) {
                                  throw ApiException(
                                    'Quantité supérieure au solde ou nulle.',
                                  );
                                }
                                final p = await widget.api.request(
                                  '/products/${l['product_id']}',
                                );
                                return {
                                  'expected_version': d['version'],
                                  'reason': v['reason'],
                                  'lines': [
                                    {
                                      'line_id': l['id'],
                                      'quantity': qty,
                                      'expected_product_version': p['version'],
                                    },
                                  ],
                                };
                              },
                            ),
                            child: const Text('Enregistrer une réception'),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
            ],
            if (widget.kind == BusinessKind.inventories) ...[
              ...lines.map(
                (l) => Card(
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${l['name']} · ${l['sku']}',
                          style: Theme.of(context).textTheme.titleMedium,
                        ),
                        Text(
                          'Stock actuel ${l['current_stock']} · compté ${l['counted'] ?? 'à saisir'}',
                        ),
                        if (write && d['status'] == 'OPEN')
                          TextButton(
                            onPressed: () => mutate(
                              'Compter ${l['sku']}',
                              '/inventories/$id/lines/${l['id']}/count',
                              'Le comptage est conservé sans modifier le stock.',
                              const [
                                BusinessField(
                                  'quantity',
                                  'Quantité comptée',
                                  integer: true,
                                ),
                                BusinessField('reason', 'Motif du comptage'),
                              ],
                              (v) async => {
                                'quantity': int.parse(v['quantity']!),
                                'reason': v['reason'],
                                'expected_version': l['version'],
                                'expected_product_version':
                                    l['current_product_version'],
                              },
                            ),
                            child: const Text('Saisir le comptage'),
                          ),
                      ],
                    ),
                  ),
                ),
              ),
              if (write && d['status'] == 'OPEN')
                ActionButton(
                  'Valider les écarts',
                  onPressed: lines.any((l) => l['counted'] == null)
                      ? null
                      : () => mutate(
                          'Valider cet inventaire',
                          '/inventories/$id/apply',
                          'Les écarts entre quantités comptées et stocks théoriques seront appliqués ensemble. Toute modification concurrente exige un recompte.',
                          const [
                            BusinessField('reason', 'Motif de validation'),
                          ],
                          (v) async => {
                            'expected_version': d['version'],
                            'reason': v['reason'],
                          },
                        ),
                ),
            ],
            if (widget.kind == BusinessKind.contacts) ...[
              Text(
                '${d['company']}\n${d['email']}\n${d['phone']}\n${d['address']}',
              ),
              if (write)
                ActionButton(
                  'Ajouter une note',
                  onPressed: () => mutate(
                    'Note de suivi',
                    '/crm/contacts/$id/notes',
                    'Note conservée dans l’historique ; aucun message envoyé.',
                    const [BusinessField('detail', 'Note de suivi')],
                    (v) async => {'detail': v['detail']},
                  ),
                ),
              ...((d['tasks'] as List?) ?? []).cast<Json>().map(
                (t) => Card(
                  child: ListTile(
                    title: Text(t['title'] as String),
                    subtitle: Text(
                      '${t['due_on']} · ${businessStatus(t['status'] as String)}',
                    ),
                    trailing: write && t['status'] == 'TODO'
                        ? IconButton(
                            tooltip: 'Terminer la tâche',
                            icon: const Icon(Icons.check_circle_outline),
                            onPressed: () => mutate(
                              'Terminer ${t['title']}',
                              '/crm/tasks/${t['id']}',
                              'Clôture de la tâche de suivi.',
                              const [],
                              (v) async => {
                                'expected_version': t['version'],
                                'status': 'DONE',
                              },
                              method: 'PATCH',
                            ),
                          )
                        : null,
                  ),
                ),
              ),
              ...((d['events'] as List?) ?? [])
                  .cast<Json>()
                  .take(30)
                  .map(
                    (e) => Text(
                      '${e['created_at']} · ${e['actor_name']}\n${e['detail']}',
                    ),
                  ),
            ],
          ],
        );
      },
    ),
  );
}
