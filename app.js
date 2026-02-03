const BINANCE_BASE = "https://api.binance.com";
const DEFAULT_SYMBOLS = [
  "BTCUSDT",
  "ETHUSDT",
  "BNBUSDT",
  "SOLUSDT",
  "XRPUSDT",
  "ADAUSDT",
  "DOGEUSDT",
  "AVAXUSDT",
  "LINKUSDT",
  "TONUSDT",
  "DOTUSDT",
  "MATICUSDT",
];

const state = {
  symbols: DEFAULT_SYMBOLS,
  marketData: new Map(),
  symbol: "BTCUSDT",
  interval: "1m",
  lastPrice: null,
  online: true,
};

const elements = {
  marketTable: document.getElementById("market-table"),
  heroSymbol: document.getElementById("hero-symbol"),
  heroPrice: document.getElementById("hero-price"),
  heroChange: document.getElementById("hero-change"),
  heroHigh: document.getElementById("hero-high"),
  heroLow: document.getElementById("hero-low"),
  heroVolume: document.getElementById("hero-volume"),
  chartTitle: document.getElementById("chart-title"),
  chartSubtitle: document.getElementById("chart-subtitle"),
  chartCanvas: document.getElementById("chart"),
  chartLast: document.getElementById("chart-last"),
  chartTrend: document.getElementById("chart-trend"),
  chartVol: document.getElementById("chart-vol"),
  bids: document.getElementById("bids"),
  asks: document.getElementById("asks"),
  trades: document.getElementById("trade-table"),
  statusDot: document.getElementById("status-dot"),
  statusText: document.getElementById("status-text"),
  orderPrice: document.getElementById("order-price"),
  orderQty: document.getElementById("order-qty"),
  orderTotal: document.getElementById("order-total"),
  orderSubmit: document.getElementById("order-submit"),
  refresh: document.getElementById("btn-refresh"),
  search: document.getElementById("search"),
  intervalGroup: document.getElementById("intervals"),
};

const formatter = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 8,
});

const shortFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 2,
});

const priceFormat = (value) => {
  if (value === null || value === undefined) return "--";
  const num = Number(value);
  if (!Number.isFinite(num)) return "--";
  if (num >= 1000) return num.toFixed(2);
  if (num >= 1) return num.toFixed(4);
  return num.toFixed(6);
};

const setStatus = (online, message) => {
  state.online = online;
  elements.statusDot.style.background = online ? "#22d3ee" : "#f97316";
  elements.statusDot.style.boxShadow = online
    ? "0 0 12px #22d3ee"
    : "0 0 12px #f97316";
  elements.statusText.textContent = message;
};

const fetchJson = async (path) => {
  const response = await fetch(`${BINANCE_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`);
  }
  return response.json();
};

const loadMarkets = async () => {
  const symbolsParam = encodeURIComponent(JSON.stringify(state.symbols));
  const data = await fetchJson(`/api/v3/ticker/24hr?symbols=${symbolsParam}`);
  data.forEach((item) => {
    state.marketData.set(item.symbol, item);
  });
  renderMarkets();
  updateHero();
};

const renderMarkets = () => {
  const filter = elements.search.value.trim().toUpperCase();
  const rows = [
    `<div class="market-row head">
      <span>交易对</span>
      <span>最新价</span>
      <span>24h%</span>
      <span>24h量</span>
    </div>`,
  ];

  state.symbols
    .filter((symbol) => symbol.includes(filter))
    .forEach((symbol) => {
      const item = state.marketData.get(symbol);
      if (!item) return;
      const change = Number(item.priceChangePercent || 0);
      const changeClass = change >= 0 ? "change-pos" : "change-neg";
      rows.push(`
      <div class="market-row data ${symbol === state.symbol ? "active" : ""}" data-symbol="${symbol}">
        <span>${symbol}</span>
        <span>${priceFormat(item.lastPrice)}</span>
        <span class="${changeClass}">${change.toFixed(2)}%</span>
        <span>${shortFormatter.format(Number(item.quoteVolume || 0))}</span>
      </div>
    `);
    });

  elements.marketTable.innerHTML = rows.join("");
  document.querySelectorAll(".market-row.data").forEach((row) => {
    row.addEventListener("click", () => {
      state.symbol = row.dataset.symbol;
      refreshDetail();
      renderMarkets();
    });
  });
};

const updateHero = () => {
  const item = state.marketData.get(state.symbol);
  if (!item) return;
  const change = Number(item.priceChangePercent || 0);
  elements.heroSymbol.textContent = state.symbol;
  elements.heroPrice.textContent = priceFormat(item.lastPrice);
  elements.heroChange.textContent = `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`;
  elements.heroChange.className = `hero-change ${change >= 0 ? "change-pos" : "change-neg"}`;
  elements.heroHigh.textContent = priceFormat(item.highPrice);
  elements.heroLow.textContent = priceFormat(item.lowPrice);
  elements.heroVolume.textContent = shortFormatter.format(Number(item.quoteVolume || 0));
};

const resizeCanvas = (canvas) => {
  const ratio = window.devicePixelRatio || 1;
  const parent = canvas.parentElement;
  const width = parent.clientWidth - 32;
  const height = parent.clientHeight - 32;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  canvas.style.width = `${width}px`;
  canvas.style.height = `${height}px`;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
};

