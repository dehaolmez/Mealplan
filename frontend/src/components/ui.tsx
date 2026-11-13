import type { ReactNode } from "react";
import type { ExpiryStatus, Macros } from "../api/types";
import { expiryText } from "../lib";

export function ExpiryBadge({ days, status, estimated }: { days: number; status: ExpiryStatus; estimated?: boolean }) {
  return (
    <span className={`badge badge-${status}`} title={estimated ? "Raf ömrü kuralından tahmin edildi" : "Etiketteki SKT"}>
      {expiryText(days, status)}
      {estimated ? " ~" : ""}
    </span>
  );
}

export function MacroRow({ m }: { m: Macros }) {
  return (
    <div className="macros">
      <span><b>{Math.round(m.kcal)}</b> kcal</span>
      <span>P <b>{m.protein_g}</b>g</span>
      <span>K <b>{m.carbs_g}</b>g</span>
      <span>Y <b>{m.fat_g}</b>g</span>
    </div>
  );
}

export function Meter({ value, label }: { value: number; label: string }) {
  return (
    <div className="meter" title={`${label}: %${Math.round(value * 100)}`}>
      <span className="meter-label">{label}</span>
      <span className="meter-track">
        <span className="meter-fill" style={{ width: `${Math.round(value * 100)}%` }} />
      </span>
    </div>
  );
}

export function Empty({ icon, children }: { icon: string; children: ReactNode }) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon}</div>
      <div>{children}</div>
    </div>
  );
}

export function ErrorBox({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="error-box" role="alert">
      <span>⚠️ {message}</span>
      {onRetry && <button className="btn btn-ghost" onClick={onRetry}>Tekrar dene</button>}
    </div>
  );
}

export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="section">
      <header className="section-head">
        <h2>{title}</h2>
        {action}
      </header>
      {children}
    </section>
  );
}
