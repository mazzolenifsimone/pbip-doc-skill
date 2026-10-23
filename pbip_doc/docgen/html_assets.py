"""
Static CSS and JavaScript assets for native HTML documentation portal.
Enterprise C-Level executive aesthetic: neutral palette, clean borders, professional typography.
Zero third-party dependencies, zero CDN requests, 100% air-gap and file:// protocol safe.
"""

STYLE_CSS = """/* pbip-doc-skill - Enterprise BI Documentation Stylesheet */
:root {
  --font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
  
  /* Executive Neutral Light Gray Palette */
  --bg-body: #eaedf0;
  --bg-surface: #f5f7f9;
  --bg-surface-hover: #e2e6eb;
  --bg-sidebar: #f8fafc;
  --bg-sidebar-hover: #edf2f7;
  --bg-sidebar-active: #e2e8f0;
  --bg-sidebar-input: #ffffff;
  --bg-sidebar-badge: #e2e8f0;

  /* Code Cells (Adaptive) */
  --bg-code: #ffffff;
  --bg-code-header: #f1f3f5;
  --border-code: #cbd2d9;
  --text-code: #1f2328;
  --text-code-muted: #57606a;
  --bg-copy-btn: #ffffff;
  --border-copy-btn: #cbd2d9;
  --text-copy-btn: #24292f;
  --bg-copy-btn-hover: #e9ecef;

  /* Global Scrollbars */
  --scrollbar-track: transparent;
  --scrollbar-thumb: #cbd2d9;
  --scrollbar-thumb-hover: #9ca3af;
  
  --text-main: #24292f;
  --text-muted: #57606a;
  --text-sidebar: #57606a;
  --text-sidebar-bright: #1f2328;
  
  --border-color: #cbd2d9;
  --border-subtle: #dde2e6;
  --border-sidebar: #cbd2d9;
  
  --primary: #1e2229;
  --primary-hover: #374151;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;

  --link-color: #1d4ed8;
  --link-hover: #1e40af;

  /* Table Role Badges (Differentiated, professional, high-contrast) */
  --role-fact-bg: #eff6ff;
  --role-fact-text: #1e40af;
  --role-fact-border: #bfdbfe;

  --role-dim-bg: #f0fdf4;
  --role-dim-text: #166534;
  --role-dim-border: #bbf7d0;

  --role-snow-bg: #fefce8;
  --role-snow-text: #854d0e;
  --role-snow-border: #fef08a;

  --role-bridge-bg: #faf5ff;
  --role-bridge-text: #6b21a8;
  --role-bridge-border: #e9d5ff;

  --role-date-bg: #f0f9ff;
  --role-date-text: #0369a1;
  --role-date-border: #bae6fd;

  --role-calcgroup-bg: #eef2ff;
  --role-calcgroup-text: #3730a3;
  --role-calcgroup-border: #c7d2fe;

  --role-utility-bg: #f4f4f5;
  --role-utility-text: #3f3f46;
  --role-utility-border: #e4e4e7;

  /* Column Types */
  --col-imported-bg: #f1f5f9;
  --col-imported-text: #475569;
  --col-imported-border: #cbd5e1;

  --col-calc-bg: #e0f2fe;
  --col-calc-text: #0369a1;
  --col-calc-border: #7dd3fc;

  --col-key-bg: #fef3c7;
  --col-key-text: #92400e;
  --col-key-border: #fcd34d;

  /* Semantic Status & Neutral Badges */
  --badge-neutral-bg: #dde2e6;
  --badge-neutral-text: #4b5563;
  --badge-neutral-border: #cbd2d9;

  --status-active-bg: #dcfce7;
  --status-active-text: #15803d;
  --status-active-border: #bbf7d0;

  --status-inactive-bg: #fef3c7;
  --status-inactive-text: #b45309;
  --status-inactive-border: #fde68a;

  --radius-sm: 4px;
  --radius-md: 6px;
  --radius-lg: 8px;
}

@media (prefers-color-scheme: dark) {
  :root:not([data-theme="light"]) {
    /* Executive Neutral Dark Gray Palette */
    --bg-body: #16181d;
    --bg-surface: #21252d;
    --bg-surface-hover: #2b313b;
    --bg-sidebar: #181a1f;
    --bg-sidebar-hover: #22262e;
    --bg-sidebar-active: #2b313b;
    --bg-sidebar-input: #121418;
    --bg-sidebar-badge: rgba(255, 255, 255, 0.08);

    /* Code Cells Dark Mode (Adaptive) */
    --bg-code: #14161a;
    --bg-code-header: #1b1e24;
    --border-code: #2d333b;
    --text-code: #e2e8f0;
    --text-code-muted: #8b949e;
    --bg-copy-btn: rgba(255, 255, 255, 0.08);
    --border-copy-btn: rgba(255, 255, 255, 0.15);
    --text-copy-btn: #e2e8f0;
    --bg-copy-btn-hover: rgba(255, 255, 255, 0.16);

    /* Global Scrollbars Dark Mode */
    --scrollbar-track: transparent;
    --scrollbar-thumb: #343a46;
    --scrollbar-thumb-hover: #4b5563;
    
    --text-main: #d0d7de;
    --text-muted: #8b949e;
    --text-sidebar: #9da7b3;
    --text-sidebar-bright: #f0f3f6;
    
    --border-color: #343a46;
    --border-subtle: #272c35;
    --border-sidebar: #272c35;
    
    --primary: #d0d7de;
    --primary-hover: #f0f3f6;
    --accent: #60a5fa;
    --accent-hover: #93c5fd;

    --link-color: #60a5fa;
    --link-hover: #93c5fd;

    /* Role Badges Dark Mode */
    --role-fact-bg: rgba(30, 64, 175, 0.2);
    --role-fact-text: #93c5fd;
    --role-fact-border: rgba(147, 197, 253, 0.3);

    --role-dim-bg: rgba(22, 101, 52, 0.2);
    --role-dim-text: #86efac;
    --role-dim-border: rgba(134, 239, 172, 0.3);

    --role-snow-bg: rgba(133, 77, 14, 0.2);
    --role-snow-text: #fde047;
    --role-snow-border: rgba(253, 224, 71, 0.3);

    --role-bridge-bg: rgba(107, 33, 168, 0.2);
    --role-bridge-text: #d8b4fe;
    --role-bridge-border: rgba(216, 180, 254, 0.3);

    --role-date-bg: rgba(3, 105, 161, 0.2);
    --role-date-text: #7dd3fc;
    --role-date-border: rgba(125, 211, 252, 0.3);

    --role-calcgroup-bg: rgba(55, 48, 163, 0.2);
    --role-calcgroup-text: #a5b4fc;
    --role-calcgroup-border: rgba(165, 180, 252, 0.3);

    --role-utility-bg: rgba(63, 63, 70, 0.25);
    --role-utility-text: #d4d4d8;
    --role-utility-border: rgba(212, 212, 216, 0.2);

    --col-imported-bg: rgba(71, 85, 105, 0.2);
    --col-imported-text: #cbd5e1;
    --col-imported-border: rgba(203, 213, 225, 0.2);

    --col-calc-bg: rgba(3, 105, 161, 0.25);
    --col-calc-text: #7dd3fc;
    --col-calc-border: rgba(125, 211, 252, 0.3);

    --col-key-bg: rgba(146, 64, 14, 0.25);
    --col-key-text: #fde68a;
    --col-key-border: rgba(252, 211, 77, 0.3);

    /* Semantic Status & Neutral Badges Dark Mode */
    --badge-neutral-bg: rgba(255, 255, 255, 0.08);
    --badge-neutral-text: #9da7b3;
    --badge-neutral-border: rgba(255, 255, 255, 0.12);

    --status-active-bg: rgba(22, 101, 52, 0.25);
    --status-active-text: #86efac;
    --status-active-border: rgba(134, 239, 172, 0.3);

    --status-inactive-bg: rgba(180, 83, 9, 0.25);
    --status-inactive-text: #fde047;
    --status-inactive-border: rgba(253, 224, 71, 0.3);
  }
}

[data-theme="dark"] {
  /* Executive Neutral Dark Gray Palette */
  --bg-body: #16181d;
  --bg-surface: #21252d;
  --bg-surface-hover: #2b313b;
  --bg-sidebar: #181a1f;
  --bg-sidebar-hover: #22262e;
  --bg-sidebar-active: #2b313b;
  --bg-sidebar-input: #121418;
  --bg-sidebar-badge: rgba(255, 255, 255, 0.08);

  /* Code Cells Dark Mode (Adaptive) */
  --bg-code: #14161a;
  --bg-code-header: #1b1e24;
  --border-code: #2d333b;
  --text-code: #e2e8f0;
  --text-code-muted: #8b949e;
  --bg-copy-btn: rgba(255, 255, 255, 0.08);
  --border-copy-btn: rgba(255, 255, 255, 0.15);
  --text-copy-btn: #e2e8f0;
  --bg-copy-btn-hover: rgba(255, 255, 255, 0.16);

  /* Global Scrollbars Dark Mode */
  --scrollbar-track: transparent;
  --scrollbar-thumb: #343a46;
  --scrollbar-thumb-hover: #4b5563;
  
  --text-main: #d0d7de;
  --text-muted: #8b949e;
  --text-sidebar: #9da7b3;
  --text-sidebar-bright: #f0f3f6;
  
  --border-color: #343a46;
  --border-subtle: #272c35;
  --border-sidebar: #272c35;
  
  --primary: #d0d7de;
  --primary-hover: #f0f3f6;
  --accent: #60a5fa;
  --accent-hover: #93c5fd;

  --link-color: #60a5fa;
  --link-hover: #93c5fd;

  /* Role Badges Dark Mode */
  --role-fact-bg: rgba(30, 64, 175, 0.2);
  --role-fact-text: #93c5fd;
  --role-fact-border: rgba(147, 197, 253, 0.3);

  --role-dim-bg: rgba(22, 101, 52, 0.2);
  --role-dim-text: #86efac;
  --role-dim-border: rgba(134, 239, 172, 0.3);

  --role-snow-bg: rgba(133, 77, 14, 0.2);
  --role-snow-text: #fde047;
  --role-snow-border: rgba(253, 224, 71, 0.3);

  --role-bridge-bg: rgba(107, 33, 168, 0.2);
  --role-bridge-text: #d8b4fe;
  --role-bridge-border: rgba(216, 180, 254, 0.3);

  --role-date-bg: rgba(3, 105, 161, 0.2);
  --role-date-text: #7dd3fc;
  --role-date-border: rgba(125, 211, 252, 0.3);

  --role-calcgroup-bg: rgba(55, 48, 163, 0.2);
  --role-calcgroup-text: #a5b4fc;
  --role-calcgroup-border: rgba(165, 180, 252, 0.3);

  --role-utility-bg: rgba(63, 63, 70, 0.25);
  --role-utility-text: #d4d4d8;
  --role-utility-border: rgba(212, 212, 216, 0.2);

  --col-imported-bg: rgba(71, 85, 105, 0.2);
  --col-imported-text: #cbd5e1;
  --col-imported-border: rgba(203, 213, 225, 0.2);

  --col-calc-bg: rgba(3, 105, 161, 0.25);
  --col-calc-text: #7dd3fc;
  --col-calc-border: rgba(125, 211, 252, 0.3);

  --col-key-bg: rgba(146, 64, 14, 0.25);
  --col-key-text: #fde68a;
  --col-key-border: rgba(252, 211, 77, 0.3);

  /* Semantic Status & Neutral Badges Dark Mode */
  --badge-neutral-bg: rgba(255, 255, 255, 0.08);
  --badge-neutral-text: #9da7b3;
  --badge-neutral-border: rgba(255, 255, 255, 0.12);

  --status-active-bg: rgba(22, 101, 52, 0.25);
  --status-active-text: #86efac;
  --status-active-border: rgba(134, 239, 172, 0.3);

  --status-inactive-bg: rgba(180, 83, 9, 0.25);
  --status-inactive-text: #fde047;
  --status-inactive-border: rgba(253, 224, 71, 0.3);
}

/* Base Reset & Core Typography */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
  scrollbar-width: thin;
  scrollbar-color: var(--scrollbar-thumb) var(--scrollbar-track);
}

/* Global Uniform Scrollbars (WebKit & Blink) */
::-webkit-scrollbar {
  width: 6px;
  height: 6px;
}

::-webkit-scrollbar-track {
  background: var(--scrollbar-track);
}

::-webkit-scrollbar-thumb {
  background-color: var(--scrollbar-thumb);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background-color: var(--scrollbar-thumb-hover);
}

::-webkit-scrollbar-corner {
  background: transparent;
}

body {
  font-family: var(--font-family);
  background-color: var(--bg-body);
  color: var(--text-main);
  line-height: 1.5;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* Core Links & Non-Purple Visited State */
a {
  color: var(--link-color);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.15s ease, text-decoration 0.15s ease;
}

a:visited {
  color: var(--link-color);
}

a:hover, a:focus {
  color: var(--link-hover);
  text-decoration: underline;
  text-underline-offset: 2px;
}

/* Master Layout Grid */
.wiki-layout {
  display: flex;
  min-height: 100vh;
}

/* Sidebar Styles */
.wiki-sidebar {
  width: 290px;
  background-color: var(--bg-sidebar);
  color: var(--text-sidebar);
  border-right: 1px solid var(--border-sidebar);
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow: hidden;
  flex-shrink: 0;
}

.sidebar-header {
  padding: 1.1rem 1.25rem;
  border-bottom: 1px solid var(--border-sidebar);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sidebar-title-link {
  color: var(--text-sidebar-bright);
  text-decoration: none;
  font-weight: 600;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar-title-link:hover {
  color: var(--text-sidebar-bright);
  text-decoration: none;
}

.sidebar-title-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  opacity: 0.9;
}

.sidebar-badge {
  font-size: 0.7rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 0.15rem 0.45rem;
  border-radius: var(--radius-sm);
  background-color: var(--bg-sidebar-badge);
  color: var(--text-sidebar);
  border: 1px solid var(--border-sidebar);
}

.sidebar-search-container {
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--border-sidebar);
}

.search-input-wrapper {
  position: relative;
  display: flex;
  align-items: center;
}

.search-icon-svg {
  position: absolute;
  left: 0.75rem;
  width: 14px;
  height: 14px;
  color: var(--text-sidebar);
  pointer-events: none;
}

.search-input {
  width: 100%;
  padding: 0.45rem 0.6rem 0.45rem 2.2rem;
  background-color: var(--bg-sidebar-input);
  border: 1px solid var(--border-sidebar);
  border-radius: var(--radius-sm);
  color: var(--text-sidebar-bright);
  font-size: 0.825rem;
  outline: none;
  transition: border-color 0.15s ease, background 0.15s ease, box-shadow 0.15s ease;
}

.search-input:focus {
  border-color: var(--primary);
  background-color: var(--bg-sidebar-input);
  box-shadow: 0 0 0 1px var(--primary);
}

.search-input::placeholder {
  color: var(--text-sidebar);
  opacity: 0.75;
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 0.75rem 0.5rem;
}

.nav-section {
  margin-bottom: 1rem;
}

.nav-section-title {
  font-size: 0.7rem;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 700;
  color: var(--text-sidebar);
  padding: 0.35rem 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  opacity: 0.85;
}

.nav-list {
  list-style: none;
}

.nav-item {
  margin: 1px 0;
}

.nav-link {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.35rem 0.75rem;
  color: var(--text-sidebar);
  text-decoration: none;
  border-radius: var(--radius-sm);
  font-size: 0.825rem;
  transition: all 0.12s ease;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.nav-link:hover {
  background-color: var(--bg-sidebar-hover);
  color: var(--text-sidebar-bright);
}

.nav-link.active {
  background-color: var(--bg-sidebar-active);
  color: var(--text-sidebar-bright);
  font-weight: 600;
}

.nav-item-badge {
  font-size: 0.65rem;
  padding: 0.1rem 0.35rem;
  font-weight: 600;
  margin-left: 0.5rem;
  flex-shrink: 0;
}

.nav-subgroup-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.35rem 0.75rem;
  color: var(--text-sidebar);
  font-size: 0.8rem;
  font-weight: 600;
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background-color 0.12s ease, color 0.12s ease;
}

.nav-subgroup-header:hover {
  background-color: var(--bg-sidebar-hover);
  color: var(--text-sidebar-bright);
}

.nav-subgroup-items {
  padding-left: 0.75rem;
}

.subgroup-icon {
  font-size: 0.75rem;
  opacity: 0.6;
}

/* Main Content Area */
.wiki-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

/* Topbar Header */
.wiki-topbar {
  background-color: var(--bg-surface);
  border-bottom: 1px solid var(--border-color);
  padding: 0.75rem 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 20;
}

.breadcrumbs {
  font-size: 0.85rem;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.breadcrumbs a {
  color: var(--text-muted);
  text-decoration: none;
}

.breadcrumbs a:hover {
  color: var(--text-main);
  text-decoration: underline;
}

.breadcrumb-sep {
  opacity: 0.5;
}

.breadcrumb-current {
  color: var(--text-main);
  font-weight: 600;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.theme-toggle-btn {
  background: transparent;
  border: 1px solid var(--border-color);
  color: var(--text-main);
  padding: 0.35rem 0.75rem;
  border-radius: var(--radius-sm);
  font-size: 0.8rem;
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  transition: all 0.15s ease;
}

.theme-toggle-btn:hover {
  background-color: var(--bg-surface-hover);
  border-color: var(--border-color);
}

.theme-toggle-svg {
  width: 14px;
  height: 14px;
}

/* Main Article Content */
.wiki-article {
  padding: 2rem 2.5rem 4rem 2.5rem;
  max-width: 1440px;
  width: 100%;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 1.75rem;
  padding-bottom: 1.25rem;
  border-bottom: 1px solid var(--border-color);
}

.page-title {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-main);
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-bottom: 0.35rem;
}

.page-subtitle {
  font-size: 0.95rem;
  color: var(--text-muted);
}

/* KPI Summary Cards Grid */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.75rem;
}

.kpi-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1rem 1.25rem;
}

.kpi-label {
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  font-weight: 600;
  margin-bottom: 0.25rem;
}

.kpi-value {
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: var(--text-main);
  line-height: 1.2;
}

.kpi-sub {
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-top: 0.25rem;
}

/* Zero-JS In-Page Quick Navigation & Clean Vertical Sections */
.page-quicknav {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1rem;
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-top: 1.25rem;
  margin-bottom: 1.75rem;
}

.page-quicknav a {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--link-color);
  text-decoration: none;
  padding: 0.25rem 0.5rem;
  border-radius: var(--radius-sm);
  transition: background-color 0.15s ease, color 0.15s ease;
}

.page-quicknav a:hover {
  background-color: var(--bg-surface-hover);
  text-decoration: underline;
}

.page-quicknav-sep {
  color: var(--text-muted);
  font-size: 0.75rem;
  user-select: none;
}

.content-section {
  margin-bottom: 2.25rem;
  scroll-margin-top: 1.5rem;
}

.section-title {
  font-size: 1.2rem;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 0.85rem;
  padding-bottom: 0.4rem;
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* Ensure all content containers are visible in Zero-JS mode */
.tab-content {
  display: block !important;
  margin-bottom: 1.5rem;
}

/* Native HTML5 Details/Summary in Sidebar & Collapsible Sections */
details.nav-details {
  width: 100%;
}

details.nav-details summary.nav-subgroup-header {
  list-style: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: space-between;
  user-select: none;
}

details.nav-details summary::-webkit-details-marker {
  display: none;
}

details.nav-details summary::after {
  content: "▸";
  font-size: 0.75rem;
  color: var(--text-muted);
  margin-left: auto;
}

details.nav-details[open] summary::after {
  content: "▾";
}

/* Target highlighting for anchor navigation */
:target {
  scroll-margin-top: 2rem;
}

.calc-col-card:target {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.2);
}

/* Content Cards & Sections */
.content-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.25rem;
}

.content-card-title {
  font-size: 1.05rem;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.description-card {
  border-left: 4px solid var(--accent);
}

.description-text {
  font-size: 0.95rem;
  line-height: 1.6;
  color: var(--text-main);
  margin: 0;
}

.description-empty {
  color: var(--text-muted);
  font-style: italic;
}

/* Calculated Column Card & Deep-Link Highlighting */
.calc-col-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 1.25rem;
  margin-bottom: 1.25rem;
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}

.calc-col-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 0.75rem;
}

.calc-col-title-group {
  display: flex;
  align-items: center;
  gap: 0.6rem;
  flex-wrap: wrap;
}

.calc-col-name {
  font-family: var(--font-mono);
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-main);
}

.calc-col-desc {
  font-size: 0.85rem;
  color: var(--text-muted);
  margin-bottom: 0.75rem;
}

.highlight-pulse {
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.15) !important;
}

/* Data Tables */
.table-toolbar {
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.table-filter-input {
  width: 280px;
  padding: 0.45rem 0.75rem;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background-color: var(--bg-surface);
  color: var(--text-main);
  font-size: 0.8rem;
  outline: none;
}

.table-filter-input:focus {
  border-color: var(--text-main);
}

.table-responsive {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background-color: var(--bg-surface);
}

.data-table {
  width: 100%;
  border-collapse: collapse;
  text-align: left;
  font-size: 0.825rem;
}

.data-table th {
  background-color: var(--bg-body);
  color: var(--text-muted);
  font-weight: 600;
  text-transform: uppercase;
  font-size: 0.7rem;
  letter-spacing: 0.05em;
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  white-space: nowrap;
}

.data-table td {
  padding: 0.65rem 0.85rem;
  border-bottom: 1px solid var(--border-color);
  color: var(--text-main);
  vertical-align: middle;
}

.data-table tr:last-child td {
  border-bottom: none;
}

.data-table tr:hover td {
  background-color: var(--bg-surface-hover);
}

.data-table a {
  color: var(--link-color);
  text-decoration: none;
  font-weight: 500;
}

.data-table a:visited {
  color: var(--link-color);
}

.data-table a:hover {
  color: var(--link-hover);
  text-decoration: underline;
  text-underline-offset: 2px;
}

.data-table code {
  font-family: var(--font-mono);
  font-size: 0.8rem;
  background: var(--bg-surface-hover);
  padding: 0.15rem 0.35rem;
  border-radius: 3px;
  border: 1px solid var(--border-color);
}

/* Badges & Tags */
.badge {
  display: inline-flex;
  align-items: center;
  font-size: 0.725rem;
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  border-radius: var(--radius-sm);
  white-space: nowrap;
  line-height: 1.3;
}

/* Table Role Badges */
.badge-role-fact, .badge-fact {
  background-color: var(--role-fact-bg);
  color: var(--role-fact-text);
  border: 1px solid var(--role-fact-border);
}

.badge-role-dim {
  background-color: var(--role-dim-bg);
  color: var(--role-dim-text);
  border: 1px solid var(--role-dim-border);
}

/* Neutral Tags & Modifiers */
.badge-dim, .badge-neutral {
  background-color: var(--badge-neutral-bg);
  color: var(--badge-neutral-text);
  border: 1px solid var(--badge-neutral-border);
}

/* Semantic Status Badges */
.badge-status-active {
  background-color: var(--status-active-bg);
  color: var(--status-active-text);
  border: 1px solid var(--status-active-border);
}

.badge-status-inactive {
  background-color: var(--status-inactive-bg);
  color: var(--status-inactive-text);
  border: 1px solid var(--status-inactive-border);
}

.badge-role-snowflake, .badge-snowflake {
  background-color: var(--role-snow-bg);
  color: var(--role-snow-text);
  border: 1px solid var(--role-snow-border);
}

.badge-role-bridge, .badge-bridge {
  background-color: var(--role-bridge-bg);
  color: var(--role-bridge-text);
  border: 1px solid var(--role-bridge-border);
}

.badge-role-date, .badge-date {
  background-color: var(--role-date-bg);
  color: var(--role-date-text);
  border: 1px solid var(--role-date-border);
}

.badge-role-calcgroup {
  background-color: var(--role-calcgroup-bg);
  color: var(--role-calcgroup-text);
  border: 1px solid var(--role-calcgroup-border);
}

.badge-role-utility {
  background-color: var(--role-utility-bg);
  color: var(--role-utility-text);
  border: 1px solid var(--role-utility-border);
}

/* Column Origin Badges */
.badge-imported {
  background-color: var(--col-imported-bg);
  color: var(--col-imported-text);
  border: 1px solid var(--col-imported-border);
}

.badge-calc {
  background-color: var(--col-calc-bg);
  color: var(--col-calc-text);
  border: 1px solid var(--col-calc-border);
  text-decoration: none;
  cursor: pointer;
  transition: all 0.15s ease;
}

.badge-calc:hover {
  text-decoration: underline;
  border-color: var(--accent);
}

.badge-key {
  background-color: var(--col-key-bg);
  color: var(--col-key-text);
  border: 1px solid var(--col-key-border);
}

.badge-type {
  background-color: var(--bg-surface-hover);
  color: var(--text-muted);
  border: 1px solid var(--border-color);
  font-family: var(--font-mono);
  font-size: 0.7rem;
}

/* Code Snippets & Containers */
.code-container {
  background-color: var(--bg-code);
  border: 1px solid var(--border-code);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin: 0.75rem 0;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.45rem 0.85rem;
  background-color: var(--bg-code-header);
  border-bottom: 1px solid var(--border-code);
  font-family: var(--font-mono);
  font-size: 0.75rem;
  color: var(--text-code-muted);
}

.code-container pre {
  padding: 1rem;
  overflow-x: auto;
  margin: 0;
  background-color: transparent;
}

.code-container code {
  font-family: var(--font-mono);
  font-size: 0.85rem;
  color: var(--text-code);
  line-height: 1.5;
  background: transparent;
  border: none;
  padding: 0;
}

.copy-btn {
  background-color: var(--bg-copy-btn);
  border: 1px solid var(--border-copy-btn);
  color: var(--text-copy-btn);
  padding: 0.2rem 0.55rem;
  border-radius: var(--radius-sm);
  font-size: 0.75rem;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}

.copy-btn:hover {
  background-color: var(--bg-copy-btn-hover);
  color: var(--text-copy-btn);
}

/* Inline Code Elements */
:not(pre) > code {
  font-family: var(--font-mono);
  font-size: 0.825em;
  background-color: var(--bg-surface-hover);
  color: var(--text-main);
  padding: 0.15rem 0.35rem;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

/* Visual Container Cards */
.visual-card {
  background-color: var(--bg-surface);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  margin-bottom: 1.25rem;
  overflow: hidden;
}

.visual-card-header {
  padding: 0.75rem 1rem;
  background-color: var(--bg-body);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.visual-card-body {
  padding: 1rem;
  display: flex;
  gap: 1.5rem;
}

.visual-minimap-col {
  width: 260px;
  flex-shrink: 0;
}

.visual-minimap-img {
  width: 100%;
  height: auto;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: transparent;
  display: block;
}

.visual-specs-col {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.spec-group-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-muted);
  margin-bottom: 0.35rem;
}

.spec-list {
  list-style: none;
  font-size: 0.825rem;
}

.spec-list li {
  margin-bottom: 0.25rem;
}

/* Responsive Breakpoints */
@media (max-width: 900px) {
  .wiki-layout {
    flex-direction: column;
  }
  .wiki-sidebar {
    width: 100%;
    height: auto;
    position: relative;
  }
  .visual-card-body {
    flex-direction: column;
  }
  .visual-minimap-col {
    width: 100%;
  }
  .wiki-article {
    padding: 1.25rem;
  }
}
"""

# Zero-JS Policy: PBIP HTML documentation is 100% pure HTML5 and CSS.
# No JavaScript files or script tags are emitted or executed, ensuring full compliance
# with strict enterprise SharePoint Modern sandboxes, air-gapped intranets, and CSP policies.
APP_JS = ""


def get_html_css() -> str:
    """Returns the core CSS stylesheet for the HTML documentation portal."""
    return STYLE_CSS


def get_html_js() -> str:
    """
    Returns the client-side JavaScript for the HTML documentation portal.
    In Zero-JS mode, this always returns an empty string as no JavaScript is used.
    """
    return APP_JS

