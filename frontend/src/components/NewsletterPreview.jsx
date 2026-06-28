import { useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { dateWindowLabel } from "../utils/dateWindow.js";
import { filterSummary } from "../utils/filterSummary.js";

// Open every Markdown link in a new tab.
const markdownComponents = {
  a: ({ node, ...props }) => (
    <a {...props} target="_blank" rel="noopener noreferrer" />
  ),
};

function issueDate(result) {
  const d = result.created_at ? new Date(result.created_at) : new Date();
  return d.toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

function fileSlug(result) {
  return (
    (result.topics || ["newsletter"])
      .join("-")
      .replace(/[^a-z0-9-]+/gi, "_")
      .toLowerCase() || "newsletter"
  );
}

// Subject + preview as front matter, then the Markdown body.
function exportMarkdown(result) {
  const lines = [];
  if (result.subject_options?.[0]) lines.push(`# ${result.subject_options[0]}`, "");
  if (result.preview_text) lines.push(`_${result.preview_text}_`, "");
  lines.push(result.markdown);
  return lines.join("\n");
}

function triggerDownload(content, filename, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

// Wrap the already-rendered newsletter HTML in a standalone, styled document.
function buildHtmlDoc(result, innerHtml) {
  const title = result.subject_options?.[0] || "Newsletter";
  return `<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>${title}</title>
<style>
  body { font-family: Georgia, "Times New Roman", serif; max-width: 680px;
         margin: 2rem auto; padding: 0 1rem; line-height: 1.65; color: #1c1b19; }
  img { max-width: 100%; height: auto; border-radius: 8px; }
  a { color: #c8553d; }
  h2 { border-bottom: 1px solid #e3e0d8; padding-bottom: .3rem; }
</style></head>
<body>${innerHtml}</body></html>`;
}

// Renders the generated newsletter: masthead, subject lines, body, footer.
export default function NewsletterPreview({ result, onRegenerate, onEmail }) {
  const bodyRef = useRef(null);
  const [copied, setCopied] = useState(false);
  const [emailMsg, setEmailMsg] = useState("");
  const [emailing, setEmailing] = useState(false);
  const [emailTo, setEmailTo] = useState("");

  if (!result) return null;

  async function emailIssue() {
    setEmailing(false);
    setEmailMsg("Sending…");
    try {
      const r = await onEmail(result.id, emailTo.trim() || undefined);
      setEmailMsg(r.status?.includes("dev mode") ? "✓ Saved to outbox" : "✓ Emailed");
      setEmailTo("");
    } catch {
      setEmailMsg("Email failed");
    }
    setTimeout(() => setEmailMsg(""), 4000);
  }

  const subjects = result.subject_options || [];

  async function copyMarkdown() {
    try {
      await navigator.clipboard.writeText(exportMarkdown(result));
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard can be blocked (e.g. non-HTTPS); fail quietly.
    }
  }

  function downloadMd() {
    triggerDownload(exportMarkdown(result), `newsletter-${fileSlug(result)}.md`, "text/markdown");
  }

  function downloadHtml() {
    const inner = bodyRef.current ? bodyRef.current.innerHTML : "";
    triggerDownload(buildHtmlDoc(result, inner), `newsletter-${fileSlug(result)}.html`, "text/html");
  }

  return (
    <div className="newsletter-preview">
      <div className="preview-toolbar">
        <div className="toolbar-meta">
          <span className="date-window" title="News date window">
            🗓 {dateWindowLabel(result.from_date, result.to_date)}
          </span>
          {filterSummary(result.filters) && (
            <span className="filter-chip" title="Filters used">
              ⚙ {filterSummary(result.filters)}
            </span>
          )}
        </div>
        <div className="toolbar-actions">
          <button className="action-btn" onClick={copyMarkdown}>
            {copied ? "✓ Copied" : "⧉ Copy"}
          </button>
          <button className="action-btn" onClick={downloadMd}>
            ⬇ .md
          </button>
          <button className="action-btn" onClick={downloadHtml}>
            ⬇ .html
          </button>
          {onRegenerate && (
            <button className="action-btn" onClick={onRegenerate}>
              ↻ Regenerate
            </button>
          )}
          {onEmail && !emailing && (
            <button className="action-btn" onClick={() => setEmailing(true)}>
              ✉ Email
            </button>
          )}
          {onEmail && emailing && (
            <span className="email-form">
              <input
                type="email"
                placeholder="your account email"
                value={emailTo}
                onChange={(e) => setEmailTo(e.target.value)}
              />
              <button className="action-btn" onClick={emailIssue}>
                Send
              </button>
              <button className="action-btn" onClick={() => setEmailing(false)}>
                ✕
              </button>
            </span>
          )}
          {emailMsg && <span className="email-msg">{emailMsg}</span>}
        </div>
      </div>

      <article className="newsletter-body" ref={bodyRef}>
        <header className="masthead">
          <div className="masthead-brand">📰 The Brief</div>
          <div className="masthead-meta">
            {issueDate(result)} · {result.topics.join(" · ")}
          </div>
        </header>

        {subjects.length > 0 && (
          <div className="subject-block">
            <h2 className="subject-line">{subjects[0]}</h2>
            {result.preview_text && (
              <p className="preview-text">{result.preview_text}</p>
            )}
            {subjects.length > 1 && (
              <details className="subject-alts">
                <summary>Other subject lines</summary>
                <ul>
                  {subjects.slice(1).map((s, i) => (
                    <li key={i}>{s}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        )}

        <ReactMarkdown components={markdownComponents}>
          {result.markdown}
        </ReactMarkdown>

        <footer className="newsletter-footer">
          <p>
            Compiled from {result.articles.length} sources on {issueDate(result)}.
          </p>
          <p>
            Newsletter Generator · <a href="#unsubscribe">Unsubscribe</a> ·{" "}
            <a href="#archive">Archive</a>
          </p>
        </footer>
      </article>

      <details className="sources">
        <summary>{result.articles.length} source articles</summary>
        <ul>
          {result.articles.map((a, i) => (
            <li key={i}>
              <a href={a.url} target="_blank" rel="noopener noreferrer">
                {a.title}
              </a>
              <span className="source-meta">
                {" "}
                — {a.source || "unknown"} · {a.topic}
              </span>
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}
