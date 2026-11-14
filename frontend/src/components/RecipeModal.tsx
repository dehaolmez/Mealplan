import { useState } from "react";
import { api } from "../api/client";
import type { Recipe } from "../api/types";
import { COURSE_LABELS, MEAL_LABELS, tl } from "../lib";
import { useToast } from "./Toast";
import { MacroRow } from "./ui";

const fmt = (v: number) => (v >= 10 ? Math.round(v).toString() : (Math.round(v * 10) / 10).toString().replace(".", ","));

function scaledLabel(qty: number, unit: string) {
  if (unit === "g" && qty >= 1000) return `${fmt(qty / 1000)} kg`;
  if (unit === "ml" && qty >= 1000) return `${fmt(qty / 1000)} l`;
  return `${fmt(qty)} ${unit}`;
}

/** Tarif ayrıntısı. `servings` verilirse malzemeler o porsiyona göre ölçeklenir (plandaki öğün için). */
export function RecipeModal({ recipe, servings, onClose, onChanged }: {
  recipe: Recipe; servings?: number; onClose: () => void; onChanged?: () => void;
}) {
  const toast = useToast();
  const [busy, setBusy] = useState(false);
  const n = servings ?? recipe.servings;
  const k = n / recipe.servings;

  const addMissing = async () => {
    setBusy(true);
    try {
      const res = await api.optimize({ selections: [{ recipe_id: recipe.id, servings: n }], strategy: "cheapest", add_to_list: true });
      toast(res.added_to_list ? `${res.added_to_list} eksik ürün listeye eklendi (~${tl(res.total)})` : "Eksik malzeme yok, hepsi evde ✅");
      onChanged?.();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" role="dialog" aria-modal="true" aria-label={recipe.name} onClick={(e) => e.stopPropagation()}>
        <header className="modal-head">
          <b>{recipe.name}</b>
          <button className="icon-btn" onClick={onClose} aria-label="Kapat">✕</button>
        </header>
        <div className="modal-body recipe-modal">
          <p className="muted small">
            {COURSE_LABELS[recipe.course] ?? MEAL_LABELS[recipe.meal_type]} · {recipe.prep_minutes} dk · {n} porsiyon
            {k !== 1 && <> (tarif {recipe.servings} kişilik, ×{fmt(k)} ölçeklendi)</>}
          </p>
          {recipe.description && <p>{recipe.description}</p>}
          <MacroRow m={recipe.per_serving} />
          <h3>Malzemeler</h3>
          <ul className="ing-list">
            {recipe.ingredients.map((l) => (
              <li key={l.ingredient.id}>
                <span>{l.ingredient.emoji} {l.ingredient.name}{l.optional && <em className="muted"> (isteğe bağlı)</em>}</span>
                <b>{scaledLabel(l.quantity * k, l.ingredient.base_unit)}</b>
              </li>
            ))}
          </ul>
          <h3>Yapılışı</h3>
          <ol className="steps">{recipe.instructions.split("\n").filter(Boolean).map((s, i) => <li key={i}>{s}</li>)}</ol>
        </div>
        <footer className="modal-foot">
          <button className="btn btn-ghost" onClick={onClose}>Kapat</button>
          <button className="btn btn-primary" disabled={busy} onClick={addMissing}>{busy ? "Bakılıyor…" : "🛒 Eksikleri listeye ekle"}</button>
        </footer>
      </div>
    </div>
  );
}
