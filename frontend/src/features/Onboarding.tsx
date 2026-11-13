import { useEffect, useMemo, useState, type ReactElement } from "react";
import { api } from "../api/client";
import type {
  Chain, Diet, Equipment, Exclusion, GoalKey, HouseholdTargets, Ingredient, Me, MealMode, MealSlot, Preferences, RepeatPolicy,
} from "../api/types";
import { useToast } from "../components/Toast";
import { ACTIVITY_LABELS, GOAL_LABELS, tl } from "../lib";
import { MemberForm } from "./ProfilePage";

const GOALS: { key: GoalKey; icon: string; title: string; desc: string }[] = [
  { key: "lose", icon: "⬇️", title: "Kilo vermek", desc: "Aç kalmadan daha az kalori" },
  { key: "muscle", icon: "💪", title: "Kas yapmak", desc: "Her gün yeterli protein" },
  { key: "decide_less", icon: "🧭", title: "Ne pişirsem derdine son", desc: "Haftada bir karar, gerisi hazır" },
  { key: "save_money", icon: "💸", title: "Daha az harcamak", desc: "Bütçene sığan bir hafta" },
  { key: "family", icon: "👨‍👩‍👧", title: "Aileyi tek listeyle doyurmak", desc: "Herkes yer, tek alışveriş" },
  { key: "healthy", icon: "🥗", title: "Daha sağlıklı beslenmek", desc: "Dengeli, gerçek yemek" },
];
const MEALS: { key: MealSlot; icon: string; title: string }[] = [
  { key: "breakfast", icon: "🍳", title: "Kahvaltı" },
  { key: "lunch", icon: "🥙", title: "Öğle yemeği" },
  { key: "dinner", icon: "🍲", title: "Akşam yemeği" },
  { key: "snack", icon: "🍎", title: "Ara öğün" },
];
const DIETS: { key: Diet; icon: string; title: string; desc: string }[] = [
  { key: "none", icon: "🍽️", title: "Kısıtlama yok", desc: "Tüm katalog" },
  { key: "vegetarian", icon: "🥕", title: "Vejetaryen", desc: "Et, tavuk, balık yok" },
  { key: "vegan", icon: "🌱", title: "Vegan", desc: "Hayvansal ürün yok" },
  { key: "pescatarian", icon: "🐟", title: "Pesketaryen", desc: "Balık var, et yok" },
];
const EXCLUSIONS: { key: Exclusion; icon: string; title: string }[] = [
  { key: "red_meat", icon: "🥩", title: "Kırmızı et" }, { key: "pork", icon: "🚫", title: "Domuz" },
  { key: "gluten", icon: "🌾", title: "Gluten" }, { key: "dairy", icon: "🥛", title: "Süt ürünü" },
  { key: "egg", icon: "🥚", title: "Yumurta" }, { key: "nuts", icon: "🌰", title: "Sert kabuklu" },
  { key: "peanut", icon: "🥜", title: "Yer fıstığı" }, { key: "fish", icon: "🐟", title: "Balık" },
  { key: "shellfish", icon: "🦐", title: "Kabuklu deniz ürünü" }, { key: "sesame", icon: "⚪", title: "Susam" },
  { key: "soy", icon: "🫘", title: "Soya" },
];
const EQUIPMENT: { key: Equipment; icon: string; title: string }[] = [
  { key: "stovetop", icon: "🔥", title: "Ocak" }, { key: "oven", icon: "♨️", title: "Fırın" },
  { key: "microwave", icon: "📻", title: "Mikrodalga" }, { key: "airfryer", icon: "🌀", title: "Airfryer" },
  { key: "blender", icon: "🥤", title: "Blender" }, { key: "grill", icon: "🍢", title: "Izgara / tost makinesi" },
  { key: "pressure_cooker", icon: "🫕", title: "Düdüklü tencere" },
];
const DAYS = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"];
const REPEATS: { key: RepeatPolicy; icon: string; title: string; desc: string; strip: string[] }[] = [
  { key: "variety", icon: "✨", title: "Her gün farklı", desc: "Aynı yemek haftada en fazla iki kez", strip: ["🍗", "🥦", "🥚", "🍲", "🐟", "🫘", "🍝"] },
  { key: "balanced", icon: "🔁", title: "Bir pişir, iki gün ye", desc: "Öğle yemekleri iki günde bir pişer", strip: ["🍗", "🍗", "🥦", "🥦", "🫘", "🫘", "🍝"] },
  { key: "batch", icon: "📦", title: "Haftalık toplu pişirme", desc: "Öğle yemeği haftada bir kez, büyük tencerede", strip: ["🍲", "🍲", "🍲", "🍲", "🍲", "🍲", "🍲"] },
];

