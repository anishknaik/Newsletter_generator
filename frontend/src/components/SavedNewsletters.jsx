import { useState } from "react";
import { dateWindowLabel } from "../utils/dateWindow.js";

// Lists previously generated newsletters; search, click to reopen, × to delete.
export default function SavedNewsletters({ items, activeId, onOpen, onDelete }) {
  const [query, setQuery] = useState("");
  if (!items.length) return null;

  const q = query.trim().toLowerCase();
  const shown = q
    ? items.filter((n) =>
        `${n.topics.join(" ")} ${n.preview_text || ""}`.toLowerCase().includes(q),
      )
    : items;

  return (
    <section className="saved">
      <h2>Saved newsletters</h2>
      <input
        className="saved-search"
        type="search"
        placeholder="Search by topic or preview…"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />

      {shown.length === 0 ? (
        <p className="hint">No saved newsletters match “{query}”.</p>
      ) : (
        <ul>
          {shown.map((n) => (
            <li key={n.id} className={n.id === activeId ? "active" : ""}>
              <button className="saved-open" onClick={() => onOpen(n.id)}>
                <span className="saved-topics">{n.topics.join(", ")}</span>
                {n.preview_text && (
                  <span className="saved-preview">{n.preview_text}</span>
                )}
                <span className="saved-date">
                  {new Date(n.created_at).toLocaleString()} · 🗓{" "}
                  {dateWindowLabel(n.from_date, n.to_date)}
                </span>
              </button>
              <button
                className="saved-delete"
                title="Delete"
                onClick={() => onDelete(n.id)}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
