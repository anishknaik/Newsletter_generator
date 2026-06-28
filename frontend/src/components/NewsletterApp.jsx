import { useEffect, useState } from "react";
import TopicSelector from "./TopicSelector.jsx";
import NewsletterPreview from "./NewsletterPreview.jsx";
import NewsletterSkeleton from "./NewsletterSkeleton.jsx";
import EmptyState from "./EmptyState.jsx";
import SavedNewsletters from "./SavedNewsletters.jsx";
import FilterPanel from "./FilterPanel.jsx";
import SubscriptionPanel from "./SubscriptionPanel.jsx";
import {
  addTopic,
  createPreset,
  deletePreset,
  deleteSaved,
  emailNewsletter,
  fetchPresets,
  fetchSaved,
  fetchSavedById,
  fetchTopics,
  generateNewsletter,
} from "../api/client.js";

// NewsAPI's free tier only reaches back ~1 month, so bound the date pickers.
function isoDaysAgo(days) {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
}
const TODAY = isoDaysAgo(0);
const EARLIEST = isoDaysAgo(30);

const DEFAULT_FILTERS = {
  language: "en",
  sort_by: "publishedAt",
  page_size: 5,
  domains: [],
  exclude_domains: [],
};

export default function NewsletterApp({ user, onLogout }) {
  const [suggested, setSuggested] = useState([]);
  const [selected, setSelected] = useState([]);
  const [tone, setTone] = useState("friendly and informative");
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [filters, setFilters] = useState(DEFAULT_FILTERS);
  const [presets, setPresets] = useState([]);
  const [result, setResult] = useState(null);
  const [saved, setSaved] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  // If a call fails because the session expired, bounce to login with a notice.
  function handleError(err) {
    if (err.status === 401 || err.status === 403) {
      onLogout("Your session expired — please log in again.");
    } else {
      setError(err.message);
    }
  }

  function loadSaved() {
    fetchSaved().then(setSaved).catch(handleError);
  }
  function loadPresets() {
    fetchPresets().then(setPresets).catch(handleError);
  }

  // Load the user's topics, saved newsletters, and presets once on mount.
  useEffect(() => {
    fetchTopics().then(setSuggested).catch(handleError);
    loadSaved();
    loadPresets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleTopic(topic) {
    setSelected((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic],
    );
  }

  async function addCustom(topic) {
    try {
      setSuggested(await addTopic(topic));
    } catch (err) {
      handleError(err);
      if (!suggested.includes(topic)) setSuggested((prev) => [...prev, topic]);
    }
    if (!selected.includes(topic)) setSelected((prev) => [...prev, topic]);
  }

  async function runGenerate(topics) {
    setError("");
    setResult(null);
    setLoading(true);
    try {
      const data = await generateNewsletter(topics, tone, fromDate, toDate, filters);
      setResult(data);
      loadSaved();
    } catch (err) {
      handleError(err);
    } finally {
      setLoading(false);
    }
  }

  // Generate from the currently selected topics.
  const handleGenerate = () => runGenerate(selected);
  // Regenerate the shown newsletter's topics with the current tone/filters.
  const regenerate = (current) => runGenerate(current.topics);

  async function openSaved(id) {
    setError("");
    try {
      setResult(await fetchSavedById(id));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      handleError(err);
    }
  }

  async function removeSaved(id) {
    try {
      await deleteSaved(id);
      setSaved((prev) => prev.filter((n) => n.id !== id));
      setResult((prev) => (prev && prev.id === id ? null : prev));
    } catch (err) {
      handleError(err);
    }
  }

  async function savePreset(name) {
    try {
      await createPreset(name, filters);
      loadPresets();
    } catch (err) {
      handleError(err);
    }
  }

  async function removePreset(id) {
    try {
      await deletePreset(id);
      setPresets((prev) => prev.filter((p) => p.id !== id));
    } catch (err) {
      handleError(err);
    }
  }

  return (
    <div className="app">
      <header className="app-header">
        <div>
          <h1>📰 Newsletter Generator</h1>
          <p>Pick a few topics and generate a newsletter from the news.</p>
        </div>
        <div className="user-box">
          <span className="user-email">{user.email}</span>
          <button className="linkish" onClick={() => onLogout()}>
            Log out
          </button>
        </div>
      </header>

      <TopicSelector
        suggested={suggested}
        selected={selected}
        onToggle={toggleTopic}
        onAddCustom={addCustom}
      />

      <FilterPanel
        filters={filters}
        onChange={setFilters}
        presets={presets}
        onApplyPreset={(f) => setFilters({ ...DEFAULT_FILTERS, ...f })}
        onSavePreset={savePreset}
        onDeletePreset={removePreset}
      />

      <SubscriptionPanel
        topics={selected}
        tone={tone}
        filters={filters}
        onError={handleError}
      />

      <div className="controls">
        <label>
          Tone
          <input
            type="text"
            value={tone}
            onChange={(e) => setTone(e.target.value)}
          />
        </label>
        <label>
          From
          <input
            type="date"
            value={fromDate}
            min={EARLIEST}
            max={toDate || TODAY}
            onChange={(e) => setFromDate(e.target.value)}
          />
        </label>
        <label>
          To
          <input
            type="date"
            value={toDate}
            min={fromDate || EARLIEST}
            max={TODAY}
            onChange={(e) => setToDate(e.target.value)}
          />
        </label>
        <button
          className="generate-btn"
          onClick={handleGenerate}
          disabled={loading || selected.length === 0}
        >
          {loading ? (
            <>
              <span className="spinner" /> Generating…
            </>
          ) : (
            "Generate newsletter"
          )}
        </button>
      </div>
      <p className="hint date-hint">
        Leave dates empty for the latest news. The free news tier only reaches
        back about a month.
      </p>

      {error && <p className="error error-banner">{error}</p>}

      {loading ? (
        <NewsletterSkeleton />
      ) : result ? (
        <NewsletterPreview
          result={result}
          onRegenerate={() => regenerate(result)}
          onEmail={emailNewsletter}
        />
      ) : (
        <EmptyState canGenerate={selected.length > 0} />
      )}

      <SavedNewsletters
        items={saved}
        activeId={result?.id}
        onOpen={openSaved}
        onDelete={removeSaved}
      />
    </div>
  );
}
