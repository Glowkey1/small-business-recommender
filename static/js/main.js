// Mobile Navigation, Outside-Click Dismiss, Escape Key, Wizard, and Direct Form Submission
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

  // 3. Multi-Step Wizard Flow with Step Validation
  let currentStep = 1;
  const maxStep = 4;

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

  // Skill search filter (hides empty field groups)
  const skillSearch = document.getElementById("skillSearch");
  if (skillSearch) {
    skillSearch.addEventListener("input", function () {
      const q = this.value.toLowerCase();
      document.querySelectorAll(".skill-field").forEach(field => {
        let visible = 0;
        field.querySelectorAll(".skill-pill").forEach(pill => {
          const matches = pill.textContent.toLowerCase().includes(q);
          pill.style.display = matches ? "inline-flex" : "none";
          if (matches) visible++;
        });
        field.style.display = visible ? "" : "none";
      });
    });
  }
});
