typedef Json = Map<String, dynamic>;

String analysisStatus(String status) => switch (status) {
  'QUEUED' => 'En attente',
  'RUNNING' => 'Calcul en cours',
  'SUCCEEDED' => 'Terminé',
  'FAILED' => 'Échec',
  'INTERRUPTED' => 'Interrompu',
  _ => status,
};

class User {
  final int id;
  final String name, email, role;
  User.fromJson(Json json)
    : id = json['id'] as int,
      name = json['name'] as String,
      email = json['email'] as String,
      role = json['role'] as String;
  bool get canWrite => role != 'VIEWER';
}

class Product {
  final int id, stock, version, minimum;
  final String name, sku;
  final String? price, minPrice, unit;
  Product.fromJson(Json json)
    : id = json['id'] as int,
      stock = json['current_stock'] as int,
      version = json['version'] as int,
      minimum = json['threshold_min'] as int,
      name = json['name'] as String,
      sku = json['sku'] as String,
      price = json['current_price'] as String?,
      minPrice = json['min_price'] as String?,
      unit = json['unit'] as String?;
}

// Affichage textuel : aucune conversion flottante des prix.
String amount(String? value) =>
    value == null ? 'Non renseigné' : value.replaceAll('.', ',');
String movementType(String type) => switch (type) {
  'IN' => 'Entrée',
  'OUT' => 'Sortie',
  _ => 'Ajustement',
};
