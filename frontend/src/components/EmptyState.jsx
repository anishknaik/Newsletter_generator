// Friendly placeholder shown before the first newsletter is generated.
export default function EmptyState({ canGenerate }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">📰</div>
      <p>
        {canGenerate
          ? "You're set — hit “Generate newsletter” to create your issue."
          : "Pick one or more topics above, then generate your newsletter."}
      </p>
    </div>
  );
}
