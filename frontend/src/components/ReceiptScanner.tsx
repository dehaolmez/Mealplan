import { useRef, useState } from "react";
import { api } from "../api/client";
import type { Location, ReceiptDraft } from "../api/types";
import { useToast } from "./Toast";

/** Görseli tarayıcıda küçültür (en uzun kenar 1600 px, JPEG): hem hız hem gönderilen veri miktarı için. */
async function downscale(file: File): Promise<{ data: string; mime: string }> {
  const bitmap = await createImageBitmap(file).catch(() => null);
  if (!bitmap) {
    const buf = new Uint8Array(await file.arrayBuffer());
    let bin = "";
    buf.forEach((b) => (bin += String.fromCharCode(b)));
    return { data: btoa(bin), mime: file.type || "image/jpeg" };
  }
  const scale = Math.min(1, 1600 / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(bitmap.width * scale);
  canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext("2d")!.drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const url = canvas.toDataURL("image/jpeg", 0.82);
  return { data: url.split(",")[1], mime: "image/jpeg" };
}

export function ReceiptScanner({ onDone, enabled, reason }: { onDone: () => void; enabled: boolean; reason?: string }) {
  const toast = useToast();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<ReceiptDraft | null>(null);

  const pick = async (file: File) => {
    setBusy(true);
    try {
      const { data, mime } = await downscale(file);
      setDraft(await api.scanReceipt(data, mime));
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const update = (i: number, patch: Partial<ReceiptDraft["lines"][number]>) =>
    setDraft((d) => d && { ...d, lines: d.lines.map((l, j) => (j === i ? { ...l, ...patch } : l)) });

  const confirm = async () => {
    if (!draft) return;
    const lines = draft.lines.filter((l) => l.selected && l.ingredient_id && l.quantity);
    try {
      const r = await api.confirmReceipt(draft.date, lines.map((l) => ({
        ingredient_id: l.ingredient_id!, quantity: l.quantity!, unit: l.unit, location: l.location,
      })));
      toast(`${r.added} ürün envantere eklendi`);
      setDraft(null);
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    }
  };

  return (
    <>
      <button className="btn btn-ghost" disabled={busy || !enabled} title={enabled ? "" : reason}
        onClick={() => input.current?.click()}>
        {busy ? "⏳ Fiş okunuyor…" : "📷 Fiş tara"}
      </button>
      <input ref={input} type="file" accept="image/*" capture="environment" hidden
        onChange={(e) => { const f = e.target.files?.[0]; if (f) void pick(f); e.target.value = ""; }} />
      {!enabled && reason && <p className="muted small">{reason}</p>}

      {draft && (
        <div className="modal-backdrop" onClick={() => setDraft(null)}>
          <div className="modal" role="dialog" aria-modal="true" aria-label="Fiş" onClick={(e) => e.stopPropagation()}>
            <header className="modal-head">
              <b>🧾 {draft.chain?.name ?? draft.store_name ?? "Fiş"} {draft.date && <small className="muted">· {draft.date}</small>}</b>
              <button className="icon-btn" onClick={() => setDraft(null)} aria-label="Kapat">✕</button>
            </header>
            <div className="modal-body">
              <p className="muted small">Kontrol et, düzelt ve envantere ekle. Katalogda karşılığı olmayan satırlar eklenmez.</p>
              <ul className="receipt-lines">
                {draft.lines.map((l, i) => (
                  <li key={i} className={l.ingredient_id ? "" : "muted"}>
                    <input type="checkbox" checked={l.selected} disabled={!l.ingredient_id || !l.quantity}
                      onChange={(e) => update(i, { selected: e.target.checked })} aria-label="Ekle" />
                    <span className="receipt-name">
                      <b>{l.emoji} {l.ingredient_name ?? "—"}</b>
                      <small>{l.raw_text}{l.line_total != null && ` · ${l.line_total.toFixed(2)} ₺`}</small>
                    </span>
                    {l.ingredient_id && (
                      <>
                        <input className="receipt-qty" inputMode="decimal" value={l.quantity ?? ""} aria-label="Miktar"
                          onChange={(e) => update(i, { quantity: Number(e.target.value.replace(",", ".")) || null })} />
                        <span className="small">{l.unit}</span>
                        <select value={l.location} aria-label="Yer" onChange={(e) => update(i, { location: e.target.value as Location })}>
                          <option value="fridge">🧊</option>
                          <option value="freezer">❄️</option>
                        </select>
                      </>
                    )}
                  </li>
                ))}
              </ul>
            </div>
            <footer className="modal-foot">
              <button className="btn btn-ghost" onClick={() => setDraft(null)}>Vazgeç</button>
              <button className="btn btn-primary" onClick={confirm}
                disabled={!draft.lines.some((l) => l.selected && l.ingredient_id && l.quantity)}>
                Envantere ekle ({draft.lines.filter((l) => l.selected && l.ingredient_id && l.quantity).length})
              </button>
            </footer>
          </div>
        </div>
      )}
    </>
  );
}
