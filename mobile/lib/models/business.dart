import 'models.dart';

enum BusinessKind {
  market('Veille concurrentielle', '/products'),
  sales('Ventes et devis', '/commerce/documents'),
  purchases('Achats et réceptions', '/purchases/orders'),
  contacts('Clients et fournisseurs', '/crm/contacts'),
  inventories('Inventaires physiques', '/inventories'),
  insights('Rentabilité', '/insights/sales'),
  actions('Décisions à suivre', '/actions');

  final String title, path;
  const BusinessKind(this.title, this.path);
}

String businessStatus(String? value) => switch (value) {
  'DRAFT' => 'Brouillon',
  'CONFIRMED' => 'Confirmée',
  'CONVERTED' => 'Converti en vente',
  'CANCELLED' => 'Annulé',
  'ORDERED' => 'Commandée',
  'PART_RECEIVED' => 'Réception partielle',
  'RECEIVED' => 'Reçue',
  'CLOSED' => 'Clôturée',
  'OPEN' => 'En comptage',
  'APPLIED' => 'Appliqué',
  'TODO' => 'À traiter',
  'IN_PROGRESS' => 'En cours',
  'ACKNOWLEDGED' => 'Pris en compte',
  'DONE' => 'Terminée',
  'ACTIVE' => 'Actif',
  'PROSPECT' => 'Prospect',
  'INACTIVE' => 'Inactif',
  _ => value ?? '',
};

class BusinessEntry {
  final int id;
  final String title, subtitle, status;
  final Json data;
  BusinessEntry(this.id, this.title, this.subtitle, this.status, this.data);
  factory BusinessEntry.fromJson(BusinessKind kind, Json data) {
    final title =
        (data['reference'] ?? data['title'] ?? data['name'] ?? '') as String;
    final subtitle = switch (kind) {
      BusinessKind.market => data['sku'] as String,
      BusinessKind.sales =>
        '${data['kind'] == 'QUOTE' ? 'Devis' : 'Vente'} · ${data['customer_name'] ?? 'Client non associé'}',
      BusinessKind.purchases =>
        '${data['supplier_name']} · attendu le ${data['expected_on']}',
      BusinessKind.contacts =>
        '${data['company'] ?? ''} · ${data['phone'] ?? ''}',
      BusinessKind.inventories => '${data['line_count']} références',
      BusinessKind.actions => data['detail'] as String,
      BusinessKind.insights =>
        '${data['sku']} · ${data['net_units']} unités nettes',
    };
    return BusinessEntry(
      (data['id'] ?? 0) as int,
      title,
      subtitle,
      businessStatus((data['status'] ?? data['stage']) as String?),
      data,
    );
  }
}
