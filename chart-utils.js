/**
 * Chart.js utility functions for NFL Knowledge Hub
 * Dark theme configuration and chart creation helpers
 */

// Color palette matching CSS variables
const CHART_COLORS = {
  blue: '#3b82f6',
  green: '#22c55e',
  orange: '#d97706',
  purple: '#a855f7',
  red: '#dc2626',
  teal: '#0d9488',
  cyan: '#06b6d4',
  text: '#f1f5f9',
  textMuted: '#94a3b8',
  grid: 'rgba(148, 163, 184, 0.1)',
  background: '#0c1322',
};

// Default dark theme for all charts
const DARK_THEME = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      labels: {
        color: CHART_COLORS.text,
        font: { family: "'Source Sans 3', sans-serif", size: 12 },
      },
    },
    tooltip: {
      backgroundColor: CHART_COLORS.background,
      titleColor: CHART_COLORS.text,
      bodyColor: CHART_COLORS.textMuted,
      borderColor: 'rgba(148, 163, 184, 0.2)',
      borderWidth: 1,
      padding: 10,
      cornerRadius: 6,
      titleFont: { family: "'Oswald', sans-serif", size: 14 },
      bodyFont: { family: "'Source Sans 3', sans-serif", size: 12 },
    },
  },
  scales: {
    x: {
      grid: { color: CHART_COLORS.grid },
      ticks: { color: CHART_COLORS.textMuted },
    },
    y: {
      grid: { color: CHART_COLORS.grid },
      ticks: { color: CHART_COLORS.textMuted },
    },
  },
};

/**
 * Create a line chart for trends over time (e.g., weekly stats)
 * @param {HTMLCanvasElement|string} canvas - Canvas element or selector
 * @param {Object} options - Chart configuration
 * @param {string[]} options.labels - X-axis labels (e.g., weeks)
 * @param {Object[]} options.datasets - Array of dataset configs
 * @param {string} options.datasets[].label - Dataset label
 * @param {number[]} options.datasets[].data - Dataset values
 * @param {string} options.datasets[].color - Line color (use CHART_COLORS key or hex)
 * @param {boolean} [options.datasets[].dashed] - Use dashed line (for averages)
 * @param {string} [options.yLabel] - Y-axis label
 * @param {boolean} [options.fill] - Fill area under line
 * @returns {Chart} Chart.js instance
 */
function createTrendChart(canvas, options) {
  const ctx = typeof canvas === 'string' ? document.querySelector(canvas) : canvas;

  const datasets = options.datasets.map(ds => ({
    label: ds.label,
    data: ds.data,
    borderColor: CHART_COLORS[ds.color] || ds.color,
    backgroundColor: ds.fill
      ? `${CHART_COLORS[ds.color] || ds.color}33`
      : 'transparent',
    fill: ds.fill || false,
    tension: 0.3,
    borderWidth: ds.dashed ? 1.5 : 2,
    borderDash: ds.dashed ? [5, 5] : [],
    pointRadius: ds.dashed ? 0 : 4,
    pointBackgroundColor: CHART_COLORS[ds.color] || ds.color,
    pointBorderColor: CHART_COLORS.background,
    pointBorderWidth: 2,
    pointHoverRadius: 6,
  }));

  const config = {
    type: 'line',
    data: {
      labels: options.labels,
      datasets,
    },
    options: {
      ...DARK_THEME,
      plugins: {
        ...DARK_THEME.plugins,
        legend: {
          ...DARK_THEME.plugins.legend,
          display: datasets.length > 1,
        },
      },
      scales: {
        ...DARK_THEME.scales,
        y: {
          ...DARK_THEME.scales.y,
          title: options.yLabel ? {
            display: true,
            text: options.yLabel,
            color: CHART_COLORS.textMuted,
          } : undefined,
          beginAtZero: options.beginAtZero !== false,
        },
      },
    },
  };

  return new Chart(ctx, config);
}

/**
 * Create a bar chart for comparisons (e.g., vs averages, team comparison)
 * @param {HTMLCanvasElement|string} canvas - Canvas element or selector
 * @param {Object} options - Chart configuration
 * @param {string[]} options.labels - X-axis labels (e.g., stat names)
 * @param {Object[]} options.datasets - Array of dataset configs
 * @param {string} options.datasets[].label - Dataset label
 * @param {number[]} options.datasets[].data - Dataset values
 * @param {string} options.datasets[].color - Bar color
 * @param {boolean} [options.horizontal] - Use horizontal bars
 * @param {boolean} [options.stacked] - Stack bars
 * @returns {Chart} Chart.js instance
 */
