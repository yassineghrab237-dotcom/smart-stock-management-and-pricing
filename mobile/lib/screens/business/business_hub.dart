import 'package:flutter/material.dart';
import '../../models/business.dart';
import '../../services/api.dart';
import '../../widgets/common.dart';
import 'business_screen.dart';

class BusinessHub extends StatelessWidget {
  final StockApi api;
  const BusinessHub({super.key, required this.api});
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('Espace commercial')),
    body: PageBody(
      children: [
        Text(
          'Votre activité, sur le terrain',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const Text(
          'Consultez les ventes, suivez vos clients et enregistrez réceptions et comptages.',
        ),
        ...BusinessKind.values.map(
          (kind) => Card(
            child: ListTile(
              contentPadding: const EdgeInsets.all(18),
              leading: Icon(switch (kind) {
                BusinessKind.market => Icons.travel_explore,
                BusinessKind.sales => Icons.receipt_long,
                BusinessKind.purchases => Icons.local_shipping_outlined,
                BusinessKind.contacts => Icons.people_outline,
                BusinessKind.inventories => Icons.inventory_2_outlined,
                BusinessKind.insights => Icons.insights,
                BusinessKind.actions => Icons.task_alt,
              }),
              title: Text(kind.title),
              trailing: const Icon(Icons.chevron_right),
              onTap: () => Navigator.push(
                context,
                MaterialPageRoute(
                  builder: (_) => BusinessScreen(api: api, kind: kind),
                ),
              ),
            ),
          ),
        ),
      ],
    ),
  );
}