const DEFAULT: Preferences = {
  preferred_chains: [], goals: [], diet: "none", low_carb: false, exclusions: [], disliked_ingredient_ids: [],
  equipment: ["stovetop", "oven"],
  meals: { breakfast: { mode: "plan", kcal: 0, protein: 0 }, lunch: { mode: "plan", kcal: 0, protein: 0 },
    dinner: { mode: "plan", kcal: 0, protein: 0 }, snack: { mode: "skip", kcal: 0, protein: 0 } },
  plan_days: [0, 1, 2, 3, 4, 5, 6], weekly_budget: 1800, repeat_policy: "variety", max_prep_minutes: null, onboarding_done: false,
};

const toggle = <T,>(list: T[], v: T) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);

export function Onboarding({ me, ingredients, initial, onDone, onClose }: {
  me: Me; ingredients: Ingredient[]; initial: Preferences | null; onDone: () => void; onClose?: () => void;
}) {
  const toast = useToast();
  const [p, setP] = useState<Preferences>(initial ?? DEFAULT);
  const [step, setStep] = useState(0);
  const [chains, setChains] = useState<Chain[]>([]);
  const [targets, setTargets] = useState<HouseholdTargets | null>(null);
  const [healthOk, setHealthOk] = useState(me.consents.find((c) => c.kind === "health_data")?.granted ?? false);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [query, setQuery] = useState("");
  const set = <K extends keyof Preferences>(k: K, v: Preferences[K]) => setP((x) => ({ ...x, [k]: v }));

  useEffect(() => { api.chains().then((c) => setChains(c.filter((x) => x.in_market_fiyati))).catch(() => {}); }, []);
  const loadTargets = () => api.targets().then(setTargets).catch(() => {});
  useEffect(() => { void loadTargets(); }, []);

  const dislikedSuggestions = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    return ingredients.filter((i) => !i.is_staple && !p.disliked_ingredient_ids.includes(i.id)
      && (!q || i.name.toLocaleLowerCase("tr").includes(q))).slice(0, q ? 12 : 10);
  }, [ingredients, query, p.disliked_ingredient_ids]);

  const plannedCount = Object.values(p.meals).filter((m) => m.mode === "plan").length;

  const steps: { title: string; sub?: string; valid?: boolean; body: ReactElement }[] = [
    {
      title: "Nereden alışveriş yaparsın?", sub: "Fiyat karşılaştırması bu zincirlerle yapılır. Hiçbirini seçmezsen hepsi karşılaştırılır.",
      body: (
        <div className="ob-grid ob-grid-3">
          {chains.map((c) => (
            <button key={c.id} className={`ob-chain ${p.preferred_chains.includes(c.slug) ? "on" : ""}`}
              style={{ ["--chain" as string]: c.color }} onClick={() => set("preferred_chains", toggle(p.preferred_chains, c.slug))}>
              <b>{c.name}</b>
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Neyi hedefliyoruz?", sub: "Birden fazla seçebilirsin.",
      body: (
        <div className="ob-list">
          {GOALS.map((g) => (
            <button key={g.key} className={`ob-option ${p.goals.includes(g.key) ? "on" : ""}`} onClick={() => set("goals", toggle(p.goals, g.key))}>
              <span className="ob-icon">{g.icon}</span><span><b>{g.title}</b><small>{g.desc}</small></span><span className="ob-check" />
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Kimler için planlıyoruz?", sub: "Kalori ve protein hedefleri Mifflin-St Jeor formülüyle hesaplanır.",
      body: (
        <div className="ob-list">
          {!healthOk && (
            <div className="card">
              <p className="small">Boy, kilo gibi bilgiler <b>sağlık verisi</b> sayılır; işlemek için açık rızan gerekir. İstemezsen
                bu adımı geçebilirsin, planlar ortalama 2000 kcal ile yapılır.</p>
              <button className="btn btn-primary btn-sm" onClick={async () => { await api.setConsent("health_data", true); setHealthOk(true); }}>
                İzin veriyorum
              </button>
            </div>
          )}
          {healthOk && targets?.members.map((m) => (
            <div key={m.id} className="card ob-formula">
              <b>{m.name}</b> <small className="muted">{m.age} yaş · {m.height_cm} cm · {m.weight_kg} kg</small>
              <dl>
                <dt>Bazal metabolizma (Mifflin-St Jeor)</dt><dd>{Math.round(m.targets.bmr)} kcal</dd>
                <dt>× {ACTIVITY_LABELS[m.activity_level].split(" (")[0].toLocaleLowerCase("tr")}</dt><dd>{Math.round(m.targets.tdee)} kcal</dd>
                <dt>{GOAL_LABELS[m.goal]}</dt><dd><b>{Math.round(m.targets.calories)} kcal</b></dd>
                <dt>Protein · karbonhidrat · yağ</dt><dd>{m.targets.protein_g} · {m.targets.carbs_g} · {m.targets.fat_g} g</dd>
              </dl>
            </div>
          ))}
          {healthOk && !adding && <button className="btn btn-ghost" onClick={() => setAdding(true)}>+ Kişi ekle</button>}
          {healthOk && adding && (
            <MemberForm initial={{ name: "", birth_date: "1990-01-01", sex: "female", height_cm: 165, weight_kg: 65, activity_level: "light", goal: "maintain" }}
              onCancel={() => setAdding(false)}
              onSave={async (m) => {
                try { await api.addMember(m); setAdding(false); void loadTargets(); } catch (e) { toast((e as Error).message, "err"); }
              }} />
          )}
        </div>
      ),
    },
    {
      title: "Hangi öğünleri planlayalım?", sub: "Yemediğin öğünü kapat; kendin hallettiğin öğünün kalorisini ayırırız.",
      valid: plannedCount > 0,
      body: (
        <div className="ob-list">
          {MEALS.map((m) => {
            const s = p.meals[m.key];
            const setMeal = (patch: Partial<typeof s>) => set("meals", { ...p.meals, [m.key]: { ...s, ...patch } });
            return (
              <div key={m.key} className={`card ob-meal mode-${s.mode}`}>
                <div className="ob-meal-head"><span className="ob-icon">{m.icon}</span><b>{m.title}</b></div>
                <div className="seg seg-wide">
                  {([["plan", "Planla"], ["skip", "Yemiyorum"], ["own", "Kendim hallederim"]] as [MealMode, string][]).map(([k, l]) => (
                    <button key={k} className={s.mode === k ? "on" : ""} onClick={() => setMeal({ mode: k })}>{l}</button>
                  ))}
                </div>
                {s.mode === "own" && (
                  <div className="ob-steppers">
                    <Stepper label="Kalori" unit="kcal" value={s.kcal} step={50} max={2000} onChange={(v) => setMeal({ kcal: v })} />
                    <Stepper label="Protein" unit="g" value={s.protein} step={5} max={200} onChange={(v) => setMeal({ protein: v })} />
                  </div>
                )}
              </div>
            );
          })}
          {plannedCount === 0 && <p className="form-error">En az bir öğün planlanmalı.</p>}
        </div>
      ),
    },
    {
      title: "Beslenme tercihin?", sub: "Seçtiğin kurala uymayan tarifler hiç önerilmez.",
      body: (
        <div className="ob-list">
          <div className="ob-grid ob-grid-2">
            {DIETS.map((d) => (
              <button key={d.key} className={`ob-tile ${p.diet === d.key ? "on" : ""}`} onClick={() => set("diet", d.key)}>
                <span className="ob-icon">{d.icon}</span><b>{d.title}</b><small>{d.desc}</small>
              </button>
            ))}
          </div>
          <label className="ob-option ob-switch">
            <span className="ob-icon">📉</span><span><b>Düşük karbonhidrat</b><small>Öğle ve akşam pilav, makarna, ekmek, patates yok</small></span>
            <input type="checkbox" checked={p.low_carb} onChange={(e) => set("low_carb", e.target.checked)} />
          </label>
        </div>
      ),
    },
    {
      title: "Alerji veya hiç istemediğin bir şey var mı?", sub: "Seçilenler tarif önerilerinden tamamen çıkarılır.",
      body: (
        <div className="ob-grid ob-grid-3">
          {EXCLUSIONS.map((x) => (
            <button key={x.key} className={`ob-tile small ${p.exclusions.includes(x.key) ? "on danger" : ""}`}
              onClick={() => set("exclusions", toggle(p.exclusions, x.key))}>
              <span className="ob-icon">{x.icon}</span><b>{x.title}</b>
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Sevmediğin malzemeler?", sub: "Ana malzemesi bunlar olan tarifler önerilmez.",
      body: (
        <div className="ob-list">
          <input className="ob-search" placeholder="Malzeme ara…" value={query} onChange={(e) => setQuery(e.target.value)} />
          {p.disliked_ingredient_ids.length > 0 && (
            <div className="chips">
              {p.disliked_ingredient_ids.map((id) => {
                const ing = ingredients.find((i) => i.id === id);
                return <button key={id} className="chip chip-danger" onClick={() => set("disliked_ingredient_ids", toggle(p.disliked_ingredient_ids, id))}>
                  {ing?.emoji} {ing?.name} ✕</button>;
              })}
            </div>
          )}
          <div className="chips">
            {dislikedSuggestions.map((i) => (
              <button key={i.id} className="chip" onClick={() => { set("disliked_ingredient_ids", [...p.disliked_ingredient_ids, i.id]); setQuery(""); }}>
                {i.emoji} {i.name}
              </button>
            ))}
          </div>
        </div>
      ),
    },
    {
      title: "Mutfağında neler var?", sub: "Tarifler yalnız elindeki aletlerle yapılabilecek olanlardan seçilir.",
      valid: p.equipment.length > 0,
      body: (
        <div className="ob-grid ob-grid-3">
          {EQUIPMENT.map((x) => (
            <button key={x.key} className={`ob-tile ${p.equipment.includes(x.key) ? "on" : ""}`} onClick={() => set("equipment", toggle(p.equipment, x.key))}>
              <span className="ob-icon big">{x.icon}</span><b>{x.title}</b>
            </button>
          ))}
        </div>
      ),
    },
    {
      title: "Hangi günleri planlayalım?", sub: "Dışarıda yediğin günleri çıkar.",
      valid: p.plan_days.length > 0,
      body: (
        <div className="ob-list">
          <div className="ob-grid ob-grid-2">
            {DAYS.map((d, i) => (
              <button key={d} className={`ob-day ${p.plan_days.includes(i) ? "on" : ""}`} onClick={() => set("plan_days", toggle(p.plan_days, i).sort())}>
                {d} <span>{p.plan_days.includes(i) ? "✓" : ""}</span>
              </button>
            ))}
          </div>
          <p className="ob-summary">📅 {p.plan_days.length} gün · {p.plan_days.length * plannedCount} öğün</p>
        </div>
      ),
    },
    {
      title: "Haftalık market bütçen", sub: "Plan, tahmini alışveriş tutarını bu sınırın altında tutmaya çalışır.",
      body: (
        <div className="ob-budget">
          <div className="ob-budget-value">{p.weekly_budget ? tl(p.weekly_budget) : "Sınır yok"}</div>
          <p className="muted">{p.weekly_budget ? budgetLabel(p.weekly_budget) : "Fiyata bakmadan en uygun tarifler"}</p>
          <input type="range" min={500} max={6000} step={100} value={p.weekly_budget ?? 6000}
            onChange={(e) => set("weekly_budget", Number(e.target.value))} aria-label="Bütçe" />
          <div className="ob-range-labels"><span>{tl(500)}</span><span>{tl(6000)}</span></div>
          <label className="check"><input type="checkbox" checked={p.weekly_budget === null}
            onChange={(e) => set("weekly_budget", e.target.checked ? null : 1800)} /> Bütçe sınırı koyma</label>
        </div>
      ),
    },
    {
      title: "Ne kadar tekrar olabilir?", sub: "Bir kez pişirip ertesi gün yemek zaman kazandırır; bazıları sever, bazıları sevmez.",
      body: (
        <div className="ob-list">
          {REPEATS.map((r) => (
            <button key={r.key} className={`ob-option col ${p.repeat_policy === r.key ? "on" : ""}`} onClick={() => set("repeat_policy", r.key)}>
              <span className="ob-row"><span className="ob-icon">{r.icon}</span><span><b>{r.title}</b><small>{r.desc}</small></span><span className="ob-check" /></span>
              <span className="ob-strip">{r.strip.map((e, i) => <span key={i}>{e}</span>)}</span>
            </button>
          ))}
        </div>
      ),
    },
  ];

  const last = step === steps.length - 1;
  const cur = steps[step];

  const finish = async () => {
    setBusy(true);
    try {
      await api.savePreferences({ ...p, onboarding_done: true });
      const res = await api.generatePlan({ days: 7 });
      toast(`${res.meals.length} öğün planlandı${res.est_cost ? ` · tahmini ${tl(res.est_cost)}` : ""}`);
      onDone();
    } catch (e) {
      toast((e as Error).message, "err");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="ob">
      <header className="ob-top">
        <button className="icon-btn" aria-label="Geri" disabled={step === 0} onClick={() => setStep(step - 1)}>‹</button>
        <span className="muted small">{step + 1} / {steps.length}</span>
        {onClose ? <button className="icon-btn" aria-label="Kapat" onClick={onClose}>✕</button> : <span />}
      </header>
      <div className="ob-progress">{steps.map((_, i) => <span key={i} className={i <= step ? "on" : ""} />)}</div>
      <main className="ob-body">
        <h1>{cur.title}</h1>
        {cur.sub && <p className="muted">{cur.sub}</p>}
        {cur.body}
      </main>
      <footer className="ob-foot">
        <button className="btn btn-primary ob-next" disabled={busy || cur.valid === false}
          onClick={() => (last ? finish() : setStep(step + 1))}>
          {last ? (busy ? "Plan hazırlanıyor…" : "✨ Haftamı planla") : "Devam"}
        </button>
      </footer>
    </div>
  );
}

function budgetLabel(v: number) {
  if (v < 1200) return "Ekonomik · sade ve doyurucu";
  if (v < 2500) return "Standart · dengeli ve çeşitli";
  return "Rahat · daha fazla et, balık ve çeşit";
}

function Stepper({ label, unit, value, step, max, onChange }: {
  label: string; unit: string; value: number; step: number; max: number; onChange: (v: number) => void;
}) {
  return (
    <div className="ob-stepper">
      <span>{label}</span>
      <b>{value} {unit}</b>
      <button className="icon-btn" onClick={() => onChange(Math.max(0, value - step))} aria-label={`${label} azalt`}>−</button>
      <button className="icon-btn" onClick={() => onChange(Math.min(max, value + step))} aria-label={`${label} artır`}>+</button>
    </div>
  );
}
