import { useEffect, useState } from "react";
import {
  getSubscription,
  putSubscription,
  sendSubscriptionNow,
} from "../api/client.js";

// Recurring-newsletter settings. Uses the current topic/tone/filter selection
// as what to schedule, so the user sets it up once where they already are.
export default function SubscriptionPanel({ topics, tone, filters, onError }) {
  const [cadence, setCadence] = useState("off");
  const [sendHour, setSendHour] = useState(8);
  const [recipients, setRecipients] = useState([]);
  const [newRecipient, setNewRecipient] = useState("");
  const [lastSent, setLastSent] = useState(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getSubscription()
      .then((s) => {
        setCadence(s.cadence);
        setSendHour(s.send_hour);
        setRecipients(s.recipients || []);
        setLastSent(s.last_sent_at);
      })
      .catch(onError);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const needsTopics = cadence !== "off" && topics.length === 0;

  function addRecipient() {
    const addr = newRecipient.trim();
    if (addr.includes("@") && !recipients.includes(addr)) {
      setRecipients((prev) => [...prev, addr]);
    }
    setNewRecipient("");
  }

  async function save() {
    setStatus("");
    try {
      await putSubscription({
        cadence,
        send_hour: sendHour,
        topics,
        tone,
        filters,
        recipients,
      });
      setStatus(
        cadence === "off"
          ? "Schedule turned off."
          : `Saved — sending ${cadence} at ${sendHour}:00 UTC.`,
      );
    } catch (err) {
      onError(err);
    }
  }

  async function sendNow() {
    setStatus("Generating and sending…");
    setBusy(true);
    try {
      const r = await sendSubscriptionNow();
      setStatus(
        r.status?.includes("dev mode")
          ? "Sent — saved to the dev outbox."
          : "Sent to your email.",
      );
      const s = await getSubscription();
      setLastSent(s.last_sent_at);
    } catch (err) {
      onError(err);
      setStatus("");
    } finally {
      setBusy(false);
    }
  }

  return (
    <details className="subscription">
      <summary>📅 Schedule a recurring newsletter</summary>

      <div className="sub-row">
        <label>
          Frequency
          <select value={cadence} onChange={(e) => setCadence(e.target.value)}>
            <option value="off">Off</option>
            <option value="daily">Daily</option>
            <option value="weekly">Weekly</option>
          </select>
        </label>
        <label>
          Send hour (UTC)
          <input
            type="number"
            min={0}
            max={23}
            value={sendHour}
            onChange={(e) =>
              setSendHour(Math.max(0, Math.min(23, Number(e.target.value) || 0)))
            }
          />
        </label>
        <button className="generate-btn" onClick={save} disabled={needsTopics}>
          Save schedule
        </button>
        <button className="action-btn" onClick={sendNow} disabled={busy || topics.length === 0}>
          {busy ? "Sending…" : "Send now"}
        </button>
      </div>

      <div className="recipients">
        <span className="recipients-label">
          Recipients (your account email is always included):
        </span>
        <ul className="recipient-chips">
          {recipients.map((addr) => (
            <li key={addr}>
              {addr}
              <button
                type="button"
                onClick={() => setRecipients((prev) => prev.filter((r) => r !== addr))}
                aria-label={`Remove ${addr}`}
              >
                ×
              </button>
            </li>
          ))}
        </ul>
        <div className="recipient-add">
          <input
            type="email"
            placeholder="add recipient email…"
            value={newRecipient}
            onChange={(e) => setNewRecipient(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addRecipient())}
          />
          <button type="button" onClick={addRecipient}>
            Add
          </button>
        </div>
      </div>

      <p className="hint sub-hint">
        Uses your current selection:{" "}
        {topics.length ? <strong>{topics.join(", ")}</strong> : "no topics yet"} ·{" "}
        {tone}.
        {needsTopics && " Pick at least one topic to schedule."}
      </p>

      {lastSent && (
        <p className="hint">Last sent: {new Date(lastSent).toLocaleString()}</p>
      )}
      {status && <p className="sub-status">{status}</p>}
    </details>
  );
}
