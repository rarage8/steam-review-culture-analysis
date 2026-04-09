const UI_LANGS = ["japanese", "english", "schinese", "russian", "german", "koreana"];
const LANGUAGE_META = {
  japanese: { flag: "🇯🇵", labels: { japanese: "日本語", english: "Japanese", schinese: "日语", russian: "Японский", german: "Japanisch", koreana: "일본어" } },
  english: { flag: "🇺🇸", labels: { japanese: "英語", english: "English", schinese: "英语", russian: "Английский", german: "Englisch", koreana: "영어" } },
  schinese: { flag: "🇨🇳", labels: { japanese: "中国語", english: "Chinese", schinese: "简体中文", russian: "Китайский", german: "Chinesisch", koreana: "중국어" } },
  russian: { flag: "🇷🇺", labels: { japanese: "ロシア語", english: "Russian", schinese: "俄语", russian: "Русский", german: "Russisch", koreana: "러시아어" } },
  german: { flag: "🇩🇪", labels: { japanese: "ドイツ語", english: "German", schinese: "德语", russian: "Немецкий", german: "Deutsch", koreana: "독일어" } },
  koreana: { flag: "🇰🇷", labels: { japanese: "韓国語", english: "Korean", schinese: "韩语", russian: "Корейский", german: "Koreanisch", koreana: "한국어" } },
};

const I18N = {
  japanese: {
    topbarSub: "言語別レビュー文化とプレイヤー人口の変化を比較します。",
    navLabel: "Pages",
    navReviews: "レビュー分析",
    navPopulation: "プレイヤー人口",
    reviewsHd: "言語別レビュー分析",
    reviewsSub: "ゲームごとに、言語別の評価傾向・翻訳済みレビュー・レビューまでに費やしたプレイ時間を確認できます。",
    reviewsGameHd: "ゲーム選択",
    reviewsGameSub: "1つのゲームを選んで、言語ごとの差を深掘りします。",
    reviewCardsHd: "言語ごとのレビュー温度感",
    reviewCardsSub: "カードを開くと、右上の表示言語に合わせてレビュー本文を表示します。原文も下に残します。",
    reviewPanelHd: "レビュー本文",
    reviewPanelSub: "表示言語は右上の切り替えに連動します。翻訳がない場合は英語または原文を表示します。",
    positive: "ポジティブ",
    neutral: "中立",
    negative: "ネガティブ",
    emptyReviews: "レビューがありません。",
    clickHint: "クリックで詳細",
    timingHd: "レビューまでに費やしたプレイ時間",
    timingSub: "言語別かつ感情別に、レビュー投稿時点までの平均プレイ日数を比較します。",
    timingNote: "Steam レビュー API には購入日時が含まれないため、このグラフは review 時点の playtime_at_review / playtime_forever を使った『レビューまでに費やしたプレイ時間』です。",
    timingStatLang: "選択中の言語",
    timingStatPositive: "平均ポジティブ日数",
    timingStatNegative: "平均ネガティブ日数",
    timingStatNeutral: "平均中立日数",
    days: "日",
    populationHd: "プレイヤー人口の比較",
    populationSub: "日次・週次・月次のスナップショットを集約して、複数ゲームを折れ線グラフで比較します。",
    populationPeriodHd: "比較条件",
    populationPeriodSub: "粒度とゲームを切り替えて推移を見比べます。",
    populationNote: "人口は Steam の現在同時接続 API を定期保存したスナップショットから再集計しています。履歴が少ない期間は線が短くなります。",
    daily: "日次",
    weekly: "週次",
    monthly: "月次",
    generated: "最終生成",
    noPopulation: "人口データがまだありません。`src/fetch_player_counts.py` を実行してください。",
  },
  english: {
    topbarSub: "Compare language-specific review culture and player population trends.",
    navLabel: "Pages",
    navReviews: "Review Analysis",
    navPopulation: "Player Population",
    reviewsHd: "Language-Specific Review Analysis",
    reviewsSub: "Inspect review sentiment, translated review samples, and time spent before reviewing for each game.",
    reviewsGameHd: "Game",
    reviewsGameSub: "Choose one game to compare languages in detail.",
    reviewCardsHd: "Review Temperature by Language",
    reviewCardsSub: "Open a card to see review samples in the UI language selected in the top-right corner.",
    reviewPanelHd: "Review Samples",
    reviewPanelSub: "The UI language selector also controls the displayed review translation. Original text stays visible underneath.",
    positive: "Positive",
    neutral: "Neutral",
    negative: "Negative",
    emptyReviews: "No reviews available.",
    clickHint: "Open details",
    timingHd: "Time Spent Before Reviewing",
    timingSub: "Compare average playtime-to-review days by language and sentiment.",
    timingNote: "Steam's review API does not expose purchase dates. This chart uses playtime_at_review / playtime_forever as observable time spent before posting a review.",
    timingStatLang: "Selected language",
    timingStatPositive: "Avg positive days",
    timingStatNegative: "Avg negative days",
    timingStatNeutral: "Avg neutral days",
    days: "days",
    populationHd: "Player Population Comparison",
    populationSub: "Compare games with day, week, and month level player-count trends in a line chart.",
    populationPeriodHd: "Comparison Settings",
    populationPeriodSub: "Switch granularity and choose games to compare on the same chart.",
    populationNote: "Population history is aggregated from stored snapshots of Steam's current-player API. Shorter lines mean we have less history for that window.",
    daily: "Daily",
    weekly: "Weekly",
    monthly: "Monthly",
    generated: "Generated",
    noPopulation: "No population data yet. Run `src/fetch_player_counts.py` first.",
  },
};

