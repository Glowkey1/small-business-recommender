# fix_button.py
from pathlib import Path

ROOT = Path(__file__).resolve().parent

print("Fixing recommendation form submit button and step validation...")

# ----------------------------------------------------------------------
# 1. Update templates/user/recommendations_form.html
# ----------------------------------------------------------------------
form_path = ROOT / "templates" / "user" / "recommendations_form.html"
form_html = r'''{% extends "base.html" %}
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

  <!-- Step Progress Indicator (Clickable) -->
  <div class="wizard-progress" id="wizardProgress">
    <div class="wizard-step-indicator active" data-step="1">1. Capital</div>
    <div class="wizard-step-indicator" data-step="2">2. Skills</div>
    <div class="wizard-step-indicator" data-step="3">3. Background</div>
    <div class="wizard-step-indicator" data-step="4">4. Location</div>
    <div class="wizard-step-indicator" data-step="5">5. Review</div>
  </div>

  <form action="/find" method="POST" id="recForm" novalidate>
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">

    <!-- STEP 1: Capital -->
    <div class="wizard-section active" id="section1">
      <div class="form-group">
        <label>Starting Capital (₱ PHP)</label>
        <input type="number" name="capital" id="capInput" value="{{ form_data.capital if form_data.capital is defined and form_data.capital else '1000' }}" min="1" max="100000000" step="any" required class="form-control">
        <small style="color: var(--color-ink-muted); font-size: 13px; display: block; margin-top: 6px;">
          No minimum. You can start small with any amount, even ₱1,000.
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
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Capital:</strong> ₱<span id="revCap">1,000</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Selected Skills:</strong> <span id="revSkills">None</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Experience:</strong> <span id="revExp">Beginner</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Available Time:</strong> <span id="revTime">5-6 hours/day</span></div>
        <div style="font-size: 14px; margin-bottom: 8px;"><strong>Setups:</strong> <span id="revSetup">Online / Home-Based</span></div>
        <div style="font-size: 14px;"><strong>Location:</strong> <span id="revLoc">Please select a municipality</span></div>
      </div>
    </div>

    <!-- Wizard Navigation Buttons -->
    <div class="wizard-nav-bar">
      <button type="button" class="btn btn-secondary" id="btnPrev" style="display: none;">Back</button>
      <button type="button" class="btn btn-primary" id="btnNext">Next</button>
      <button type="button" class="btn btn-primary" id="btnSubmit" style="display: none;">GET RECOMMENDATIONS</button>
    </div>
  </form>
</div>

<script>
window.LOCATION_HIERARCHY = {{ hierarchy | tojson }};
</script>
{% endblock %}
'''
form_path.write_text(form_html.strip() + "\n", encoding="utf-8")
print("  ✓ Updated templates/user/recommendations_form.html with step='any' and novalidate")

# ----------------------------------------------------------------------
# 2. Update static/js/main.js
# ----------------------------------------------------------------------
js_path = ROOT / "static" / "js" / "main.js"
js_code = r'''// Mobile Navigation, Outside-Click Dismiss, Escape Key, Wizard, and Direct Form Submission
document.addEventListener("DOMContentLoaded", function () {
  // 1. Mobile Menu Toggle
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

    document.addEventListener("click", function (e) {
      if (primaryNav.classList.contains("is-open")) {
        if (!primaryNav.contains(e.target) && e.target !== navToggle && !navToggle.contains(e.target)) {
          closeMenu();
        }
      }
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && primaryNav.classList.contains("is-open")) {
        closeMenu();
        navToggle.focus();
      }
    });
  }

  // 2. Cascading Locations
  const regSelect = document.getElementById("regionSelect");
  const provSelect = document.getElementById("provinceSelect");
  const citySelect = document.getElementById("citySelect");

  if (regSelect && provSelect && citySelect && window.LOCATION_HIERARCHY) {
    const data = window.LOCATION_HIERARCHY;
    const regions = data.regions || [];

    regSelect.addEventListener("change", function () {
      const regCode = this.value;
      provSelect.innerHTML = '<option value="">-- Choose Province --</option>';
      citySelect.innerHTML = '<option value="">-- Choose Municipality --</option>';

      if (!regCode) return;
      const regObj = regions.find(r => r.code === regCode);
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
      const regObj = regions.find(r => r.code === regCode);
      if (regObj && regObj.provinces) {
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

  // 3. Multi-Step Wizard Flow with Step Validation
  let currentStep = 1;
  const maxStep = 5;

  const btnPrev = document.getElementById("btnPrev");
  const btnNext = document.getElementById("btnNext");
  const btnSubmit = document.getElementById("btnSubmit");
  const recForm = document.getElementById("recForm");

  function validateStep(step) {
    if (step === 1) {
      const cap = document.getElementById("capInput");
      if (!cap || !cap.value || parseFloat(cap.value) < 1) {
        alert("Please enter a starting capital of at least ₱1.");
        if (cap) cap.focus();
        return false;
      }
    }
    if (step === 4) {
      const city = document.getElementById("citySelect");
      if (!city || !city.value) {
        alert("Please select a Philippine City / Municipality in Step 4.");
        if (city) city.focus();
        return false;
      }
    }
    return true;
  }

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
      const cap = document.getElementById("capInput")?.value || "1000";
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
      if (elSkills) elSkills.textContent = checkedSkills.length ? checkedSkills.join(", ") : "None";
      if (elExp) elExp.textContent = exp;
      if (elTime) elTime.textContent = time;
      if (elSetup) elSetup.textContent = checkedSetups.join(", ") || "None";
      if (elLoc) elLoc.textContent = cityOpt;
    }
  }

  // Clickable step indicator tabs
  document.querySelectorAll(".wizard-step-indicator").forEach(ind => {
    ind.style.cursor = "pointer";
    ind.addEventListener("click", function () {
      const target = parseInt(this.getAttribute("data-step"), 10);
      if (target < currentStep || validateStep(currentStep)) {
        currentStep = target;
        updateWizard();
      }
    });
  });

  if (btnNext && btnPrev) {
    btnNext.addEventListener("click", function () {
      if (!validateStep(currentStep)) return;
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

  // Explicit submit handler that ensures all steps are valid before submitting
  if (btnSubmit && recForm) {
    btnSubmit.addEventListener("click", function (e) {
      e.preventDefault();
      if (!validateStep(1)) {
        currentStep = 1;
        updateWizard();
        return;
      }
      if (!validateStep(4)) {
        currentStep = 4;
        updateWizard();
        return;
      }
      recForm.submit();
    });
  }

  // Skill search filter
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
js_path.write_text(js_code.strip() + "\n", encoding="utf-8")
print("  ✓ Updated static/js/main.js with direct form submission and validation")

print("\nDone! Submit button is now fully functional.")