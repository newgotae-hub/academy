const tabs = Array.from(document.querySelectorAll("[data-target]"));
const cases = Array.from(document.querySelectorAll("[data-case]"));
const highlightToggle = document.querySelector("[data-toggle-highlights]");
const slots = Array.from(document.querySelectorAll(".full-slot"));

function selectCase(id) {
  tabs.forEach((tab) => {
    tab.classList.toggle("is-active", tab.dataset.target === id);
  });

  cases.forEach((item) => {
    item.classList.toggle("is-active", item.id === id);
  });

  const active = document.getElementById(id);
  if (active) {
    active.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

tabs.forEach((tab) => {
  tab.addEventListener("click", () => selectCase(tab.dataset.target));
});

highlightToggle?.addEventListener("click", () => {
  document.body.classList.toggle("no-highlight");
  highlightToggle.textContent = document.body.classList.contains("no-highlight")
    ? "하이라이트 켜기"
    : "하이라이트";
});

const observer = new IntersectionObserver(
  (entries) => {
    const visible = entries
      .filter((entry) => entry.isIntersecting)
      .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

    if (!visible) return;

    tabs.forEach((tab) => {
      tab.classList.toggle("is-active", tab.dataset.target === visible.target.id);
    });
  },
  { threshold: [0.45, 0.7] },
);

cases.forEach((item) => observer.observe(item));

slots.forEach((slot, index) => {
  const currentCase = slot.closest("[data-case]");
  const side = slot.closest(".original") ? "original" : "exam";
  const key = `kwangyoung-fulltext:${currentCase?.id ?? "case"}:${side}:${index}`;

  slot.contentEditable = "true";
  slot.spellcheck = false;
  slot.tabIndex = 0;
  slot.dataset.placeholder = slot.textContent.trim();
  slot.textContent = localStorage.getItem(key) || "";

  slot.addEventListener("input", () => {
    localStorage.setItem(key, slot.textContent);
  });
});

async function loadLocalFullText() {
  try {
    const response = await fetch("./fulltext.local.json", { cache: "no-store" });
    if (!response.ok) return;
    const data = await response.json();

    slots.forEach((slot, index) => {
      const currentCase = slot.closest("[data-case]");
      const side = slot.closest(".original") ? "original" : "exam";
      const caseId = currentCase?.id;
      const key = `kwangyoung-fulltext:${caseId ?? "case"}:${side}:${index}`;
      const value = data?.[caseId]?.[side];

      if (!value) return;
      if (localStorage.getItem(key)) return;

      slot.textContent = value;
      localStorage.setItem(key, value);
    });
  } catch {
    // The page also works without the local-only full text JSON.
  }
}

loadLocalFullText();
