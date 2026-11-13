import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { MealType, OptimizeResult, PlanEntry, Recipe, Strategy } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { addDays, CATEGORY_EMOJI, dayLabel, isoDate, MEAL_LABELS, STRATEGY_LABELS, tl } from "../lib";
import { Empty, ErrorBox, Section } from "../components/ui";
import { useToast } from "../components/Toast";

const MEAL_ORDER: MealType[] = ["breakfast", "lunch", "dinner", "snack"];

export function PlanPage({ recipes, onChanged }: { recipes: Recipe[]; onChanged: () => void }) {
  const toast = useToast();
  const start = isoDate(new Date());
  const end = isoDate(addDays(new Date(), 6));
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => isoDate(addDays(new Date(), i))), []);
  const { data, error, reload } = useAsync(() => api.plan(start, 7), [start]);
  const [optimized, setOptimized] = useState<OptimizeResult | null>(null);
  const [strategy, setStrategy] = useState<Strategy>("cheapest");
  const [busy, setBusy] = useState(false);
  const [nearbyOnly, setNearbyOnly] = useState(false);

  const byDay = useMemo(() => {
    const map = new Map<string, PlanEntry[]>();
    for (const e of data ?? []) map.set(e.day, [...(map.get(e.day) ?? []), e]);
    for (const list of map.values()) list.sort((a, b) => MEAL_ORDER.indexOf(a.meal_type) - MEAL_ORDER.indexOf(b.meal_type));
    return map;
  }, [data]);

  const refresh = () => { setOptimized(null); void reload(); onChanged(); };

  const runOptimize = async (addToList: boolean) => {
    setBusy(true);
    try {
      const res = await api.optimize({ plan_from: start, plan_to: end, strategy, add_to_list: addToList, nearby_only: nearbyOnly });
      setOptimized(res);
      if (addToList) { toast(`${res.added_to_list} ürün alışveriş listesine eklendi`); onChanged(); }
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  const cook = async (e: PlanEntry) => {
    try {
      const r = await api.cook(e.id);
      toast(r.shortages.length ? `Pişti; eksikler: ${r.shortages.join(", ")}` : `Afiyet olsun! Envanter güncellendi`);
      refresh();
    } catch (err) { toast((err as Error).message, "err"); }
  };

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Haftalık plan</h1>
        <p className="muted">Planla, eksikleri gör, en uygun marketten listeye ekle.</p>
      </div>

      <AddPlanForm recipes={recipes} days={days} onAdded={refresh} />
      {error && <ErrorBox message={error} onRetry={reload} />}

      <div className="week">
        {days.map((d) => (
          <div key={d} className="day">
            <div className="day-head">{dayLabel(d)}</div>
            {(byDay.get(d) ?? []).length === 0 && <div className="muted small day-empty">—</div>}
            {(byDay.get(d) ?? []).map((e) => (
              <div key={e.id} className={`plan-entry ${e.cooked ? "cooked" : ""}`}>
                <div>
                  <small className="muted">{MEAL_LABELS[e.meal_type]} · {e.servings} kişilik · {Math.round(e.kcal_per_serving)} kcal/porsiyon</small>
                  <div>{e.recipe_name}</div>
                </div>
                <div className="inv-actions">
                  {!e.cooked && <button className="icon-btn" title="Pişirdim (envanterden düş)" onClick={() => cook(e)}>🍳</button>}
                  <button className="icon-btn" title="Sil" onClick={async () => { await api.deletePlan(e.id); refresh(); }}>🗑️</button>
                </div>
              </div>
            ))}
          </div>
        ))}
      </div>

      <Section title="Eksikler & fiyat karşılaştırma">
        <div className="toolbar">
          <select value={strategy} onChange={(e) => { setStrategy(e.target.value as Strategy); setOptimized(null); }} aria-label="Strateji">
            {(Object.keys(STRATEGY_LABELS) as Strategy[]).map((s) => <option key={s} value={s}>{STRATEGY_LABELS[s]}</option>)}
          </select>
          <label className="check" title="Ev konumuna yakın şubesi olan zincirlerin gerçek fiyatlarını kullan">
            <input type="checkbox" checked={nearbyOnly} onChange={(e) => { setNearbyOnly(e.target.checked); setOptimized(null); }} />
            📍 Yalnız yakındakiler
          </label>
          <button className="btn btn-ghost" disabled={busy || !data?.length} onClick={() => runOptimize(false)}>Hesapla</button>
          <button className="btn btn-primary" disabled={busy || !data?.length} onClick={() => runOptimize(true)}>🛒 Listeye ekle</button>
        </div>
        {!data?.length && <Empty icon="📅">Önce plana tarif ekle.</Empty>}
        {optimized && <OptimizeView res={optimized} />}
      </Section>
    </div>
  );
}

