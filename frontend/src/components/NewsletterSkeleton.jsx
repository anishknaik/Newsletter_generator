// Shimmer placeholder shown while a newsletter is being generated.
export default function NewsletterSkeleton() {
  return (
    <div className="newsletter-preview">
      <div className="newsletter-body skeleton">
        <div className="sk-line sk-title" />
        <div className="sk-line sk-meta" />
        <div className="sk-gap" />
        <div className="sk-line sk-h" />
        <div className="sk-line" />
        <div className="sk-line" />
        <div className="sk-line short" />
        <div className="sk-gap" />
        <div className="sk-line sk-h" />
        <div className="sk-line" />
        <div className="sk-line short" />
        <p className="sk-status">
          <span className="spinner" /> Pulling the latest news and writing your
          newsletter… this can take up to a minute.
        </p>
      </div>
    </div>
  );
}
