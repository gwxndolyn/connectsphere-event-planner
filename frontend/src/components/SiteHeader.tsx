import "./SiteHeader.css";

interface SiteHeaderProps {
  search: string;
  onSearchChange: (value: string) => void;
}

export function SiteHeader({ search, onSearchChange }: SiteHeaderProps) {
  return (
    <header className="site-header">
      <div className="site-header__bar">
        <a href="/" className="site-header__logo">
          <span className="site-header__logo-mark" aria-hidden="true" />
          ConnectSphere
        </a>

        <div className="site-header__search">
          <svg viewBox="0 0 20 20" width="18" height="18" aria-hidden="true">
            <path
              fill="currentColor"
              d="M13.6 12.2a6 6 0 1 0-1.4 1.4l4 4 1.4-1.4zM3 8a5 5 0 1 1 10 0A5 5 0 0 1 3 8"
            />
          </svg>
          <input
            type="search"
            placeholder="Search campus events"
            value={search}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search campus events"
          />
        </div>

        <div className="site-header__location">
          <svg viewBox="0 0 20 20" width="16" height="16" aria-hidden="true">
            <path
              fill="currentColor"
              d="M10 1a6 6 0 0 0-6 6c0 4.5 6 12 6 12s6-7.5 6-12a6 6 0 0 0-6-6m0 8.5A2.5 2.5 0 1 1 10 4a2.5 2.5 0 0 1 0 5.5"
            />
          </svg>
          Main Campus
        </div>
      </div>
    </header>
  );
}