function createComparisonChart(canvas, options) {
  const ctx = typeof canvas === 'string' ? document.querySelector(canvas) : canvas;

  const datasets = options.datasets.map(ds => ({
    label: ds.label,
    data: ds.data,
    backgroundColor: CHART_COLORS[ds.color] || ds.color,
    borderColor: CHART_COLORS[ds.color] || ds.color,
    borderWidth: 0,
    borderRadius: 4,
    barPercentage: 0.7,
    categoryPercentage: 0.8,
  }));

  const config = {
    type: 'bar',
    data: {
      labels: options.labels,
      datasets,
    },
    options: {
      ...DARK_THEME,
      indexAxis: options.horizontal ? 'y' : 'x',
      plugins: {
        ...DARK_THEME.plugins,
        legend: {
          ...DARK_THEME.plugins.legend,
          display: datasets.length > 1,
        },
      },
      scales: {
        ...DARK_THEME.scales,
        x: {
          ...DARK_THEME.scales.x,
          stacked: options.stacked || false,
        },
        y: {
          ...DARK_THEME.scales.y,
          stacked: options.stacked || false,
          beginAtZero: true,
        },
      },
    },
  };

  return new Chart(ctx, config);
}

/**
 * Create a horizontal grouped bar chart for head-to-head comparison
 * @param {HTMLCanvasElement|string} canvas - Canvas element or selector
 * @param {Object} options - Chart configuration
 * @param {string} options.team1 - First team code
 * @param {string} options.team2 - Second team code
 * @param {string[]} options.labels - Stat labels
 * @param {number[]} options.team1Data - Team 1 values
 * @param {number[]} options.team2Data - Team 2 values
 * @returns {Chart} Chart.js instance
 */
function createH2HChart(canvas, options) {
  return createComparisonChart(canvas, {
    labels: options.labels,
    datasets: [
      { label: options.team1, data: options.team1Data, color: 'blue' },
      { label: options.team2, data: options.team2Data, color: 'orange' },
    ],
    horizontal: true,
  });
}

/**
 * Create a stacked bar chart for quarter breakdown
 * @param {HTMLCanvasElement|string} canvas - Canvas element or selector
 * @param {Object} options - Chart configuration
 * @param {string[]} options.labels - X-axis labels (e.g., game dates or weeks)
 * @param {Object} options.scored - Points scored per quarter {q1, q2, q3, q4}
 * @param {Object} options.allowed - Points allowed per quarter (optional)
 * @returns {Chart} Chart.js instance
 */
function createQuarterChart(canvas, options) {
  const datasets = [];

  if (options.scored) {
    datasets.push(
      { label: 'Q1', data: options.scored.q1, color: 'blue' },
      { label: 'Q2', data: options.scored.q2, color: 'cyan' },
      { label: 'Q3', data: options.scored.q3, color: 'green' },
      { label: 'Q4', data: options.scored.q4, color: 'teal' },
    );
  }

  return createComparisonChart(canvas, {
    labels: options.labels,
    datasets: datasets.map(ds => ({
      label: ds.label,
      data: ds.data,
      color: ds.color,
    })),
    stacked: true,
  });
}

/**
 * Create a dual-axis line chart for comparing two related metrics
 * @param {HTMLCanvasElement|string} canvas - Canvas element or selector
 * @param {Object} options - Chart configuration
 * @param {string[]} options.labels - X-axis labels
 * @param {Object} options.primary - Primary axis data { label, data, color }
 * @param {Object} options.secondary - Secondary axis data { label, data, color }
 * @returns {Chart} Chart.js instance
 */
function createDualAxisChart(canvas, options) {
  const ctx = typeof canvas === 'string' ? document.querySelector(canvas) : canvas;

  const config = {
    type: 'line',
    data: {
      labels: options.labels,
      datasets: [
        {
          label: options.primary.label,
          data: options.primary.data,
          borderColor: CHART_COLORS[options.primary.color] || options.primary.color,
          backgroundColor: 'transparent',
          tension: 0.3,
          borderWidth: 2,
          yAxisID: 'y',
        },
        {
          label: options.secondary.label,
          data: options.secondary.data,
          borderColor: CHART_COLORS[options.secondary.color] || options.secondary.color,
          backgroundColor: 'transparent',
          tension: 0.3,
          borderWidth: 2,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      ...DARK_THEME,
      scales: {
        x: DARK_THEME.scales.x,
        y: {
          ...DARK_THEME.scales.y,
          position: 'left',
          title: {
            display: true,
            text: options.primary.label,
            color: CHART_COLORS.textMuted,
          },
        },
        y1: {
          ...DARK_THEME.scales.y,
          position: 'right',
          grid: { drawOnChartArea: false },
          title: {
            display: true,
            text: options.secondary.label,
            color: CHART_COLORS.textMuted,
          },
        },
      },
    },
  };

  return new Chart(ctx, config);
}

/**
 * Compute rolling average for a data array
 * @param {number[]} data - Raw data values
 * @param {number} window - Window size (default 3)
 * @returns {number[]} Rolling average values
 */
function computeRollingAverage(data, window = 3) {
  const result = [];
  for (let i = 0; i < data.length; i++) {
    if (i < window - 1) {
      result.push(null);
    } else {
      const slice = data.slice(i - window + 1, i + 1);
      const avg = slice.reduce((a, b) => a + b, 0) / window;
      result.push(Math.round(avg * 10) / 10);
    }
  }
  return result;
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    CHART_COLORS,
    DARK_THEME,
    createTrendChart,
    createComparisonChart,
    createH2HChart,
    createQuarterChart,
    createDualAxisChart,
    computeRollingAverage,
  };
}
