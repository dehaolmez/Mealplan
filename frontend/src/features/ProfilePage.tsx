import { useState } from "react";
import { api } from "../api/client";
import type { Activity, Chain, ChainKind, ConsentKind, Goal, Me, Member, MemberIn, PriceImportResult, Sex, Store } from "../api/types";
import { LegalLink, LegalModal } from "../components/LegalModal";
import { useAsync } from "../hooks/useAsync";
import { ACTIVITY_LABELS, GOAL_LABELS, KIND_LABELS } from "../lib";
import { ErrorBox, Section } from "../components/ui";
import { useToast } from "../components/Toast";

const EMPTY: MemberIn = {
  name: "", birth_date: "1990-01-01", sex: "female", height_cm: 165, weight_kg: 65, activity_level: "light", goal: "maintain",
};

export function ProfilePage({ me, setMe, stores, onChanged, onEditPreferences }: {
  me: Me; setMe: (m: Me | null) => void; stores: Store[]; onChanged: () => void; onEditPreferences: () => void;
}) {
  const toast = useToast();
  const healthOk = me.consents.find((c) => c.kind === "health_data")?.granted ?? false;
  const targets = useAsync(() => api.targets(), []);
  const household = useAsync(() => api.household(), []);
  const [editing, setEditing] = useState<Member | "new" | null>(null);

  const t = targets.data;

  const saveStores = async (selected: number[], preferred: number | null) => {
    try {
      await api.updateHousehold({ selected_store_ids: selected, preferred_store_id: preferred });
      void household.reload();
      toast("Market tercihleri kaydedildi");
    } catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <div className="page">
      <div className="page-intro">
        <h1>Hane & beslenme</h1>
        <p className="muted">Günlük ihtiyaçlar Mifflin-St Jeor formülüyle hesaplanır.</p>
      </div>
      {targets.error && <ErrorBox message={targets.error} onRetry={targets.reload} />}

      <button className="card pref-entry" onClick={onEditPreferences}>
        <span className="ob-icon">⚙️</span>
        <span><b>Planlama tercihleri</b><small className="muted">Marketler, öğünler, diyet, alerjiler, aletler, günler, bütçe, tekrar</small></span>
        <span>›</span>
      </button>

      {t?.total && (
        <div className="card total-card">
          <div className="total-kcal"><b>{Math.round(t.total.calories)}</b><span>kcal / gün (hane)</span></div>
          <div className="total-macros">
            <span>Protein <b>{t.total.protein_g} g</b></span>
            <span>Karbonhidrat <b>{t.total.carbs_g} g</b></span>
            <span>Yağ <b>{t.total.fat_g} g</b></span>
          </div>
          {t.meal_kcal_target && <p className="muted small">Kişi başı öğün hedefi ≈ {t.meal_kcal_target} kcal (tarif puanlamasında kullanılır)</p>}
        </div>
      )}

      <Section title="Bireyler" action={healthOk && <button className="btn btn-primary btn-sm" onClick={() => setEditing("new")}>+ Kişi</button>}>
        {!healthOk && (
          <p className="note">Kalori hesabı için boy/kilo gibi sağlık verileri gerekir. Aşağıdaki <b>Gizlilik</b> bölümünden
            sağlık verisi iznini açarsan bireyleri ekleyebilirsin.</p>
        )}
        {editing && (
          <MemberForm
            initial={editing === "new" ? EMPTY : editing}
            onCancel={() => setEditing(null)}
            onSave={async (m) => {
              try {
                if (editing === "new") await api.addMember(m); else await api.updateMember(editing.id, m);
                setEditing(null);
                void targets.reload();
                onChanged();
              } catch (e) { toast((e as Error).message, "err"); }
            }}
          />
        )}
        <div className="members">
          {t?.members.map((m) => (
            <div key={m.id} className="card member">
              <header>
                <b>{m.name}</b>
                <span className="muted small">{m.age} yaş · {m.height_cm} cm · {m.weight_kg} kg</span>
              </header>
              <div className="member-kcal"><b>{Math.round(m.targets.calories)}</b> kcal</div>
              <div className="muted small">
                BMR {Math.round(m.targets.bmr)} · TDEE {Math.round(m.targets.tdee)} · {GOAL_LABELS[m.goal]}
              </div>
              <div className="macros">
                <span>P <b>{m.targets.protein_g}</b>g</span>
                <span>K <b>{m.targets.carbs_g}</b>g</span>
                <span>Y <b>{m.targets.fat_g}</b>g</span>
              </div>
              {m.targets.warnings.map((w) => <p key={w} className="note small">{w}</p>)}
              <footer className="card-actions">
                <button className="btn btn-ghost btn-sm" onClick={() => setEditing(m)}>Düzenle</button>
                <button className="btn btn-ghost btn-sm" onClick={async () => { await api.deleteMember(m.id); void targets.reload(); onChanged(); }}>Sil</button>
              </footer>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Marketler">
        {household.data && (
          <StorePrefs stores={stores} selected={household.data.selected_store_ids} preferred={household.data.preferred_store_id} onSave={saveStores} />
        )}
        <p className="muted small">"Demo" etiketli marketlerin fiyatları örnek veridir. Gerçek fiyatları aşağıdan CSV ile yükleyebilirsin.</p>
      </Section>

      <PriceImport onDone={onChanged} />
      {me.is_admin && <AdminPanel />}
      <ChainList />
      <AccountSection me={me} setMe={(m) => { setMe(m); void targets.reload(); void household.reload(); onChanged(); }} />
    </div>
  );
}

export function MemberForm({ initial, onSave, onCancel }: { initial: MemberIn; onSave: (m: MemberIn) => void; onCancel: () => void }) {
  const [m, setM] = useState<MemberIn>({
    name: initial.name, birth_date: initial.birth_date, sex: initial.sex, height_cm: initial.height_cm,
    weight_kg: initial.weight_kg, activity_level: initial.activity_level, goal: initial.goal,
  });
  const set = <K extends keyof MemberIn>(k: K, v: MemberIn[K]) => setM((x) => ({ ...x, [k]: v }));
  return (
    <form className="card form-grid" onSubmit={(e) => { e.preventDefault(); onSave(m); }}>
      <label className="field"><span>Ad</span><input value={m.name} onChange={(e) => set("name", e.target.value)} required /></label>
      <label className="field"><span>Doğum tarihi</span><input type="date" value={m.birth_date} onChange={(e) => set("birth_date", e.target.value)} required /></label>
      <label className="field"><span>Cinsiyet</span>
        <select value={m.sex} onChange={(e) => set("sex", e.target.value as Sex)}>
          <option value="female">Kadın</option><option value="male">Erkek</option>
        </select>
      </label>
      <label className="field"><span>Boy (cm)</span><input type="number" min={60} max={250} value={m.height_cm} onChange={(e) => set("height_cm", Number(e.target.value))} /></label>
      <label className="field"><span>Kilo (kg)</span><input type="number" min={15} max={300} step="0.1" value={m.weight_kg} onChange={(e) => set("weight_kg", Number(e.target.value))} /></label>
      <label className="field"><span>Aktivite</span>
        <select value={m.activity_level} onChange={(e) => set("activity_level", e.target.value as Activity)}>
          {(Object.keys(ACTIVITY_LABELS) as Activity[]).map((a) => <option key={a} value={a}>{ACTIVITY_LABELS[a]}</option>)}
        </select>
      </label>
      <label className="field"><span>Hedef</span>
        <select value={m.goal} onChange={(e) => set("goal", e.target.value as Goal)}>
          {(Object.keys(GOAL_LABELS) as Goal[]).map((g) => <option key={g} value={g}>{GOAL_LABELS[g]}</option>)}
        </select>
      </label>
      <div className="card-actions">
        <button type="button" className="btn btn-ghost" onClick={onCancel}>Vazgeç</button>
        <button type="submit" className="btn btn-primary">Kaydet</button>
      </div>
    </form>
  );
}

function StorePrefs({ stores, selected, preferred, onSave }: {
  stores: Store[]; selected: number[]; preferred: number | null; onSave: (s: number[], p: number | null) => void;
}) {
  return (
    <div className="stores">
      {stores.map((s) => {
        const on = selected.includes(s.id);
        return (
          <div key={s.id} className={`store-pill ${on ? "on" : ""}`} style={{ ["--store" as string]: s.color }}>
            <label>
              <input type="checkbox" checked={on}
                onChange={() => onSave(on ? selected.filter((x) => x !== s.id) : [...selected, s.id], preferred)} />
              {s.name}{s.is_demo && <small className="muted"> {s.chain_id ? "test" : "demo"}</small>}
            </label>
            <button className={`star ${preferred === s.id ? "on" : ""}`} title="Tercih edilen market"
              onClick={() => onSave(on ? selected : [...selected, s.id], preferred === s.id ? null : s.id)}>★</button>
          </div>
        );
      })}
    </div>
  );
}

function PriceImport({ onDone }: { onDone: () => void }) {
  const toast = useToast();
  const [result, setResult] = useState<PriceImportResult | null>(null);
  const [busy, setBusy] = useState(false);

  const onFile = async (file: File) => {
    setBusy(true);
    try {
      const buf = await file.arrayBuffer();
      let text = new TextDecoder("utf-8", { fatal: false }).decode(buf);
      if (text.includes("\uFFFD")) text = new TextDecoder("windows-1254").decode(buf); // Excel Türkçe kodlaması
      const r = await api.importPrices(text);
      setResult(r);
      toast(`${r.created} yeni, ${r.updated} güncellenen fiyat`);
      onDone();
    } catch (e) { toast((e as Error).message, "err"); } finally { setBusy(false); }
  };

  return (
    <Section title="Gerçek fiyatları yükle (CSV)">
      <div className="card add-form">
        <p className="muted small">
          Sütunlar: <code>chain, ingredient, package_size, unit, price, brand, date</code>.{" "}
          <a href={api.priceTemplateUrl} download="meall-fiyat-sablonu.csv">Şablonu indir</a>
        </p>
        <input type="file" accept=".csv,text/csv" disabled={busy}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) void onFile(f); e.target.value = ""; }} />
        {result && (
          <div className="small">
            <p>✅ {result.created} yeni · {result.updated} güncellendi{result.stores_created.length > 0 && ` · yeni market: ${result.stores_created.join(", ")}`}</p>
            {result.errors.length > 0 && (
              <ul className="import-errors">
                {result.errors.slice(0, 10).map((e) => <li key={e.line}>Satır {e.line}: {e.error}</li>)}
                {result.errors.length > 10 && <li>… ve {result.errors.length - 10} hata daha</li>}
              </ul>
            )}
          </div>
        )}
      </div>
    </Section>
  );
}

