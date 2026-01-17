const state = {
  models: [],
};

const leaderboardEl = document.getElementById("leaderboard");
const refreshBtn = document.getElementById("refresh");

function parseCsv(text) {
  const lines = text.trim().split("\n");
  const header = lines.shift().split(",");
  return lines.map((line) => {
    const values = line.split(",");
    return header.reduce((acc, key, i) => {
      acc[key] = values[i];
      return acc;
    }, {});
  });
}

function formatScore(value) {
  return Number(value).toFixed(2);
}

function formatTokens(value) {
  if (value === undefined || value === null) return "--";
  if (!value) return "0";
  return `${(value / 1000).toFixed(1)}k`;
}

function formatCost(value) {
  if (value === undefined || value === null) return "--";
  return `$${value.toFixed(2)}`;
}

function pickTop(models) {
  return models.slice().sort((a, b) => b.avgScore - a.avgScore)[0];
}

function renderSummary(models) {
  if (!models.length) {
    document.getElementById("top-score").textContent = "--";
    document.getElementById("top-model").textContent = "No data";
    document.getElementById("avg-cost").textContent = "--";
    document.getElementById("avg-tokens").textContent = "--";
    document.getElementById("constraint-rate").textContent = "--";
    return;
  }
  const top = pickTop(models);
  document.getElementById("top-score").textContent = top ? formatScore(top.avgScore) : "--";
  document.getElementById("top-model").textContent = top ? top.name : "--";

  const avgCost = models.length
    ? models.reduce((sum, m) => sum + (m.cost || 0), 0) / models.length
    : 0;
  const avgTokens = models.length
    ? models.reduce((sum, m) => sum + (m.tokens || 0), 0) / models.length
    : 0;

  document.getElementById("avg-cost").textContent = formatCost(avgCost);
  document.getElementById("avg-tokens").textContent = `${formatTokens(avgTokens)} tokens`;

  const avgSuccess = models.length
    ? models.reduce((sum, m) => sum + (m.successRate || 0), 0) / models.length
    : 0;
  document.getElementById("constraint-rate").textContent = `${Math.round(avgSuccess * 100)}%`;
}

function renderLeaderboard(models) {
  leaderboardEl.innerHTML = "";
  if (!models.length) {
    leaderboardEl.innerHTML = "<p>No leaderboard data found.</p>";
    return;
  }
  const rows = models
    .slice()
    .sort((a, b) => b.avgScore - a.avgScore)
    .map((model, index) => {
      const row = document.createElement("div");
      row.className = "leaderboard__row";
      row.innerHTML = `
        <strong>${index + 1}. ${model.name}</strong>
        <div><span class="badge">${formatScore(model.avgScore)}</span></div>
        <div>${formatTokens(model.tokens)} tokens</div>
        <div>${formatCost(model.cost)}</div>
      `;
      row.addEventListener("click", () => setCompareModels(model.name));
      return row;
    });
  rows.forEach((row) => leaderboardEl.appendChild(row));
}

function renderCompare(models) {
  const selectA = document.getElementById("model-a");
  const selectB = document.getElementById("model-b");
  selectA.innerHTML = "";
  selectB.innerHTML = "";

  if (!models.length) {
    document.getElementById("compare-grid").innerHTML = "<p>No comparison data.</p>";
    return;
  }

  models.forEach((model) => {
    const optionA = document.createElement("option");
    optionA.value = model.name;
    optionA.textContent = model.name;
    selectA.appendChild(optionA);
    const optionB = document.createElement("option");
    optionB.value = model.name;
    optionB.textContent = model.name;
    selectB.appendChild(optionB);
  });

  if (models.length > 1) {
    selectA.value = models[0].name;
    selectB.value = models[1].name;
  }

  selectA.addEventListener("change", () => updateCompare(selectA.value, selectB.value));
  selectB.addEventListener("change", () => updateCompare(selectA.value, selectB.value));

  updateCompare(selectA.value, selectB.value);
}

function setCompareModels(name) {
  const selectA = document.getElementById("model-a");
  if (selectA) {
    selectA.value = name;
    updateCompare(selectA.value, document.getElementById("model-b").value);
  }
}

function updateCompare(nameA, nameB) {
  const modelA = state.models.find((m) => m.name === nameA);
  const modelB = state.models.find((m) => m.name === nameB);
  if (!modelA || !modelB) return;

  const grid = document.getElementById("compare-grid");
  const diffScore = modelA.avgScore - modelB.avgScore;
  const diffCost = (modelA.cost || 0) - (modelB.cost || 0);
  const diffTokens = (modelA.tokens || 0) - (modelB.tokens || 0);

  grid.innerHTML = `
    <div class="compare__card">
      <h4>Score Delta</h4>
      <p>${diffScore.toFixed(2)}</p>
    </div>
    <div class="compare__card">
      <h4>Token Delta</h4>
      <p>${formatTokens(Math.abs(diffTokens))}</p>
    </div>
    <div class="compare__card">
      <h4>Cost Delta</h4>
      <p>${formatCost(Math.abs(diffCost))}</p>
    </div>
    <div class="compare__card">
      <h4>Constraint Rate</h4>
      <p>${Math.round(((modelA.successRate || 0) - (modelB.successRate || 0)) * 100)}%</p>
    </div>
  `;
}

