import type {
  Alerts, Household, HouseholdTargets, Ingredient, InventoryItem, Location, Member, MemberIn, MealType,
  MissingLine, OptimizeResult, PlanEntry, Recipe, Recommendations, ShoppingItem, ShoppingList, Store, Strategy,
} from "./types";

const BASE = import.meta.env.VITE_API_URL ?? "/api";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
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
  household: () => request<Household>("GET", "/household"),
  updateHousehold: (data: Partial<Omit<Household, "id">>) => request<Household>("PATCH", "/household", data),
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
  optimize: (p: PlanRange & { strategy: Strategy; store_ids?: number[]; add_to_list?: boolean }) =>
    request<OptimizeResult>("POST", "/shopping/optimize", { selections: [], ...p }),
};
