import 'package:flutter/material.dart';
import '../models/models.dart';
import '../services/api.dart';
import '../widgets/common.dart';
import 'product_detail.dart';
import 'product_create.dart';

class Workspace extends StatefulWidget {
  final StockApi api;
  final VoidCallback onLogout;
  const Workspace({super.key, required this.api, required this.onLogout});
  @override
  State<Workspace> createState() => _WorkspaceState();
}

class _WorkspaceState extends State<Workspace> with WidgetsBindingObserver {
  int tab = 0;
  late Future<Json> data;
  String search = '', filter = 'all';
  String? message;
  bool busy = false;
  Json? pending;
  final titles = ['Accueil', 'Produits', 'Alertes', 'Historique', 'Plus'];
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    load();
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.resumed) setState(load);
  }

  void load() {
    data = widget.api.request(switch (tab) {
      0 => '/dashboard',
      1 => '/products',
      2 => '/alerts',
      3 => '/movements',
      _ => '/analysis/jobs',
    });
    widget.api
        .pending()
        .then((p) {
          if (mounted) setState(() => pending = p);
        })
        .catchError((Object e) {
          if (mounted) {
            setState(
              () => message = 'Le brouillon sécurisé est indisponible : $e',
            );
          }
        });
  }

  void navigate(int next) {
    setState(() {
      tab = next;
      load();
    });
  }

  Future<void> detail(int id) async {
    await Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => ProductDetailScreen(api: widget.api, id: id),
      ),
    );
    if (mounted) setState(load);
  }

  Future<void> create() async {
    final result = await Navigator.push<bool>(
      context,
      MaterialPageRoute(builder: (_) => ProductCreateScreen(api: widget.api)),
    );
    if (mounted) {
      setState(() {
        if (result == true) {
          message =
              'Produit créé. Ouvrez sa fiche pour enregistrer une entrée.';
        }
        load();
      });
    }
  }

  Future<void> logout() async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await widget.api.logout();
      if (mounted) widget.onLogout();
    } catch (e) {
      if (mounted) {
        setState(
          () =>
              message = '$e Votre session n’a pas été déconnectée. Réessayez.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> resume() async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Opération à vérifier'),
        content: Text(
          '${pending?['summary']}\n\nConsultez l’historique si nécessaire. Réessayer utilise exactement la même clé et les mêmes valeurs pour éviter un doublon.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Retour'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Réessayer sans changer'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    setState(() => busy = true);
    try {
      await widget.api.sendPending();
      if (mounted) {
        setState(() {
          pending = null;
          message = 'Opération confirmée par le service.';
          load();
        });
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => message =
              '$e Le brouillon est conservé. Un conflit impose de vérifier l’historique et les données actuelles avant de préparer une nouvelle opération.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> forget() async {
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Retirer le brouillon local ?'),
        content: const Text(
          'Cette action n’annule aucune opération sur le serveur. Vérifiez d’abord l’historique. Retirez ce brouillon seulement si vous avez contrôlé le résultat ou si le serveur a refusé l’opération.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Conserver'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Retirer ce brouillon'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    try {
      await widget.api.forgetPending();
      if (mounted) setState(() => pending = null);
    } catch (e) {
      if (mounted) setState(() => message = e.toString());
    }
  }

  Future<void> analyze() async {
    if (busy) return;
    final accepted = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Analyser les ventes importées ?'),
        content: const Text(
          'Le service évalue les prévisions sur des semaines passées. Aucun stock ni prix ne sera modifié. L’analyse peut rester indisponible si l’historique manque.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('Retour'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('Lancer l’analyse'),
          ),
        ],
      ),
    );
    if (accepted != true || !mounted) return;
    setState(() => busy = true);
    try {
      await widget.api.request('/analysis/jobs', method: 'POST', body: {});
      if (mounted) {
        setState(() {
          message =
              'Analyse prise en charge. Appuyez sur Actualiser pour suivre son état.';
          load();
        });
      }
    } catch (e) {
      if (mounted) {
        setState(
          () => message = '$e Consultez les traitements avant de relancer.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: Text(titles[tab]),
      actions: [
        IconButton(
          tooltip: 'Actualiser',
          onPressed: busy ? null : () => setState(load),
          icon: const Icon(Icons.refresh),
        ),
      ],
    ),
    bottomNavigationBar: NavigationBar(
      selectedIndex: tab,
      onDestinationSelected: busy ? null : navigate,
      destinations: const [
        NavigationDestination(
          icon: Icon(Icons.home_outlined),
          label: 'Accueil',
        ),
        NavigationDestination(
          icon: Icon(Icons.inventory_2_outlined),
          label: 'Produits',
        ),
        NavigationDestination(
          icon: Icon(Icons.notifications_outlined),
          label: 'Alertes',
        ),
        NavigationDestination(icon: Icon(Icons.history), label: 'Historique'),
        NavigationDestination(icon: Icon(Icons.more_horiz), label: 'Plus'),
      ],
    ),
    body: FutureBuilder<Json>(
      future: data,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const Center(child: CircularProgressIndicator());
        }
        final children = <Widget>[
          if (message != null) MessageCard(message!),
          if (pending != null) ...[
            MessageCard(
              'Une opération est à vérifier : ${pending!['summary']}',
            ),
            ActionButton(
              'Vérifier l’opération en attente',
              busy: busy,
              onPressed: resume,
            ),
            TextButton(
              onPressed: busy ? null : forget,
              child: const Text('Retirer le brouillon après vérification'),
            ),
          ],
          if (snapshot.hasError)
            MessageCard(
              snapshot.error.toString(),
              error: true,
              retry: () => setState(load),
            ),
          if (!snapshot.hasData && !snapshot.hasError)
            const Center(child: CircularProgressIndicator()),
        ];
        final d = snapshot.data;
        if (d != null && !snapshot.hasError) {
          if (tab == 0) {
            children.addAll([
              Text(
                'Bonjour ${widget.api.user!.name}',
                style: Theme.of(context).textTheme.headlineMedium,
              ),
              const Text(
                'Vos données viennent du même service que le web. Tirez l’écran vers le bas pour les actualiser.',
              ),
              Row(
                children: [
                  Expanded(
                    child: _stat(
                      'Produits',
                      '${d['product_count']}',
                      () => navigate(1),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _stat(
                      'Alertes',
                      '${(d['low_stock_count'] as int) + (d['overstock_count'] as int)}',
                      () => navigate(2),
                    ),
                  ),
                ],
              ),
              ActionButton(
                'Consulter les produits',
                onPressed: () => navigate(1),
              ),
              if (widget.api.user!.canWrite)
                OutlinedButton(
                  onPressed: create,
                  child: const Text('Ajouter un produit'),
                ),
              Text(
                'Dernières activités',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              ...(d['recent_movements'] as List).cast<Json>().map(_movement),
              if ((d['recent_movements'] as List).isEmpty)
                const MessageCard(
                  'Votre historique est vide. Créez un produit, puis ajoutez du stock avec une entrée.',
                ),
            ]);
          }
          if (tab == 1) {
            final products = (d['items'] as List)
                .cast<Json>()
                .map(Product.fromJson)
                .where(
                  (p) =>
                      '${p.name} ${p.sku}'.toLowerCase().contains(
                        search.toLowerCase(),
                      ) &&
                      (filter == 'all' || p.stock < p.minimum),
                )
                .toList();
            children.addAll([
              TextField(
                decoration: const InputDecoration(
                  labelText: 'Rechercher un produit',
                  prefixIcon: Icon(Icons.search),
                ),
                onChanged: (v) => setState(() => search = v),
              ),
              Wrap(
                spacing: 12,
                children: [
                  ChoiceChip(
                    label: const Text('Tous'),
                    selected: filter == 'all',
                    onSelected: (_) => setState(() => filter = 'all'),
                  ),
                  ChoiceChip(
                    label: const Text('Stock bas'),
                    selected: filter == 'low',
                    onSelected: (_) => setState(() => filter = 'low'),
                  ),
                ],
              ),
              if (widget.api.user!.canWrite)
                ActionButton('Ajouter un produit', onPressed: create),
              if (products.isEmpty)
                const MessageCard(
                  'Aucun produit dans cette vue. Modifiez la recherche ou ajoutez un produit.',
                ),
              ...products.map(
                (p) => Card(
                  child: ListTile(
                    minVerticalPadding: 16,
                    title: Text(p.name),
                    subtitle: Text(
                      '${p.sku}\n${p.stock} ${p.unit ?? 'unités'} · ${amount(p.price)}',
                    ),
                    isThreeLine: true,
                    trailing: const Icon(Icons.chevron_right),
                    onTap: () => detail(p.id),
                  ),
                ),
              ),
            ]);
          }
          if (tab == 2) {
            final alerts = (d['items'] as List).cast<Json>();
            children.addAll([
              const Text(
                'Les alertes évoluent avec les mouvements. Ouvrez un produit pour décider de l’action à faire.',
              ),
              if (alerts.isEmpty)
                const MessageCard(
                  'Aucune alerte. Tous les produits respectent leurs seuils.',
                ),
              ...alerts.map(
                (a) => Card(
                  child: ListTile(
                    leading: const Icon(
                      Icons.warning_amber,
                      color: Color(0xff995e00),
                    ),
                    title: Text(a['product_name'] as String),
                    subtitle: Text(
                      '${a['message']}\nStock : ${a['current_stock']} · Seuil : ${a['threshold']}',
                    ),
                    onTap: () => detail(a['product_id'] as int),
                  ),
                ),
              ),
            ]);
          }
          if (tab == 3) {
            final history = (d['items'] as List).cast<Json>();
            children.addAll([
              const Text(
                'Opérations enregistrées par le service. Les brouillons ne figurent pas dans cet historique.',
              ),
              if (history.isEmpty)
                const MessageCard('Aucun mouvement enregistré.'),
              ...history.take(100).map(_movement),
            ]);
          }
          if (tab == 4) {
            children.addAll([
              Text(
                'Analyses et paramètres',
                style: Theme.of(context).textTheme.headlineSmall,
              ),
              const Text(
                'L’IA calcule localement, sans tokens. Elle ne change jamais les prix ou le stock toute seule.',
              ),
              if (widget.api.user!.canWrite)
                ActionButton(
                  'Analyser les ventes',
                  busy: busy,
                  onPressed: analyze,
                ),
              ...(d['items'] as List).cast<Json>().map(
                (j) => Card(
                  child: ListTile(
                    title: Text(
                      'Analyse ${j['id']} · ${analysisStatus(j['status'] as String)}',
                    ),
                    subtitle: Text('${j['message']}\n${j['progress']} %'),
                    onTap: () => _showJob(j),
                  ),
                ),
              ),
              const MessageCard(
                'Pour importer un CSV, régler les seuils ou gérer les collaborateurs, utilisez le web. Les alertes sont consultables ici ; aucune notification push n’est activée.',
              ),
              Text(
                'Service : ${widget.api.endpoint}\nCompte : ${widget.api.user!.email}\nRôle : ${widget.api.user!.role}',
              ),
              OutlinedButton(
                onPressed: busy ? null : logout,
                child: const Text('Se déconnecter'),
              ),
            ]);
          }
        }
        return PageBody(
          refresh: () async {
            setState(load);
            await data;
          },
          children: children,
        );
      },
    ),
  );
  Widget _stat(String title, String value, VoidCallback tap) => Card(
    child: InkWell(
      onTap: tap,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              value,
              style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold),
            ),
            Text(title),
          ],
        ),
      ),
    ),
  );
  Widget _movement(Json m) => Card(
    child: ListTile(
      title: Text(
        '${m['product_name']} · ${movementType(m['type'] as String)}',
      ),
      subtitle: Text(
        '${m['stock_before']} → ${m['stock_after']} · ${m['reason']}\n${m['actor_name']} · ${m['created_at']}',
      ),
      onTap: () => detail(m['product_id'] as int),
    ),
  );
  void _showJob(Json j) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => Scaffold(
          appBar: AppBar(title: const Text('Résultat de l’analyse')),
          body: PageBody(
            children: [
              Text(j['message'] as String),
              if (j['stale'] == true)
                const MessageCard(
                  'Ces résultats sont anciens : les données ou la date ont changé. Relancez une analyse avant décision.',
                  error: true,
                ),
              ...((j['result'] as Json?)?['products'] as List? ?? [])
                  .cast<Json>()
                  .map(
                    (p) => Card(
                      child: Padding(
                        padding: const EdgeInsets.all(16),
                        child: Text(
                          '${p['name']} · ${p['sku']}\n${p['detail']}\n${p['prediction'] != null && j['stale'] != true ? 'Estimation : ${p['prediction']} unités · semaine ${p['target_week']}' : ''}',
                        ),
                      ),
                    ),
                  ),
            ],
          ),
        ),
      ),
    );
  }
}
