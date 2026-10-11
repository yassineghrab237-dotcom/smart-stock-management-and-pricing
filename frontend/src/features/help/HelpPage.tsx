import { Button } from "../../ui";
export default function HelpPage({
  navigate,
}: {
  navigate: (page: string) => void;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">PREMIERS PAS</span>
          <h1>Commencer en 5 minutes</h1>
          <p>
            Votre boutique reçoit 20 câbles. Smart Stock vous aide à savoir
            combien il en reste.
          </p>
        </div>
        <Button onClick={() => navigate("products")}>
          Ouvrir les produits
        </Button>
      </div>
      <div className="help-grid">
        {[
          [
            "1",
            "Ouvrir votre espace",
            "Lancez le service sur votre ordinateur. Ouvrez l’application et utilisez Se connecter. La première fois, utilisez Créer mon espace pour créer l’administrateur.",
          ],
          [
            "2",
            "Créer un produit",
            "Dans Produits et stock, cliquez sur Ajouter un produit. Saisissez un nom et une Référence / SKU unique. Cliquez sur Créer le produit. Son stock commence à zéro.",
          ],
          [
            "3",
            "Ajouter du stock",
            "Ouvrez le produit. Cliquez sur Enregistrer un mouvement. Choisissez Entrée, saisissez 20 et un motif. Cliquez sur Vérifier le mouvement, puis Confirmer le mouvement. Attendez le message Mouvement enregistré.",
          ],
          [
            "4",
            "Suivre sur le téléphone",
            "Ouvrez l’application native Smart Stock installée avec le guide technique. Connectez-vous au même service et au même compte. Dans Produits, ouvrez le câble. Vous devez voir 20 unités. Tirez l’écran vers le bas ou utilisez Actualiser.",
          ],
          [
            "5",
            "Voir le résultat",
            "Historique sur mobile et Mouvements sur le web montrent les opérations confirmées. Alertes montre les stocks trop bas ou trop hauts. Pour estimer la demande, importez un historique puis utilisez Analyser les ventes.",
          ],
          [
            "?",
            "Si cela ne marche pas",
            "Connexion impossible : vérifiez que le PC et le service sont allumés. Stock insuffisant : corrigez la quantité. Données modifiées : actualisez, puis vérifiez de nouveau. Réponse perdue : consultez l’historique ou réessayez sans changer les valeurs. Ne créez pas une deuxième opération pour la même action.",
          ],
        ].map(([number, title, text]) => (
          <section className="panel padded" key={number}>
            <span className="help-step">{number}</span>
            <h2>{title}</h2>
            <p>{text}</p>
          </section>
        ))}
      </div>
      <p className="source-note">
        Les alertes mobiles se consultent dans l’application. Les notifications
        push et l’accès distant ne sont pas activés. Pour l’installation et la
        connexion, suivez le guide technique fourni avec le projet.
      </p>
    </>
  );
}