UI_LANGS.forEach((lang) => {
  if (!I18N[lang]) I18N[lang] = I18N.english;
});

let dashboard = null;
let uiLang = localStorage.getItem("steam-lang") || "japanese";
let theme = localStorage.getItem("steam-theme") || "dark";
let currentGameId = null;
let selectedReviewLang = null;
let selectedPopulationGames = [];
let populationPeriod = "monthly";
let timingChart = null;
let populationChart = null;

const t = (key) => (I18N[uiLang] || I18N.english)[key] || key;

function themeVars() {
  const styles = getComputedStyle(document.documentElement);
  return {
    text: styles.getPropertyValue("--text").trim(),
    text2: styles.getPropertyValue("--text-2").trim(),
    border: styles.getPropertyValue("--border").trim(),
    positive: styles.getPropertyValue("--positive").trim(),
    neutral: styles.getPropertyValue("--neutral").trim(),
    negative: styles.getPropertyValue("--negative").trim(),
  };
}

function approvalColor(rate) {
  const hue = Math.round(8 + rate * 120);
  return `linear-gradient(135deg, hsla(${hue}, 78%, 50%, 0.92), hsla(${Math.max(0, hue - 20)}, 68%, 38%, 0.98))`;
}

function getGameMeta(gameId) {
  return (dashboard?.games || []).find((game) => game.id === gameId) || null;
}

function getGameReviews(gameId) {
  return (dashboard?.reviews || {})[gameId] || {};
}

function formatGeneratedAt() {
  const generatedAt = dashboard?.meta?.generated_at;
  if (!generatedAt) return "";
  try {
    return `${t("generated")}: ${new Date(generatedAt).toLocaleString()}`;
  } catch {
    return `${t("generated")}: ${generatedAt}`;
  }
}

function translatedReviewText(review) {
  return review?.translations?.[uiLang] || review?.english || review?.original || "";
}

