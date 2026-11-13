// Backend şemalarının (app/schemas) TypeScript karşılıkları
export type Category =
  | "Manav" | "Süt Ürünleri" | "Et & Balık" | "Fırın" | "Temel Gıda"
  | "Dondurulmuş" | "Baharat & Sos" | "İçecek" | "Diğer";
export type BaseUnit = "g" | "ml" | "adet";
export type Location = "fridge" | "freezer";
export type ExpiryStatus = "expired" | "critical" | "warning" | "ok";
export type MealType = "breakfast" | "lunch" | "dinner" | "snack";
export type Sex = "male" | "female";
export type Activity = "sedentary" | "light" | "moderate" | "active" | "very_active";
export type Goal = "lose" | "maintain" | "gain";
export type Strategy = "cheapest" | "single" | "preferred";

export interface Ingredient {
  id: number;
  name: string;
  category: Category;
  base_unit: BaseUnit;
  emoji: string;
  is_staple: boolean;
  grams_per_piece: number | null;
  shelf_life_fridge_days: number | null;
  shelf_life_freezer_days: number | null;
  shelf_life_opened_days: number | null;
}

export interface Targets {
  bmr: number;
  tdee: number;
  calories: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  warnings: string[];
}

export interface Member {
  id: number;
  name: string;
  birth_date: string;
  age: number;
  sex: Sex;
  height_cm: number;
  weight_kg: number;
  activity_level: Activity;
  goal: Goal;
  targets: Targets;
}

export type MemberIn = Omit<Member, "id" | "age" | "targets">;

export interface HouseholdTargets {
  members: Member[];
  total: Targets | null;
  meal_kcal_target: number | null;
}

export interface Household {
  id: number;
  name: string;
  preferred_store_id: number | null;
  selected_store_ids: number[];
  home_lat: number | null;
  home_lon: number | null;
  search_radius_m: number;
}

export interface InventoryItem {
  id: number;
  ingredient: Ingredient;
  location: Location;
  quantity: number;
  quantity_label: string;
  added_on: string;
  expiry_date: string;
  expiry_estimated: boolean;
  opened: boolean;
  days_left: number;
  status: ExpiryStatus;
}

export interface ExpiryAlert {
  item_id: number;
  ingredient_name: string;
  emoji: string;
  location: Location;
  days_left: number;
  status: ExpiryStatus;
  message: string;
}

export interface Alerts {
  expired: number;
  critical: number;
  warning: number;
  alerts: ExpiryAlert[];
}

export interface Macros {
  kcal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
}

export interface Recipe {
  id: number;
  name: string;
  description: string;
  instructions: string;
  servings: number;
  prep_minutes: number;
  meal_type: MealType;
  tags: string[];
  per_serving: Macros;
  ingredients: { ingredient: Ingredient; quantity: number; quantity_label: string; optional: boolean }[];
}

export interface MissingLine {
  ingredient: Ingredient;
  required: number;
  available: number;
  missing: number;
  missing_label: string;
  recipes: string[];
}

export interface Recommendation {
  recipe: Recipe;
  servings: number;
  score: number;
  coverage: number;
  urgency: number;
  nutrition_fit: number;
  uses_expiring: { ingredient_name: string; days_left: number }[];
  missing: MissingLine[];
  ai_reason: string | null;
}

export interface Recommendations {
  ai_requested: boolean;
  ai_used: boolean;
  ai_error: string | null;
  meal_kcal_target: number | null;
  results: Recommendation[];
}

export interface PlanEntry {
  id: number;
  day: string;
  meal_type: MealType;
  recipe_id: number;
  recipe_name: string;
  servings: number;
  cooked: boolean;
  kcal_per_serving: number;
}

export interface Store {
  id: number;
  name: string;
  color: string;
  chain_id: number | null;
  is_demo: boolean;
}

export interface Purchase {
  ingredient_id: number;
  name: string;
  emoji: string;
  category: Category;
  missing_label: string;
  store_id: number | null;
  store_name: string | null;
  brand: string | null;
  package_label: string | null;
  packages: number;
  cost: number;
}

export interface OptimizeResult {
  strategy: Strategy;
  chosen_store_id: number | null;
  total: number;
  unavailable: string[];
  purchases: Purchase[];
  store_totals: { store_id: number; store_name: string; total: number; available_items: number; missing_items: string[] }[];
  savings_vs_worst_single_store: number | null;
  added_to_list: number;
}

export interface ShoppingItem {
  id: number;
  ingredient_id: number | null;
  name: string;
  emoji: string;
  category: Category;
  quantity: number | null;
  unit: string | null;
  note: string;
  checked: boolean;
  checked_at: string | null;
  store_id: number | null;
  store_name: string | null;
  estimated_price: number | null;
  source: string;
}

export interface ShoppingList {
  open_count: number;
  estimated_total: number;
  categories: { category: Category; items: ShoppingItem[] }[];
  recently_bought: ShoppingItem[];
}

export type ChainKind = "discount" | "supermarket" | "hypermarket" | "premium" | "wholesale" | "cooperative" | "regional";

export interface Chain {
  id: number;
  slug: string;
  name: string;
  kind: ChainKind;
  parent: string;
  website: string;
  color: string;
  in_market_fiyati: boolean;
  has_prices: boolean;
  price_source: "real" | "test" | null;
}

export interface Place {
  id: number;
  name: string;
  brand: string;
  shop: string;
  lat: number;
  lon: number;
  address: string;
  opening_hours: string;
  distance_m: number;
  chain: Chain | null;
  osm_url: string;
}

export interface Nearby {
  lat: number;
  lon: number;
  radius_m: number;
  from_cache: boolean;
  chains: { chain: Chain; count: number; nearest_m: number; nearest_place_id: number }[];
  places: Place[];
}

export interface PriceImportResult {
  created: number;
  updated: number;
  stores_created: string[];
  errors: { line: number; error: string }[];
}

export type ConsentKind = "privacy_notice" | "terms" | "health_data" | "location" | "ai_transfer" | "marketing";

export interface Me {
  id: number;
  email: string;
  display_name: string;
  email_verified: boolean;
  has_password: boolean;
  google_linked: boolean;
  household_id: number;
  household_name: string;
  role: "owner" | "member";
  invite_code: string | null;
  consents: { kind: ConsentKind; granted: boolean; text_version: string | null; updated_at: string | null }[];
  legal_version: string;
  needs_reconsent: boolean;
}

export interface RegisterIn {
  email: string;
  password: string;
  display_name: string;
  accept_terms: boolean;
  acknowledge_privacy_notice: boolean;
  health_data_consent: boolean;
  location_consent: boolean;
  ai_transfer_consent: boolean;
  marketing_consent: boolean;
  with_sample_data: boolean;
  invite_code?: string;
}
