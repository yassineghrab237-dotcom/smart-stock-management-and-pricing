import { useCallback, useState } from "react";
import {
  Badge,
  Button,
  Empty,
  Modal,
  ResourceState,
  useResource,
} from "../../ui";
import { type Inventory, statuses } from "./types";
import InventoryForm from "./InventoryForm";
import InventoryWorkspace from "./InventoryWorkspace";
import "../commerce/commerce.css";
import "./inventories.css";
export default function InventoriesPage({
  write,
  refresh,
}: {
  write: boolean;
  refresh: () => void;
}) {
  const [revision, setRevision] = useState(0),
    [creating, setCreating] = useState(false),
    [selected, setSelected] = useState<number | null>(null);
  const resource = useResource<{ items: Inventory[] }>(
    "/inventories",
    revision,
  );
  const close = useCallback(() => setCreating(false), []);
  const changed = () => {
    setRevision((v) => v + 1);
    refresh();
  };
  return (
    <div className="commercial-page">
      <div className="page-heading">
        <div>
          <span className="eyebrow">COMPTAGE · ÉCARTS · TRAÇABILITÉ</span>
          <h1>Inventaires physiques</h1>
          <p>
            Comptez vos produits, contrôlez les écarts puis validez les
            ajustements ensemble.
          </p>
        </div>
        {write && (
          <Button onClick={() => setCreating(true)}>
            Nouvelle campagne d’inventaire
          </Button>
        )}
      </div>
      <ResourceState {...resource} />
      <div className="commercial-layout">
        <section
          className="commercial-list"
          aria-label="Campagnes d’inventaire"
        >
          {resource.data?.items.map((i) => (
            <button
              className={`commercial-document ${i.id === selected ? "selected" : ""}`}
              aria-pressed={i.id === selected}
              key={i.id}
              onClick={() => setSelected(i.id)}
            >
              <strong>{i.title}</strong>
              <Badge>{statuses[i.status]}</Badge>
              <span>{i.line_count} référence(s)</span>
            </button>
          ))}
          {resource.data?.items.length === 0 && (
            <Empty title="Aucune campagne">
              Préparez une première sélection de produits à compter.
            </Empty>
          )}
        </section>
        {selected ? (
          <InventoryWorkspace
            key={selected}
            id={selected}
            revision={revision}
            write={write}
            onSaved={changed}
          />
        ) : (
          <section className="commercial-panel">
            <Empty title="Sélectionnez une campagne">
              Aucun stock n’est modifié pendant le comptage. Un mouvement
              intervenu après un comptage imposera une nouvelle vérification.
            </Empty>
          </section>
        )}
      </div>
      {creating && (
        <Modal title="Ouvrir une campagne d’inventaire" onClose={close}>
          <InventoryForm
            onSaved={(id) => {
              setCreating(false);
              setSelected(id);
              changed();
            }}
          />
        </Modal>
      )}
    </div>
  );
}
