import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { Ingredient, InventoryItem, Location } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { Empty, ErrorBox, ExpiryBadge } from "../components/ui";
import { IngredientPicker } from "../components/IngredientPicker";
import { useToast } from "../components/Toast";

const LOCATIONS: { key: Location; label: string; icon: string }[] = [
  { key: "fridge", label: "Buzdolabı", icon: "🧊" },
  { key: "freezer", label: "Buzluk", icon: "❄️" },
];

export function InventoryPage({ ingredients, onChanged }: { ingredients: Ingredient[]; onChanged: () => void }) {
  const [location, setLocation] = useState<Location>("fridge");
  const { data, error, loading, reload } = useAsync(() => api.inventory(), []);
  const items = useMemo(() => (data ?? []).filter((i) => i.location === location), [data, location]);
  const counts = useMemo(() => ({
    fridge: (data ?? []).filter((i) => i.location === "fridge").length,
    freezer: (data ?? []).filter((i) => i.location === "freezer").length,
  }), [data]);

  const refresh = () => { void reload(); onChanged(); };

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Envanter</h1>
        <p className="muted">SKT girmezsen raf ömrü kurallarından tahmin edilir (~ işareti).</p>
      </div>

      <div className="seg seg-wide">
        {LOCATIONS.map((l) => (
          <button key={l.key} className={location === l.key ? "on" : ""} onClick={() => setLocation(l.key)}>
            {l.icon} {l.label} <span className="count">{counts[l.key]}</span>
          </button>
        ))}
      </div>

      <AddItemForm ingredients={ingredients} location={location} onAdded={refresh} />

      {error && <ErrorBox message={error} onRetry={reload} />}
      {loading && !data && <div className="skeleton-list"><div /><div /></div>}
      {data && items.length === 0 && (
        <Empty icon={location === "fridge" ? "🧊" : "❄️"}>Burada henüz ürün yok.</Empty>
      )}

      <ul className="inv-list">
        {items.map((item) => <InventoryRow key={item.id} item={item} onChanged={refresh} />)}
      </ul>
    </div>
  );
}

function AddItemForm({ ingredients, location, onAdded }: { ingredients: Ingredient[]; location: Location; onAdded: () => void }) {
  const toast = useToast();
  const [ingredient, setIngredient] = useState<Ingredient | null>(null);
  const [quantity, setQuantity] = useState("");
  const [unit, setUnit] = useState("");
  const [expiry, setExpiry] = useState("");
  const [opened, setOpened] = useState(false);

  const units = ingredient?.base_unit === "g" ? ["g", "kg"] : ingredient?.base_unit === "ml" ? ["ml", "l"] : ["adet"];
  const shelf = ingredient
    ? location === "freezer" ? ingredient.shelf_life_freezer_days : ingredient.shelf_life_fridge_days
    : null;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!ingredient || !quantity) return;
    try {
      const item = await api.addInventory({
        ingredient_id: ingredient.id,
        location,
        quantity: Number(quantity.replace(",", ".")),
        unit: unit || ingredient.base_unit,
        expiry_date: expiry || null,
        opened,
      });
      toast(`${item.ingredient.name} eklendi · SKT ${item.expiry_date}${item.expiry_estimated ? " (tahmini)" : ""}`);
      setIngredient(null); setQuantity(""); setUnit(""); setExpiry(""); setOpened(false);
      onAdded();
    } catch (err) {
      toast((err as Error).message, "err");
    }
  };

  return (
    <form className="card add-form" onSubmit={submit}>
      <IngredientPicker ingredients={ingredients} value={ingredient} onChange={(i) => { setIngredient(i); setUnit(""); }} />
      {ingredient && (
        <>
          <div className="row">
            <input inputMode="decimal" placeholder="Miktar" value={quantity} onChange={(e) => setQuantity(e.target.value)} required aria-label="Miktar" />
            <select value={unit || units[0]} onChange={(e) => setUnit(e.target.value)} aria-label="Birim">
              {units.map((u) => <option key={u}>{u}</option>)}
            </select>
          </div>
          <div className="row">
            <label className="field">
              <span>SKT (isteğe bağlı)</span>
              <input type="date" value={expiry} onChange={(e) => setExpiry(e.target.value)} />
            </label>
            <label className="check">
              <input type="checkbox" checked={opened} onChange={(e) => setOpened(e.target.checked)} /> Açılmış
            </label>
          </div>
          {!expiry && shelf && <p className="muted small">Tahmini raf ömrü: ~{shelf} gün</p>}
          <button className="btn btn-primary" type="submit">Ekle</button>
        </>
      )}
    </form>
  );
}

function InventoryRow({ item, onChanged }: { item: InventoryItem; onChanged: () => void }) {
  const toast = useToast();
  const run = async (fn: () => Promise<unknown>, msg?: string) => {
    try { await fn(); if (msg) toast(msg); onChanged(); } catch (e) { toast((e as Error).message, "err"); }
  };
  const step = item.ingredient.base_unit === "adet" ? 1 : item.ingredient.base_unit === "g" ? 100 : 100;
  const other: Location = item.location === "fridge" ? "freezer" : "fridge";

  return (
    <li className={`inv-row status-${item.status}`}>
      <span className="inv-emoji">{item.ingredient.emoji}</span>
      <div className="inv-main">
        <div className="inv-name">
          {item.ingredient.name}
          {item.opened && <span className="tag">açık</span>}
        </div>
        <div className="muted small">{item.quantity_label} · {item.expiry_date}</div>
      </div>
      <ExpiryBadge days={item.days_left} status={item.status} estimated={item.expiry_estimated} />
      <div className="inv-actions">
        <button className="icon-btn" title={`${step} ${item.ingredient.base_unit} kullan`}
          onClick={() => run(() => api.updateInventory(item.id, { quantity: Math.max(0, item.quantity - step) }))}>−</button>
        {!item.opened && item.location === "fridge" && (
          <button className="icon-btn" title="Açıldı olarak işaretle (raf ömrü kısalır)"
            onClick={() => run(() => api.updateInventory(item.id, { opened: true }), "Açıldı; SKT güncellendi")}>📂</button>
        )}
        <button className="icon-btn" title={other === "freezer" ? "Buzluğa taşı" : "Buzdolabına al (çözdür)"}
          onClick={() => run(() => api.updateInventory(item.id, { location: other }), other === "freezer" ? "Buzluğa taşındı" : "Buzdolabına alındı")}>
          {other === "freezer" ? "❄️" : "🧊"}
        </button>
        <button className="icon-btn" title="Sil" onClick={() => run(() => api.deleteInventory(item.id), "Silindi")}>🗑️</button>
      </div>
    </li>
  );
}
