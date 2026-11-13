import { useState } from "react";
import { api } from "../api/client";
import type { Activity, Chain, ChainKind, Goal, Member, MemberIn, PriceImportResult, Sex, Store } from "../api/types";
import { useAsync } from "../hooks/useAsync";
import { ACTIVITY_LABELS, GOAL_LABELS, KIND_LABELS } from "../lib";
import { ErrorBox, Section } from "../components/ui";
import { useToast } from "../components/Toast";

const EMPTY: MemberIn = {
  name: "", birth_date: "1990-01-01", sex: "female", height_cm: 165, weight_kg: 65, activity_level: "light", goal: "maintain",
};

export function ProfilePage({ stores, onChanged }: { stores: Store[]; onChanged: () => void }) {
  const toast = useToast();
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

      <Section title="Bireyler" action={<button className="btn btn-primary btn-sm" onClick={() => setEditing("new")}>+ Kişi</button>}>
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
      <ChainList />
    </div>
  );
}

function MemberForm({ initial, onSave, onCancel }: { initial: MemberIn; onSave: (m: MemberIn) => void; onCancel: () => void }) {
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
              {s.name}{s.is_demo && <small className="muted"> demo</small>}
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
          <a href={api.priceTemplateUrl} download="mealbird-fiyat-sablonu.csv">Şablonu indir</a>
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
                  {c.name}{c.has_prices ? " 💰" : ""}{c.in_market_fiyati ? " ✓" : ""}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
      <p className="muted small">✓ TÜBİTAK "Market Fiyatı" platformunda fiyatları yayımlanan zincir · 💰 uygulamada fiyat verisi var</p>
    </Section>
  );
}
