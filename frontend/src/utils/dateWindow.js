// Human-readable label for a newsletter's news date window.
// Dates arrive as ISO strings ("YYYY-MM-DD") or null/undefined.
export function dateWindowLabel(fromDate, toDate) {
  if (fromDate && toDate) return `${fromDate} → ${toDate}`;
  if (fromDate) return `Since ${fromDate}`;
  if (toDate) return `Up to ${toDate}`;
  return "Latest news";
}
