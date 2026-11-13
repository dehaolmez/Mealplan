import type {
  Chain, Me, Nearby, PriceImportResult, RegisterIn, ConsentKind, ReceiptDraft,
  Alerts, Household, HouseholdTargets, Ingredient, InventoryItem, Location, Member, MemberIn, MealType,
  MissingLine, OptimizeResult, PlanEntry, Recipe, Recommendations, ShoppingItem, ShoppingList, Store, Strategy,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown, rawCsv?: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: rawCsv !== undefined ? { "Content-Type": "text/csv" } : body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: rawCsv !== undefined ? rawCsv : body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401 && !path.startsWith("/auth/")) {
    // Oturum düştü: uygulama giriş ekranına dönsün
    window.dispatchEvent(new Event("mealbird:unauthorized"));
  }
  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") message = data.detail;
      else if (Array.isArray(data.detail)) message = data.detail.map((d: { msg: string }) => d.msg).join(", ");
    } catch {
      /* gövde JSON değil */
    }
    throw new ApiError(res.status, message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

const qs = (params: Record<string, string | number | boolean | undefined | null>) => {
  const s = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") s.set(k, String(v));
  const str = s.toString();
  return str ? `?${str}` : "";
};

export interface AdminStats {
  users: number;
  households: number;
  inventory_items: number;
  live_products: number;
  live_products_by_store: Record<string, number>;
  live_last_fetch: string | null;
  live_prices_enabled: boolean;
  ai_available: boolean;
  ai_provider: string;
  pilot: string;
  refresh: { running: boolean; last_result: { queried: number; matched: number } | null; last_error: string | null; finished_at: string | null };
}

export interface Selection {
  recipe_id: number;
  servings?: number;
}
export interface PlanRange {
  selections?: Selection[];
  plan_from?: string;
  plan_to?: string;
}

export const api = {
  authConfig: () => request<{ google_client_id: string | null; legal_version: string }>("GET", "/auth/config"),
  me: () => request<Me>("GET", "/auth/me"),
  register: (data: RegisterIn) => request<Me>("POST", "/auth/register", data),
  login: (email: string, password: string) => request<Me>("POST", "/auth/login", { email, password }),
  google: (data: Record<string, unknown>) => request<Me>("POST", "/auth/google", data),
  logout: async () => {
    await request<void>("POST", "/auth/logout");
    navigator.serviceWorker?.controller?.postMessage("clear-user-data");
  },
  forgot: (email: string) => request<void>("POST", "/auth/forgot", { email }),
  reset: (token: string, new_password: string) => request<Me>("POST", "/auth/reset", { token, new_password }),
  verifyEmail: (token: string) => request<void>("POST", `/auth/verify${qs({ token })}`),
  resendVerification: () => request<void>("POST", "/auth/me/resend-verification"),
  acceptTerms: () => request<Me>("POST", "/auth/me/accept-terms"),
  setConsent: (kind: ConsentKind, granted: boolean) => request<Me>("POST", "/auth/me/consents", { kind, granted }),
  changePassword: (current_password: string | null, new_password: string) =>
    request<void>("POST", "/auth/me/password", { current_password, new_password }),
  joinHousehold: (invite_code: string) => request<Me>("POST", "/auth/me/household/join", { invite_code }),
  rotateInvite: () => request<Me>("POST", "/auth/me/household/invite"),
  exportUrl: `${BASE}/auth/me/export`,
  deleteAccount: async () => {
    await request<void>("DELETE", "/auth/me");
    navigator.serviceWorker?.controller?.postMessage("clear-user-data");
  },
  legal: async (slug: string) => {
    const res = await fetch(`${BASE}/legal/${slug}`);
    if (!res.ok) throw new ApiError(res.status, "Belge yüklenemedi");
    return res.text();
  },
  geocode: (q: string) => request<{ label: string; lat: number; lon: number }[]>("GET", `/geocode${qs({ q })}`),
  pilot: () => request<{ name: string; lat: number; lon: number }>("GET", "/places/pilot"),

  household: () => request<Household>("GET", "/household"),
  updateHousehold: (data: Partial<Omit<Household, "id" | "home_lat" | "home_lon">> & { home_lat?: number | null; home_lon?: number | null }) => request<Household>("PATCH", "/household", data),
  targets: () => request<HouseholdTargets>("GET", "/household/targets"),
  addMember: (m: MemberIn) => request<Member>("POST", "/household/members", m),
  updateMember: (id: number, m: MemberIn) => request<Member>("PUT", `/household/members/${id}`, m),
  deleteMember: (id: number) => request<void>("DELETE", `/household/members/${id}`),

  ingredients: (q?: string) => request<Ingredient[]>("GET", `/ingredients${qs({ q })}`),
  stores: () => request<Store[]>("GET", "/stores"),

  inventory: (location?: Location) => request<InventoryItem[]>("GET", `/inventory${qs({ location })}`),
  addInventory: (data: {
    ingredient_id: number; location: Location; quantity: number; unit?: string; expiry_date?: string | null; opened?: boolean;
  }) => request<InventoryItem>("POST", "/inventory", data),
  updateInventory: (id: number, data: Partial<{ quantity: number; unit: string; expiry_date: string; opened: boolean; location: Location }>) =>
    request<InventoryItem | undefined>("PATCH", `/inventory/${id}`, data),
  deleteInventory: (id: number) => request<void>("DELETE", `/inventory/${id}`),
  alerts: () => request<Alerts>("GET", "/inventory/alerts"),

  recipes: () => request<Recipe[]>("GET", "/recipes"),
  recommendations: (p: { meal_type?: MealType; servings?: number; limit?: number; ai?: boolean }) =>
    request<Recommendations>("GET", `/recipes/recommendations${qs(p)}`),
  missing: (p: PlanRange) => request<{ lines: MissingLine[] }>("POST", "/recipes/missing", { selections: [], ...p }),

  plan: (start: string, days = 7) => request<PlanEntry[]>("GET", `/plan${qs({ start, days })}`),
  addPlan: (data: { day: string; meal_type: MealType; recipe_id: number; servings: number }) =>
    request<PlanEntry>("POST", "/plan", data),
  deletePlan: (id: number) => request<void>("DELETE", `/plan/${id}`),
  cook: (id: number) => request<{ consumed: string[]; shortages: string[] }>("POST", `/plan/${id}/cook`),

  shopping: () => request<ShoppingList>("GET", "/shopping"),
  addShopping: (data: { name?: string; ingredient_id?: number; quantity?: number; unit?: string; note?: string }) =>
    request<ShoppingItem>("POST", "/shopping/items", data),
  updateShopping: (id: number, data: Partial<{ checked: boolean; quantity: number; note: string }>) =>
    request<ShoppingItem>("PATCH", `/shopping/items/${id}`, data),
  deleteShopping: (id: number) => request<void>("DELETE", `/shopping/items/${id}`),
  checkout: () => request<{ moved_to_inventory: number; cleared: number }>("POST", "/shopping/checkout"),
  optimize: (p: PlanRange & { strategy: Strategy; store_ids?: number[]; add_to_list?: boolean; nearby_only?: boolean }) =>
    request<OptimizeResult>("POST", "/shopping/optimize", { selections: [], ...p }),

  chains: () => request<Chain[]>("GET", "/chains"),
  adminStats: () => request<AdminStats>("GET", "/admin/stats"),
  adminRefreshPrices: () => request<{ started: boolean; message?: string }>("POST", "/admin/live-prices/refresh"),
  health: () => request<{ ai_available: boolean; ai_provider: string; live_prices: boolean }>("GET", "/health"),
  scanReceipt: (image_base64: string, mime_type: string) =>
    request<ReceiptDraft>("POST", "/receipts/scan", { image_base64, mime_type }),
  confirmReceipt: (date: string | null, lines: { ingredient_id: number; quantity: number; unit: string | null; location: Location }[]) =>
    request<{ added: number }>("POST", "/receipts/confirm", { date, lines }),
  nearby: (p: { lat?: number; lon?: number; radius_m?: number; only_chains?: boolean; refresh?: boolean }) =>
    request<Nearby>("GET", `/places/nearby${qs(p)}`),
  importPrices: (csv: string) => request<PriceImportResult>("POST", "/prices/import", undefined, csv),
  priceTemplateUrl: `${BASE}/prices/template.csv`,
};