function ChainList() {
  const { data } = useAsync(() => api.chains(), []);
  if (!data) return null;
  const groups = new Map<ChainKind, Chain[]>();
  for (const c of data) groups.set(c.kind, [...(groups.get(c.kind) ?? []), c]);
  return (
    <Section title="Türkiye'deki büyük market zincirleri">
      <div className="chain-groups">
        {(Object.keys(KIND_LABELS) as ChainKind[]).filter((k) => groups.has(k)).map((kind) => [kind, groups.get(kind)!] as const).map(([kind, chains]) => (
          <div key={kind}>
            <h3 className="cat-title">{KIND_LABELS[kind]}</h3>
            <div className="chips">
              {chains.map((c) => (
                <span key={c.id} className="chip chain-tag" style={{ ["--chain" as string]: c.color }}
                  title={`${c.parent}${c.in_market_fiyati ? " · TÜBİTAK Market Fiyatı platformunda" : ""}`}>
                  {c.name}{c.price_source === "real" ? " 💰" : c.price_source === "test" ? " 🧪" : ""}{c.in_market_fiyati ? " ✓" : ""}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="muted small">✓ TÜBİTAK "Market Fiyatı" platformunda fiyatları yayımlanan zincir · 💰 gerçek fiyat verisi var · 🧪 yalnız test fiyatı var</p>
    </Section>
  );
}

const CONSENT_LABELS: { kind: ConsentKind; title: string; desc: string }[] = [
  { kind: "health_data", title: "Sağlık verisi", desc: "Boy, kilo, hedef → kalori hesabı. Kapatınca bireyler silinir." },
  { kind: "location", title: "Ev konumu", desc: "~11 m hassasiyetle saklanır. Kapatınca konum silinir." },
  { kind: "ai_transfer", title: "Yapay zekâ (Gemini)", desc: "Fiş fotoğrafı ve envanter ürün adları Google'a (yurt dışı) gönderilir; kimlik gönderilmez." },
  { kind: "marketing", title: "Ticari ileti", desc: "Kampanya/yenilik e-postaları." },
];

function AccountSection({ me, setMe }: { me: Me; setMe: (m: Me | null) => void }) {
  const toast = useToast();
  const [legal, setLegal] = useState<string | null>(null);
  const [joinCode, setJoinCode] = useState("");
  const [pw, setPw] = useState({ current: "", next: "" });
  const granted = (k: ConsentKind) => me.consents.find((c) => c.kind === k)?.granted ?? false;

  const toggle = async (kind: ConsentKind, value: boolean) => {
    if (!value && kind === "health_data" && !confirm("Sağlık verisi izni kapatılırsa tüm bireylerin bilgileri silinir. Emin misin?")) return;
    try { setMe(await api.setConsent(kind, value)); toast(value ? "İzin verildi" : "İzin geri çekildi"); }
    catch (e) { toast((e as Error).message, "err"); }
  };

  return (
    <>
      <Section title="Hane paylaşımı">
        <div className="card add-form">
          <p className="small"><b>{me.household_name}</b> · {me.role === "owner" ? "Sahibi sensin" : "Üyesin"}</p>
          {me.invite_code && (
            <div className="row">
              <span>Davet kodu: <code className="invite">{me.invite_code}</code></span>
              <button className="btn btn-ghost btn-sm" onClick={() => navigator.clipboard?.writeText(me.invite_code!).then(() => toast("Kopyalandı"))}>Kopyala</button>
              <button className="btn btn-ghost btn-sm" onClick={async () => setMe(await api.rotateInvite())}>Yenile</button>
            </div>
          )}
          <p className="muted small">Aile üyelerin kayıt olurken bu kodu girerse aynı envanteri ve listeyi paylaşırsınız.</p>
          <form className="row" onSubmit={async (e) => {
            e.preventDefault();
            if (!confirm("Başka bir haneye katılırsan mevcut hanenden ayrılırsın. Devam?")) return;
            try { setMe(await api.joinHousehold(joinCode)); setJoinCode(""); toast("Haneye katıldın"); }
            catch (err) { toast((err as Error).message, "err"); }
          }}>
            <input placeholder="Başka bir hanenin davet kodu" value={joinCode} onChange={(e) => setJoinCode(e.target.value.toUpperCase())} />
            <button className="btn btn-ghost" disabled={joinCode.length < 6}>Katıl</button>
          </form>
        </div>
      </Section>

      <Section title="Gizlilik ve izinler (KVKK)">
        <div className="card consent-list">
          {CONSENT_LABELS.map((c) => (
            <label key={c.kind} className="consent-row">
              <span><b>{c.title}</b><small className="muted">{c.desc}</small></span>
              <input type="checkbox" role="switch" checked={granted(c.kind)} onChange={(e) => toggle(c.kind, e.target.checked)} />
            </label>
          ))}
          <p className="muted small">
            <LegalLink slug="aydinlatma" onOpen={setLegal} /> · <LegalLink slug="acik-riza" onOpen={setLegal} /> ·{" "}
            <LegalLink slug="kullanim-kosullari" onOpen={setLegal} /> · <LegalLink slug="cerez" onOpen={setLegal}>Çerezler</LegalLink>
          </p>
        </div>
      </Section>

      <Section title="Hesap">
        <div className="card add-form">
          <p className="small">{me.email} {me.email_verified ? "✓" : "(doğrulanmadı)"} {me.google_linked && "· Google bağlı"}</p>
          <form className="row" onSubmit={async (e) => {
            e.preventDefault();
            try { await api.changePassword(me.has_password ? pw.current : null, pw.next); setPw({ current: "", next: "" }); toast("Şifre güncellendi; diğer cihazlardan çıkış yapıldı"); setMe(await api.me()); }
            catch (err) { toast((err as Error).message, "err"); }
          }}>
            {me.has_password && <input type="password" autoComplete="current-password" placeholder="Mevcut şifre" value={pw.current} onChange={(e) => setPw({ ...pw, current: e.target.value })} />}
            <input type="password" autoComplete="new-password" minLength={8} placeholder={me.has_password ? "Yeni şifre" : "Şifre belirle"} value={pw.next} onChange={(e) => setPw({ ...pw, next: e.target.value })} />
            <button className="btn btn-ghost" disabled={pw.next.length < 8}>Kaydet</button>
          </form>
          <div className="card-actions">
            <a className="btn btn-ghost btn-sm" href={api.exportUrl} download="meall-verilerim.json">⬇️ Verilerimi indir</a>
            <button className="btn btn-ghost btn-sm" onClick={async () => { await api.logout(); setMe(null); }}>Çıkış yap</button>
            <button className="btn btn-danger btn-sm" onClick={async () => {
              if (!confirm("Hesabın ve (başka üyesi yoksa) hanenin tüm verileri kalıcı olarak silinecek. Emin misin?")) return;
              await api.deleteAccount(); setMe(null);
            }}>Hesabı sil</button>
          </div>
        </div>
      </Section>
      {legal && <LegalModal slug={legal} onClose={() => setLegal(null)} />}
    </>
  );
}

function AdminPanel() {
  const toast = useToast();
  const { data, reload } = useAsync(() => api.adminStats(), []);
  const fmt = (iso: string | null) => (iso ? new Date(iso).toLocaleString("tr-TR", { timeZone: "Europe/Istanbul" }) : "—");
  const refresh = async () => {
    const r = await api.adminRefreshPrices();
    toast(r.started ? "Fiyat tazeleme başladı (~1-2 dk)" : r.message ?? "Zaten çalışıyor");
    setTimeout(() => void reload(), 3000);
  };
  if (!data) return null;
  return (
    <Section title="🛠️ Yönetim" action={<button className="btn btn-ghost btn-sm" onClick={() => void reload()}>Yenile</button>}>
      <div className="card admin-grid">
        <div><b>{data.users}</b><small>kullanıcı</small></div>
        <div><b>{data.households}</b><small>hane</small></div>
        <div><b>{data.inventory_items}</b><small>envanter kalemi</small></div>
        <div><b>{data.live_products}</b><small>canlı ürün fiyatı</small></div>
      </div>
      <div className="card add-form small">
        <p>Canlı fiyat: {data.live_prices_enabled ? "açık" : "kapalı"} · Pilot: {data.pilot} · Son çekim: {fmt(data.live_last_fetch)}</p>
        <p>Marketlere göre: {Object.entries(data.live_products_by_store).map(([k, v]) => `${k} ${v}`).join(" · ") || "—"}</p>
        <p>Yapay zekâ: {data.ai_available ? `hazır (${data.ai_provider})` : "anahtar yok"}</p>
        {data.refresh.running && <p className="note">⏳ Fiyatlar tazeleniyor…</p>}
        {data.refresh.last_result && <p className="muted">Son tazeleme: {data.refresh.last_result.queried} malzeme, {data.refresh.last_result.matched} ürün · {fmt(data.refresh.finished_at)}</p>}
        {data.refresh.last_error && <p className="form-error">{data.refresh.last_error}</p>}
        <button className="btn btn-primary btn-sm" disabled={data.refresh.running} onClick={refresh}>Pilot bölge fiyatlarını şimdi tazele</button>
      </div>
    </Section>
  );
}
