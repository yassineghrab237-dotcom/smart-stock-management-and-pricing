import {
  useEffect,
  useId,
  useState,
  type ReactNode,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
} from "react";
import { AlertCircle, PackageOpen, RefreshCw, X } from "lucide-react";
import { api, errorMessage } from "./api";
export function Button({
  variant = "primary",
  className = "",
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
}) {
  return <button className={`button ${variant} ${className}`} {...props} />;
}
export function Field({
  label,
  hint,
  id,
  "aria-describedby": describedBy,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string }) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const hintId = `${inputId}-hint`;
  const descriptions =
    [describedBy, hint ? hintId : undefined].filter(Boolean).join(" ") ||
    undefined;
  return (
    <div className="field">
      <label htmlFor={inputId}>{label}</label>
      <input {...props} id={inputId} aria-describedby={descriptions} />
      {hint && <small id={hintId}>{hint}</small>}
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "success" | "warning" | "danger";
}) {
  return <span className={`badge ${tone}`}>{children}</span>;
}
export function Notice({
  children,
  success = false,
}: {
  children: ReactNode;
  success?: boolean;
}) {
  return (
    <div
      className={`notice ${success ? "success" : ""}`}
      role={success ? "status" : "alert"}
    >
      <AlertCircle size={18} />
      <div>{children}</div>
    </div>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <PackageOpen size={34} />
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <RefreshCw size={20} /> Chargement des données…
    </div>
  );
}
export function Modal({
  title,
  children,
  onClose,
}: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const dialog = document.querySelector<HTMLElement>('[role="dialog"]');
    dialog?.querySelector<HTMLElement>("input,button,select")?.focus();
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "Tab" && dialog) {
        const els = Array.from(
          dialog.querySelectorAll<HTMLElement>(
            'button:not(:disabled),input,select,textarea,[tabindex="0"]',
          ),
        );
        const first = els[0],
          last = els.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };
    document.addEventListener("keydown", handler);
    const old = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", handler);
      document.body.style.overflow = old;
      previous?.focus();
    };
  }, [onClose]);
  return (
    <div className="overlay">
      <section
        className="modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dialog-title"
      >
        <header>
          <h2 id="dialog-title">{title}</h2>
          <Button variant="ghost" aria-label="Fermer" onClick={onClose}>
            <X size={20} />
          </Button>
        </header>
        {children}
      </section>
    </div>
  );
}
export function useResource<T>(path: string, revision = 0) {
  const [record, setRecord] = useState<{ path: string; data: T } | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    api<T>(path)
      .then((d) => {
        if (active) setRecord({ path, data: d });
      })
      .catch((e) => {
        if (active) setError(errorMessage(e));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, revision, retry]);
  const data = record?.path === path ? record.data : null;
  return { data, error, loading, reload: () => setRetry((v) => v + 1) };
}
export function ResourceState({
  loading,
  error,
  reload,
}: {
  loading: boolean;
  error: string;
  reload: () => void;
}) {
  return loading ? (
    <Loading />
  ) : error ? (
    <Notice>
      {error}{" "}
      <Button variant="secondary" onClick={reload}>
        Réessayer
      </Button>
    </Notice>
  ) : null;
}