function AddPlanForm({ recipes, days, onAdded }: { recipes: Recipe[]; days: string[]; onAdded: () => void }) {
  const toast = useToast();
  const [day, setDay] = useState(days[0]);
  const [meal, setMeal] = useState<MealType>("dinner");
  const [recipeId, setRecipeId] = useState<number | "">("");
  const [servings, setServings] = useState(2);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!recipeId) return;
    try {
      await api.addPlan({ day, meal_type: meal, recipe_id: recipeId, servings });
      setRecipeId("");
      onAdded();
    } catch (err) { toast((err as Error).message, "err"); }
  };

  return (
    <form className="card add-form plan-form" onSubmit={submit}>
      <select value={day} onChange={(e) => setDay(e.target.value)} aria-label="Gün">
        {days.map((d) => <option key={d} value={d}>{dayLabel(d)}</option>)}
      </select>
      <select value={meal} onChange={(e) => setMeal(e.target.value as MealType)} aria-label="Öğün">
        {MEAL_ORDER.map((m) => <option key={m} value={m}>{MEAL_LABELS[m]}</option>)}
      </select>
      <select value={recipeId} onChange={(e) => setRecipeId(Number(e.target.value) || "")} aria-label="Tarif" required>
        <option value="">Tarif seç…</option>
        {recipes.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
      </select>
      <input type="number" min={1} max={20} value={servings} onChange={(e) => setServings(Number(e.target.value))} aria-label="Porsiyon" />
      <button className="btn btn-primary" type="submit">Ekle</button>
    </form>
  );
}

function OptimizeView({ res }: { res: OptimizeResult }) {
  if (res.purchases.length === 0) return <p className="ok-line">✅ Plan için eksik malzeme yok.</p>;
  return (
    <div className="card optimize">
      <div className="opt-total">
        <span>Tahmini toplam</span>
        <b>{tl(res.total)}</b>
      </div>
      {res.savings_vs_worst_single_store != null && res.savings_vs_worst_single_store > 0 && (
        <p className="note note-ok">💸 En pahalı tek markete göre {tl(res.savings_vs_worst_single_store)} tasarruf</p>
      )}
      {res.unavailable.length > 0 && <p className="note">Seçili marketlerde bulunamadı: {res.unavailable.join(", ")}</p>}
      <ul className="opt-list">
        {res.purchases.map((p) => (
          <li key={p.ingredient_id}>
            <span>{p.emoji || CATEGORY_EMOJI[p.category]} {p.name} <small className="muted">eksik {p.missing_label}</small></span>
            <span className="muted small">
              {p.store_name ? `${p.packages}× ${p.package_label} · ${p.store_name}` : "bulunamadı"}
            </span>
            <b>{p.cost ? tl(p.cost) : "—"}</b>
          </li>
        ))}
      </ul>
      <div className="store-totals">
        {res.store_totals.map((s) => (
          <div key={s.store_id} className={`store-total ${s.store_id === res.chosen_store_id ? "chosen" : ""}`}>
            <b>{s.store_name}</b>
            <span>{tl(s.total)}</span>
            <small className="muted">{s.missing_items.length ? `${s.missing_items.length} ürün yok` : "hepsi var"}</small>
          </div>
        ))}
      </div>
    </div>
  );
}
