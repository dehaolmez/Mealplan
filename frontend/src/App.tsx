import { lazy, Suspense, useCallback, useEffect, useState } from "react";
import { api } from "./api/client";
import type { Alerts, Ingredient, Me, Recipe, Store } from "./api/types";
import { AlertBanner } from "./components/AlertBanner";
import { LegalLink, LegalModal } from "./components/LegalModal";
import { useToast } from "./components/Toast";
import { AuthPage } from "./features/AuthPage";
import { InventoryPage } from "./features/InventoryPage";
import { PlanPage } from "./features/PlanPage";
import { ProfilePage } from "./features/ProfilePage";
import { RecommendationsPage } from "./features/RecommendationsPage";
import { ShoppingPage } from "./features/ShoppingPage";

// Leaflet yalnız harita sekmesi açılınca yüklenir
const NearbyPage = lazy(() => import("./features/NearbyPage").then((m) => ({ default: m.NearbyPage })));

type Tab = "suggest" | "inventory" | "plan" | "shopping" | "nearby" | "profile";
const TABS: { key: Tab; label: string; icon: string }[] = [
  { key: "suggest", label: "Öneriler", icon: "🍳" },
  { key: "inventory", label: "Envanter", icon: "🧊" },
  { key: "plan", label: "Plan", icon: "📅" },
  { key: "shopping", label: "Liste", icon: "🛒" },
  { key: "nearby", label: "Yakında", icon: "📍" },
  { key: "profile", label: "Profil", icon: "👤" },
];

const hashParam = (name: string): string | null => {
  const m = new RegExp(`[#&]${name}=([^&]+)`).exec(window.location.hash);
  return m ? decodeURIComponent(m[1]) : null;
};

const tabFromHash = (): Tab => {
  const h = window.location.hash.replace("#", "") as Tab;
  return TABS.some((t) => t.key === h) ? h : "suggest";
};

export default function App() {
  const toast = useToast();
  const [me, setMe] = useState<Me | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [resetToken] = useState(() => hashParam("reset"));

  useEffect(() => {
    const verify = hashParam("verify");
    if (verify) {
      api.verifyEmail(verify)
        .then(() => toast("E-posta adresin doğrulandı ✓"))
        .catch((e) => toast((e as Error).message, "err"))
        .finally(() => history.replaceState(null, "", "#suggest"));
    }
    api.me().then(setMe).catch(() => setMe(null)).finally(() => setAuthChecked(true));
    const onUnauthorized = () => setMe(null);
    window.addEventListener("mealbird:unauthorized", onUnauthorized);
    return () => window.removeEventListener("mealbird:unauthorized", onUnauthorized);
  }, [toast]);

  if (!authChecked) return <div className="splash">🐦</div>;
  if (!me) return <AuthPage resetToken={resetToken} onAuthed={(m) => { setMe(m); history.replaceState(null, "", "#suggest"); }} />;
  if (me.needs_reconsent) return <ReconsentGate onAccepted={setMe} />;
  return <Shell me={me} setMe={setMe} />;
}

function ReconsentGate({ onAccepted }: { onAccepted: (m: Me) => void }) {
  const [legal, setLegal] = useState<string | null>(null);
  return (
    <div className="auth">
      <div className="auth-card card">
        <h2>Metinlerimiz güncellendi</h2>
        <p>Devam etmek için güncel <LegalLink slug="kullanim-kosullari" onOpen={setLegal} /> ve{" "}
          <LegalLink slug="aydinlatma" onOpen={setLegal} />'ni incelemeni rica ediyoruz.</p>
        <button className="btn btn-primary" onClick={async () => onAccepted(await api.acceptTerms())}>Okudum, kabul ediyorum</button>
        <button className="link" onClick={async () => { await api.logout(); location.reload(); }}>Çıkış yap</button>
      </div>
      {legal && <LegalModal slug={legal} onClose={() => setLegal(null)} />}
    </div>
  );
}

function Shell({ me, setMe }: { me: Me; setMe: (m: Me | null) => void }) {
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
      setOffline(!navigator.onLine);
    }
  }, []);

  useEffect(() => {
    Promise.all([api.ingredients(), api.recipes(), api.stores()])
      .then(([i, r, s]) => { setIngredients(i); setRecipes(r); setStores(s); })
      .catch(() => setOffline(true));
    void refreshMeta();
    const onHash = () => setTab(tabFromHash());
    const onOnline = () => { setOffline(false); void refreshMeta(); };
    const onOffline = () => setOffline(true);
    window.addEventListener("hashchange", onHash);
    window.addEventListener("online", onOnline);
    window.addEventListener("offline", onOffline);
    return () => {
      window.removeEventListener("hashchange", onHash);
      window.removeEventListener("online", onOnline);
      window.removeEventListener("offline", onOffline);
    };
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

      {offline && <div className="offline">Çevrimdışısın. Son açılan sayfalar görüntülenebilir; değişiklikler bağlantı gelince yapılabilir.</div>}
      {!me.email_verified && (
        <div className="note verify-note">
          📧 E-posta adresini doğrula.{" "}
          <button className="link" onClick={() => api.resendVerification().then(() => alert("Doğrulama e-postası gönderildi."))}>Tekrar gönder</button>
        </div>
      )}
      {tab !== "inventory" && <AlertBanner alerts={alerts} onOpen={() => go("inventory")} />}

      <main>
        {tab === "suggest" && <RecommendationsPage onChanged={refreshMeta} />}
        {tab === "inventory" && <InventoryPage ingredients={ingredients} onChanged={refreshMeta} />}
        {tab === "plan" && <PlanPage recipes={recipes} onChanged={refreshMeta} />}
        {tab === "shopping" && <ShoppingPage ingredients={ingredients} onChanged={refreshMeta} />}
        {tab === "nearby" && <Suspense fallback={<div className="skeleton-list"><div /></div>}><NearbyPage me={me} /></Suspense>}
        {tab === "profile" && <ProfilePage me={me} setMe={setMe} stores={stores} onChanged={refreshMeta} />}
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
