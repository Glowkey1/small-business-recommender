# apply_mobile_fixes.py
"""
Applies mobile responsiveness fixes in-place:
1. static/js/main.js (hamburger toggle, outside click, Escape close, wizard, location cascade)
2. static/css/main.css (mobile-first breakpoints, 44px touch targets, 16px inputs, non-overflowing cards)
3. templates/ (removes sub-12px text nodes, links base layout correctly)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
print("Applying mobile responsiveness fixes in-place...")

UPDATES = {}

# ----------------------------------------------------------------------
# 1. static/js/main.js
# ----------------------------------------------------------------------
UPDATES["static/js/main.js"] = r'''// Mobile Navigation, Outside-Click Dismiss, Escape Key, and Wizard Logic
document.addEventListener("DOMContentLoaded", function () {
  // 1. Mobile Menu Toggle with Outside Click & Escape Handlers
  const navToggle = document.getElementById("navToggle");
  const primaryNav = document.getElementById("primaryNav");

  if (navToggle && primaryNav) {
    function openMenu() {
      primaryNav.classList.add("is-open");
      navToggle.setAttribute("aria-expanded", "true");
    }

    function closeMenu() {
      primaryNav.classList.remove("is-open");
      navToggle.setAttribute("aria-expanded", "false");
    }

    navToggle.addEventListener("click", function (e) {
      e.stopPropagation();
      const isOpen = primaryNav.classList.contains("is-open");
      if (isOpen) {
        closeMenu();
      } else {
        openMenu();
      }
    });

    // Close on outside click
    document.addEventListener("click", function (e) {
      if (primaryNav.classList.contains("is-open")) {
        if (!primaryNav.contains(e.target) && e.target !== navToggle && !navToggle.contains(e.target)) {
          closeMenu();
        }
      }
    });

    // Close on Escape key and return focus to toggle button
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && primaryNav.classList.contains("is-open")) {
        closeMenu();
        navToggle.focus();
      }
    });
  }

  // 2. Cascading Philippine Locations
  const regSelect = document.getElementById("regionSelect");
  const provSelect = document.getElementById("provinceSelect");
  const citySelect = document.getElementById("citySelect");

  if (regSelect && provSelect && citySelect && window.LOCATION_HIERARCHY) {
    const data = window.LOCATION_HIERARCHY;

    regSelect.addEventListener("change", function () {
      const regCode = this.value;
      provSelect.innerHTML = '<option value="">-- Choose Province --</option>';
      citySelect.innerHTML = '<option value="">-- Choose Municipality --</option>';

      if (!regCode) return;
      const regObj = data.regions.find(r => r.code === regCode);
      if (regObj && regObj.provinces) {
        regObj.provinces.forEach(p => {
          const opt = document.createElement("option");
          opt.value = p.code;
          opt.textContent = p.name;
          provSelect.appendChild(opt);
        });
      }
    });

    provSelect.addEventListener("change", function () {
      const regCode = regSelect.value;
      const provCode = this.value;
      citySelect.innerHTML = '<option value="">-- Choose Municipality --</option>';

      if (!provCode) return;
      const regObj = data.regions.find(r => r.code === regCode);
      if (regObj) {
        const provObj = regObj.provinces.find(p => p.code === provCode);
        if (provObj && provObj.cities) {
          provObj.cities.forEach(c => {
            const opt = document.createElement("option");
            opt.value = c.code;
            opt.textContent = c.name;
            citySelect.appendChild(opt);
          });
        }
      }
    });
  }

  // 3. Multi-Step Wizard Flow
  let currentStep = 1;
  const maxStep = 5;

  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const btnSubmit = document.getElementById("btnSubmit");

  function updateWizard() {
    for (let i = 1; i <= maxStep; i++) {
      const sec = document.getElementById("section" + i);
      const ind = document.querySelector(`.wizard-step-indicator[data-step="${i}"]`);
      if (sec) sec.classList.toggle("active", i === currentStep);
      if (ind) ind.classList.toggle("active", i === currentStep);
    }

    if (btnPrev) btnPrev.style.display = currentStep > 1 ? "inline-flex" : "none";
    if (btnNext) btnNext.style.display = currentStep < maxStep ? "inline-flex" : "none";
    if (btnSubmit) btnSubmit.style.display = currentStep === maxStep ? "inline-flex" : "none";

    // Populate review summary step
    if (currentStep === maxStep) {
      const cap = document.getElementById("capInput")?.value || "10000";
      const checkedSkills = Array.from(document.querySelectorAll('input[name="skills"]:checked')).map(cb => cb.value);
      const exp = document.querySelector('select[name="experience"]')?.value || "Beginner";
      const time = document.querySelector('select[name="available_time"]')?.value || "5-6 hours/day";
      const checkedSetups = Array.from(document.querySelectorAll('input[name="setup"]:checked')).map(cb => cb.value);
      const cityOpt = citySelect?.options[citySelect.selectedIndex]?.text || "Not selected";

      const elCap = document.getElementById("revCap");
      const elSkills = document.getElementById("revSkills");
      const elExp = document.getElementById("revExp");
      const elTime = document.getElementById("revTime");
      const elSetup = document.getElementById("revSetup");
      const elLoc = document.getElementById("revLoc");

      if (elCap) elCap.textContent = Number(cap).toLocaleString();
      if (elSkills) elSkills.textContent = checkedSkills.length ? checkedSkills.join(", ") : "No skills selected";
      if (elExp) elExp.textContent = exp;
      if (elTime) elTime.textContent = time;
      if (elSetup) elSetup.textContent = checkedSetups.join(", ") || "None";
      if (elLoc) elLoc.textContent = cityOpt;
    }
  }

  if (btnNext && btnPrev) {
    btnNext.addEventListener("click", function () {
      if (currentStep < maxStep) {
        currentStep++;
        updateWizard();
      }
    });

    btnPrev.addEventListener("click", function () {
      if (currentStep > 1) {
        currentStep--;
        updateWizard();
      }
    });
  }

  // 4. Skill Filter
  const skillSearch = document.getElementById("skillSearch");
  if (skillSearch) {
    skillSearch.addEventListener("input", function () {
      const q = this.value.toLowerCase();
      document.querySelectorAll(".skill-pill").forEach(p => {
        p.style.display = p.textContent.toLowerCase().includes(q) ? "inline-flex" : "none";
      });
    });
  }
});
'''

# ----------------------------------------------------------------------
# 2. static/css/main.css
# ----------------------------------------------------------------------
UPDATES["static/css/main.css"] = r'''@charset "UTF-8";

:root {
  --color-canvas: #f6f4ee;
  --color-surface: #ffffff;
  --color-surface-soft: #edeae0;
  --color-ink: #1c1f1d;
  --color-ink-muted: #5c635d;
  --color-border: #dcd7c9;
  --color-brand: #0f4c3a;
  --color-brand-hover: #0a3528;
  --color-accent: #c85a17;
  --color-badge-bg: #e6ede8;
  --color-badge-text: #0f4c3a;

  --font-display: 'Space Grotesk', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-body: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  --font-mono: 'Space Mono', monospace;

  --shadow-flat: 3px 3px 0px var(--color-ink);
  --shadow-flat-sm: 2px 2px 0px var(--color-ink);
}

*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

html, body {
  overflow-x: hidden;
  max-width: 100%;
  width: 100%;
}

body {
  font-family: var(--font-body);
  background-color: var(--color-canvas);
  color: var(--color-ink);
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
  padding-bottom: env(safe-area-inset-bottom, 20px);
}

a:focus-visible, button:focus-visible, input:focus-visible, select:focus-visible, textarea:focus-visible {
  outline: 2px solid var(--color-brand);
  outline-offset: 2px;
}

/* Header & Collapsible Navigation */
.header {
  background: var(--color-surface);
  border-bottom: 2px solid var(--color-ink);
  padding: 10px 20px;
  position: sticky;
  top: 0;
  z-index: 1000;
  width: 100%;
}

.nav-container {
  max-width: 1040px;
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: center;
  position: relative;
  width: 100%;
}

.brand {
  font-family: var(--font-display);
  font-size: 19px;
  font-weight: 700;
  color: var(--color-ink);
  text-decoration: none;
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 44px;
  min-width: 44px;
}

.brand-dot {
  width: 8px;
  height: 8px;
  background: var(--color-accent);
  display: inline-block;
  flex-shrink: 0;
}

.nav-toggle {
  display: none;
  background: transparent;
  border: 1.5px solid var(--color-ink);
  width: 44px;
  height: 44px;
  min-width: 44px;
  min-height: 44px;
  padding: 8px;
  cursor: pointer;
  flex-direction: column;
  justify-content: space-around;
  align-items: center;
  border-radius: 0;
  flex-shrink: 0;
}

.nav-toggle span {
  display: block;
  width: 24px;
  height: 2px;
  background: var(--color-ink);
}

nav.nav-menu {
  display: flex;
  align-items: center;
  gap: 12px;
}

nav.nav-menu a {
  text-decoration: none;
  color: var(--color-ink);
  font-size: 14px;
  font-weight: 600;
  min-height: 44px;
  min-width: 44px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 10px 14px;
  border-radius: 0;
}

nav.nav-menu a:hover {
  color: var(--color-brand);
}

@media (max-width: 760px) {
  .nav-toggle {
    display: flex;
  }

  nav.nav-menu {
    display: none;
    position: absolute;
    top: calc(100% + 10px);
    left: -20px;
    right: -20px;
    background: var(--color-surface);
    border-bottom: 2px solid var(--color-ink);
    border-top: 1px solid var(--color-border);
    flex-direction: column;
    padding: 12px 20px;
    gap: 4px;
    align-items: stretch;
    box-shadow: var(--shadow-flat);
    z-index: 1000;
  }

  nav.nav-menu.is-open {
    display: flex;
  }

  nav.nav-menu a {
    width: 100%;
    justify-content: flex-start;
    padding: 12px 14px;
    border-bottom: 1px solid var(--color-border);
  }

  nav.nav-menu a:last-child {
    border-bottom: none;
  }
}

/* Layout Containers & Cards */
.container {
  max-width: 1040px;
  margin: 32px auto;
  padding: 0 20px;
  width: 100%;
  min-width: 0;
}

.card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  padding: 28px;
  margin-bottom: 24px;
  width: 100%;
  min-width: 0;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.card-editorial {
  border: 1.5px solid var(--color-ink);
  box-shadow: var(--shadow-flat);
  background: var(--color-surface);
}

@media (max-width: 600px) {
  .container {
    margin: 16px auto;
    padding: 0 16px;
  }

  .card, .card-editorial {
    padding: 18px 16px;
    margin-bottom: 16px;
  }
}

/* Typography Scale */
h1, h2, h3, h4 {
  font-family: var(--font-display);
  color: var(--color-ink);
  font-weight: 700;
  line-height: 1.2;
  overflow-wrap: anywhere;
  word-break: break-word;
}

h1 { font-size: clamp(24px, 5vw, 38px); letter-spacing: -1px; }
h2 { font-size: clamp(20px, 4vw, 26px); margin-bottom: 12px; }
h3 { font-size: 19px; }
h4 { font-size: 16px; }
p { font-size: 15px; overflow-wrap: anywhere; }

.subtitle {
  color: var(--color-ink-muted);
  font-size: 15px;
  margin-bottom: 20px;
  line-height: 1.5;
}

.mono-tag {
  font-family: var(--font-mono);
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--color-brand);
  display: inline-block;
  margin-bottom: 8px;
  font-weight: 700;
}

/* Touch-Target Buttons (>= 44x44px) */
.btn {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  padding: 12px 20px;
  min-height: 44px;
  min-width: 44px;
  border-radius: 0;
  border: 1.5px solid var(--color-ink);
  cursor: pointer;
  text-decoration: none;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-sizing: border-box;
}

.btn-primary {
  background-color: var(--color-brand);
  color: var(--color-surface);
  box-shadow: var(--shadow-flat-sm);
}

.btn-primary:hover {
  background-color: var(--color-brand-hover);
}

.btn-secondary {
  background: var(--color-surface);
  color: var(--color-ink);
  box-shadow: var(--shadow-flat-sm);
}

.btn-block {
  width: 100%;
  display: flex;
}

.btn-sm {
  padding: 10px 16px;
  font-size: 13px;
  min-height: 44px;
  min-width: 44px;
}

/* Form Controls (16px font to prevent iOS zoom, 48px min-height) */
.form-group {
  margin-bottom: 20px;
  width: 100%;
}

.form-group > label {
  display: block;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 13px;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-control {
  width: 100%;
  min-height: 48px;
  padding: 12px 14px;
  font-family: var(--font-body);
  font-size: 16px;
  border: 1.5px solid var(--color-ink);
  background: var(--color-surface);
  color: var(--color-ink);
  border-radius: 0;
  box-sizing: border-box;
}

.form-control:focus {
  outline: 2px solid var(--color-brand);
}

/* Skills Grid & Pill Rules (Explicit normal case, 14px, 44px target) */
.skills-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 150px), 1fr));
  gap: 8px;
  max-height: 260px;
  overflow-y: auto;
  padding: 10px;
  background: var(--color-surface-soft);
  border: 1.5px solid var(--color-ink);
  width: 100%;
  box-sizing: border-box;
}

.form-group label.skill-pill,
label.skill-pill,
.skill-pill {
  font-family: var(--font-body) !important;
  font-size: 14px !important;
  text-transform: none !important;
  font-weight: 500 !important;
  letter-spacing: normal !important;
  min-height: 44px;
  min-width: 44px;
  background: var(--color-surface);
  padding: 10px 12px;
  cursor: pointer;
  border: 1px solid var(--color-border);
  display: inline-flex;
  align-items: center;
  gap: 8px;
  user-select: none;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
}

.skill-pill input[type="checkbox"] {
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  accent-color: var(--color-brand);
  cursor: pointer;
  flex-shrink: 0;
}

.setup-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(100%, 160px), 1fr));
  gap: 10px;
  width: 100%;
}

.form-group label.setup-target,
label.setup-target,
.setup-target {
  font-family: var(--font-body) !important;
  font-size: 14px !important;
  text-transform: none !important;
  font-weight: 500 !important;
  letter-spacing: normal !important;
  min-height: 44px;
  min-width: 44px;
  display: inline-flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  cursor: pointer;
  width: 100%;
  box-sizing: border-box;
  margin: 0;
}

.setup-target input[type="checkbox"] {
  width: 20px;
  height: 20px;
  min-width: 20px;
  min-height: 20px;
  accent-color: var(--color-brand);
  cursor: pointer;
  flex-shrink: 0;
}

/* Results Recommendation Cards */
.business-card {
  background: var(--color-surface);
  border: 1.5px solid var(--color-ink);
  box-shadow: var(--shadow-flat);
  margin-bottom: 20px;
  padding: 24px;
  display: grid;
  grid-template-columns: 140px 1fr 180px;
  gap: 20px;
  align-items: center;
  width: 100%;
  min-width: 0;
  box-sizing: border-box;
}

.biz-cost-col {
  border-right: 1px dashed var(--color-border);
  padding-right: 16px;
  text-align: left;
  min-width: 0;
}

.biz-cost-label {
  font-family: var(--font-mono);
  font-size: 12px;
  text-transform: uppercase;
  color: var(--color-ink-muted);
}

.biz-cost-val {
  font-family: var(--font-mono);
  font-size: 19px;
  font-weight: 700;
  color: var(--color-ink);
}

.biz-main-col {
  min-width: 0;
  overflow-wrap: anywhere;
}

.biz-main-col h3 {
  font-size: 19px;
  margin-bottom: 4px;
}

.biz-meta {
  font-size: 13px;
  color: var(--color-ink-muted);
  margin-bottom: 6px;
}

.skills-match {
  font-size: 13px;
  color: var(--color-brand);
  font-weight: 600;
}

.biz-score-col {
  text-align: right;
  border-left: 1px dashed var(--color-border);
  padding-left: 16px;
  min-width: 0;
}

.score-num {
  font-family: var(--font-mono);
  font-size: 32px;
  font-weight: 700;
  color: var(--color-brand);
  line-height: 1;
  margin-bottom: 6px;
}

.score-lbl {
  font-size: 12px;
  text-transform: uppercase;
  color: var(--color-ink-muted);
  font-family: var(--font-mono);
  margin-bottom: 10px;
}

@media (max-width: 760px) {
  .business-card {
    grid-template-columns: 1fr;
    gap: 14px;
    padding: 16px;
  }

  .biz-cost-col {
    border-right: none;
    border-bottom: 1px dashed var(--color-border);
    padding-right: 0;
    padding-bottom: 10px;
  }

  .biz-score-col {
    border-left: none;
    border-top: 1px dashed var(--color-border);
    padding-left: 0;
    padding-top: 12px;
    text-align: left;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;
    flex-wrap: wrap;
  }

  .biz-score-col .score-num {
    font-size: 28px;
  }

  .biz-score-col .btn {
    width: 100%;
  }
}

/* Phase Cards & Pathway */
.phase-card {
  border: 1.5px solid var(--color-ink);
  border-left: 6px solid var(--color-brand);
  background: var(--color-surface);
  padding: 18px 20px;
  margin-bottom: 14px;
  min-width: 0;
  overflow-wrap: anywhere;
}

.phase-title {
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--color-brand);
  margin-bottom: 4px;
}

.badge {
  font-family: var(--font-mono);
  background: var(--color-badge-bg);
  color: var(--color-badge-text);
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 700;
  text-transform: uppercase;
  border: 1px solid var(--color-brand);
  display: inline-block;
}

.alert {
  padding: 14px 18px;
  border: 1.5px solid var(--color-ink);
  margin-bottom: 20px;
  font-size: 14px;
  min-height: 44px;
  overflow-wrap: anywhere;
}

.alert-info { background: var(--color-surface-soft); border-left: 6px solid var(--color-ink); }
.alert-danger { background: #fbeae8; border-left: 6px solid var(--color-accent); color: #851e06; }
.alert-success { background: #eaf3ed; border-left: 6px solid var(--color-brand); color: #0f4c3a; }

/* Responsive Grid Systems */
.grid-2, .grid-3, .grid-4 {
  display: grid;
  gap: 16px;
  width: 100%;
  min-width: 0;
}

.grid-2 { grid-template-columns: 1fr 1fr; }
.grid-3 { grid-template-columns: repeat(3, 1fr); }
.grid-4 { grid-template-columns: repeat(4, 1fr); }

.grid-2 > *, .grid-3 > *, .grid-4 > * {
  min-width: 0;
}

@media (max-width: 760px) {
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
  }
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--color-border);
  gap: 10px;
  flex-wrap: wrap;
}

/* Wizard Steps & Sticky Navigation Bar */
.wizard-progress {
  display: flex;
  border-bottom: 1.5px solid var(--color-ink);
  margin-bottom: 20px;
  overflow-x: auto;
  width: 100%;
}

.wizard-step-indicator {
  padding: 10px 14px;
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--color-ink-muted);
  border-bottom: 3px solid transparent;
  white-space: nowrap;
}

.wizard-step-indicator.active {
  color: var(--color-brand);
  font-weight: 700;
  border-bottom-color: var(--color-brand);
}

.wizard-section {
  display: none;
  width: 100%;
}

.wizard-section.active {
  display: block;
}

.wizard-nav-bar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-top: 24px;
  padding-top: 12px;
  border-top: 1px solid var(--color-border);
  background: var(--color-surface);
}

@media (max-width: 600px) {
  .wizard-nav-bar {
    position: sticky;
    bottom: 0;
    z-index: 100;
    padding: 12px 0 calc(12px + env(safe-area-inset-bottom, 0px));
    border-top: 2px solid var(--color-ink);
    background: var(--color-surface);
    margin-left: -16px;
    margin-right: -16px;
    padding-left: 16px;
    padding-right: 16px;
  }

  .wizard-nav-bar .btn {
    flex: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0.001ms !important;
    transition-duration: 0.001ms !important;
  }
}
'''

# ----------------------------------------------------------------------
# 3. templates/base.html (Viewport & theme-color meta, accessible nav)
# ----------------------------------------------------------------------
UPDATES["templates/base.html"] = r'''<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
  <meta name="theme-color" content="#0f4c3a">
  <title>{% block title %}SmallBiz Match{% endblock %}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&family=Space+Mono:wght@400;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="/static/css/main.css">
</head>
<body>
  <header class="header">
    <div class="nav-container">
      <a href="/" class="brand">
        <span class="brand-dot"></span>
        SMALLBIZ MATCH
      </a>

      <button class="nav-toggle" id="navToggle" aria-label="Toggle Navigation" aria-expanded="false" aria-controls="primaryNav">
        <span></span>
        <span></span>
        <span></span>
      </button>

      <nav id="primaryNav" class="nav-menu">
        <a href="/find">Find Ideas</a>
        {% if current_user.is_authenticated %}
          <a href="/dashboard">Dashboard</a>
          <a href="/profile">Profile</a>
          <a href="/history">History</a>
          {% if current_user.role == 'admin' %}
            <a href="/admin/metrics">ML Admin</a>
          {% endif %}
          <a href="/logout">Logout</a>
        {% else %}
          <a href="/login">Login</a>
          <a href="/register" class="btn btn-sm btn-primary">Register</a>
        {% endif %}
      </nav>
    </div>
  </header>

  <main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for cat, msg in messages %}
          <div class="alert alert-{{ cat }}">{{ msg }}</div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
  </main>

  <script src="/static/js/main.js"></script>
</body>
</html>
'''

# ----------------------------------------------------------------------
# 4. templates/user/recommendations_form.html (>=12px labels & inputs)
# ----------------------------------------------------------------------
UPDATES["templates/user/recommendations_form.html"] = r'''{% extends "base.html" %}
{% block title %}Find Business Ideas — SmallBiz Match{% endblock %}

{% block content %}
<div class="card card-editorial">
  <span class="mono-tag">PHILIPPINE HYBRID RECOMMENDER // STEP-BY-STEP</span>
  <h2 style="margin: 8px 0 12px 0;">Find Your Compatible Small Business</h2>
  <p class="subtitle">Complete the form below to discover businesses that fit your budget, background, and local market.</p>

  {% if errors %}
    <div class="alert alert-danger">
      <strong>Please correct the following errors:</strong>
      <ul style="margin-left: 20px; margin-top: 6px;">
        {% for err in errors %}
          <li>{{ err }}</li>
        {% endfor %}
      </ul>
    </div>
  {% endif %}

  <div class="wizard-progress" id="wizardProgress">
    <div class="wizard-step-indicator active" data-step="1">1. Capital</div>
    <div class="wizard-step-indicator" data-step="2">2. Skills</div>
    <div class="wizard-step-indicator" data-step="3">3. Background</div>
    <div class="wizard-step-indicator" data-step="4">4. Location</div>
    <div class="wizard-step-indicator" data-step="5">5. Review</div>
  </div>

  <form action="/find" method="POST" id="recForm">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <!-- STEP 1: Capital -->
    <div class="wizard-section active" id="section1">
      <div class="form-group">
        <label>Starting Capital (₱ PHP)</label>
        <input type="number" name="capital" id="capInput" value="{{ form_data.capital if form_data.capital is defined else '10000' }}" min="0" max="100000000" step="500" required class="form-control">
        <small style="color: var(--color-ink-muted); font-size: 13px; display: block; margin-top: 6px;">
          * Hard Constraint: Businesses requiring more capital than this amount are strictly excluded.
        </small>
      </div>
    </div>

    <!-- STEP 2: Skills -->
    <div class="wizard-section" id="section2">
      <div class="form-group">
        <label>Select Your Skills (Multi-select)</label>
        <input type="text" id="skillSearch" placeholder="Filter skills..." class="form-control" style="margin-bottom: 10px;">
        <div class="skills-grid" id="skillsGrid">
          {% for s in skills %}
            <label class="skill-pill">
              <input type="checkbox" name="skills" value="{{ s }}" {% if form_data.skills and s in form_data.skills %}checked{% endif %}>
              <span>{{ s }}</span>
            </label>
          {% endfor %}
        </div>
        <small style="color: var(--color-ink-muted); font-size: 13px; display: block; margin-top: 6px;">
          Leave unchecked if you are starting with no specific business skills.
        </small>
      </div>
    </div>

    <!-- STEP 3: Experience, Time, Setup -->
    <div class="wizard-section" id="section3">
      <div class="grid-2">
        <div class="form-group">
          <label>Experience Level</label>
          <select name="experience" class="form-control">
            <option value="Beginner" {% if form_data.experience == 'Beginner' %}selected{% endif %}>Beginner (First-time entrepreneur)</option>
            <option value="Intermediate" {% if form_data.experience == 'Intermediate' %}selected{% endif %}>Intermediate (Hands-on experience)</option>
            <option value="Experienced" {% if form_data.experience == 'Experienced' %}selected{% endif %}>Experienced (Industry veteran)</option>
          </select>
        </div>

        <div class="form-group">
          <label>Available Daily Time</label>
          <select name="available_time" class="form-control">
            <option value="1-2 hours/day" {% if form_data.available_time == '1-2 hours/day' %}selected{% endif %}>1-2 hours/day (Micro side-hustle)</option>
            <option value="3-4 hours/day" {% if form_data.available_time == '3-4 hours/day' %}selected{% endif %}>3-4 hours/day (Part-time)</option>
            <option value="5-6 hours/day" {% if not form_data.available_time or form_data.available_time == '5-6 hours/day' %}selected{% endif %}>5-6 hours/day (Dedicated)</option>
            <option value="7-8 hours/day" {% if form_data.available_time == '7-8 hours/day' %}selected{% endif %}>7-8 hours/day (Full-time)</option>
            <option value="Full-time" {% if form_data.available_time == 'Full-time' %}selected{% endif %}>Full-time (8+ hours/day)</option>
          </select>
        </div>
      </div>

      <div class="form-group">
        <label>Preferred Business Setup (Select one or more)</label>
        <div class="setup-grid">
          {% set sel_setups = form_data.setup if form_data.setup else ['Online / Home-Based'] %}
          <label class="setup-target"><input type="checkbox" name="setup" value="Online" {% if 'Online' in sel_setups or 'Online / Home-Based' in sel_setups %}checked{% endif %}> <span>Online</span></label>
          <label class="setup-target"><input type="checkbox" name="setup" value="Home-Based" {% if 'Home-Based' in sel_setups or 'Online / Home-Based' in sel_setups %}checked{% endif %}> <span>Home-Based</span></label>
          <label class="setup-target"><input type="checkbox" name="setup" value="Physical Store" {% if 'Physical Store' in sel_setups %}checked{% endif %}> <span>Physical Store</span></label>
          <label class="setup-target"><input type="checkbox" name="setup" value="Service / Mobile" {% if 'Service / Mobile' in sel_setups %}checked{% endif %}> <span>Service / Mobile</span></label>
        </div>
      </div>
    </div>

    <!-- STEP 4: Cascading Location -->
    <div class="wizard-section" id="section4">
      <div class="form-group">
        <label>Philippine Location (Cascading Selection)</label>
        <div class="grid-3">
          <div>
            <label style="font-size: 12px; margin-bottom: 4px;">1. Region</label>
            <select id="regionSelect" class="form-control" aria-label="Select Region">
              <option value="">-- Choose Region --</option>
              {% for reg in hierarchy.regions %}
                <option value="{{ reg.code }}">{{ reg.name }}</option>
              {% endfor %}
            </select>
          </div>
          <div>
            <label style="font-size: 12px; margin-bottom: 4px;">2. Province</label>
            <select id="provinceSelect" class="form-control" aria-label="Select Province">
              <option value="">-- Choose Province --</option>
            </select>
          </div>
          <div>
            <label style="font-size: 12px; margin-bottom: 4px;">3. City / Municipality</label>
            <select name="location" id="citySelect" class="form-control" required aria-label="Select Municipality">
              <option value="">-- Choose Municipality --</option>
              {% for reg in hierarchy.regions %}
                {% for prov in reg.provinces %}
                  <optgroup label="{{ reg.name }} — {{ prov.name }}">
                    {% for city in prov.cities %}
                      <option value="{{ city.code }}" {% if form_data.location == city.code %}selected{% endif %}>{{ city.name }}</option>
                    {% endfor %}
                  </optgroup>
                {% endfor %}
              {% endfor %}
            </select>
          </div>
        </div>
        <small style="color: var(--color-ink-muted); font-size: 13px; display: block; margin-top: 6px;">
          Coverage: 250 municipalities in 9 regions in the current dataset. Uses PSGC 10-digit codes.
        </small>
      </div>
    </div>

    <!-- STEP 5: Review -->
    <div class="wizard-section" id="section5">
      <h3 style="font-size: 18px; margin-bottom: 12px;">Review Your Submission</h3>
      <div class="card" style="background: var(--color-surface-soft); padding: 16px; margin-bottom: 20px;">
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Capital:</strong> ₱<span id="revCap">10,000</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Selected Skills:</strong> <span id="revSkills">None</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Experience:</strong> <span id="revExp">Beginner</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Available Time:</strong> <span id="revTime">5-6 hours/day</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Setups:</strong> <span id="revSetup">Online / Home-Based</span></div>
        <div style="font-size: 14px;"><strong>Location:</strong> <span id="revLoc">Please select a municipality</span></div>
      </div>
    </div>

    <div class="wizard-nav-bar">
      <button type="button" class="btn btn-secondary" id="btnPrev" style="display: none;">Back</button>
      <button type="button" class="btn btn-primary" id="btnNext">Next</button>
      <button type="submit" class="btn btn-primary" id="btnSubmit" style="display: none;">GET RECOMMENDATIONS</button>
    </div>
  </form>
</div>

<script>
window.LOCATION_HIERARCHY = {{ hierarchy | tojson }};
</script>
{% endblock %}
'''

# ----------------------------------------------------------------------
# 5. templates/user/recommendations.html (>=12px text nodes)
# ----------------------------------------------------------------------
UPDATES["templates/user/recommendations.html"] = r'''{% extends "base.html" %}
{% block title %}Top Recommendations — SmallBiz Match{% endblock %}

{% block content %}
<div style="display: flex; justify-content: space-between; align-items: flex-end; margin-bottom: 24px; flex-wrap: wrap; gap: 16px;">
  <div>
    <span class="mono-tag">HYBRID FEASIBILITY MATCHES // ₱{{ "{:,.2f}".format(profile.capital) }} CAPITAL</span>
    <h2>Recommended Business Ideas</h2>
    <p class="subtitle" style="margin-bottom: 0;">
      Location: <strong>{{ profile.location_display or 'Philippine Dataset' }}</strong> · Experience: <strong>{{ profile.experience }}</strong>
    </p>
  </div>
  <a href="/find" class="btn btn-secondary btn-sm">Adjust Filters</a>
</div>

<div class="alert alert-info" style="font-size: 13.5px;">
  <strong>Notice:</strong> Recommendation Score is a weighted match of your inputs, not a probability of success. Time compatibility is estimated from the business setup and operational complexity.
</div>

{% for r in recs %}
  <div class="business-card">
    <div class="biz-cost-col">
      <div class="biz-cost-label">Required Capital</div>
      <div class="biz-cost-val">₱{{ "{:,.0f}".format(r.min_capital) }}</div>
      <div style="font-size: 12px; color: var(--color-ink-muted); margin-top: 4px;">{{ r.startup_cost }}</div>
    </div>

    <div class="biz-main-col">
      <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap;">
        <h3 style="margin: 0;">{{ r.business_type }}</h3>
        <span class="badge">{{ r.category }}</span>
        {% if r.market_category %}
          <span class="badge" style="background: #fdf3e7; color: var(--color-accent); border-color: var(--color-accent);">OSM: {{ r.market_category }}</span>
        {% endif %}
      </div>
      <div class="biz-meta">
        Setup: <strong>{{ r.business_setup }}</strong> · Required Staff: <strong>{{ r.people_needed }}</strong> · Level: <strong>{{ r.experience_level }}</strong>
      </div>

      <div style="margin: 6px 0;">
        {% if r.matched_skills %}
          <div class="skills-match">✓ Matching Skills: {{ r.matched_skills | join(', ') }}</div>
        {% else %}
          <div style="font-size: 13px; color: var(--color-ink-muted);">No skills selected</div>
        {% endif %}
      </div>

      <div style="font-size: 13px; color: var(--color-ink-muted); margin: 6px 0; background: var(--color-surface-soft); padding: 8px 10px; border-left: 3px solid var(--color-brand);">
        <strong>Market Evidence:</strong> {{ r.location_evidence }}
      </div>

      <div style="margin-top: 8px;">
        <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--color-ink-muted); font-family: var(--font-mono);">Why Recommended:</span>
        <ul style="font-size: 13px; color: var(--color-ink); margin-left: 18px; margin-top: 2px;">
          {% for reason in r.reasons %}
            <li>{{ reason }}</li>
          {% endfor %}
        </ul>
      </div>

      <details style="margin-top: 10px; font-size: 13px;">
        <summary style="cursor: pointer; font-weight: 600; color: var(--color-brand); min-height: 44px; display: inline-flex; align-items: center;">View Score Breakdown</summary>
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 8px; margin-top: 8px; padding: 10px; background: var(--color-surface-soft);">
          <div>Capital: <strong>{{ r.component_scores.capital }}%</strong></div>
          <div>Skills: <strong>{{ r.component_scores.skills }}%</strong></div>
          <div>Experience: <strong>{{ r.component_scores.experience }}%</strong></div>
          <div>Setup: <strong>{{ r.component_scores.setup }}%</strong></div>
          <div>Time: <strong>{{ r.component_scores.time }}%</strong></div>
          <div>Location: <strong>{{ r.component_scores.location ~ '%' if r.component_scores.location is not none else 'Not available' }}</strong></div>
          <div>Success Model: <strong>{{ r.component_scores.success ~ '%' if r.component_scores.success is not none else 'Not available' }}</strong></div>
        </div>
      </details>
    </div>

    <div class="biz-score-col">
      <div>
        <div class="score-num">{{ r.recommendation_score }}%</div>
        <div class="score-lbl">Recommendation Score</div>
      </div>
      <a href="{{ url_for('rec.pathway', biz_id=r.id) }}" class="btn btn-primary btn-sm btn-block">View Pathway</a>
    </div>
  </div>
{% else %}
  <div class="card card-editorial" style="border-left: 6px solid var(--color-accent);">
    <h3>No business ideas in the current catalog meet your starting-capital requirement.</h3>
    <p style="margin-top: 8px;">
      All business ideas in our 119-record Philippine catalog require starting capital exceeding ₱{{ "{:,.2f}".format(profile.capital) }}.
    </p>
    <a href="/find" class="btn btn-primary" style="margin-top: 16px;">Increase Capital or Adjust Inputs</a>
  </div>
{% endfor %}

<div class="card card-editorial" id="feedback-card" style="text-align: center; margin-top: 40px; background: var(--color-surface-soft);">
  <h4 style="margin-bottom: 6px;">User satisfaction (poll)</h4>
  <p style="font-size: 14px; color: var(--color-ink-muted); margin-bottom: 16px;">
    Are these business ideas feasible with your funds and aligned with your local market?
  </p>
  <div style="display: flex; justify-content: center; gap: 14px; flex-wrap: wrap;">
    <button onclick="sendFeedback('yes')" class="btn btn-primary btn-sm">👍 Yes, Realistic Match</button>
    <button onclick="sendFeedback('no')" class="btn btn-secondary btn-sm">👎 Not a Good Fit</button>
  </div>
</div>

<script>
function sendFeedback(choice) {
  const formData = new FormData();
  formData.append('rating', choice);
  formData.append('csrf_token', '{{ csrf_token() }}');
  fetch('/feedback', {
    method: 'POST',
    headers: { 'X-CSRF-Token': '{{ csrf_token() }}' },
    body: formData
  })
  .then(res => res.text())
  .then(html => { document.getElementById('feedback-card').innerHTML = html; });
}
</script>
{% endblock %}
'''

for rel_path, content in UPDATES.items():
    p = ROOT / rel_path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content.strip() + "\n", encoding="utf-8")
    print(f"  ✓ Updated {rel_path}")

print("Mobile styles and templates updated.")