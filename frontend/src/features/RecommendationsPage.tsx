import { useState } from "react";
import { api } from "../api/client";
import type { MealType, Recommendation } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { isoDate, MEAL_LABELS } from "../lib";
import { Empty, ErrorBox, MacroRow, Meter } from "../components/ui";
import { useToast } from "../components/Toast";

export function RecommendationsPage({ onChanged }: { onChanged: () => void }) {
  const [mealType, setMealType] = useState<MealType | "">("");
  const [ai, setAi] = useState(false);
  const { data, error, loading, reload } = useAsync(
    () => api.recommendations({ meal_type: mealType || undefined, limit: 8, ai }),
    [mealType, ai],
  );

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Buzdolabında ne var?</h1>
        <p className="muted">Evdeki ürünlerle — önce bozulmak üzere olanlarla — yapabileceğin tarifler.</p>
      </div>

      <div className="toolbar">
        <div className="seg" role="tablist">
          {(["", "breakfast", "lunch", "dinner"] as const).map((m) => (
            <button key={m} className={mealType === m ? "on" : ""} onClick={() => setMealType(m)}>
              {m ? MEAL_LABELS[m] : "Tümü"}
            </button>
          ))}
        </div>
        <label className="switch">
          <input type="checkbox" checked={ai} onChange={(e) => setAi(e.target.checked)} />
          <span>✨ Yapay zekâ</span>
        </label>
      </div>

      {data?.ai_requested && (
        <p className={`note ${data.ai_used ? "note-ok" : ""}`}>
          {data.ai_used ? "✨ Öneriler yapay zekâ ile sıralandı ve açıklandı." : `ℹ️ ${data.ai_error}`}
        </p>
      )}
      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <div className="skeleton-list"><div /><div /><div /></div>}
      {data && data.results.length === 0 && <Empty icon="🍽️">Uygun tarif bulunamadı.</Empty>}

      <div className={`cards ${loading ? "is-loading" : ""}`}>
        {data?.results.map((r) => (
          <RecipeCard key={r.recipe.id} rec={r} onChanged={() => { onChanged(); void reload(); }} />
        ))}
      </div>
    </div>
  );
}

function RecipeCard({ rec, onChanged }: { rec: Recommendation; onChanged: () => void }) {
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { recipe } = rec;

  const addToPlan = async () => {
    setBusy(true);
    try {
      const meal = recipe.meal_type === "snack" ? "dinner" : recipe.meal_type;
      await api.addPlan({ day: isoDate(new Date()), meal_type: meal, recipe_id: recipe.id, servings: rec.servings });
      toast(`${recipe.name} bugünün planına eklendi`);
      onChanged();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const addMissing = async () => {
    toast("Güncel fiyatlar alınıyor…");
    setBusy(true);
    try {
      const res = await api.optimize({
        selections: [{ recipe_id: recipe.id, servings: rec.servings }],
        strategy: "cheapest",
        add_to_list: true,
      });
      toast(`${res.added_to_list} eksik ürün listeye eklendi (~${res.total.toFixed(2)} ₺)`);
      onChanged();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <article className="card recipe-card">
      <header className="recipe-head">
        <div>
          <h3>{recipe.name}</h3>
          <p className="muted small">
            {MEAL_LABELS[recipe.meal_type]} · {recipe.prep_minutes} dk · {rec.servings} porsiyon
          </p>
        </div>
        <div className="score" title="Toplam uygunluk puanı">{Math.round(rec.score * 100)}</div>
      </header>

      {rec.ai_reason && <p className="ai-reason">✨ {rec.ai_reason}</p>}

      <div className="meters">
        <Meter value={rec.coverage} label="Evde var" />
        <Meter value={rec.urgency} label="İsraf önleme" />
        <Meter value={rec.nutrition_fit} label="Hedefe uyum" />
      </div>

      {rec.uses_expiring.length > 0 && (
        <div className="chips">
          {rec.uses_expiring.map((e) => (
            <span key={e.ingredient_name} className={`chip ${e.days_left <= 1 ? "chip-danger" : "chip-warn"}`}>
              ⏳ {e.ingredient_name} · {e.days_left === 0 ? "bugün" : `${e.days_left} gün`}
            </span>
          ))}
        </div>
      )}

      {rec.missing.length > 0 ? (
        <div className="missing">
          <span className="muted small">Eksik:</span>{" "}
          {rec.missing.map((m) => (
            <span key={m.ingredient.id} className="chip chip-missing">
              {m.ingredient.emoji} {m.ingredient.name} {m.missing_label}
            </span>
          ))}
        </div>
      ) : (
        <p className="ok-line">✅ Tüm malzemeler evde</p>
      )}

      <MacroRow m={recipe.per_serving} />

      {open && (
        <div className="recipe-detail">
          <p>{recipe.description}</p>
          <ul>
            {recipe.ingredients.map((l) => (
              <li key={l.ingredient.id}>
                {l.ingredient.emoji} {l.ingredient.name} — {l.quantity_label}
                {l.optional && <em className="muted"> (isteğe bağlı)</em>}
              </li>
            ))}
          </ul>
          <p>{recipe.instructions}</p>
        </div>
      )}

      <footer className="card-actions">
        <button className="btn btn-ghost" onClick={() => setOpen((o) => !o)}>{open ? "Kapat" : "Tarif"}</button>
        {rec.missing.length > 0 && (
          <button className="btn btn-ghost" disabled={busy} onClick={addMissing}>🛒 Eksikleri ekle</button>
        )}
        <button className="btn btn-primary" disabled={busy} onClick={addToPlan}>📅 Plana ekle</button>
      </footer>
    </article>
  );
}
