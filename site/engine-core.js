(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  root.KYEngine = api;
})(typeof globalThis !== "undefined" ? globalThis : window, function () {
  const ENGINE_VERSION = "0.2.0";

  const STOPWORDS = new Set(
    "the,a,an,and,or,but,so,because,if,when,while,with,without,from,into,onto,over,under,between,among,that,this,these,those,there,here,then,than,also,very,more,most,some,any,each,every,only,just,not,can,could,may,might,will,would,should,must,have,has,had,been,being,are,was,were,is,am,do,does,did,for,of,to,in,on,at,by,as,it,its,they,them,their,we,our,you,your,he,his,she,her,which,who,whom,whose,what,how,why"
      .split(","),
  );

  const PRESETS = {
    g1: {
      id: "g1",
      label: "광영여고 고1",
      profile: "YBM박 본문 + 과거 고1 학평 변형",
      defaultTypes: [
        "gist",
        "content_false",
        "context_vocab",
        "grammar_mc",
        "grammar_edit",
        "order",
        "insertion",
        "summary_short",
        "condition_writing",
      ],
      typeWeights: {
        gist: 3,
        content_false: 5,
        context_vocab: 5,
        grammar_mc: 5,
        grammar_edit: 3,
        order: 2,
        insertion: 2,
        summary_short: 4,
        condition_writing: 3,
      },
      blueprint: {
        label: "고1 동형",
        listening: 5,
        textbook: 8,
        mockTransform: 10,
        shortAnswer: 4,
        vocab: 6,
        totalObjective: 27,
      },
    },
    g2: {
      id: "g2",
      label: "광영여고 고2",
      profile: "학평 클러스터 + 작품/수업지문 단답형",
      defaultTypes: [
        "gist",
        "content_false",
        "context_vocab",
        "grammar_mc",
        "grammar_edit",
        "order",
        "insertion",
        "summary_short",
        "condition_writing",
      ],
      typeWeights: {
        gist: 4,
        content_false: 5,
        context_vocab: 5,
        grammar_mc: 6,
        grammar_edit: 5,
        order: 3,
        insertion: 2,
        summary_short: 4,
        condition_writing: 4,
      },
      blueprint: {
        label: "고2 동형",
        listening: 5,
        schoolPassage: 11,
        mockTransform: 7,
        shortAnswer: 4,
        vocab: 6,
        totalObjective: 27,
      },
    },
  };

  const TYPE_META = {
    gist: { label: "요지/제목", family: "objective", category: "comprehension" },
    content_false: { label: "내용 불일치", family: "objective", category: "detail" },
    context_vocab: { label: "문맥상 어휘", family: "objective", category: "vocab" },
    grammar_mc: { label: "어법 객관식", family: "objective", category: "grammar" },
    grammar_edit: { label: "어법수정 단답", family: "short_answer", category: "grammar" },
    order: { label: "순서", family: "objective", category: "structure" },
    insertion: { label: "문장삽입", family: "objective", category: "structure" },
    summary_short: { label: "요약 단답", family: "short_answer", category: "summary" },
    condition_writing: { label: "조건 영작", family: "short_answer", category: "writing" },
  };

  const DISTRACTOR_TAGS = {
    PARTIAL_MATCH: "원문 단어는 맞지만 결론이 다른 선택지",
    CAUSAL_REVERSE: "원인과 결과 반전",
    SUBJECT_SWAP: "주체/대상 교체",
    SCOPE_EXPAND: "부분 정보를 전체 주장으로 확대",
    SCOPE_NARROW: "전체 주장을 부분 정보로 축소",
    POLARITY_FLIP: "긍정/부정, 증가/감소 반전",
    TIME_NUMBER_SWAP: "수치, 순서, 날짜 변경",
    GRAMMAR_ONLY: "의미는 자연스럽지만 문법만 틀림",
    COLLOCATION_ERROR: "뜻은 맞지만 결합이 어색함",
    TOO_GENERAL: "너무 넓은 일반화",
    TOO_SPECIFIC: "예시만 가리키는 축소",
  };

  function normalizePassage(text) {
    return String(text || "")
      .replace(/\r/g, "\n")
      .replace(/\u00a0/g, " ")
      .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, " ")
      .replace(/[ \t]+/g, " ")
      .replace(/\n[ \t]+/g, "\n")
      .replace(/[ \t]+\n/g, "\n")
      .replace(/\n{3,}/g, "\n\n")
      .trim();
  }

  function splitSentences(text) {
    const cleaned = String(text || "").replace(/\s+/g, " ").trim();
    if (!cleaned) return [];
    const protectedText = cleaned
      .replace(/\b(Mr|Mrs|Ms|Dr|Prof|St)\./g, "$1<dot>")
      .replace(/\be\.g\./g, "e<dot>g<dot>")
      .replace(/\bi\.e\./g, "i<dot>e<dot>");
    return protectedText
      .split(/(?<=[.!?])\s+(?=[A-Z0-9"'])/)
      .map((sentence) => sentence.replace(/<dot>/g, ".").trim())
      .filter(Boolean);
  }

  function splitPassageIntoUnits(text) {
    const normalized = normalizePassage(text);
    const rawParagraphs = normalized
      .split(/\n{2,}/)
      .map((paragraph) => paragraph.trim())
      .filter(Boolean);
    const paragraphs = rawParagraphs.length ? rawParagraphs : [normalized];
    return paragraphs.map((paragraph, index) => ({
      id: `P${index + 1}`,
      no: index + 1,
      text: paragraph,
      sentences: splitSentences(paragraph).map((sentence, sentenceIndex) => ({
        id: `P${index + 1}-S${sentenceIndex + 1}`,
        no: sentenceIndex + 1,
        text: sentence,
      })),
    }));
  }

  function words(text) {
    return String(text || "")
      .toLowerCase()
      .match(/[a-z][a-z'-]{2,}/g) || [];
  }

  function extractKeywords(text, limit = 16) {
    const counts = new Map();
    for (const rawWord of words(text)) {
      const word = rawWord.replace(/^'+|'+$/g, "");
      if (!word || STOPWORDS.has(word) || word.length < 4) continue;
      counts.set(word, (counts.get(word) || 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1] || b[0].length - a[0].length || a[0].localeCompare(b[0]))
      .slice(0, limit)
      .map(([word, count]) => ({ word, count }));
  }

  function extractConnectors(text) {
    const connectors = [
      "however",
      "therefore",
      "for example",
      "for instance",
      "in contrast",
      "as a result",
      "in other words",
      "moreover",
      "also",
      "instead",
      "although",
      "because",
      "finally",
      "first",
      "second",
      "another",
    ];
    const lower = String(text || "").toLowerCase();
    return connectors
      .filter((connector) => lower.includes(connector))
      .map((connector) => ({ connector, role: connectorRole(connector) }));
  }

  function connectorRole(connector) {
    if (/however|contrast|although|instead/.test(connector)) return "대조";
    if (/therefore|result|because/.test(connector)) return "인과";
    if (/example|instance/.test(connector)) return "예시";
    if (/other words/.test(connector)) return "재진술";
    if (/first|second|another|finally/.test(connector)) return "순서";
    return "부가";
  }

  function classifyParagraph(paragraph, index, total) {
    const lower = paragraph.toLowerCase();
    if (index === 0 && /\?|have you|did you|imagine|let/.test(lower)) return "도입/문제제기";
    if (/means|refers to|is called|defined|concept/.test(lower)) return "정의";
    if (/for example|for instance|such as|take/.test(lower)) return "예시";
    if (/however|in contrast|but|although|instead/.test(lower)) return "대조/반박";
    if (/therefore|as a result|so|thus|consequently/.test(lower)) return "인과/결론";
    if (index === total - 1) return "결론/정리";
    return "설명/전개";
  }

  function extractGrammarCandidates(units) {
    const patterns = [
      { key: "sv_agreement", label: "수일치", regex: /\b(is|are|was|were|has|have)\b/i },
      { key: "relative", label: "관계사", regex: /\b(which|that|who|whom|whose|where|when)\b/i },
      { key: "participle", label: "분사", regex: /\b\w+(ing|ed)\b/i },
      { key: "infinitive", label: "준동사", regex: /\b(to\s+[a-z]+|help\s+[a-z]+|allow\s+\w+\s+to|enable\s+\w+\s+to)\b/i },
      { key: "parallel", label: "병렬", regex: /\b(and|or|but)\b/i },
      { key: "voice", label: "태", regex: /\b(be|been|being|is|are|was|were)\s+\w+ed\b/i },
      { key: "comparison", label: "비교", regex: /\b(more|less|most|least|better|worse|than)\b/i },
    ];
    const candidates = [];
    for (const unit of units) {
      for (const sentence of unit.sentences) {
        for (const pattern of patterns) {
          if (pattern.regex.test(sentence.text)) {
            candidates.push({
              id: `${sentence.id}-${pattern.key}`,
              sentenceId: sentence.id,
              sentence: sentence.text,
              label: pattern.label,
              key: pattern.key,
            });
          }
        }
      }
    }
    return candidates.slice(0, 28);
  }

  function extractVocabularyCandidates(text, keywords) {
    const polarity = [
      "increase",
      "decrease",
      "benefit",
      "harm",
      "success",
      "failure",
      "positive",
      "negative",
      "possible",
      "impossible",
      "common",
      "rare",
      "improve",
      "worsen",
      "expand",
      "reduce",
      "support",
      "prevent",
    ];
    const lower = String(text || "").toLowerCase();
    const hits = polarity.filter((word) => lower.includes(word));
    const keywordWords = keywords.map((keyword) => keyword.word).slice(0, 12);
    return [...new Set([...hits, ...keywordWords])].slice(0, 16).map((word) => ({
      word,
      tag: polarity.includes(word) ? "극성어" : "핵심어",
    }));
  }

  function analyzeComplexityMetrics(text, units) {
    const sentenceList = units.flatMap((unit) => unit.sentences);
    const tokenList = words(text);
    const avgSentenceLength = sentenceList.length
      ? Math.round((tokenList.length / sentenceList.length) * 10) / 10
      : 0;
    const longWords = tokenList.filter((word) => word.length >= 9).length;
    const connectorCount = extractConnectors(text).length;
    const score = Math.min(
      100,
      Math.round(avgSentenceLength * 2.2 + longWords * 1.4 + connectorCount * 5 + units.length * 3),
    );
    const level = score >= 72 ? "상" : score >= 44 ? "중" : "하";
    return {
      paragraphCount: units.length,
      sentenceCount: sentenceList.length,
      wordCount: tokenList.length,
      avgSentenceLength,
      longWordCount: longWords,
      connectorCount,
      difficultyScore: score,
      difficultyLevel: level,
    };
  }

  function analyzePassage(input) {
    const text = normalizePassage(input.text);
    const units = splitPassageIntoUnits(text);
    const keywords = extractKeywords(text);
    const connectors = extractConnectors(text);
    const grammarCandidates = extractGrammarCandidates(units);
    const vocabularyCandidates = extractVocabularyCandidates(text, keywords);
    const metrics = analyzeComplexityMetrics(text, units);
    const paragraphFunctions = units.map((unit, index) => ({
      id: unit.id,
      function: classifyParagraph(unit.text, index, units.length),
      sentenceCount: unit.sentences.length,
      keywords: extractKeywords(unit.text, 5).map((item) => item.word),
    }));
    const id = input.sourceId || makeSourceId(input, text);
    return {
      schemaVersion: "ky-analysis@1",
      engineVersion: ENGINE_VERSION,
      sourceId: id,
      title: input.title || "Untitled passage",
      grade: input.grade || "g1",
      preset: input.preset || input.grade || "g1",
      sourceType: input.sourceType || "textbook",
      sourceRef: input.sourceRef || "",
      examScope: input.examScope || "",
      fingerprint: hashString(text),
      textLength: text.length,
      units,
      paragraphFunctions,
      keywords,
      connectors,
      grammarCandidates,
      vocabularyCandidates,
      metrics,
      recommendations: buildRecommendations(input.grade || "g1", metrics),
      createdAt: new Date().toISOString(),
    };
  }

  function buildRecommendations(grade, metrics) {
    const common = [
      "문단 기능을 먼저 확정한 뒤 문제 유형 비중을 고른다.",
      "오답은 정답 이유가 아니라 매력적인 왜곡 기준으로 설계한다.",
    ];
    if (grade === "g2") {
      common.unshift("학평 원문 유형을 제거하고 제목/어법/내용불일치로 전환한다.");
      common.push("작품/수업지문은 어법수정 단답과 조건영작을 우선 생성한다.");
    } else {
      common.unshift("교과서 본문은 목적/내용불일치/문맥어휘/요약단답 세트로 만든다.");
      common.push("학평 변형은 빈칸에서 삽입, 어법에서 빈칸으로 바꾸는 전환을 우선 적용한다.");
    }
    if (metrics.difficultyLevel === "상") {
      common.push("긴 문장 지문은 순서보다 어법수정과 요약 단답이 적합하다.");
    }
    return common;
  }

  function generateQuestions(analysis, options = {}) {
    const preset = PRESETS[options.preset || analysis.preset || analysis.grade] || PRESETS.g1;
    const targetCount = clamp(Number(options.targetCount) || 30, 1, 120);
    const selectedTypes = options.types && options.types.length ? options.types : preset.defaultTypes;
    const seed = options.seed || `${analysis.fingerprint}-${targetCount}-${selectedTypes.join("-")}`;
    const rng = mulberry32(hashNumber(seed));
    const plan = buildGenerationPlan(preset, selectedTypes, targetCount);
    const generated = [];
    let index = 0;

    for (const type of plan) {
      const generator = GENERATORS[type];
      if (!generator) continue;
      const item = generator(analysis, { rng, index, preset, seed });
      if (!item) continue;
      item.questionId = `KYQ-${Date.now().toString(36)}-${index.toString(36)}`;
      item.engineVersion = ENGINE_VERSION;
      item.schemaVersion = "ky-question@1";
      item.preset = preset.id;
      item.type = type;
      item.typeLabel = TYPE_META[type].label;
      item.family = TYPE_META[type].family;
      item.sourceId = analysis.sourceId;
      item.sourceTitle = analysis.title;
      item.sourceType = analysis.sourceType;
      item.sourceRef = analysis.sourceRef;
      item.examScope = analysis.examScope;
      item.createdAt = new Date().toISOString();
      item.quality = validateItem(item);
      generated.push(item);
      index += 1;
    }
    return generated;
  }

  function buildGenerationPlan(preset, selectedTypes, targetCount) {
    const weights = selectedTypes.map((type) => [type, preset.typeWeights[type] || 1]);
    const totalWeight = weights.reduce((sum, [, weight]) => sum + weight, 0);
    const plan = [];
    for (const [type, weight] of weights) {
      const count = Math.max(1, Math.round((targetCount * weight) / totalWeight));
      for (let i = 0; i < count; i += 1) plan.push(type);
    }
    while (plan.length < targetCount) plan.push(selectedTypes[plan.length % selectedTypes.length]);
    return plan.slice(0, targetCount);
  }

  const GENERATORS = {
    gist: generateGistItem,
    content_false: generateContentFalseItem,
    context_vocab: generateContextVocabItem,
    grammar_mc: generateGrammarMcItem,
    grammar_edit: generateGrammarEditItem,
    order: generateOrderItem,
    insertion: generateInsertionItem,
    summary_short: generateSummaryShortItem,
    condition_writing: generateConditionWritingItem,
  };

  function generateGistItem(analysis, ctx) {
    const kws = keywordWords(analysis);
    const correct = `글의 핵심은 ${pickKeyword(kws, 0)}와 ${pickKeyword(kws, 1)}의 관계를 이해하는 데 있다.`;
    const options = shuffle(
      [
        correct,
        `글은 ${pickKeyword(kws, 2)}의 종류만을 나열한다.`,
        `${pickKeyword(kws, 3)}의 역사적 배경이 글의 유일한 목적이다.`,
        `${pickKeyword(kws, 4)}를 완전히 부정해야 한다는 주장이다.`,
        `개인의 취향이 모든 판단보다 중요하다는 내용이다.`,
      ],
      ctx.rng,
    );
    return makeObjective({
      stem: "다음 글의 제목 또는 요지로 가장 적절한 것은?",
      options,
      answer: options.indexOf(correct) + 1,
      explanation: "반복 핵심어와 결론 기능 문단을 기준으로 가장 포괄적인 선택지를 고른다.",
      evidence: evidenceFromAnalysis(analysis, "결론/요지"),
      distractorTags: ["TOO_SPECIFIC", "TOO_GENERAL", "POLARITY_FLIP"],
      difficulty: analysis.metrics.difficultyLevel,
      transformRule: "본문/학평 지문 -> 제목/요지형",
    });
  }

  function generateContentFalseItem(analysis, ctx) {
    const sentences = usableSentences(analysis).slice(0, 8);
    if (sentences.length < 3) return generateGistItem(analysis, ctx);
    const chosen = sentences.slice(0, 5);
    const answerIndex = Math.floor(ctx.rng() * chosen.length);
    const options = chosen.map((sentence, index) =>
      index === answerIndex ? flipStatement(sentence.text) : shorten(sentence.text, 130),
    );
    return makeObjective({
      stem: "다음 글의 내용과 일치하지 않는 것은?",
      options,
      answer: answerIndex + 1,
      explanation: "정답 선택지는 원문 사실의 극성, 범위, 조건 중 하나를 바꾼 것이다.",
      evidence: `${chosen[answerIndex].id}: ${shorten(chosen[answerIndex].text, 150)}`,
      distractorTags: ["PARTIAL_MATCH", "POLARITY_FLIP", "SCOPE_EXPAND"],
      difficulty: "중",
      transformRule: "원문 사실 -> 내용불일치 선택지",
    });
  }

  function generateContextVocabItem(analysis, ctx) {
    const vocab = analysis.vocabularyCandidates.length
      ? analysis.vocabularyCandidates
      : keywordWords(analysis).map((word) => ({ word, tag: "핵심어" }));
    const target = vocab[Math.floor(ctx.rng() * vocab.length)]?.word || "concept";
    const correct = target;
    const pool = [...keywordWords(analysis), ...oppositePool(target), "context", "result", "process"].filter(
      (word) => word && word !== correct,
    );
    const options = shuffle(unique([correct, ...pool]).slice(0, 5), ctx.rng);
    while (options.length < 5) options.push(`option${options.length + 1}`);
    return makeObjective({
      stem: `다음 글의 문맥상 빈칸에 들어갈 말로 가장 적절한 것은? (${target} 계열)`,
      options,
      answer: options.indexOf(correct) + 1,
      explanation: "문맥의 의미 방향과 주변 collocation을 기준으로 판단한다.",
      evidence: evidenceContaining(analysis, target),
      distractorTags: ["COLLOCATION_ERROR", "POLARITY_FLIP", "PARTIAL_MATCH"],
      difficulty: "중",
      transformRule: "핵심어/극성어 -> 문맥상 어휘형",
    });
  }

  function generateGrammarMcItem(analysis, ctx) {
    const candidates = analysis.grammarCandidates.length
      ? analysis.grammarCandidates
      : usableSentences(analysis).map((sentence) => ({ sentence: sentence.text, sentenceId: sentence.id, label: "문장구조" }));
    const chosen = sample(candidates, 5, ctx.rng);
    if (!chosen.length) return null;
    const wrongIndex = Math.floor(ctx.rng() * chosen.length);
    const options = chosen.map((candidate, index) => {
      const fragment = extractGrammarFragment(candidate.sentence);
      return index === wrongIndex ? injectGrammarError(fragment).wrong : fragment;
    });
    const original = extractGrammarFragment(chosen[wrongIndex].sentence);
    const wrong = options[wrongIndex];
    return makeObjective({
      stem: "다음 밑줄 친 부분 중 어법상 틀린 것은?",
      options,
      answer: wrongIndex + 1,
      explanation: `정답은 ${wrong} -> ${original} 방향으로 고쳐야 한다. 후보 문법: ${chosen[wrongIndex].label}`,
      evidence: `${chosen[wrongIndex].sentenceId}: ${shorten(chosen[wrongIndex].sentence, 150)}`,
      distractorTags: ["GRAMMAR_ONLY"],
      difficulty: "상",
      transformRule: "원문 문장 -> 어법 객관식",
    });
  }

  function generateGrammarEditItem(analysis, ctx) {
    const candidates = analysis.grammarCandidates.length
      ? analysis.grammarCandidates
      : usableSentences(analysis).map((sentence) => ({ sentence: sentence.text, sentenceId: sentence.id, label: "문장구조" }));
    const candidate = candidates[Math.floor(ctx.rng() * candidates.length)];
    if (!candidate) return null;
    const injected = injectGrammarError(candidate.sentence);
    return makeShortAnswer({
      stem: "다음 문장에서 어법상 틀린 단어를 찾아 바르게 고쳐 쓰시오.",
      prompt: injected.marked,
      answer: [`${injected.wrong} -> ${injected.correct}`],
      explanation: `광영여고 단답형은 오류 단어와 수정형을 모두 요구한다. 문법 사인: ${candidate.label}`,
      evidence: `${candidate.sentenceId}: ${shorten(candidate.sentence, 150)}`,
      distractorTags: ["GRAMMAR_ONLY"],
      difficulty: "상",
      transformRule: "원문 문장 -> 어법수정 단답",
      scoring: ["오류 단어 식별", "정확한 수정형", "철자와 수일치"],
    });
  }

  function generateOrderItem(analysis, ctx) {
    const chunks = getOrderChunks(analysis);
    if (chunks.length < 3) return generateContentFalseItem(analysis, ctx);
    const selected = chunks.slice(0, 3);
    const shuffled = shuffle(selected, ctx.rng);
    const labels = ["A", "B", "C"];
    const options = ["A-B-C", "A-C-B", "B-A-C", "B-C-A", "C-A-B", "C-B-A"];
    const labeled = shuffled.map((chunk, index) => ({
      label: labels[index],
      id: chunk.id,
      text: chunk.text,
    }));
    const answerOrder = selected.map((chunk) => labeled.find((item) => item.id === chunk.id)?.label).join("-");
    return makeObjective({
      stem: `주어진 글 다음에 이어질 글의 순서로 가장 적절한 것은?\n${labeled
        .map((item) => `(${item.label}) ${shorten(item.text, 180)}`)
        .join("\n")}`,
      options,
      answer: Math.max(1, options.indexOf(answerOrder) + 1),
      explanation: "지시어, 연결어, 예시-일반화 흐름을 기준으로 원문 순서를 복원한다.",
      evidence: selected.map((chunk) => chunk.id).join(" -> "),
      distractorTags: ["PARTIAL_MATCH", "TOO_SPECIFIC"],
      difficulty: "상",
      transformRule: "문단/문장 흐름 -> 순서형",
    });
  }

  function generateInsertionItem(analysis, ctx) {
    const sentences = usableSentences(analysis);
    if (sentences.length < 5) return generateOrderItem(analysis, ctx);
    const insertSentence =
      sentences.find((sentence) => /however|therefore|for example|this|these|such|another/i.test(sentence.text)) ||
      sentences[Math.min(2, sentences.length - 1)];
    const remaining = sentences.filter((sentence) => sentence.id !== insertSentence.id).slice(0, 5);
    const originalIndex = sentences.findIndex((sentence) => sentence.id === insertSentence.id);
    const answer = Math.min(5, Math.max(1, originalIndex));
    const positions = ["①", "②", "③", "④", "⑤"];
    return makeObjective({
      stem: `글의 흐름으로 보아, 다음 문장이 들어가기에 가장 적절한 곳은?\n[삽입문] ${shorten(
        insertSentence.text,
        180,
      )}\n${remaining.map((sentence, index) => `${positions[index]} ${shorten(sentence.text, 120)}`).join("\n")}`,
      options: positions,
      answer,
      explanation: "삽입문 안의 지시어와 연결어가 앞뒤 문맥과 맞는 위치를 찾는다.",
      evidence: insertSentence.id,
      distractorTags: ["PARTIAL_MATCH", "TOO_GENERAL"],
      difficulty: "상",
      transformRule: "연결어/지시어 문장 -> 문장삽입형",
    });
  }

  function generateSummaryShortItem(analysis, ctx) {
    const kws = keywordWords(analysis);
    const first = pickKeyword(kws, Math.floor(ctx.rng() * Math.max(1, kws.length)));
    const second = pickKeyword(kws, Math.floor(ctx.rng() * Math.max(1, kws.length - 1)) + 1);
    return makeShortAnswer({
      stem: "다음 글을 한 문장으로 요약할 때 빈칸 (A), (B)에 들어갈 말을 본문에서 찾아 쓰시오.",
      prompt: `The passage shows that (A) ${blank()} and (B) ${blank()} are central to understanding the writer's point.`,
      answer: [first, second],
      explanation: "반복 핵심어와 결론 문단의 추상어를 요약 빈칸으로 묻는다.",
      evidence: evidenceFromAnalysis(analysis, "핵심어"),
      distractorTags: ["PARTIAL_MATCH", "SCOPE_EXPAND"],
      difficulty: "중상",
      transformRule: "원문 핵심어 -> 요약 단답",
      scoring: ["본문 내 핵심어", "품사 적합성", "철자"],
    });
  }

  function generateConditionWritingItem(analysis, ctx) {
    const sentence = chooseWritableSentence(analysis, ctx.rng);
    const bank = shuffle(wordsFromSentence(sentence.text).slice(0, 12), ctx.rng);
    return makeShortAnswer({
      stem: "아래 조건에 맞게 보기의 단어를 모두 사용하여 문장을 완성하시오.",
      prompt: `조건: 보기 단어를 모두 한 번씩 사용하고, 원문의 의미가 유지되도록 배열하시오.\n보기: ${bank.join(" / ")}`,
      answer: [sentence.text],
      explanation: "조건 영작은 의미뿐 아니라 어순, 위치, 동사 형태까지 채점한다.",
      evidence: sentence.id,
      distractorTags: ["GRAMMAR_ONLY", "COLLOCATION_ERROR"],
      difficulty: "상",
      transformRule: "원문 문장 -> 조건 영작",
      scoring: ["필수어 사용", "어순", "시제/태", "위치", "의미 일치"],
    });
  }

  function makeObjective(base) {
    return {
      ...base,
      family: "objective",
      points: base.difficulty === "상" ? 3.8 : base.difficulty === "중상" ? 3.5 : 3.2,
    };
  }

  function makeShortAnswer(base) {
    return {
      ...base,
      family: "short_answer",
      points: base.difficulty === "상" ? 6 : 4,
      options: [],
    };
  }

  function validateItem(item) {
    const issues = [];
    if (!item.stem || item.stem.length < 8) issues.push("문항 발문이 너무 짧음");
    if (item.family === "objective") {
      if (!Array.isArray(item.options) || item.options.length < 2) issues.push("객관식 보기가 부족함");
      if (!Number.isInteger(item.answer) || item.answer < 1 || item.answer > item.options.length) {
        issues.push("정답 번호가 보기 범위를 벗어남");
      }
      const optionSet = new Set(item.options.map((option) => normalizeOption(option)));
      if (optionSet.size !== item.options.length) issues.push("중복 보기가 있음");
    }
    if (item.family === "short_answer" && (!item.answer || !item.answer.length)) issues.push("단답형 정답 누락");
    if (!item.evidence) issues.push("근거 위치 누락");
    if (!item.transformRule) issues.push("변형 규칙 누락");
    const score = Math.max(0, 100 - issues.length * 15);
    return {
      score,
      status: score >= 85 ? "검수통과" : score >= 70 ? "수정필요" : "폐기권장",
      issues,
    };
  }

  function composeMockExam(bankItems, constraints = {}) {
    const preset = PRESETS[constraints.preset || "g1"] || PRESETS.g1;
    const blueprint = { ...preset.blueprint, ...constraints.blueprint };
    const seed = constraints.seed || `mock-${Date.now()}`;
    const rng = mulberry32(hashNumber(seed));
    const shuffled = shuffle([...bankItems], rng);
    const shortTarget = Number(constraints.shortAnswerCount || blueprint.shortAnswer || 4);
    const objectiveTarget = Number(constraints.objectiveCount || blueprint.totalObjective || 27);
    const shortAnswers = shuffled.filter((item) => item.family === "short_answer").slice(0, shortTarget);
    const objectivePool = shuffled.filter((item) => item.family !== "short_answer").slice(0, objectiveTarget);
    const finalItems = shuffle([...objectivePool, ...shortAnswers], rng).map((item, index) => ({
      ...item,
      examNo: index + 1,
    }));
    return {
      schemaVersion: "ky-mock@1",
      engineVersion: ENGINE_VERSION,
      mockId: `KYM-${Date.now().toString(36)}`,
      title: constraints.title || `${preset.label} 동형 모의고사`,
      preset: preset.id,
      blueprint,
      itemCount: finalItems.length,
      shortAnswerCount: finalItems.filter((item) => item.family === "short_answer").length,
      totalPoints: Math.round(finalItems.reduce((sum, item) => sum + (Number(item.points) || 0), 0) * 10) / 10,
      items: finalItems,
      createdAt: new Date().toISOString(),
    };
  }

  function serializeBankItem(item) {
    const allowed = [
      "questionId",
      "schemaVersion",
      "engineVersion",
      "preset",
      "type",
      "typeLabel",
      "family",
      "sourceId",
      "sourceTitle",
      "sourceType",
      "sourceRef",
      "examScope",
      "stem",
      "prompt",
      "options",
      "answer",
      "explanation",
      "evidence",
      "distractorTags",
      "difficulty",
      "points",
      "transformRule",
      "scoring",
      "quality",
      "createdAt",
    ];
    return Object.fromEntries(allowed.map((key) => [key, item[key] ?? ""]));
  }

  function exportCsv(rows) {
    if (!rows.length) return "";
    const flatRows = rows.map((row) => flattenForCsv(row));
    const headers = unique(flatRows.flatMap((row) => Object.keys(row)));
    const lines = [headers.join(",")];
    for (const row of flatRows) {
      lines.push(headers.map((header) => csvCell(row[header])).join(","));
    }
    return "\ufeff" + lines.join("\n");
  }

  function flattenForCsv(row) {
    const output = {};
    for (const [key, value] of Object.entries(row)) {
      if (Array.isArray(value)) output[key] = value.join(" | ");
      else if (value && typeof value === "object") output[key] = JSON.stringify(value);
      else output[key] = value ?? "";
    }
    return output;
  }

  function csvCell(value) {
    const text = String(value ?? "");
    const escaped = text.replace(/"/g, '""');
    if (/^[=+\-@]/.test(text)) return "\"'" + escaped + "\"";
    if (/[",\n]/.test(text)) return "\"" + escaped + "\"";
    return text;
  }

  function makeSourceId(input, text) {
    const grade = input.grade || "G";
    const title = slug(input.title || "passage").slice(0, 18);
    return `${grade.toUpperCase()}-${title}-${hashString(text).slice(0, 8)}`;
  }

  function unique(items) {
    return [...new Set(items.filter((item) => item !== undefined && item !== null && item !== ""))];
  }

  function shuffle(items, rng = Math.random) {
    const arr = [...items];
    for (let i = arr.length - 1; i > 0; i -= 1) {
      const j = Math.floor(rng() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
    return arr;
  }

  function sample(items, count, rng = Math.random) {
    return shuffle(items, rng).slice(0, count);
  }

  function usableSentences(analysis) {
    return analysis.units
      .flatMap((unit) => unit.sentences)
      .filter((sentence) => sentence.text.length >= 38)
      .slice(0, 60);
  }

  function keywordWords(analysis) {
    return analysis.keywords.map((item) => item.word);
  }

  function pickKeyword(keywords, index) {
    return keywords[index % Math.max(1, keywords.length)] || "central idea";
  }

  function evidenceFromAnalysis(analysis, label) {
    const last = analysis.units[analysis.units.length - 1];
    const sentence = last?.sentences?.[last.sentences.length - 1] || usableSentences(analysis)[0];
    return `${label}: ${sentence ? shorten(sentence.text, 150) : analysis.sourceId}`;
  }

  function evidenceContaining(analysis, target) {
    const sentence =
      usableSentences(analysis).find((item) => item.text.toLowerCase().includes(String(target).toLowerCase())) ||
      usableSentences(analysis)[0];
    return sentence ? `${sentence.id}: ${shorten(sentence.text, 150)}` : analysis.sourceId;
  }

  function shorten(text, limit = 120) {
    const clean = String(text || "").replace(/\s+/g, " ").trim();
    return clean.length > limit ? `${clean.slice(0, limit - 1)}...` : clean;
  }

  function flipStatement(text) {
    const replacements = [
      [/\bcan\b/i, "cannot"],
      [/\bcannot\b/i, "can"],
      [/\bincrease(s|d)?\b/i, "decrease$1"],
      [/\bdecrease(s|d)?\b/i, "increase$1"],
      [/\bmore\b/i, "less"],
      [/\bless\b/i, "more"],
      [/\bbenefit(s|ed)?\b/i, "harm$1"],
      [/\bharm(s|ed)?\b/i, "benefit$1"],
      [/\bpositive\b/i, "negative"],
      [/\bnegative\b/i, "positive"],
      [/\balways\b/i, "never"],
      [/\bnever\b/i, "always"],
      [/\bshould\b/i, "should not"],
    ];
    for (const [regex, replacement] of replacements) {
      if (regex.test(text)) return shorten(text.replace(regex, replacement), 130);
    }
    return shorten(`Only ${text.charAt(0).toLowerCase()}${text.slice(1)}`, 130);
  }

  function oppositePool(word) {
    const opposites = {
      increase: ["decrease", "reduce", "limit"],
      decrease: ["increase", "expand", "raise"],
      benefit: ["harm", "damage", "weaken"],
      harm: ["benefit", "support", "improve"],
      positive: ["negative", "harmful", "limited"],
      negative: ["positive", "helpful", "useful"],
      common: ["rare", "unusual", "exceptional"],
      rare: ["common", "ordinary", "frequent"],
      improve: ["worsen", "damage", "reduce"],
      reduce: ["increase", "expand", "raise"],
      support: ["prevent", "weaken", "oppose"],
      prevent: ["support", "allow", "encourage"],
    };
    return opposites[word] || [];
  }

  function extractGrammarFragment(sentence) {
    const matches = String(sentence || "").match(
      /\b(is|are|was|were|has|have|which|that|who|where|when|to\s+[a-z]+|\w+ing|\w+ed)\b/i,
    );
    if (matches) return matches[0];
    const candidates = wordsFromSentence(sentence);
    return candidates[Math.min(2, candidates.length - 1)] || "is";
  }

  function injectGrammarError(text) {
    const source = String(text || "");
    const rules = [
      [/\bis\b/i, "are"],
      [/\bare\b/i, "is"],
      [/\bwas\b/i, "were"],
      [/\bwere\b/i, "was"],
      [/\bhas\b/i, "have"],
      [/\bhave\b/i, "has"],
      [/\bwhich\b/i, "where"],
      [/\bwhere\b/i, "which"],
      [/\bwho\b/i, "which"],
      [/\bto ([a-z]+)\b/i, "$1ing"],
      [/\bbeing\b/i, "be"],
    ];
    for (const [regex, replacement] of rules) {
      const match = source.match(regex);
      if (match) {
        const correct = match[0];
        const wrongSentence = source.replace(regex, replacement);
        const wrong = wrongSentence === source ? replacement : wrongSentence.slice(match.index, match.index + replacement.length + 8).split(/\s+/)[0];
        return {
          correct,
          wrong,
          marked: source.replace(regex, `[${wrong}]`),
        };
      }
    }
    const tokens = wordsFromSentence(source);
    const correct = tokens[0] || "word";
    return {
      correct,
      wrong: `${correct}s`,
      marked: source.replace(correct, `[${correct}s]`),
    };
  }

  function getOrderChunks(analysis) {
    if (analysis.units.length >= 3) {
      return analysis.units.map((unit) => ({ id: unit.id, text: unit.text }));
    }
    return usableSentences(analysis)
      .slice(0, 6)
      .map((sentence) => ({ id: sentence.id, text: sentence.text }));
  }

  function chooseWritableSentence(analysis, rng) {
    const sentences = usableSentences(analysis).filter((sentence) => {
      const count = wordsFromSentence(sentence.text).length;
      return count >= 7 && count <= 18;
    });
    return sentences[Math.floor(rng() * Math.max(1, sentences.length))] || usableSentences(analysis)[0] || { id: "S1", text: "" };
  }

  function wordsFromSentence(sentence) {
    return String(sentence || "")
      .replace(/[^\w\s'-]/g, " ")
      .split(/\s+/)
      .map((word) => word.trim())
      .filter(Boolean);
  }

  function blank() {
    return "________";
  }

  function normalizeOption(option) {
    return String(option || "").replace(/\s+/g, " ").trim().toLowerCase();
  }

  function slug(text) {
    return String(text || "")
      .toLowerCase()
      .replace(/[^a-z0-9가-힣]+/g, "-")
      .replace(/^-+|-+$/g, "");
  }

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function hashString(text) {
    let hash = 2166136261;
    for (let i = 0; i < String(text).length; i += 1) {
      hash ^= String(text).charCodeAt(i);
      hash = Math.imul(hash, 16777619);
    }
    return (hash >>> 0).toString(16);
  }

  function hashNumber(text) {
    return parseInt(hashString(text), 16) || 1;
  }

  function mulberry32(seed) {
    let value = seed >>> 0;
    return function () {
      value += 0x6d2b79f5;
      let t = value;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  return {
    ENGINE_VERSION,
    PRESETS,
    TYPE_META,
    DISTRACTOR_TAGS,
    normalizePassage,
    splitSentences,
    splitPassageIntoUnits,
    extractKeywords,
    extractConnectors,
    extractGrammarCandidates,
    extractVocabularyCandidates,
    analyzeComplexityMetrics,
    analyzePassage,
    generateQuestions,
    validateItem,
    composeMockExam,
    serializeBankItem,
    exportCsv,
    shuffleItemsDeterministic: shuffle,
    _private: {
      hashString,
      mulberry32,
      buildGenerationPlan,
      flipStatement,
      injectGrammarError,
    },
  };
});