const drawChart = (values) => {
  const canvas = elements.chartCanvas;
  resizeCanvas(canvas);
  const ctx = canvas.getContext("2d");
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  ctx.clearRect(0, 0, width, height);

  if (!values.length) return;

  const min = Math.min(...values);
  const max = Math.max(...values);
  const padding = 12;
  const range = max - min || 1;

  const points = values.map((value, index) => {
    const x = padding + (index / (values.length - 1)) * (width - padding * 2);
    const y = padding + ((max - value) / range) * (height - padding * 2);
    return { x, y };
  });

  const gradient = ctx.createLinearGradient(0, 0, 0, height);
  gradient.addColorStop(0, "rgba(34, 211, 238, 0.35)");
  gradient.addColorStop(1, "rgba(34, 211, 238, 0)");

  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  points.forEach((point) => ctx.lineTo(point.x, point.y));
  ctx.strokeStyle = "#22d3ee";
  ctx.lineWidth = 2;
  ctx.shadowColor = "rgba(34, 211, 238, 0.5)";
  ctx.shadowBlur = 12;
  ctx.stroke();
  ctx.shadowBlur = 0;

  ctx.lineTo(points[points.length - 1].x, height - padding);
  ctx.lineTo(points[0].x, height - padding);
  ctx.closePath();
  ctx.fillStyle = gradient;
  ctx.fill();

  ctx.strokeStyle = "rgba(148, 163, 184, 0.15)";
  ctx.lineWidth = 1;
  for (let i = 0; i < 4; i += 1) {
    const y = padding + (i / 3) * (height - padding * 2);
    ctx.beginPath();
    ctx.moveTo(padding, y);
    ctx.lineTo(width - padding, y);
    ctx.stroke();
  }
};

const loadKlines = async () => {
  const limit = 120;
  const data = await fetchJson(
    `/api/v3/klines?symbol=${state.symbol}&interval=${state.interval}&limit=${limit}`
  );
  const closes = data.map((row) => Number(row[4]));
  drawChart(closes);

  const first = closes[0];
  const last = closes[closes.length - 1];
  const trend = ((last - first) / first) * 100;
  const volatility = ((Math.max(...closes) - Math.min(...closes)) / last) * 100;

  elements.chartTitle.textContent = `${state.symbol} 走势`;
  elements.chartSubtitle.textContent = `K线 ${state.interval} / ${limit} 根`;
  elements.chartLast.textContent = priceFormat(last);
  elements.chartTrend.textContent = `${trend >= 0 ? "+" : ""}${trend.toFixed(2)}%`;
  elements.chartTrend.className = trend >= 0 ? "change-pos" : "change-neg";
  elements.chartVol.textContent = `${volatility.toFixed(2)}%`;

  state.lastPrice = last;
  elements.orderPrice.value = last ? Number(last).toFixed(4) : "";
};

const loadDepth = async () => {
  const data = await fetchJson(`/api/v3/depth?symbol=${state.symbol}&limit=10`);
  const bids = data.bids || [];
  const asks = data.asks || [];

  elements.bids.innerHTML = bids
    .map((bid) => {
      return `
      <div class="depth-row">
        <span class="change-pos">${priceFormat(bid[0])}</span>
        <span>${Number(bid[1]).toFixed(4)}</span>
      </div>`;
    })
    .join("");

  elements.asks.innerHTML = asks
    .map((ask) => {
      return `
      <div class="depth-row">
        <span class="change-neg">${priceFormat(ask[0])}</span>
        <span>${Number(ask[1]).toFixed(4)}</span>
      </div>`;
    })
    .join("");
};

const loadTrades = async () => {
  const data = await fetchJson(`/api/v3/trades?symbol=${state.symbol}&limit=20`);
  elements.trades.innerHTML = data
    .map((trade) => {
      const sideClass = trade.isBuyerMaker ? "change-neg" : "change-pos";
      const time = new Date(trade.time).toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
      return `
      <div class="trade-row">
        <span class="${sideClass}">${priceFormat(trade.price)}</span>
        <span>${Number(trade.qty).toFixed(4)}</span>
        <span>${time}</span>
      </div>`;
    })
    .join("");
};

const refreshDetail = async () => {
  try {
    setStatus(true, "连接 Binance");
    updateHero();
    await Promise.all([loadKlines(), loadDepth(), loadTrades()]);
  } catch (error) {
    console.error(error);
    setStatus(false, "连接失败：可能被浏览器拦截 CORS");
  }
};

const handleOrderForm = () => {
  const price = Number(elements.orderPrice.value || state.lastPrice || 0);
  const qty = Number(elements.orderQty.value || 0);
  if (price && qty) {
    elements.orderTotal.value = (price * qty).toFixed(2);
  }
};

const bindEvents = () => {
  elements.refresh.addEventListener("click", () => {
    init();
  });

  elements.search.addEventListener("input", () => {
    renderMarkets();
  });

  elements.intervalGroup.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-interval]");
    if (!button) return;
    document.querySelectorAll("#intervals .chip").forEach((chip) => {
      chip.classList.remove("active");
    });
    button.classList.add("active");
    state.interval = button.dataset.interval;
    refreshDetail();
  });

  elements.orderQty.addEventListener("input", handleOrderForm);
  elements.orderPrice.addEventListener("input", handleOrderForm);

  document.querySelectorAll(".order-toggle .chip").forEach((chip) => {
    chip.addEventListener("click", () => {
      document.querySelectorAll(".order-toggle .chip").forEach((item) => {
        item.classList.remove("active");
      });
      chip.classList.add("active");
      elements.orderSubmit.classList.toggle("sell", chip.dataset.side === "sell");
    });
  });

  window.addEventListener("resize", () => {
    if (state.lastPrice) refreshDetail();
  });
};

const init = async () => {
  try {
    await loadMarkets();
    await refreshDetail();
  } catch (error) {
    console.error(error);
    setStatus(false, "加载失败：请检查网络或 API 访问");
  }
};

bindEvents();
init();

setInterval(() => {
  loadMarkets().catch((error) => {
    console.error(error);
    setStatus(false, "行情刷新失败");
  });
}, 6000);

setInterval(() => {
  refreshDetail();
}, 5000);
