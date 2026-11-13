import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { MealType, Recipe } from "../api/types";
import { MacroRow } from "../components/ui";
import { useToast } from "../components/Toast";
import { isoDate, MEAL_LABELS } from "../lib";

/** Tüm tarifler: arama, öğün filtresi, ayrıntı ve plana ekleme. */
export function RecipeBrowser({ recipes, onChanged }: { recipes: Recipe[]; onChanged: () => void }) {
  const toast = useToast();
  const [q, setQ] = useState("");
  const [meal, setMeal] = useState<MealType | "">("");
  const [open, setOpen] = useState<number | null>(null);
  const list = useMemo(() => {
    const term = q.trim().toLocaleLowerCase("tr");
    return recipes.filter((r) => (!meal || r.meal_type === meal) && (!term
      || r.name.toLocaleLowerCase("tr").includes(term)
      || r.ingredients.some((i) => i.ingredient.name.toLocaleLowerCase("tr").includes(term))));
  }, [recipes, q, meal]);

  const addToPlan = async (r: Recipe) => {
    try {
      await api.addPlan({ day: isoDate(new Date()), meal_type: r.meal_type === "snack" ? "snack" : r.meal_type, recipe_id: r.id, servings: r.servings });
      toast(`${r.name} bugünün planına eklendi`);
      onChanged();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <div className="page">
      <div className="toolbar">
        <input className="ob-search" placeholder={`${recipes.length} tarif içinde ara (ad veya malzeme)…`} value={q} onChange={(e) => setQ(e.target.value)} />
        <div className="seg">
          {(["", "breakfast", "lunch", "dinner", "snack"] as const).map((m) => (
            <button key={m} className={meal === m ? "on" : ""} onClick={() => setMeal(m)}>{m ? MEAL_LABELS[m] : "Tümü"}</button>
          ))}
        </div>
      </div>
      <p className="muted small">{list.length} tarif</p>
      <ul className="recipe-list">
        {list.map((r) => (
          <li key={r.id} className="card">
            <button className="recipe-row" onClick={() => setOpen(open === r.id ? null : r.id)}>
              <span>
                <b>{r.name}</b> {r.own && <span className="tag">✨ benim</span>}
                <small className="muted">{MEAL_LABELS[r.meal_type]} · {r.prep_minutes} dk · {Math.round(r.per_serving.kcal)} kcal/porsiyon</small>
              </span>
              <span>{open === r.id ? "▾" : "▸"}</span>
            </button>
            {open === r.id && (
              <div className="recipe-detail">
                <p>{r.description}</p>
                <MacroRow m={r.per_serving} />
                <ul>
                  {r.ingredients.map((l) => (
                    <li key={l.ingredient.id}>{l.ingredient.emoji} {l.ingredient.name} — {l.quantity_label}{l.optional && <em className="muted"> (isteğe bağlı)</em>}</li>
                  ))}
                </ul>
                <ol>{r.instructions.split("\n").filter(Boolean).map((s, i) => <li key={i}>{s}</li>)}</ol>
                <div className="card-actions"><button className="btn btn-primary btn-sm" onClick={() => addToPlan(r)}>📅 Bugüne ekle</button></div>
              </div>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
