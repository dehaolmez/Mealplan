import { useMemo, useState } from "react";
import type { Ingredient } from "../api/types";

/** Katalogda arama yapan, klavye dostu basit otomatik tamamlama. */
export function IngredientPicker({
  ingredients,
  value,
  onChange,
  placeholder = "Malzeme ara…",
}: {
  ingredients: Ingredient[];
  value: Ingredient | null;
  onChange: (i: Ingredient | null) => void;
  placeholder?: string;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const matches = useMemo(() => {
    const q = query.trim().toLocaleLowerCase("tr");
    return ingredients.filter((i) => !q || i.name.toLocaleLowerCase("tr").includes(q)).slice(0, 8);
  }, [ingredients, query]);

  if (value) {
    return (
      <button type="button" className="chip chip-selected" onClick={() => onChange(null)} title="Değiştir">
        {value.emoji} {value.name} ✕
      </button>
    );
  }
  return (
    <div className="picker">
      <input
        value={query}
        placeholder={placeholder}
        onChange={(e) => { setQuery(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        onBlur={() => setTimeout(() => setOpen(false), 150)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && matches[0]) { e.preventDefault(); onChange(matches[0]); setQuery(""); }
        }}
      />
      {open && matches.length > 0 && (
        <ul className="picker-list" role="listbox">
          {matches.map((i) => (
            <li key={i.id}>
              <button type="button" onMouseDown={() => { onChange(i); setQuery(""); }}>
                {i.emoji} {i.name} <small>{i.category}</small>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
