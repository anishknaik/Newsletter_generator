// Short, human label for the non-default parts of a filter set.
// Returns null when everything is at its default (so we can hide the chip).
const SORT_LABELS = {
  publishedAt: "newest",
  relevancy: "relevant",
  popularity: "popular",
};

export function filterSummary(filters) {
  if (!filters) return null;
  const parts = [];
  if (filters.language && filters.language !== "en")
    parts.push(filters.language.toUpperCase());
  if (filters.sort_by && filters.sort_by !== "publishedAt")
    parts.push(SORT_LABELS[filters.sort_by] || filters.sort_by);
  if (filters.page_size && filters.page_size !== 5)
    parts.push(`${filters.page_size}/topic`);
  if (filters.domains?.length) parts.push(`only ${filters.domains.join(", ")}`);
  if (filters.exclude_domains?.length)
    parts.push(`–${filters.exclude_domains.join(", ")}`);
  return parts.length ? parts.join(" · ") : null;
}
