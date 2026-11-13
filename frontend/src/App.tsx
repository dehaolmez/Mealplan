import { useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import type { Alerts, Ingredient, Recipe, Store } from "./api/types";
import { AlertBanner } from "./components/AlertBanner";
import { InventoryPage } from "./features/InventoryPage";
import { PlanPage } from "./features/PlanPage";
import { ProfilePage } from "./features/ProfilePage";
import { RecommendationsPage } from "./features/RecommendationsPage";
import { ShoppingPage } from "./features/ShoppingPage";

type Tab = "suggest" | "inventory" | "plan" | "shopping" | "profile";
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "suggest", label: "Öneriler", icon: "🍳" },
  { key: "inventory", label: "Envanter", icon: "🧊" },
  { key: "plan", label: "Plan", icon: "📅" },
  { key: "shopping", label: "Liste", icon: "🛒" },
  { key: "profile", label: "Profil", icon: "👤" },
];

const tabFromHash = (): Tab => {
  const h = window.location.hash.replace("#", "") as Tab;
  return TABS.some((t) => t.key === h) ? h : "suggest";
};

export default function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [ingredients, setIngredients] = useState<Ingredient[]>([]);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [stores, setStores] = useState<Store[]>([]);
  const [alerts, setAlerts] = useState<Alerts | null>(null);
  const [shopCount, setShopCount] = useState(0);
  const [offline, setOffline] = useState(false);

  const refreshMeta = useCallback(async () => {
    try {
      const [a, s] = await Promise.all([api.alerts(), api.shopping()]);
      setAlerts(a);
      setShopCount(s.open_count);
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, []);

  useEffect(() => {
    Promise.all([api.ingredients(), api.recipes(), api.stores()])
      .then(([i, r, s]) => { setIngredients(i); setRecipes(r); setStores(s); })
      .catch(() => setOffline(true));
    void refreshMeta();
    const onHash = () => setTab(tabFromHash());
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [refreshMeta]);

  const go = (t: Tab) => { window.location.hash = t; setTab(t); };

  return (
    <div className="app">
      <header className="topbar">
        <span className="brand">🐦 Mealbird</span>
        {alerts && alerts.expired + alerts.critical > 0 && (
          <button className="pill pill-danger" onClick={() => go("inventory")}>⏳ {alerts.expired + alerts.critical}</button>
        )}
      </header>

      {offline && <div className="offline">Sunucuya ulaşılamıyor. Backend çalışıyor mu? (uvicorn app.main:app)</div>}
      {tab !== "inventory" && <AlertBanner alerts={alerts} onOpen={() => go("inventory")} />}

      <main>
        {tab === "suggest" && <RecommendationsPage onChanged={refreshMeta} />}
        {tab === "inventory" && <InventoryPage ingredients={ingredients} onChanged={refreshMeta} />}
        {tab === "plan" && <PlanPage recipes={recipes} onChanged={refreshMeta} />}
        {tab === "shopping" && <ShoppingPage ingredients={ingredients} onChanged={refreshMeta} />}
        {tab === "profile" && <ProfilePage stores={stores} onChanged={refreshMeta} />}
      </main>

      <nav className="tabbar">
        {TABS.map((t) => (
          <button key={t.key} className={tab === t.key ? "on" : ""} onClick={() => go(t.key)} aria-current={tab === t.key}>
            <span className="tab-icon">
              {t.icon}
              {t.key === "shopping" && shopCount > 0 && <span className="tab-badge">{shopCount}</span>}
            </span>
            <span>{t.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
}
