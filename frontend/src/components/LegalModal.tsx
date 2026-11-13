import { useEffect, useState } from "react";
import { api } from "../api/client";
import { Markdown } from "./Markdown";

export const LEGAL_TITLES: Record<string, string> = {
  aydinlatma: "Aydınlatma Metni",
  "acik-riza": "Açık Rıza Metni",
  "kullanim-kosullari": "Kullanım Koşulları",
  cerez: "Çerez ve Yerel Depolama",
};

export function LegalModal({ slug, onClose }: { slug: string; onClose: () => void }) {
  const [text, setText] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    api.legal(slug).then(setText).catch((e) => setError((e as Error).message));
  }, [slug]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={LEGAL_TITLES[slug]} onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <b>{LEGAL_TITLES[slug]}</b>
          <button className="icon-btn" onClick={onClose} aria-label="Kapat">✕</button>
        </header>
        <div className="modal-body">
          {error && <p className="muted">{error}</p>}
          {!text && !error && <p className="muted">Yükleniyor…</p>}
          {text && <Markdown text={text} />}
        </div>
      </div>
    </div>
  );
}

export function LegalLink({ slug, onOpen, children }: { slug: string; onOpen: (s: string) => void; children?: React.ReactNode }) {
  return (
    <button type="button" className="link" onClick={() => onOpen(slug)}>{children ?? LEGAL_TITLES[slug]}</button>
  );
}
