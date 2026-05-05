(function () {
  const STORAGE_KEY = "ky-transform-engine:v1";
  const TEXTBOOK_LIBRARY_STORAGE_KEY = "ky-transform-engine:textbook-library:v1";

  const state = {
    analysis: null,
    generated: [],
    bank: [],
    mock: null,
    savedAt: null,
  };

  const libraryState = {
    source: "catalog",
    loadedAt: null,
    bookCount: 0,
    lessonCount: 0,
    readyLessonCount: 0,
  };

  const $ = (id) => document.getElementById(id);

  const RANGE_PRESETS = [
    {
      id: "g1_s1_mid",
      label: "고1 1학기 중간",
      bookId: "common_english_1",
      lessonNos: [1, 2],
      grade: "g1",
      preset: "g1",
      title: "공통영어1 1-2과",
      sourceRef: "YBM박 공통영어1 1-2과",
      examScope: "고1 1학기 중간",
    },
    {
      id: "g1_s1_final",
      label: "고1 1학기 기말",
      bookId: "common_english_1",
      lessonNos: [3, 4],
      grade: "g1",
      preset: "g1",
      title: "공통영어1 3-4과",
      sourceRef: "YBM박 공통영어1 3-4과",
      examScope: "고1 1학기 기말",
    },
    {
      id: "g1_s2_mid",
      label: "고1 2학기 중간",
      bookId: "common_english_2",
      lessonNos: [1, 2],
      grade: "g1",
      preset: "g1",
      title: "공통영어2 1-2과",
      sourceRef: "YBM박 공통영어2 1-2과",
      examScope: "고1 2학기 중간",
    },
    {
      id: "g1_s2_final",
      label: "고1 2학기 기말",
      bookId: "common_english_2",
      lessonNos: [3, 4],
      grade: "g1",
      preset: "g1",
      title: "공통영어2 3-4과",
      sourceRef: "YBM박 공통영어2 3-4과",
      examScope: "고1 2학기 기말",
    },
    {
      id: "g2_s1_mid",
      label: "고2 1학기 중간",
      bookId: "english_1",
      lessonNos: [1, 2],
      grade: "g2",
      preset: "g2",
      title: "영어1 1-2과",
      sourceRef: "YBM박 영어1 1-2과",
      examScope: "고2 1학기 중간",
    },
    {
      id: "g2_s1_final",
      label: "고2 1학기 기말",
      bookId: "english_1",
      lessonNos: [3, 4, 5],
      grade: "g2",
      preset: "g2",
      title: "영어1 3-5과",
      sourceRef: "YBM박 영어1 3-5과",
      examScope: "고2 1학기 기말",
    },
    {
      id: "g2_s2_mid",
      label: "고2 2학기 중간",
      bookId: "english_2",
      lessonNos: [1, 2],
      grade: "g2",
      preset: "g2",
      title: "영어2 1-2과",
      sourceRef: "YBM박 영어2 1-2과",
      examScope: "고2 2학기 중간",
    },
    {
      id: "g2_s2_final",
      label: "고2 2학기 기말",
      bookId: "english_2",
      lessonNos: [3, 4, 5],
      grade: "g2",
      preset: "g2",
      title: "영어2 3-5과",
      sourceRef: "YBM박 영어2 3-5과",
      examScope: "고2 2학기 기말",
    },
  ];

  const GENRE_PRESETS = {
    all: {
      label: "전체 자동 생성",
      types: null,
    },
    school_body: {
      label: "광영여고 본문 기본팩",
      types: ["gist", "content_false", "context_vocab", "grammar_mc", "grammar_edit", "order", "summary_short"],
    },
    grammar: {
      label: "어법만",
      types: ["grammar_mc", "grammar_edit"],
    },
    vocab: {
      label: "어휘/문맥만",
      types: ["context_vocab"],
    },
    structure: {
      label: "순서/삽입만",
      types: ["order", "insertion"],
    },
    short_answer: {
      label: "단답형만",
      types: ["grammar_edit", "summary_short", "condition_writing"],
    },
    objective: {
      label: "객관식만",
      types: ["gist", "content_false", "context_vocab", "grammar_mc", "order", "insertion"],
    },
  };

  document.addEventListener("DOMContentLoaded", () => {
    init();
  });

  async function init() {
    if (!window.KYEngine) {
      showToast("엔진 로드에 실패했습니다. engine-core.js를 확인하세요.");
      return;
    }
    await loadPrivateTextbookLibrary();
    hydrate();
    initTextbookPicker();
    initRangePicker();
    initTypePicker();
    initBankTypeFilter();
    bindEvents();
    applySelectedRange({ loadBody: true, silent: true });
    applyGenrePreset({ silent: true });
    renderAll();
  }

  async function loadPrivateTextbookLibrary() {
    if (window.KYTextbookLibrary) return;
    const stored = localStorage.getItem(TEXTBOOK_LIBRARY_STORAGE_KEY);
    if (stored) {
      try {
        window.KYTextbookLibrary = parseTextbookLibrarySource(stored);
        updateLibraryState("browser");
        return;
      } catch (error) {
        localStorage.removeItem(TEXTBOOK_LIBRARY_STORAGE_KEY);
        console.warn("Stored textbook library was invalid and has been cleared.", error);
      }
    }
    try {
      const response = await fetch("./textbook-private.js", { cache: "no-store" });
      if (!response.ok) return;
      const source = await response.text();
      window.KYTextbookLibrary = parseTextbookLibrarySource(source);
      updateLibraryState("deployment");
    } catch (error) {
      console.info("Private textbook library is not available in this deployment.", error);
    }
  }

  function bindEvents() {
    $("runAnalyze").addEventListener("click", runAnalyze);
    $("runAnalyzeTop").addEventListener("click", runAnalyze);
    $("loadTextbookPassage").addEventListener("click", () => applySelectedRange({ loadBody: true }));
    $("importTextbookLibrary").addEventListener("change", importTextbookLibrary);
    $("clearTextbookLibrary").addEventListener("click", clearStoredTextbookLibrary);
    $("rangePreset").addEventListener("change", () => applySelectedRange({ loadBody: true }));
    $("genrePreset").addEventListener("change", () => applyGenrePreset());
    $("textbookBook").addEventListener("change", () => {
      syncLessonOptions();
      syncSelectedLesson({ loadBody: true });
      renderRangeSummary();
    });
    $("textbookLesson").addEventListener("change", () => {
      syncSelectedLesson({ loadBody: true });
      renderRangeSummary();
    });
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

  function textbookLibrary() {
    return window.KYTextbookLibrary || window.KYTextbookCatalog || { books: [] };
  }

  function parseTextbookLibrarySource(source) {
    const text = String(source || "").trim();
    let library = null;
    if (text.startsWith("{")) {
      library = JSON.parse(text);
    } else {
      const match = text.match(/window\.KYTextbookLibrary\s*=\s*({[\s\S]*});\s*\}\)\(\);?\s*$/);
      if (!match) {
        throw new Error("KYTextbookLibrary assignment was not found.");
      }
      library = JSON.parse(match[1]);
    }
    validateTextbookLibrary(library);
    return library;
  }

  function validateTextbookLibrary(library) {
    if (!library || !Array.isArray(library.books)) {
      throw new Error("Textbook library must contain a books array.");
    }
    const lessonCount = library.books.reduce((sum, book) => sum + (Array.isArray(book.lessons) ? book.lessons.length : 0), 0);
    const readyLessonCount = library.books.reduce(
      (sum, book) => sum + (Array.isArray(book.lessons) ? book.lessons.filter((lesson) => lesson.body).length : 0),
      0,
    );
    if (!lessonCount || !readyLessonCount) {
      throw new Error("Textbook library does not include usable lesson bodies.");
    }
  }

  function updateLibraryState(source) {
    const library = textbookLibrary();
    const books = Array.isArray(library.books) ? library.books : [];
    libraryState.source = source || (window.KYTextbookLibrary ? "deployment" : "catalog");
    libraryState.loadedAt = new Date().toISOString();
    libraryState.bookCount = books.length;
    libraryState.lessonCount = books.reduce((sum, book) => sum + (Array.isArray(book.lessons) ? book.lessons.length : 0), 0);
    libraryState.readyLessonCount = books.reduce(
      (sum, book) => sum + (Array.isArray(book.lessons) ? book.lessons.filter((lesson) => lesson.body).length : 0),
      0,
    );
  }

  async function importTextbookLibrary(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const source = await file.text();
      const library = parseTextbookLibrarySource(source);
      window.KYTextbookLibrary = library;
      localStorage.setItem(TEXTBOOK_LIBRARY_STORAGE_KEY, source);
      updateLibraryState("browser");
      initTextbookPicker();
      initRangePicker();
      applySelectedRange({ loadBody: true, silent: true });
      renderAll();
      showToast(`본문 라이브러리를 연결했습니다. ${libraryState.readyLessonCount}개 단원을 사용할 수 있습니다.`);
    } catch (error) {
      console.error(error);
      showToast("본문 라이브러리를 읽지 못했습니다. build_textbook_private_library.py로 만든 파일인지 확인하세요.");
    } finally {
      event.target.value = "";
    }
  }

  function clearStoredTextbookLibrary() {
    localStorage.removeItem(TEXTBOOK_LIBRARY_STORAGE_KEY);
    delete window.KYTextbookLibrary;
    updateLibraryState("catalog");
    initTextbookPicker();
    initRangePicker();
    applySelectedRange({ loadBody: true, silent: true });
    renderAll();
    showToast("브라우저에 저장된 본문 라이브러리를 해제했습니다.");
  }

  function initTextbookPicker() {
    updateLibraryState(window.KYTextbookLibrary ? libraryState.source : "catalog");
    const library = textbookLibrary();
    const bookSelect = $("textbookBook");
    clear(bookSelect);
    const books = Array.isArray(library.books) ? library.books : [];
    books.forEach((book) => {
      const availability = book.availability === "ready" ? "" : " · 본문 미탑재";
      bookSelect.append(create("option", { value: book.id, text: `${book.label} (${book.gradeLabel} ${book.semester})${availability}` }));
    });
    if (!books.length) {
      bookSelect.append(create("option", { value: "", text: "교과서 라이브러리 없음" }));
    }
    syncLessonOptions();
    syncSelectedLesson({ loadBody: false, silent: true });
  }

  function initRangePicker() {
    const picker = $("rangePreset");
    if (!picker) return;
    const current = picker.value || "g1_s1_mid";
    clear(picker);
    RANGE_PRESETS.forEach((range) => {
      const status = rangeAvailability(range);
      const suffix = status.ready === status.total && status.total ? "" : ` · 본문 ${status.ready}/${status.total}`;
      picker.append(create("option", { value: range.id, text: `${range.label}${suffix}` }));
    });
    if (RANGE_PRESETS.some((range) => range.id === current)) {
      picker.value = current;
    }
    renderRangeSummary();
  }

  function selectedRange() {
    return RANGE_PRESETS.find((range) => range.id === $("rangePreset").value) || RANGE_PRESETS[0];
  }

  function getBookById(bookId) {
    return (textbookLibrary().books || []).find((book) => book.id === bookId) || null;
  }

  function rangeLessons(range = selectedRange()) {
    const book = getBookById(range.bookId);
    if (!book) return { book: null, lessons: [] };
    const lessons = (book.lessons || []).filter((lesson) => range.lessonNos.includes(Number(lesson.lessonNo)));
    return { book, lessons };
  }

  function rangeAvailability(range = selectedRange()) {
    const { lessons } = rangeLessons(range);
    return {
      total: range.lessonNos.length,
      found: lessons.length,
      ready: lessons.filter((lesson) => lesson.body).length,
    };
  }

  function applySelectedRange(options = {}) {
    const { loadBody = false, silent = false } = options;
    const range = selectedRange();
    const { book, lessons } = rangeLessons(range);
    if (!book) {
      $("passageText").value = "";
      renderRangeSummary();
      if (!silent) showToast("해당 범위의 교재가 아직 등록되지 않았습니다.");
      return;
    }

    $("textbookBook").value = book.id;
    syncLessonOptions();
    const firstLesson = lessons[0] || (book.lessons || [])[0];
    if (firstLesson) $("textbookLesson").value = firstLesson.id;

    $("grade").value = range.grade || book.grade || "g1";
    $("preset").value = range.preset || book.preset || book.grade || "g1";
    $("sourceType").value = "textbook";
    $("title").value = range.title || book.label;
    $("sourceRef").value = range.sourceRef || `YBM박 ${book.course}`;
    $("examScope").value = range.examScope || book.examScope || "";
    $("mockTitle").value = `${range.examScope || range.label} 동형 1회`;

    if (loadBody) {
      const readyLessons = lessons.filter((lesson) => lesson.body);
      if (!readyLessons.length) {
        $("passageText").value = "";
        if (!silent) showToast("이 범위의 본문 전문이 아직 연결되지 않았습니다. 본문 라이브러리를 먼저 연결하세요.");
      } else {
        $("passageText").value = composeRangePassage(book, readyLessons);
        if (!silent) showToast(`${range.label} 본문 ${readyLessons.length}개 단원을 불러왔습니다.`);
      }
    }

    renderRangeSummary();
    renderStatus();
  }

  function composeRangePassage(book, lessons) {
    return lessons
      .map((lesson) => {
        const heading = `[${book.label} ${lesson.lessonNo}과] ${lesson.title || ""}`.trim();
        return `${heading}\n\n${lesson.body}`;
      })
      .join("\n\n");
  }

  function renderRangeSummary() {
    const wrap = $("rangeSummary");
    if (!wrap) return;
    const range = selectedRange();
    const { book, lessons } = rangeLessons(range);
    clear(wrap);
    const head = create("div", { className: "range-summary-head" });
    const status = rangeAvailability(range);
    head.append(
      create("strong", { text: range.label }),
      create("span", { text: book ? `${book.label} · ${range.lessonNos.join(", ")}과 · 본문 ${status.ready}/${status.total}` : "교재 미등록" }),
    );
    wrap.append(head);
    const list = create("div", { className: "range-lesson-list" });
    range.lessonNos.forEach((lessonNo) => {
      const lesson = lessons.find((item) => Number(item.lessonNo) === Number(lessonNo));
      const item = create("div", { className: `range-lesson ${lesson?.body ? "ready" : "missing"}` });
      item.append(
        create("span", { text: `${lessonNo}과` }),
        create("strong", { text: lesson?.title || "단원 정보 없음" }),
        create("em", { text: lesson?.body ? "본문 준비" : "본문 필요" }),
      );
      list.append(item);
    });
    wrap.append(list);
  }

  function selectedBook() {
    const library = textbookLibrary();
    return (library.books || []).find((book) => book.id === $("textbookBook").value) || null;
  }

  function selectedLesson(book = selectedBook()) {
    if (!book) return null;
    return (book.lessons || []).find((lesson) => lesson.id === $("textbookLesson").value) || null;
  }

  function syncLessonOptions() {
    const lessonSelect = $("textbookLesson");
    clear(lessonSelect);
    const book = selectedBook();
    const lessons = book?.lessons || [];
    lessons.forEach((lesson) => {
      const bodyMark = lesson.body ? "" : " · 본문 없음";
      lessonSelect.append(create("option", { value: lesson.id, text: `${lesson.lessonNo}과 · ${lesson.title}${bodyMark}` }));
    });
    if (!lessons.length) {
      lessonSelect.append(create("option", { value: "", text: "등록된 단원이 없습니다" }));
    }
  }

  function syncSelectedLesson(options = {}) {
    const { loadBody = false, silent = false } = options;
    const book = selectedBook();
    const lesson = selectedLesson(book);
    if (!book || !lesson) return;

    $("grade").value = book.grade || "g1";
    $("preset").value = book.preset || book.grade || "g1";
    $("sourceType").value = "textbook";
    $("title").value = lesson.title || "";
    $("sourceRef").value = lesson.sourceRef || `YBM박 ${book.course} ${lesson.lessonNo}과`;
    $("examScope").value = book.examScope || `${book.gradeLabel || ""} ${book.semester || ""}`.trim();

    if (loadBody) {
      loadSelectedTextbookPassage({ silent });
    } else {
      renderStatus();
    }
  }

  function loadSelectedTextbookPassage(options = {}) {
    const { silent = false } = options;
    const book = selectedBook();
    const lesson = selectedLesson(book);
    if (!book || !lesson) {
      if (!silent) showToast("책과 단원을 먼저 선택하세요.");
      return;
    }
    syncSelectedLesson({ loadBody: false });
    if (!lesson.body) {
      $("passageText").value = "";
      if (!silent) {
        showToast("본문 전문 파일이 아직 연결되지 않았습니다. 로컬에서 textbook-private.js를 생성해야 합니다.");
      }
      return;
    }
    $("passageText").value = lesson.body;
    if (!silent) showToast(`${book.label} ${lesson.lessonNo}과 본문을 불러왔습니다.`);
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

  function applyGenrePreset(options = {}) {
    const { silent = false } = options;
    const selected = GENRE_PRESETS[$("genrePreset").value] || GENRE_PRESETS.all;
    const targetTypes = selected.types ? new Set(selected.types) : new Set(Object.keys(KYEngine.TYPE_META));
    document.querySelectorAll("#typePicker input").forEach((input) => {
      input.checked = targetTypes.has(input.value);
    });
    if (!silent) showToast(`${selected.label} 유형으로 맞췄습니다.`);
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
    renderLibraryStatus();
    renderStatus();
    renderAnalysis();
    renderQuestions();
    renderBank();
    renderMock();
  }

  function renderLibraryStatus() {
    const status = $("textbookLibraryStatus");
    if (!status) return;
    if (libraryState.readyLessonCount > 0) {
      const sourceLabel =
        libraryState.source === "browser" ? "브라우저 저장됨" : libraryState.source === "deployment" ? "배포 포함" : "연결됨";
      status.textContent = `${sourceLabel} · ${libraryState.bookCount}권 · 본문 ${libraryState.readyLessonCount}단원`;
      status.dataset.state = "ready";
      return;
    }
    status.textContent = "카탈로그만 연결됨 · 본문 파일 필요";
    status.dataset.state = "empty";
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
    const groups = groupItemsBySource(items);
    let index = 0;
    groups.forEach((group) => {
      container.append(renderSourcePassage(group));
      group.items.forEach((item) => {
        container.append(renderQuestionCard(item, index));
        index += 1;
      });
    });
  }

  function groupItemsBySource(items) {
    const groups = [];
    const byKey = new Map();
    items.forEach((item) => {
      const key = item.sourceId || item.sourceTitle || item.sourceRef || "unknown";
      if (!byKey.has(key)) {
        const group = {
          key,
          title: item.sourceTitle || item.sourceRef || "본문",
          sourceRef: item.sourceRef || "",
          passage: passageForItem(item),
          items: [],
        };
        byKey.set(key, group);
        groups.push(group);
      }
      byKey.get(key).items.push(item);
    });
    return groups;
  }

  function passageForItem(item) {
    if (item.sourcePassage) return item.sourcePassage;
    if (state.analysis && item.sourceId && item.sourceId === state.analysis.sourceId) {
      return (state.analysis.units || []).map((unit) => unit.text).join("\n\n");
    }
    return "";
  }

  function renderSourcePassage(group) {
    const details = create("details", { className: "source-passage" });
    details.open = true;
    const summary = create("summary");
    summary.append(
      create("strong", { text: group.title || "본문" }),
      create("span", { text: group.sourceRef ? ` · ${group.sourceRef}` : "" }),
    );
    const body = create("div", { className: "source-passage-body" });
    const passage = group.passage || "저장된 본문이 없습니다. 이 문항은 이전 버전에서 생성되어 본문 전문을 포함하지 않을 수 있습니다.";
    passage
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean)
      .forEach((paragraph) => body.append(create("p", { text: paragraph })));
    details.append(summary, body);
    return details;
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
    ["유형", "출처", "본문", "발문", "정답", "품질", "관리"].forEach((text) => headerRow.append(create("th", { text })));
    thead.append(headerRow);
    const tbody = create("tbody");
    filtered.forEach((item) => {
      const row = create("tr");
      row.append(
        create("td", { text: item.typeLabel || item.type || "" }),
        create("td", { text: item.sourceTitle || item.sourceRef || "" }),
        create("td", { text: item.sourcePassage ? "포함" : "없음" }),
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
