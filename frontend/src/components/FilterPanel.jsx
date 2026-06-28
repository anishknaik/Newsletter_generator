import { useState } from "react";

// NewsAPI-supported languages (subset of the common ones).
const LANGUAGES = [
  ["en", "English"],
  ["es", "Spanish"],
  ["fr", "French"],
  ["de", "German"],
  ["it", "Italian"],
  ["pt", "Portuguese"],
  ["nl", "Dutch"],
  ["ru", "Russian"],
  ["zh", "Chinese"],
];

const SORTS = [
  ["publishedAt", "Newest first"],
  ["relevancy", "Most relevant"],
  ["popularity", "Most popular"],
];

// Parse a comma-separated input into a trimmed, non-empty array.
const parseList = (s) =>
  s
    .split(",")
    .map((x) => x.trim())
    .filter(Boolean);

export default function FilterPanel({
  filters,
  onChange,
  presets,
  onApplyPreset,
  onSavePreset,
  onDeletePreset,
}) {
  const [open, setOpen] = useState(false);
  const [presetName, setPresetName] = useState("");

  const set = (patch) => onChange({ ...filters, ...patch });

  function handleSave() {
    const name = presetName.trim();
    if (name) {
      onSavePreset(name);
      setPresetName("");
    }
  }

  return (
    <details className="filter-panel" open={open} onToggle={(e) => setOpen(e.target.open)}>
      <summary>⚙ News filters</summary>

      <div className="filter-grid">
        <label>
          Language
          <select
            value={filters.language}
            onChange={(e) => set({ language: e.target.value })}
          >
            {LANGUAGES.map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Sort by
          <select
            value={filters.sort_by}
            onChange={(e) => set({ sort_by: e.target.value })}
          >
            {SORTS.map(([val, name]) => (
              <option key={val} value={val}>
                {name}
              </option>
            ))}
          </select>
        </label>

        <label>
          Articles / topic
          <input
            type="number"
            min={1}
            max={20}
            value={filters.page_size}
            onChange={(e) =>
              set({ page_size: Math.max(1, Math.min(20, Number(e.target.value) || 1)) })
            }
          />
        </label>

        <label className="wide">
          Only these domains (comma-separated)
          <input
            type="text"
            placeholder="e.g. techcrunch.com, theverge.com"
            value={filters.domains.join(", ")}
            onChange={(e) => set({ domains: parseList(e.target.value) })}
          />
        </label>

        <label className="wide">
          Exclude domains
          <input
            type="text"
            placeholder="e.g. example.com"
            value={filters.exclude_domains.join(", ")}
            onChange={(e) => set({ exclude_domains: parseList(e.target.value) })}
          />
        </label>
      </div>

      <div className="preset-bar">
        <div className="preset-save">
          <input
            type="text"
            placeholder="Save current filters as…"
            value={presetName}
            onChange={(e) => setPresetName(e.target.value)}
          />
          <button type="button" onClick={handleSave} disabled={!presetName.trim()}>
            Save preset
          </button>
        </div>

        {presets.length > 0 && (
          <ul className="preset-list">
            {presets.map((p) => (
              <li key={p.id}>
                <button
                  type="button"
                  className="preset-apply"
                  onClick={() => onApplyPreset(p.filters)}
                  title="Apply this preset"
                >
                  {p.name}
                </button>
                <button
                  type="button"
                  className="preset-delete"
                  onClick={() => onDeletePreset(p.id)}
                  title="Delete preset"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </details>
  );
}
