import { useState } from "react";

// Checkbox/tag UI for picking topics, plus a free-text "add your own".
export default function TopicSelector({
  suggested,
  selected,
  onToggle,
  onAddCustom,
}) {
  const [custom, setCustom] = useState("");

  function handleAdd(e) {
    e.preventDefault();
    const trimmed = custom.trim();
    if (trimmed) {
      onAddCustom(trimmed);
      setCustom("");
    }
  }

  return (
    <div className="topic-selector">
      <div className="topic-tags">
        {suggested.map((topic) => (
          <button
            key={topic}
            type="button"
            className={`topic-tag ${selected.includes(topic) ? "active" : ""}`}
            onClick={() => onToggle(topic)}
          >
            {topic}
          </button>
        ))}
      </div>

      <form className="custom-topic" onSubmit={handleAdd}>
        <input
          type="text"
          placeholder="Add your own topic…"
          value={custom}
          onChange={(e) => setCustom(e.target.value)}
        />
        <button type="submit">Add</button>
      </form>
    </div>
  );
}
