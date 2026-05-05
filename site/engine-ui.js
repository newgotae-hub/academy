(function () {
  const STORAGE_KEY = "ky-transform-engine:v1";

  const state = {
    analysis: null,
    generated: [],
    bank: [],
    mock: null,
    savedAt: null,
  };

  const $ = (id) => document.getElementById(id);

  document.addEventListener("DOMContentLoaded", init);

  function init() {
    if (!window.KYEngine) {
      showToast("엔진 로드에 실패했습니다. engine-core.js를 확인하세요.");
      return;
    }
    hydrate();
    initTypePicker();
    initBankTypeFilter();
    bindEvents();
    renderAll();
  }

  function bindEvents() {
    $("runAnalyze").addEventListener("click", runAnalyze);
    $("runAnalyzeTop").addEventListener("click", runAnalyze);
    $("loadSample").addEventListener("click", loadSample);
    $("runGenerate").addEventListener("click", runGenerate);
    $("saveGenerated").addEventListener("click", saveGenerated);
    $("selectAllTypes").addEventListener("click", selectAllTypes);
    $("copyAnalysisJson").addEventListener("click", copyAnalysisJson);
    $("exportGeneratedCsv").addEventListener("click", () => exportItemsCsv(state.generated, "ky-generated-items.csv"));
    $("exportGeneratedJson").addEventListener("click", () => exportJson(state.generated.map(KYEngine.serializeBankItem), "ky-generated-items.json"));
    $("exportBankCsv").addEventListener("click", () => exportItemsCsv(state.bank, "ky-bank.csv"));
    $("exportBankJson").addEventListener("click", () => exportJson(state.bank, "ky-bank.json"));
    $("clearBank").addEventListener("click", clearBank);
    $("buildMock").addEventListener("click", buildMock);
    $("exportMockCsv").addEventListener("click", exportMockCsv);
    $("exportMockJson").addEventListener("click", () => exportJson(state.mock || {}, "ky-mock-exam.json"));
    $("exportProject").addEventListener("click", exportProject);
    $("importProject").addEventListener("change", importProject);
    $("bankTypeFilter").addEventListener("change", renderBank);
    $("bankSearch").addEventListener("input", renderBank);
    $("grade").addEventListener("change", () => {
      $("preset").value = $("grade").value;
      renderStatus();
    });
    $("preset").addEventListener("change", renderStatus);
  }

  function initTypePicker() {
    const picker = $("typePicker");
    clear(picker);
    for (const [type, meta] of Object.entries(KYEngine.TYPE_META)) {
      const label = create("label", { className: "type-pill" });
      const input = create("input", { type: "checkbox", value: type, checked: true });
      const span = create("span", { text: `${meta.label} · ${meta.family === "short_answer" ? "단답" : "객관식"}` });
      label.append(input, span);
      picker.append(label);
    }
  }

  function initBankTypeFilter() {
    const filter = $("bankTypeFilter");
    for (const [type, meta] of Object.entries(KYEngine.TYPE_META)) {
      filter.append(create("option", { value: type, text: meta.label }));
    }
  }

  function hydrate() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (!raw) return;
      const saved = JSON.parse(raw);
      state.analysis = saved.analysis || null;
      state.generated = Array.isArray(saved.generated) ? saved.generated : [];
      state.bank = Array.isArray(saved.bank) ? saved.bank : [];
      state.mock = saved.mock || null;
      state.savedAt = saved.savedAt || null;
    } catch (error) {
      console.warn(error);
      showToast("이전 작업 상태를 읽지 못했습니다.");
    }
  }

  function persist() {
    state.savedAt = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  function readInput() {
    return {
      grade: $("grade").value,
      preset: $("preset").value,
      sourceType: $("sourceType").value,
      title: $("title").value.trim(),
      sourceRef: $("sourceRef").value.trim(),
      examScope: $("examScope").value.trim(),
      text: $("passageText").value,
    };
  }

  function loadSample() {
    $("grade").value = "g1";
    $("preset").value = "g1";
    $("sourceType").value = "textbook";
    $("title").value = "Sample Transform Passage";
    $("sourceRef").value = "샘플 원문";
    $("examScope").value = "광영여고 변형 테스트";
    $("passageText").value = [
      "When students review a passage, they often try to memorize every sentence. However, this habit can hide the structure of the passage. A better reader first asks why each paragraph exists and how it moves the writer's idea forward.",
      "For example, one paragraph may introduce a problem, while another paragraph may show evidence. If students mark those paragraph roles, they can predict which sentence will become a grammar question, a summary blank, or an insertion question.",
      "Therefore, strong test preparation is not just translation practice. It is a process of rebuilding the original text into several school-style questions and checking whether every answer has clear textual evidence.",
    ].join("\n\n");
    runAnalyze();
  }

  function runAnalyze() {
    const input = readInput();
    if (KYEngine.normalizePassage(input.text).length < 80) {
      showToast("분석하려면 최소 80자 이상의 지문을 붙여넣으세요.");
      return;
    }
    try {
      state.analysis = KYEngine.analyzePassage(input);
      state.generated = [];
      state.mock = state.mock || null;
      persist();
      renderAll();
      showToast("지문 분석을 완료했습니다.");
      document.querySelector("#analysis").scrollIntoView({ block: "start" });
    } catch (error) {
      console.error(error);
      showToast("분석 중 오류가 발생했습니다.");
    }
  }

  function runGenerate() {
    if (!state.analysis) {
      showToast("먼저 지문 분석을 실행하세요.");
      return;
    }
    const types = selectedTypes();
    if (!types.length) {
      showToast("최소 1개 이상의 문항 유형을 선택하세요.");
      return;
    }
    try {
      state.generated = KYEngine.generateQuestions(state.analysis, {
        preset: $("preset").value,
        targetCount: Number($("targetCount").value || 36),
        seed: $("seed").value.trim(),
        types,
      });
      persist();
      renderAll();
      showToast(`${state.generated.length}개 문항을 생성했습니다.`);
      document.querySelector("#generation").scrollIntoView({ block: "start" });
    } catch (error) {
      console.error(error);
      showToast("문항 생성 중 오류가 발생했습니다.");
    }
  }

  function selectedTypes() {
    return [...document.querySelectorAll("#typePicker input:checked")].map((input) => input.value);
  }

  function selectAllTypes() {
    const boxes = [...document.querySelectorAll("#typePicker input")];
    const allChecked = boxes.every((box) => box.checked);
    boxes.forEach((box) => {
      box.checked = !allChecked;
    });
  }

  function saveGenerated() {
    if (!state.generated.length) {
      showToast("저장할 생성 문항이 없습니다.");
      return;
    }
    const next = [...state.bank];
    const seen = new Set(next.map((item) => item.questionId));
    for (const item of state.generated.map(KYEngine.serializeBankItem)) {
      if (!seen.has(item.questionId)) {
        next.push(item);
        seen.add(item.questionId);
      }
    }
    state.bank = next;
    persist();
    renderAll();
    showToast("생성 문항을 문제은행에 저장했습니다.");
  }

  function clearBank() {
    if (!state.bank.length) return;
    if (!window.confirm("문제은행을 비울까요? 이 작업은 현재 브라우저 상태에서 되돌릴 수 없습니다.")) return;
    state.bank = [];
    state.mock = null;
    persist();
    renderAll();
    showToast("문제은행을 비웠습니다.");
  }

  function buildMock() {
    if (!state.bank.length) {
      showToast("먼저 문제은행에 문항을 저장하세요.");
      return;
    }
    state.mock = KYEngine.composeMockExam(state.bank, {
      preset: $("preset").value,
      title: $("mockTitle").value.trim(),
      objectiveCount: Number($("objectiveCount").value || 27),
      shortAnswerCount: Number($("shortAnswerCount").value || 4),
    });
    persist();
    renderAll();
    showToast(`${state.mock.itemCount}문항 동형 모의고사를 조립했습니다.`);
  }

  function exportItemsCsv(items, filename) {
    if (!items.length) {
      showToast("내보낼 문항이 없습니다.");
      return;
    }
    const rows = items.map(KYEngine.serializeBankItem);
    downloadText(filename, KYEngine.exportCsv(rows), "text/csv;charset=utf-8");
  }

  function exportMockCsv() {
    if (!state.mock || !state.mock.items?.length) {
      showToast("내보낼 모의고사가 없습니다.");
      return;
    }
    const rows = state.mock.items.map((item) => ({
      examNo: item.examNo,
      ...KYEngine.serializeBankItem(item),
    }));
    downloadText("ky-mock-exam.csv", KYEngine.exportCsv(rows), "text/csv;charset=utf-8");
  }

  function exportJson(data, filename) {
    const payload = JSON.stringify(data, null, 2);
    downloadText(filename, payload, "application/json;charset=utf-8");
  }

  function exportProject() {
    const bundle = {
      schemaVersion: "ky-project@1",
      engineVersion: KYEngine.ENGINE_VERSION,
      exportedAt: new Date().toISOString(),
      analysis: redactAnalysis(state.analysis),
      generated: state.generated.map(KYEngine.serializeBankItem),
      bank: state.bank,
      mock: state.mock,
    };
    exportJson(bundle, "ky-transform-project.json");
  }

  function importProject(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const bundle = JSON.parse(String(reader.result || "{}"));
        state.analysis = bundle.analysis || null;
        state.generated = Array.isArray(bundle.generated) ? bundle.generated : [];
        state.bank = Array.isArray(bundle.bank) ? bundle.bank : [];
        state.mock = bundle.mock || null;
        persist();
        renderAll();
        showToast("프로젝트 JSON을 불러왔습니다.");
      } catch (error) {
        console.error(error);
        showToast("JSON을 불러오지 못했습니다.");
      } finally {
        event.target.value = "";
      }
    };
    reader.readAsText(file, "utf-8");
  }

  function copyAnalysisJson() {
    if (!state.analysis) {
      showToast("복사할 분석 결과가 없습니다.");
      return;
    }
    const payload = JSON.stringify(redactAnalysis(state.analysis), null, 2);
    navigator.clipboard
      .writeText(payload)
      .then(() => showToast("원문 제외 분석 JSON을 복사했습니다."))
      .catch(() => showToast("클립보드 복사에 실패했습니다."));
  }

  function renderAll() {
    renderStatus();
    renderAnalysis();
    renderQuestions();
    renderBank();
    renderMock();
  }

  function renderStatus() {
    const preset = KYEngine.PRESETS[$("preset").value] || KYEngine.PRESETS.g1;
    $("statusPreset").textContent = preset.label;
    $("statusAnalysis").textContent = state.analysis ? `${state.analysis.metrics.wordCount} words` : "대기";
    $("statusGenerated").textContent = String(state.generated.length);
    $("statusBank").textContent = String(state.bank.length);
  }

  function renderAnalysis() {
    renderMetrics();
    renderParagraphRoles();
    renderSignals();
  }

  function renderMetrics() {
    const wrap = $("analysisMetrics");
    clear(wrap);
    if (!state.analysis) {
      wrap.append(create("div", { className: "empty-state", text: "분석 지표가 없습니다." }));
      return;
    }
    const metrics = state.analysis.metrics;
    const rows = [
      ["문단", metrics.paragraphCount],
      ["문장", metrics.sentenceCount],
      ["단어", metrics.wordCount],
      ["평균 문장 길이", metrics.avgSentenceLength],
      ["긴 단어", metrics.longWordCount],
      ["난도", `${metrics.difficultyLevel} · ${metrics.difficultyScore}`],
    ];
    rows.forEach(([label, value]) => {
      const card = create("div", { className: "metric" });
      card.append(create("span", { text: label }), create("strong", { text: String(value) }));
      wrap.append(card);
    });
  }

  function renderParagraphRoles() {
    const wrap = $("paragraphRoles");
    clear(wrap);
    if (!state.analysis) {
      wrap.className = "role-list empty-state";
      wrap.textContent = "분석을 실행하면 문단 기능이 표시됩니다.";
      return;
    }
    wrap.className = "role-list";
    state.analysis.paragraphFunctions.forEach((role) => {
      const item = create("div", { className: "role-item" });
      item.append(
        create("strong", { text: `${role.id} · ${role.function}` }),
        create("span", { text: `문장 ${role.sentenceCount}개 · 핵심어 ${role.keywords.join(", ") || "없음"}` }),
      );
      wrap.append(item);
    });
  }

  function renderSignals() {
    const wrap = $("analysisSignals");
    clear(wrap);
    if (!state.analysis) {
      wrap.className = "signal-list empty-state";
      wrap.textContent = "핵심어, 연결어, 어법 후보가 표시됩니다.";
      return;
    }
    wrap.className = "signal-list";
    const chips = [
      ...state.analysis.keywords.slice(0, 10).map((item) => `핵심어:${item.word}`),
      ...state.analysis.connectors.slice(0, 8).map((item) => `연결어:${item.connector}/${item.role}`),
      ...state.analysis.grammarCandidates.slice(0, 8).map((item) => `어법:${item.label}`),
    ];
    if (!chips.length) chips.push("출제 사인 부족: 짧은 지문");
    chips.forEach((text) => wrap.append(create("span", { className: "chip", text })));
  }

  function renderQuestions() {
    renderQuestionList($("generatedList"), state.generated, { empty: "분석 후 문항을 생성하세요." });
  }

  function renderQuestionList(container, items, options = {}) {
    clear(container);
    if (!items.length) {
      container.className = `${container.id === "mockPreview" ? "mock-preview" : "question-list"} empty-state`;
      container.textContent = options.empty || "문항이 없습니다.";
      return;
    }
    container.className = container.id === "mockPreview" ? "mock-preview" : "question-list";
    items.forEach((item, index) => container.append(renderQuestionCard(item, index)));
  }

  function renderQuestionCard(item, index) {
    const card = create("article", { className: "question-card" });
    const meta = create("div", { className: "question-meta" });
    const labels = [
      item.examNo ? `${item.examNo}번` : `${index + 1}번`,
      item.typeLabel || item.type,
      item.family === "short_answer" ? "단답형" : "객관식",
      `난도 ${item.difficulty || "-"}`,
      item.quality?.status || "검수대기",
    ];
    labels.forEach((label) => meta.append(create("span", { text: label })));
    card.append(meta, create("h3", { text: item.stem || item.prompt || "문항 발문 없음" }));
    if (item.prompt) {
      const prompt = create("p", { text: item.prompt });
      card.append(prompt);
    }
    if (Array.isArray(item.options) && item.options.length) {
      const list = create("ol");
      item.options.forEach((option) => list.append(create("li", { text: option })));
      card.append(list);
    }
    const qa = create("div", { className: "qa-grid" });
    qa.append(
      qaBox("정답", Array.isArray(item.answer) ? item.answer.join(" / ") : String(item.answer ?? "")),
      qaBox("변형 규칙", item.transformRule || ""),
      qaBox("근거", item.evidence || ""),
      qaBox("해설", item.explanation || ""),
    );
    card.append(qa);
    return card;
  }

  function qaBox(title, value) {
    const box = create("div");
    box.append(create("strong", { text: title }), create("span", { text: value || "-" }));
    return box;
  }

  function renderBank() {
    const wrap = $("bankTable");
    clear(wrap);
    const filtered = filteredBankItems();
    if (!filtered.length) {
      wrap.className = "bank-table empty-state";
      wrap.textContent = state.bank.length ? "필터 조건에 맞는 문항이 없습니다." : "저장된 문항이 없습니다.";
      return;
    }
    wrap.className = "bank-table";
    const table = create("table");
    const thead = create("thead");
    const headerRow = create("tr");
    ["유형", "출처", "발문", "정답", "품질", "관리"].forEach((text) => headerRow.append(create("th", { text })));
    thead.append(headerRow);
    const tbody = create("tbody");
    filtered.forEach((item) => {
      const row = create("tr");
      row.append(
        create("td", { text: item.typeLabel || item.type || "" }),
        create("td", { text: item.sourceTitle || item.sourceRef || "" }),
        create("td", { className: "mini", text: item.stem || item.prompt || "" }),
        create("td", { text: Array.isArray(item.answer) ? item.answer.join(" / ") : String(item.answer ?? "") }),
        create("td", { text: item.quality?.status || "" }),
      );
      const cell = create("td");
      const button = create("button", { className: "danger", text: "삭제" });
      button.addEventListener("click", () => deleteBankItem(item.questionId));
      cell.append(button);
      row.append(cell);
      tbody.append(row);
    });
    table.append(thead, tbody);
    wrap.append(table);
  }

  function filteredBankItems() {
    const type = $("bankTypeFilter").value;
    const query = $("bankSearch").value.trim().toLowerCase();
    return state.bank.filter((item) => {
      if (type && item.type !== type) return false;
      if (!query) return true;
      const haystack = [item.typeLabel, item.sourceTitle, item.sourceRef, item.stem, item.prompt, item.evidence]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }

  function deleteBankItem(questionId) {
    state.bank = state.bank.filter((item) => item.questionId !== questionId);
    if (state.mock?.items) {
      state.mock.items = state.mock.items.filter((item) => item.questionId !== questionId);
      state.mock.itemCount = state.mock.items.length;
    }
    persist();
    renderAll();
    showToast("문항을 삭제했습니다.");
  }

  function renderMock() {
    const preview = $("mockPreview");
    if (!state.mock || !state.mock.items?.length) {
      renderQuestionList(preview, [], { empty: "문제은행에 문항을 저장한 뒤 조립하세요." });
      return;
    }
    clear(preview);
    preview.className = "mock-preview";
    const summary = create("article", { className: "question-card" });
    summary.append(
      create("h3", { text: state.mock.title }),
      qaBox("문항 수", `${state.mock.itemCount}문항`),
      qaBox("단답형", `${state.mock.shortAnswerCount}문항`),
      qaBox("총점 추정", `${state.mock.totalPoints}점`),
    );
    preview.append(summary);
    state.mock.items.forEach((item, index) => preview.append(renderQuestionCard(item, index)));
  }

  function redactAnalysis(analysis) {
    if (!analysis) return null;
    return {
      schemaVersion: analysis.schemaVersion,
      engineVersion: analysis.engineVersion,
      sourceId: analysis.sourceId,
      title: analysis.title,
      grade: analysis.grade,
      preset: analysis.preset,
      sourceType: analysis.sourceType,
      sourceRef: analysis.sourceRef,
      examScope: analysis.examScope,
      fingerprint: analysis.fingerprint,
      textLength: analysis.textLength,
      metrics: analysis.metrics,
      paragraphFunctions: analysis.paragraphFunctions,
      keywords: analysis.keywords,
      connectors: analysis.connectors,
      grammarCandidates: (analysis.grammarCandidates || []).map((item) => ({
        sentenceId: item.sentenceId,
        label: item.label,
        key: item.key,
      })),
      vocabularyCandidates: analysis.vocabularyCandidates,
      recommendations: analysis.recommendations,
      createdAt: analysis.createdAt,
      redacted: true,
    };
  }

  function downloadText(filename, content, type) {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = create("a", { href: url, download: filename });
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  function create(tag, props = {}) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props)) {
      if (key === "text") node.textContent = value;
      else if (key === "className") node.className = value;
      else if (key === "checked") node.checked = Boolean(value);
      else node.setAttribute(key, value);
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.firstChild.remove();
  }

  let toastTimer = null;
  function showToast(message) {
    const toast = $("toast");
    toast.textContent = message;
    toast.classList.add("show");
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2400);
  }
})();