function renderStaticText() {
  document.documentElement.lang = uiLang === "japanese" ? "ja" : "en";
  document.getElementById("uiLangSel").value = uiLang;
  document.getElementById("topbarSub").textContent = t("topbarSub");
  document.getElementById("navLabel").textContent = t("navLabel");
  document.getElementById("navReviews").textContent = t("navReviews");
  document.getElementById("navPopulation").textContent = t("navPopulation");
  document.getElementById("reviewsHd").textContent = t("reviewsHd");
  document.getElementById("reviewsSub").textContent = t("reviewsSub");
  document.getElementById("reviewsGameHd").textContent = t("reviewsGameHd");
  document.getElementById("reviewsGameSub").textContent = t("reviewsGameSub");
  document.getElementById("reviewCardsHd").textContent = t("reviewCardsHd");
  document.getElementById("reviewCardsSub").textContent = t("reviewCardsSub");
  document.getElementById("reviewPanelHd").textContent = t("reviewPanelHd");
  document.getElementById("reviewPanelSub").textContent = t("reviewPanelSub");
  document.getElementById("positiveHd").textContent = t("positive");
  document.getElementById("neutralHd").textContent = t("neutral");
  document.getElementById("negativeHd").textContent = t("negative");
  document.getElementById("timingHd").textContent = t("timingHd");
  document.getElementById("timingSub").textContent = t("timingSub");
  document.getElementById("timingNote").textContent = t("timingNote");
  document.getElementById("populationHd").textContent = t("populationHd");
  document.getElementById("populationSub").textContent = t("populationSub");
  document.getElementById("populationPeriodHd").textContent = t("populationPeriodHd");
  document.getElementById("populationPeriodSub").textContent = t("populationPeriodSub");
  document.getElementById("populationNote").textContent = t("populationNote");
  document.getElementById("generatedNote").textContent = formatGeneratedAt();
}

function buildGameSelector(containerId, selectedIds, onClick) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  (dashboard?.games || []).forEach((game) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "selector-btn" + (selectedIds.includes(game.id) ? " active" : "");
    btn.textContent = game.title;
    btn.addEventListener("click", () => onClick(game.id));
    container.appendChild(btn);
  });
}

function renderLanguageCards() {
  const grid = document.getElementById("langGrid");
  grid.innerHTML = "";
  const gameReviews = getGameReviews(currentGameId);
  Object.entries(gameReviews).forEach(([langKey, langData]) => {
    const meta = LANGUAGE_META[langKey] || LANGUAGE_META.english;
    const card = document.createElement("button");
    card.type = "button";
    card.className = "lang-card" + (selectedReviewLang === langKey ? " selected" : "");
    card.style.background = approvalColor(langData.approval_rate || 0);
    card.innerHTML = `
      <div class="lang-card-top">
        <span class="flag">${meta.flag}</span>
        <span class="rate">${Math.round((langData.approval_rate || 0) * 100)}%</span>
      </div>
      <div>${meta.labels[uiLang] || meta.labels.english}</div>
      <div class="counts">
        <span>${t("positive")}: ${langData.pos_count || 0}</span>
        <span>${t("neutral")}: ${langData.neu_count || 0}</span>
        <span>${t("negative")}: ${langData.neg_count || 0}</span>
      </div>
      <div class="counts"><span>${t("clickHint")}</span></div>
    `;
    card.addEventListener("click", () => {
      selectedReviewLang = langKey;
      renderLanguageCards();
      renderReviewPanel();
      renderTimingStats();
    });
    grid.appendChild(card);
  });
}

function renderReviewList(containerId, reviews) {
  const container = document.getElementById(containerId);
  container.innerHTML = "";
  if (!reviews || reviews.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty";
    empty.textContent = t("emptyReviews");
    container.appendChild(empty);
    return;
  }
  reviews.forEach((review) => {
    const translated = translatedReviewText(review);
    const original = review.original || review.english || "";
    const showOriginal = original && original !== translated;
    const item = document.createElement("article");
    item.className = "review-item";
    item.innerHTML = `
      <p class="review-main"></p>
      ${showOriginal ? '<p class="review-original"></p>' : ""}
    `;
    item.querySelector(".review-main").textContent = translated;
    if (showOriginal) item.querySelector(".review-original").textContent = original;
    container.appendChild(item);
  });
}

function renderReviewPanel() {
  const panel = document.getElementById("reviewPanel");
  if (!currentGameId || !selectedReviewLang) {
    panel.classList.remove("visible");
    return;
  }
  const game = getGameMeta(currentGameId);
  const langMeta = LANGUAGE_META[selectedReviewLang] || LANGUAGE_META.english;
  const langData = getGameReviews(currentGameId)[selectedReviewLang];
  if (!game || !langData) {
    panel.classList.remove("visible");
    return;
  }
  panel.classList.add("visible");
  document.getElementById("reviewPanelHd").textContent = `${langMeta.flag} ${langMeta.labels[uiLang] || langMeta.labels.english} × ${game.title}`;
  renderReviewList("positiveReviews", langData.sample_reviews?.positive || []);
  renderReviewList("neutralReviews", langData.sample_reviews?.neutral || []);
  renderReviewList("negativeReviews", langData.sample_reviews?.negative || []);
}

