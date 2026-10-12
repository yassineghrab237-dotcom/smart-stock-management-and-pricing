import 'market_product.dart';
import 'package:flutter/material.dart';
import '../../models/business.dart';
import '../../models/models.dart';
import '../../services/api.dart';
import '../../widgets/common.dart';
import 'business_detail.dart';
import 'business_mutation.dart';

class BusinessScreen extends StatefulWidget {
  final StockApi api;
  final BusinessKind kind;
  const BusinessScreen({super.key, required this.api, required this.kind});
  @override
  State<BusinessScreen> createState() => _BusinessScreenState();
}

class _BusinessScreenState extends State<BusinessScreen> {
  late Future<Json> data;
  String search = '';
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    data = widget.api.request(widget.kind.path);
  }

  Future<void> open(BusinessEntry entry) async {
    if (widget.kind == BusinessKind.insights) return;
    if (widget.kind == BusinessKind.market) {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => MarketProduct(api: widget.api, productId: entry.id),
        ),
      );
    } else if (widget.kind == BusinessKind.actions) {
      if (!widget.api.user!.canWrite) return;
      final decision = entry.data['decision'] as Json?;
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) => BusinessMutation(
            api: widget.api,
            title: 'Prendre en charge : ${entry.title}',
            path: '/actions/decisions',
            impact: 'La condition reste visible tant que sa cause persiste.',
            fields: const [BusinessField('reason', 'Motif de prise en charge')],
            prepare: (values) async => {
              'action_key': entry.data['key'],
              'expected_event_id': decision?['id'] ?? 0,
              'status': 'IN_PROGRESS',
              'reason': values['reason'],
            },
          ),
        ),
      );
    } else {
      await Navigator.push(
        context,
        MaterialPageRoute(
          builder: (_) =>
              BusinessDetail(api: widget.api, kind: widget.kind, id: entry.id),
        ),
      );
    }
    if (mounted) setState(load);
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
        final entries =
            ((d[widget.kind == BusinessKind.insights ? 'products' : 'items']
                        as List?) ??
                    [])
                .cast<Json>()
                .map((j) => BusinessEntry.fromJson(widget.kind, j))
                .where(
                  (e) => '${e.title} ${e.subtitle}'.toLowerCase().contains(
                    search.toLowerCase(),
                  ),
                )
                .toList();
        return PageBody(
          refresh: () async {
            setState(load);
            await data;
          },
          children: [
            if (widget.kind == BusinessKind.insights) ...[
              const MessageCard(
                'Ventes confirmées des 90 derniers jours, nettes des retours connus. Contribution HT hors frais externes. Coût absent = contribution totale inconnue.',
              ),
              Text(
                'Ventes : ${d['sales_count']}',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              Text(
                'CA net TTC : ${amount((d['totals'] as Json)['net_ttc'] as String?)} TND',
              ),
              Text(
                'Contribution HT : ${amount((d['totals'] as Json)['contribution_ht'] as String?)}',
              ),
            ],
            if (widget.kind == BusinessKind.sales)
              const MessageCard(
                'Préparez les ventes et devis sur le web. Ici, contrôlez les lignes et confirmez une vente ou un devis existant.',
              ),
            if (widget.kind == BusinessKind.inventories)
              const MessageCard(
                'Ouvrez une campagne sur le web. Le comptage n’ajuste pas le stock ; la validation applique les écarts.',
              ),
            TextField(
              decoration: const InputDecoration(
                labelText: 'Rechercher dans cette liste',
                prefixIcon: Icon(Icons.search),
              ),
              onChanged: (v) => setState(() => search = v),
            ),
            if (entries.isEmpty)
              const MessageCard('Aucun élément dans cette vue.'),
            ...entries.map(
              (e) => Card(
                child: ListTile(
                  contentPadding: const EdgeInsets.all(16),
                  title: Text(e.title),
                  subtitle: Text(
                    '${e.subtitle}\n${widget.kind == BusinessKind.insights ? 'Contribution HT : ${amount(e.data['contribution_ht'] as String?)} TND' : e.status}',
                  ),
                  trailing: widget.kind == BusinessKind.insights
                      ? null
                      : const Icon(Icons.chevron_right),
                  onTap: () => open(e),
                ),
              ),
            ),
          ],
        );
      },
    ),
  );
}
