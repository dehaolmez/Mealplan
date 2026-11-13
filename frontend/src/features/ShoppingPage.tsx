import { useMemo, useState } from "react";
import { api } from "../api/client";
import type { Ingredient, ShoppingItem } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { CATEGORY_COLOR, CATEGORY_EMOJI, tl } from "../lib";
import { Empty, ErrorBox } from "../components/ui";
import { useToast } from "../components/Toast";

/** Bring! tarzı liste: reyonlara göre renkli kutucuklar; dokun = alındı, tekrar dokun = geri al. */
export function ShoppingPage({ ingredients, onChanged }: { ingredients: Ingredient[]; onChanged: () => void }) {
  const toast = useToast();
  const { data, error, reload, setData } = useAsync(() => api.shopping(), []);
  const [query, setQuery] = useState("");

  const refresh = () => { void reload(); onChanged(); };

  const suggestions = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    if (!q) return [];
    return ingredients.filter((i) => i.name.toLocaleLowerCase("tr").includes(q)).slice(0, 6);
  }, [ingredients, query]);

  const add = async (payload: { name?: string; ingredient_id?: number }) => {
    try {
      const item = await api.addShopping(payload);
      toast(`${item.emoji} ${item.name} listede`);
      setQuery("");
      refresh();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  const toggle = async (item: ShoppingItem) => {
    // İyimser güncelleme: kutucuk anında değişsin
    setData((d) => d && {
      ...d,
      categories: d.categories.map((c) => ({ ...c, items: c.items.map((i) => i.id === item.id ? { ...i, checked: !i.checked } : i) })),
    });
    try { await api.updateShopping(item.id, { checked: !item.checked }); } catch (e) { toast((e as Error).message, "err"); }
    refresh();
  };

  const open = data?.categories.map((c) => ({ ...c, items: c.items.filter((i) => !i.checked) })).filter((c) => c.items.length) ?? [];
  const inCart = data?.categories.flatMap((c) => c.items.filter((i) => i.checked)) ?? [];

  const checkout = async () => {
    try {
      const r = await api.checkout();
      toast(`${r.moved_to_inventory} ürün envantere eklendi`);
      refresh();
    } catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <div className="page">
      <div className="page-intro shop-intro">
        <h1>Alışveriş listesi</h1>
        {data && (
          <p className="muted">{data.open_count} ürün{data.estimated_total > 0 && ` · tahmini ${tl(data.estimated_total)}`}</p>
        )}
      </div>

      <form className="quick-add" onSubmit={(e) => {
        e.preventDefault();
        if (suggestions[0] && suggestions[0].name.toLocaleLowerCase("tr") === query.trim().toLocaleLowerCase("tr")) add({ ingredient_id: suggestions[0].id });
        else if (query.trim()) add({ name: query.trim() });
      }}>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Ne lazım? (ör. süt, peçete)" aria-label="Ürün ekle" />
        <button className="btn btn-primary" type="submit" disabled={!query.trim()}>Ekle</button>
      </form>
      {suggestions.length > 0 && (
        <div className="tiles tiles-suggest">
          {suggestions.map((i) => (
            <button key={i.id} className="tile tile-suggest" style={{ ["--tile" as string]: CATEGORY_COLOR[i.category] }} onClick={() => add({ ingredient_id: i.id })}>
              <span className="tile-emoji">{i.emoji}</span>
              <span className="tile-name">{i.name}</span>
            </button>
          ))}
        </div>
      )}

      {error && <ErrorBox message={error} onRetry={reload} />}
      {data && open.length === 0 && inCart.length === 0 && <Empty icon="🧺">Liste boş. Yukarıdan ekleyebilir veya plandan eksikleri aktarabilirsin.</Empty>}

      {open.map((c) => (
        <section key={c.category} className="shop-cat">
          <h2 className="cat-title">{CATEGORY_EMOJI[c.category]} {c.category}</h2>
          <div className="tiles">
            {c.items.map((i) => <Tile key={i.id} item={i} onTap={() => toggle(i)} onRemove={async () => { await api.deleteShopping(i.id); refresh(); }} />)}
          </div>
        </section>
      ))}

      {inCart.length > 0 && (
        <section className="shop-cat in-cart">
          <div className="section-head">
            <h2 className="cat-title">🧺 Sepette ({inCart.length})</h2>
            <button className="btn btn-primary btn-sm" onClick={checkout}>Envantere aktar</button>
          </div>
          <div className="tiles">
            {inCart.map((i) => <Tile key={i.id} item={i} onTap={() => toggle(i)} />)}
          </div>
        </section>
      )}

      {data && data.recently_bought.length > 0 && (
        <section className="shop-cat recent">
          <h2 className="cat-title">🕘 Son alınanlar</h2>
          <div className="tiles">
            {data.recently_bought.map((i) => (
              <button key={i.id} className="tile tile-recent" style={{ ["--tile" as string]: CATEGORY_COLOR[i.category] }}
                onClick={() => add(i.ingredient_id ? { ingredient_id: i.ingredient_id } : { name: i.name })}>
                <span className="tile-emoji">{i.emoji}</span>
                <span className="tile-name">{i.name}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function qtyLabel(i: ShoppingItem) {
  if (i.quantity == null) return "";
  if (i.unit === "g" && i.quantity >= 1000) return `${+(i.quantity / 1000).toFixed(2)} kg`;
  if (i.unit === "ml" && i.quantity >= 1000) return `${+(i.quantity / 1000).toFixed(2)} l`;
  return `${+i.quantity.toFixed(2)} ${i.unit ?? ""}`;
}

function Tile({ item, onTap, onRemove }: { item: ShoppingItem; onTap: () => void; onRemove?: () => void }) {
  return (
    <div className={`tile ${item.checked ? "tile-checked" : ""}`} style={{ ["--tile" as string]: CATEGORY_COLOR[item.category] }}>
      <button className="tile-hit" onClick={onTap} aria-pressed={item.checked} title={item.checked ? "Geri al" : "Alındı"}>
        <span className="tile-emoji">{item.emoji}</span>
        <span className="tile-name">{item.name}</span>
        <span className="tile-qty">{qtyLabel(item)}</span>
        {item.store_name && <span className="tile-store">{item.store_name}</span>}
      </button>
      {onRemove && <button className="tile-x" onClick={onRemove} aria-label={`${item.name} sil`}>✕</button>}
    </div>
  );
}