function renderTimingChart() {
  const vars = themeVars();
  const reviewMap = getGameReviews(currentGameId);
  const labels = Object.keys(reviewMap).map((lang) => LANGUAGE_META[lang]?.labels?.[uiLang] || lang);
  const positive = Object.keys(reviewMap).map((lang) => reviewMap[lang]?.review_timing?.positive?.avg_days ?? null);
  const neutral = Object.keys(reviewMap).map((lang) => reviewMap[lang]?.review_timing?.neutral?.avg_days ?? null);
  const negative = Object.keys(reviewMap).map((lang) => reviewMap[lang]?.review_timing?.negative?.avg_days ?? null);
  if (timingChart) timingChart.destroy();
  timingChart = new Chart(document.getElementById("timingChart"), {
    type: "bar",
    data: {
      labels,
      datasets: [
        { label: t("positive"), data: positive, backgroundColor: vars.positive },
        { label: t("neutral"), data: neutral, backgroundColor: vars.neutral },
        { label: t("negative"), data: negative, backgroundColor: vars.negative },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: vars.text2 }, grid: { color: vars.border } },
        y: { ticks: { color: vars.text2 }, grid: { color: vars.border } },
      },
      plugins: {
        legend: { labels: { color: vars.text } },
        tooltip: { callbacks: { label: (ctx) => `${ctx.dataset.label}: ${ctx.raw ?? "-"} ${t("days")}` } },
      },
    },
  });
}

function renderTimingStats() {
  const container = document.getElementById("timingStats");
  container.innerHTML = "";
  const langData = selectedReviewLang ? getGameReviews(currentGameId)[selectedReviewLang] : null;
  const selectedLabel = selectedReviewLang ? (LANGUAGE_META[selectedReviewLang]?.labels?.[uiLang] || selectedReviewLang) : "-";
  const stats = [
    { label: t("timingStatLang"), value: selectedLabel },
    { label: t("timingStatPositive"), value: langData?.review_timing?.positive?.avg_days != null ? `${langData.review_timing.positive.avg_days} ${t("days")}` : "-" },
    { label: t("timingStatNeutral"), value: langData?.review_timing?.neutral?.avg_days != null ? `${langData.review_timing.neutral.avg_days} ${t("days")}` : "-" },
    { label: t("timingStatNegative"), value: langData?.review_timing?.negative?.avg_days != null ? `${langData.review_timing.negative.avg_days} ${t("days")}` : "-" },
  ];
  stats.forEach((stat) => {
    const card = document.createElement("div");
    card.className = "stat-card";
    card.innerHTML = '<div class="stat-label"></div><div class="stat-value"></div>';
    card.querySelector(".stat-label").textContent = stat.label;
    card.querySelector(".stat-value").textContent = stat.value;
    container.appendChild(card);
  });
}

function renderPeriodSelector() {
  const container = document.getElementById("periodSelector");
  container.innerHTML = "";
  ["daily", "weekly", "monthly"].forEach((period) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "period-btn" + (populationPeriod === period ? " active" : "");
    btn.textContent = t(period);
    btn.addEventListener("click", () => {
      populationPeriod = period;
      renderPeriodSelector();
      renderPopulationChart();
    });
    container.appendChild(btn);
  });
}

function togglePopulationGame(gameId) {
  if (selectedPopulationGames.includes(gameId)) {
    selectedPopulationGames = selectedPopulationGames.filter((id) => id !== gameId);
  } else {
    selectedPopulationGames = [...selectedPopulationGames, gameId];
  }
  if (!selectedPopulationGames.length && dashboard?.games?.length) {
    selectedPopulationGames = [dashboard.games[0].id];
  }
  buildGameSelector("populationGameSelector", selectedPopulationGames, togglePopulationGame);
  renderPopulationChart();
}

