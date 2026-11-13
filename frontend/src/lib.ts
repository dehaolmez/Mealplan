import type { Activity, Category, ExpiryStatus, Goal, MealType, Strategy } from "./api/types";

export const MEAL_LABELS: Record<MealType, string> = {
  breakfast: "Kahvaltı",
  lunch: "Öğle",
  dinner: "Akşam",
  snack: "Ara öğün",
};

export const ACTIVITY_LABELS: Record<Activity, string> = {
  sedentary: "Hareketsiz (masa başı)",
  light: "Hafif aktif (haftada 1-3 gün)",
  moderate: "Orta aktif (haftada 3-5 gün)",
  active: "Çok aktif (haftada 6-7 gün)",
  very_active: "Aşırı aktif (fiziksel iş + spor)",
};

export const GOAL_LABELS: Record<Goal, string> = {
  lose: "Kilo vermek",
  maintain: "Kiloyu korumak",
  gain: "Kas / kilo kazanmak",
};

export const STRATEGY_LABELS: Record<Strategy, string> = {
  cheapest: "En ucuz (marketleri böl)",
  single: "Tek markette tamamla",
  preferred: "Tercih ettiğim market",
};

export const CATEGORY_EMOJI: Record<Category, string> = {
  Manav: "🥬",
  "Süt Ürünleri": "🥛",
  "Et & Balık": "🥩",
  Fırın: "🥖",
  "Temel Gıda": "🌾",
  Dondurulmuş: "🧊",
  "Baharat & Sos": "🧂",
  İçecek: "🧃",
  Diğer: "🛒",
};

export const CATEGORY_COLOR: Record<Category, string> = {
  Manav: "var(--cat-produce)",
  "Süt Ürünleri": "var(--cat-dairy)",
  "Et & Balık": "var(--cat-meat)",
  Fırın: "var(--cat-bakery)",
  "Temel Gıda": "var(--cat-staples)",
  Dondurulmuş: "var(--cat-frozen)",
  "Baharat & Sos": "var(--cat-spices)",
  İçecek: "var(--cat-drinks)",
  Diğer: "var(--cat-other)",
};

export function expiryText(days: number, status: ExpiryStatus): string {
  if (status === "expired") return `${-days} gün geçti`;
  if (days === 0) return "Bugün";
  if (days === 1) return "Yarın";
  return `${days} gün`;
}

export const tl = (n: number) =>
  n.toLocaleString("tr-TR", { style: "currency", currency: "TRY", maximumFractionDigits: 2 });

/** Yerel saat dilimine göre YYYY-AA-GG (toISOString UTC'ye kaydırır, kullanmıyoruz). */
export function isoDate(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

export function addDays(d: Date, n: number): Date {
  const copy = new Date(d);
  copy.setDate(copy.getDate() + n);
  return copy;
}

export function dayLabel(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(y, m - 1, d).toLocaleDateString("tr-TR", { weekday: "short", day: "numeric", month: "short" });
}