function chartBars(models) {
  const container = document.getElementById("chart-bars");
  if (!models.length) {
    container.innerHTML = "<p>No data.</p>";
    return;
  }
  const width = container.clientWidth || 300;
  const height = 200;
  const maxScore = Math.max(...models.map((m) => m.avgScore), 1);

  const barWidth = width / models.length;
  const bars = models
    .map((model, i) => {
      const barHeight = (model.avgScore / maxScore) * (height - 20);
      return `
        <rect x="${i * barWidth + 10}" y="${height - barHeight}" width="${barWidth - 20}" height="${barHeight}" rx="8" fill="#c45a2a" />
        <text x="${i * barWidth + barWidth / 2}" y="${height - 4}" text-anchor="middle" font-size="10" fill="#6b6b73">${model.name.split("/")[1]}</text>
      `;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
      ${bars}
    </svg>
  `;
}

function chartScatter(models) {
  const container = document.getElementById("chart-scatter");
  if (!models.length) {
    container.innerHTML = "<p>No data.</p>";
    return;
  }
  const width = container.clientWidth || 300;
  const height = 200;
  const maxScore = Math.max(...models.map((m) => m.avgScore), 1);
  const maxCost = Math.max(...models.map((m) => m.cost || 0), 1);

  const points = models
    .map((model) => {
      const x = ((model.cost || 0) / maxCost) * (width - 40) + 20;
      const y = height - ((model.avgScore / maxScore) * (height - 40) + 20);
      return `
        <circle cx="${x}" cy="${y}" r="8" fill="#1b1b1f" opacity="0.85" />
        <text x="${x}" y="${y - 12}" text-anchor="middle" font-size="10" fill="#6b6b73">${model.name.split("/")[1]}</text>
      `;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
      <rect x="10" y="10" width="${width - 20}" height="${height - 20}" fill="none" stroke="#e7ded4" />
      ${points}
    </svg>
  `;
}

function chartTrend(models) {
  const container = document.getElementById("chart-trend");
  if (!models.length) {
    container.innerHTML = "<p>No data.</p>";
    return;
  }
  const width = container.clientWidth || 300;
  const height = 200;

  const points = models.map((model) => model.history || [model.avgScore]);
  const maxLen = Math.max(...points.map((series) => series.length));
  const maxScore = Math.max(...points.flat(), 1);

  const paths = points
    .map((series, idx) => {
      const step = (width - 40) / (maxLen - 1 || 1);
      const path = series
        .map((value, i) => {
          const x = 20 + step * i;
          const y = height - ((value / maxScore) * (height - 40) + 20);
          return `${i === 0 ? "M" : "L"}${x},${y}`;
        })
        .join(" ");
      const color = idx === 0 ? "#c45a2a" : "#1b1b1f";
      return `<path d="${path}" fill="none" stroke="${color}" stroke-width="2" />`;
    })
    .join("");

  container.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" width="100%" height="100%">
      <rect x="10" y="10" width="${width - 20}" height="${height - 20}" fill="none" stroke="#e7ded4" />
      ${paths}
    </svg>
  `;
}

async function loadLeaderboard() {
  try {
    const response = await fetch("../leaderboard/leaderboard.csv");
    if (!response.ok) throw new Error("missing leaderboard");
    const csv = await response.text();
    const rows = parseCsv(csv);
    const models = rows.map((row) => ({
      name: row.model,
      avgScore: Number(row.avg_score),
      lastRun: row.last_run,
      tokens: 0,
      cost: 0,
      successRate: 0,
      history: [Number(row.avg_score)],
    }));
    await Promise.all(
      models.map(async (model) => {
        const safe = model.name.replaceAll("/", "__").replaceAll(":", "__");
        try {
          const report = await fetch(`../leaderboard/reports/${safe}.json`);
          if (!report.ok) return;
          const data = await report.json();
          model.tokens = data.tokens ?? 0;
          model.cost = data.cost_usd ?? 0;
          model.successRate = data.constraint_success_rate ?? 0;
          model.history = data.history || [model.avgScore];
        } catch (err) {
          return;
        }
      })
    );
    return models;
  } catch (err) {
    return [];
  }
}

async function boot() {
  state.models = await loadLeaderboard();
  renderSummary(state.models);
  renderLeaderboard(state.models);
  renderCompare(state.models);
  chartBars(state.models);
  chartScatter(state.models);
  chartTrend(state.models);
}

refreshBtn.addEventListener("click", () => boot());
window.addEventListener("resize", () => {
  chartBars(state.models);
  chartScatter(state.models);
  chartTrend(state.models);
});

boot();