function renderPopulationChart() {
  const vars = themeVars();
  const rows = dashboard?.population?.[populationPeriod] || [];
  if (populationChart) populationChart.destroy();
  if (!rows.length) {
    const canvas = document.getElementById("populationChart");
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = vars.text2;
    ctx.font = "14px Segoe UI";
    ctx.fillText(t("noPopulation"), 24, 32);
    return;
  }
  const labels = rows.map((row) => row.bucket);
  const palette = ["#58a6ff", "#34d399", "#f59e0b", "#f87171", "#a78bfa", "#14b8a6", "#fb7185"];
  const datasets = selectedPopulationGames.map((gameId, index) => ({
    label: getGameMeta(gameId)?.title || gameId,
    data: rows.map((row) => row.values?.[gameId] ?? null),
    borderColor: palette[index % palette.length],
    backgroundColor: palette[index % palette.length],
    pointRadius: 2.5,
    pointHoverRadius: 4,
    spanGaps: true,
    tension: 0.28,
  }));
  populationChart = new Chart(document.getElementById("populationChart"), {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: vars.text2 }, grid: { color: vars.border } },
        y: { ticks: { color: vars.text2 }, grid: { color: vars.border }, beginAtZero: true },
      },
      plugins: { legend: { labels: { color: vars.text } } },
    },
  });
}

function selectReviewGame(gameId) {
  currentGameId = gameId;
  selectedReviewLang = Object.keys(getGameReviews(gameId))[0] || null;
  buildGameSelector("reviewGameSelector", [gameId], selectReviewGame);
  renderLanguageCards();
  renderReviewPanel();
  renderTimingChart();
  renderTimingStats();
}

function navigate(page) {
  document.querySelectorAll(".page").forEach((el) => {
    const targetId = page === "reviews" ? "pageReviews" : "pagePopulation";
    el.classList.toggle("active", el.id === targetId);
  });
  document.querySelectorAll(".nav-btn").forEach((btn) => btn.classList.toggle("active", btn.dataset.page === page));
}

function applyTheme(nextTheme) {
  theme = nextTheme;
  document.documentElement.setAttribute("data-theme", theme);
  localStorage.setItem("steam-theme", theme);
  if (dashboard) {
    renderTimingChart();
    renderPopulationChart();
  }
}

async function loadDashboardData() {
  for (const url of ["data/games.json", "data/mock.json"]) {
    try {
      const response = await fetch(url);
      if (!response.ok) continue;
      const json = await response.json();
      if (json?.games && json?.reviews) return json;
    } catch (_) {}
  }
  throw new Error("dashboard data not found");
}

function initialize(data) {
  dashboard = data;
  if (!dashboard.games?.length) throw new Error("No games in dashboard data");
  if (!selectedPopulationGames.length) {
    selectedPopulationGames = dashboard.games.slice(0, Math.min(5, dashboard.games.length)).map((game) => game.id);
  }
  renderStaticText();
  buildGameSelector("populationGameSelector", selectedPopulationGames, togglePopulationGame);
  renderPeriodSelector();
  selectReviewGame(dashboard.games[0].id);
  renderPopulationChart();
}

document.getElementById("uiLangSel").addEventListener("change", (event) => {
  uiLang = event.target.value;
  localStorage.setItem("steam-lang", uiLang);
  renderStaticText();
  buildGameSelector("reviewGameSelector", [currentGameId], selectReviewGame);
  buildGameSelector("populationGameSelector", selectedPopulationGames, togglePopulationGame);
  renderLanguageCards();
  renderReviewPanel();
  renderTimingChart();
  renderTimingStats();
  renderPeriodSelector();
  renderPopulationChart();
});

document.getElementById("themeBtn").addEventListener("click", () => {
  applyTheme(theme === "dark" ? "light" : "dark");
});

document.querySelectorAll(".nav-btn").forEach((btn) => {
  btn.addEventListener("click", () => navigate(btn.dataset.page));
});

applyTheme(theme);
renderStaticText();

loadDashboardData()
  .then(initialize)
  .catch((error) => {
    document.querySelector(".main").innerHTML = `<p style="color:#f87171">${error.message}</p>`;
  });
