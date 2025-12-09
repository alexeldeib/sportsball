/**
 * NFL Betting Odds Engine
 * Computes moneyline, spread, and over/under for matchups
 */

const OddsEngine = (function() {
  // Constants
  const DEFAULT_HFA = 2.5;           // Default home field advantage (points)
  const LOGISTIC_K = 0.145;          // Calibration constant for win probability

  // Advanced stats cache (loaded from JSON)
  let advancedStatsCache = null;

  /**
   * Load advanced team stats from JSON
   * Call this once when initializing the page
   * @param {string} url - Path to advanced-team-stats JSON
   * @param {number} season - Season year
   * @returns {Promise<Object>} Map of team_code -> stats
   */
  async function loadAdvancedStats(season = 2025) {
    if (advancedStatsCache && advancedStatsCache.season === season) {
      return advancedStatsCache.data;
    }
    try {
      const response = await fetch(`advanced-team-stats-${season}.json?v=${Date.now()}`);
      if (!response.ok) throw new Error('Failed to load advanced stats');
      const data = await response.json();
      const statsMap = {};
      data.forEach(team => { statsMap[team.team_code] = team; });
      advancedStatsCache = { season, data: statsMap };
      return statsMap;
    } catch (e) {
      console.warn('Could not load advanced stats:', e);
      return {};
    }
  }

  /**
   * Get advanced stats for a team (if loaded)
   */
  function getAdvancedStats(teamCode) {
    return advancedStatsCache?.data?.[teamCode] || null;
  }

  /**
   * Convert win probability to American odds format
   * @param {number} prob - Win probability (0-1)
   * @returns {number} American odds
   */
  function probToAmericanOdds(prob) {
    if (prob <= 0) return 10000;   // Max underdog
    if (prob >= 1) return -10000;  // Max favorite

    if (prob >= 0.5) {
      // Favorite: negative odds
      return Math.round(-100 * prob / (1 - prob));
    } else {
      // Underdog: positive odds
      return Math.round(100 * (1 - prob) / prob);
    }
  }

  /**
   * Apply vigorish to probability and convert to odds
   * @param {number} fairProb - Fair win probability (0-1)
   * @param {number} vig - Vig percentage (default 4.76%)
   * @returns {number} American odds with vig applied
   */
  function applyVig(fairProb, vig = 0.0476) {
    const adjusted = Math.min(fairProb * (1 + vig), 0.99);
    return probToAmericanOdds(adjusted);
  }

  /**
   * Calculate team power rating from stats
   * Uses SRS (Simple Rating System) when available, otherwise falls back to PPD
   *
   * Components:
   * - SRS: Point differential adjusted for strength of schedule
   * - Efficiency: Yards per play, turnover differential
   * - Recent form: Last 5 games (reduced weight to 15%)
   *
   * @param {Object} teamStats - Team statistics from database
   * @param {Object} advStats - Advanced stats from JSON (optional)
   * @returns {number} Power rating (point differential scale)
   */
  function calculatePowerRating(teamStats, advStats = null) {
    if (!teamStats) return 0;

    // Try to get advanced stats if not provided
    if (!advStats && teamStats.team_code) {
      advStats = getAdvancedStats(teamStats.team_code);
    }

    // If we have SRS, use it as the primary rating
    if (advStats?.srs !== undefined) {
      let rating = advStats.srs;

      // Add efficiency adjustments
      // Yards per play: league avg ~5.5, +1 YPP = ~+3 points of value
      const ypp = advStats.yards_per_play || 5.5;
      const yppAdj = (ypp - 5.5) * 2;  // Smaller multiplier since SRS already captures much of this

      // Turnover differential: each turnover ~= 4 points
      const toDiff = advStats.turnover_diff || 0;
      const toAdj = toDiff * 0.2;  // Small adjustment since PPD includes turnovers

      // Recent form (15% weight now)
      const last5Ppg = teamStats.last_5_ppg || teamStats.ppg_scored || 21;
      const last5Allowed = teamStats.last_5_ppg_allowed || teamStats.ppg_allowed || 21;
      const recentDiff = last5Ppg - last5Allowed;
      const recentAdj = (recentDiff - rating) * 0.15;  // 15% pull toward recent form

      return rating + yppAdj + toAdj + recentAdj;
    }

    // Fallback to original calculation if no advanced stats
    const ppg = teamStats.ppg_scored || 21.0;
    const ppgAllowed = teamStats.ppg_allowed || 21.0;
    const base = ppg - ppgAllowed;

    const last5Ppg = teamStats.last_5_ppg || ppg;
    const last5Allowed = teamStats.last_5_ppg_allowed || ppgAllowed;
    const recentDiff = last5Ppg - last5Allowed;

    // Fallback: 85% season, 15% recent (reduced from 30%)
    return 0.85 * base + 0.15 * recentDiff;
  }

  /**
   * Get team-specific home field advantage
   * @param {string} teamCode - Team code
   * @returns {number} HFA in points
   */
  function getHomeFieldAdvantage(teamCode) {
    const advStats = getAdvancedStats(teamCode);
    if (advStats?.hfa !== undefined) {
      return advStats.hfa;
    }
    return DEFAULT_HFA;
  }

  /**
   * Calculate full matchup odds
   * @param {Object} homeStats - Home team statistics
   * @param {Object} awayStats - Away team statistics
   * @param {Object} homeAdvStats - Advanced home stats (optional)
   * @param {Object} awayAdvStats - Advanced away stats (optional)
   * @returns {Object} Odds object with all betting lines
   */
  function calculateMatchupOdds(homeStats, awayStats, homeAdvStats = null, awayAdvStats = null) {
    const homePower = calculatePowerRating(homeStats, homeAdvStats);
    const awayPower = calculatePowerRating(awayStats, awayAdvStats);

    // Get team-specific home field advantage
    const homeTeamCode = homeStats?.team_code || homeAdvStats?.team_code;
    const hfa = homeTeamCode ? getHomeFieldAdvantage(homeTeamCode) : DEFAULT_HFA;

    // Expected point differential (home perspective)
    const expectedDiff = (homePower - awayPower) + hfa;

    // Win probability using logistic function
    const homeWinProb = 1 / (1 + Math.exp(-LOGISTIC_K * expectedDiff));

    // Moneyline odds (fair, no vig)
    const homeMl = probToAmericanOdds(homeWinProb);
    const awayMl = probToAmericanOdds(1 - homeWinProb);

    // Spread (round to nearest 0.5) - negative means home favored
    const spread = -Math.round(expectedDiff * 2) / 2;

    // Over/Under calculation
    const homePpg = (homeStats && homeStats.ppg_scored) || 21.0;
    const awayPpg = (awayStats && awayStats.ppg_scored) || 21.0;
    const homeAllowed = (homeStats && homeStats.ppg_allowed) || 21.0;
    const awayAllowed = (awayStats && awayStats.ppg_allowed) || 21.0;

    // Method: average of both offense vs defense matchups
    const method1 = homePpg + awayAllowed;  // Home offense vs away defense
    const method2 = awayPpg + homeAllowed;  // Away offense vs home defense
    const total = Math.round((method1 + method2) / 2 * 2) / 2;

    // Team totals
    const homeTotal = Math.round(((homePpg + awayAllowed) / 2 + 1.25) * 2) / 2;
    const awayTotal = Math.round(((awayPpg + homeAllowed) / 2 - 1.25) * 2) / 2;

    return {
      homeWinProb: Math.round(homeWinProb * 1000) / 1000,
      awayWinProb: Math.round((1 - homeWinProb) * 1000) / 1000,
      homeMoneyline: homeMl,
      awayMoneyline: awayMl,
      spread: spread,
      spreadHomeOdds: -110,
      spreadAwayOdds: -110,
      overUnder: total,
      overOdds: -110,
      underOdds: -110,
      homeTeamTotal: homeTotal,
      awayTeamTotal: awayTotal,
      expectedDiff: Math.round(expectedDiff * 10) / 10,
      homeFieldAdvantage: Math.round(hfa * 10) / 10,
      homePower: Math.round(homePower * 10) / 10,
      awayPower: Math.round(awayPower * 10) / 10,
    };
  }

  /**
   * Format American odds for display
   * @param {number} odds - American odds
   * @returns {string} Formatted odds string
   */
  function formatOdds(odds) {
    if (odds > 0) return '+' + odds;
    return String(odds);
  }

  /**
   * Format spread for display
   * @param {number} spread - Point spread
   * @returns {string} Formatted spread string
   */
  function formatSpread(spread) {
    if (spread > 0) return '+' + spread.toFixed(1);
    if (spread < 0) return spread.toFixed(1);
    return 'PK';  // Pick 'em
  }

  /**
   * Get win probability from American odds
   * @param {number} odds - American odds
   * @returns {number} Implied probability (0-1)
   */
  function oddsToProb(odds) {
    if (odds < 0) {
      return Math.abs(odds) / (Math.abs(odds) + 100);
    } else {
      return 100 / (odds + 100);
    }
  }

  /**
   * Calculate expected value of a bet
   * @param {number} odds - American odds
   * @param {number} trueProb - True win probability (0-1)
   * @returns {number} Expected value percentage
   */
  function expectedValue(odds, trueProb) {
    const impliedProb = oddsToProb(odds);
    // EV = (trueProb * payout) - (1 - trueProb) * stake
    if (odds > 0) {
      return (trueProb * (odds / 100)) - (1 - trueProb);
    } else {
      return (trueProb * (100 / Math.abs(odds))) - (1 - trueProb);
    }
  }

  /**
   * Get team stats from database using sql.js
   * @param {Object} db - sql.js database instance
   * @param {string} teamCode - Team code (e.g., 'KC')
   * @param {number} season - Season year
   * @returns {Object|null} Team stats object
   */
  function getTeamStats(db, teamCode, season) {
    const stmt = db.prepare(`
      SELECT * FROM team_stats
      WHERE team_code = ? AND season = ?
    `);
    stmt.bind([teamCode, season]);

    if (stmt.step()) {
      const cols = stmt.getColumnNames();
      const vals = stmt.get();
      const stats = {};
      cols.forEach((col, i) => {
        stats[col] = vals[i];
      });
      stmt.free();
      return stats;
    }
    stmt.free();
    return null;
  }

  /**
   * Get upcoming matchups from database
   * @param {Object} db - sql.js database instance
   * @param {number} season - Season year
   * @param {number} week - Week number (optional)
   * @returns {Array} Array of matchup objects
   */
  function getUpcomingMatchups(db, season, week = null) {
    let sql = `
      SELECT * FROM games
      WHERE season = ? AND is_completed = 0
    `;
    const params = [season];

    if (week !== null) {
      sql += ' AND week = ?';
      params.push(week);
    }
    sql += ' ORDER BY week, game_date';

    const results = [];
    const stmt = db.prepare(sql);
    stmt.bind(params);

    while (stmt.step()) {
      const cols = stmt.getColumnNames();
      const vals = stmt.get();
      const game = {};
      cols.forEach((col, i) => {
        game[col] = vals[i];
      });
      results.push(game);
    }
    stmt.free();
    return results;
  }

  /**
   * Compute odds for all upcoming matchups
   * @param {Object} db - sql.js database instance
   * @param {number} season - Season year
   * @param {number} week - Week number (optional)
   * @returns {Array} Array of matchup objects with computed odds
   */
  function computeAllOdds(db, season, week = null) {
    const matchups = getUpcomingMatchups(db, season, week);

    return matchups.map(game => {
      const homeStats = getTeamStats(db, game.home_team, season);
      const awayStats = getTeamStats(db, game.away_team, season);
      const odds = calculateMatchupOdds(homeStats, awayStats);

      return {
        ...game,
        ...odds,
        homeStats: homeStats,
        awayStats: awayStats
      };
    });
  }

  // ============ Monte Carlo Simulation ============

  /**
   * Generate random sample from normal distribution (Box-Muller)
   */
  function sampleNormal(mean, stdDev) {
    const u1 = Math.random();
    const u2 = Math.random();
    const z = Math.sqrt(-2 * Math.log(u1)) * Math.cos(2 * Math.PI * u2);
    return mean + z * stdDev;
  }

  /**
   * Calculate percentile from sorted array
   */
  function percentile(arr, p) {
    const idx = (arr.length - 1) * p;
    const lower = Math.floor(idx);
    const upper = Math.ceil(idx);
    if (lower === upper) return arr[lower];
    return arr[lower] * (upper - idx) + arr[upper] * (idx - lower);
  }

  /**
   * Run Monte Carlo simulation for a matchup
   * @param {Object} homeStats - Home team statistics
   * @param {Object} awayStats - Away team statistics
   * @param {Object} options - Simulation options
   * @param {number} options.iterations - Number of simulations (default 10000)
   * @param {boolean} options.useRawPpg - Use raw PPG instead of SRS-adjusted (default false)
   * @returns {Object} Simulation results with distributions
   */
  function monteCarloSimulation(homeStats, awayStats, options = {}) {
    const iterations = options.iterations || 10000;
    const useRawPpg = options.useRawPpg || false;

    const homeStd = homeStats?.scoring_std_dev || 10;
    const awayStd = awayStats?.scoring_std_dev || 10;

    // Calculate expected total from raw PPG
    const homePpg = homeStats?.ppg_scored || 21;
    const awayPpg = awayStats?.ppg_scored || 21;
    const homeAllowed = homeStats?.ppg_allowed || 21;
    const awayAllowed = awayStats?.ppg_allowed || 21;
    const expectedTotal = ((homePpg + awayAllowed) + (awayPpg + homeAllowed)) / 2;

    let homeExpected, awayExpected;

    if (useRawPpg) {
      // Raw PPG: simple matchup-based scoring (ignores strength of schedule)
      homeExpected = (homePpg + awayAllowed) / 2 + 1.25;  // HFA
      awayExpected = (awayPpg + homeAllowed) / 2 - 1.25;
    } else {
      // SRS-adjusted: use power ratings for expected margin
      const homePower = calculatePowerRating(homeStats);
      const awayPower = calculatePowerRating(awayStats);
      const homeTeamCode = homeStats?.team_code;
      const hfa = homeTeamCode ? getHomeFieldAdvantage(homeTeamCode) : DEFAULT_HFA;
      const expectedMargin = (homePower - awayPower) + hfa;

      // Derive individual team expected scores from margin and total
      homeExpected = (expectedTotal + expectedMargin) / 2;
      awayExpected = (expectedTotal - expectedMargin) / 2;
    }

    // Simulate games
    const homeScores = [];
    const awayScores = [];
    const totals = [];
    const margins = [];
    let homeWins = 0;

    for (let i = 0; i < iterations; i++) {
      const hs = Math.max(0, sampleNormal(homeExpected, homeStd));
      const as = Math.max(0, sampleNormal(awayExpected, awayStd));
      homeScores.push(hs);
      awayScores.push(as);
      totals.push(hs + as);
      margins.push(hs - as);
      if (hs > as) homeWins++;
    }

    // Sort for percentiles
    const sortedMargins = [...margins].sort((a, b) => a - b);
    const sortedTotals = [...totals].sort((a, b) => a - b);

    return {
      homeWinProb: homeWins / iterations,
      spread: {
        mean: margins.reduce((a, b) => a + b, 0) / iterations,
        p5: percentile(sortedMargins, 0.05),
        p25: percentile(sortedMargins, 0.25),
        median: percentile(sortedMargins, 0.5),
        p75: percentile(sortedMargins, 0.75),
        p95: percentile(sortedMargins, 0.95),
      },
      total: {
        mean: totals.reduce((a, b) => a + b, 0) / iterations,
        p5: percentile(sortedTotals, 0.05),
        p25: percentile(sortedTotals, 0.25),
        median: percentile(sortedTotals, 0.5),
        p75: percentile(sortedTotals, 0.75),
        p95: percentile(sortedTotals, 0.95),
      },
      // Probability of covering various spreads
      spreadCoverProb: (spread) => margins.filter(m => m > spread).length / iterations,
      // Probability of hitting over
      overProb: (total) => totals.filter(t => t > total).length / iterations,
    };
  }

  /**
   * Detect value bets by comparing model probability to market odds
   * @param {number} modelProb - Model's estimated probability (0-1)
   * @param {number} marketOdds - Market American odds
   * @param {number} threshold - Minimum edge to flag (default 5%)
   * @returns {Object} Value analysis
   */
  function detectValue(modelProb, marketOdds, threshold = 0.05) {
    const impliedProb = oddsToProb(marketOdds);
    const edge = modelProb - impliedProb;
    const ev = expectedValue(marketOdds, modelProb);

    return {
      modelProb: Math.round(modelProb * 1000) / 10,
      impliedProb: Math.round(impliedProb * 1000) / 10,
      edge: Math.round(edge * 1000) / 10,
      ev: Math.round(ev * 1000) / 10,
      hasValue: edge >= threshold,
      rating: edge >= 0.10 ? 'strong' : edge >= 0.05 ? 'moderate' : edge > 0 ? 'slight' : 'none',
    };
  }

  /**
   * Calculate enhanced matchup odds with Monte Carlo and advanced factors
   */
  function calculateEnhancedOdds(homeStats, awayStats) {
    // Get base odds
    const baseOdds = calculateMatchupOdds(homeStats, awayStats);

    // Run both Monte Carlo simulations
    const srsSimulation = monteCarloSimulation(homeStats, awayStats, { iterations: 5000 });
    const rawSimulation = monteCarloSimulation(homeStats, awayStats, { iterations: 5000, useRawPpg: true });

    // Advanced factors
    const factors = analyzeMatchupFactors(homeStats, awayStats);

    return {
      ...baseOdds,
      // SRS-adjusted simulation (primary - matches win probability model)
      simulation: {
        homeWinProb: Math.round(srsSimulation.homeWinProb * 1000) / 1000,
        spreadRange: {
          low: Math.round(srsSimulation.spread.p5 * 10) / 10,
          mid: Math.round(srsSimulation.spread.median * 10) / 10,
          high: Math.round(srsSimulation.spread.p95 * 10) / 10,
        },
        totalRange: {
          low: Math.round(srsSimulation.total.p5 * 10) / 10,
          mid: Math.round(srsSimulation.total.median * 10) / 10,
          high: Math.round(srsSimulation.total.p95 * 10) / 10,
        },
      },
      // Raw PPG simulation (ignores strength of schedule)
      rawSimulation: {
        homeWinProb: Math.round(rawSimulation.homeWinProb * 1000) / 1000,
        spreadRange: {
          low: Math.round(rawSimulation.spread.p5 * 10) / 10,
          mid: Math.round(rawSimulation.spread.median * 10) / 10,
          high: Math.round(rawSimulation.spread.p95 * 10) / 10,
        },
        totalRange: {
          low: Math.round(rawSimulation.total.p5 * 10) / 10,
          mid: Math.round(rawSimulation.total.median * 10) / 10,
          high: Math.round(rawSimulation.total.p95 * 10) / 10,
        },
      },
      factors,
      confidence: calculateConfidence(srsSimulation, factors),
    };
  }

  /**
   * Analyze matchup-specific factors
   */
  function analyzeMatchupFactors(homeStats, awayStats) {
    const factors = [];

    if (!homeStats || !awayStats) return factors;

    // EMA momentum
    const homeEma = homeStats.ema_differential || 0;
    const awayEma = awayStats.ema_differential || 0;
    if (Math.abs(homeEma - awayEma) > 5) {
      const better = homeEma > awayEma ? 'home' : 'away';
      factors.push({
        type: 'momentum',
        team: better,
        magnitude: Math.abs(homeEma - awayEma).toFixed(1),
        description: `${better === 'home' ? homeStats.team_code : awayStats.team_code} has momentum edge (+${Math.abs(homeEma - awayEma).toFixed(1)} EMA diff)`,
      });
    }

    // Changepoint detection - use team code in type for unique tags
    if (homeStats.scoring_changepoint) {
      factors.push({
        type: `${homeStats.team_code} ${homeStats.scoring_changepoint_direction}`,
        team: 'home',
        direction: homeStats.scoring_changepoint_direction,
        magnitude: homeStats.scoring_changepoint_magnitude,
        description: `${homeStats.team_code} trending ${homeStats.scoring_changepoint_direction} (${homeStats.scoring_changepoint_magnitude > 0 ? '+' : ''}${homeStats.scoring_changepoint_magnitude} PPG shift)`,
      });
    }
    if (awayStats.scoring_changepoint) {
      factors.push({
        type: `${awayStats.team_code} ${awayStats.scoring_changepoint_direction}`,
        team: 'away',
        direction: awayStats.scoring_changepoint_direction,
        magnitude: awayStats.scoring_changepoint_magnitude,
        description: `${awayStats.team_code} trending ${awayStats.scoring_changepoint_direction} (${awayStats.scoring_changepoint_magnitude > 0 ? '+' : ''}${awayStats.scoring_changepoint_magnitude} PPG shift)`,
      });
    }

    // Consistency mismatch
    const homeConsistency = homeStats.scoring_consistency || 50;
    const awayConsistency = awayStats.scoring_consistency || 50;
    if (Math.abs(homeConsistency - awayConsistency) > 15) {
      const consistent = homeConsistency > awayConsistency ? 'home' : 'away';
      factors.push({
        type: 'consistency',
        team: consistent,
        description: `${consistent === 'home' ? homeStats.team_code : awayStats.team_code} is more consistent (${Math.max(homeConsistency, awayConsistency).toFixed(0)} vs ${Math.min(homeConsistency, awayConsistency).toFixed(0)})`,
      });
    }

    // Game profile clash
    const homeProfile = homeStats.game_profile || 'balanced';
    const awayProfile = awayStats.game_profile || 'balanced';
    if (homeProfile !== awayProfile && homeProfile !== 'balanced' && awayProfile !== 'balanced') {
      factors.push({
        type: 'profile_clash',
        home_profile: homeProfile,
        away_profile: awayProfile,
        description: `Style clash: ${homeStats.team_code} (${homeProfile}) vs ${awayStats.team_code} (${awayProfile})`,
      });
    }

    // Total points tendency
    const homeTotal = homeStats.avg_total_points || 43;
    const awayTotal = awayStats.avg_total_points || 43;
    const avgTotal = (homeTotal + awayTotal) / 2;
    if (avgTotal > 48) {
      factors.push({
        type: 'high_scoring',
        description: `Both teams in high-scoring games (avg ${avgTotal.toFixed(1)} total)`,
      });
    } else if (avgTotal < 40) {
      factors.push({
        type: 'low_scoring',
        description: `Both teams in low-scoring games (avg ${avgTotal.toFixed(1)} total)`,
      });
    }

    return factors;
  }

  /**
   * Calculate confidence level for prediction
   */
  function calculateConfidence(simulation, factors) {
    // Base confidence from simulation spread
    const spreadRange = simulation.spread.p95 - simulation.spread.p5;
    let confidence = 100 - (spreadRange * 2);  // Wider range = lower confidence

    // Adjust for factors
    factors.forEach(f => {
      if (f.type === 'momentum') confidence += 5;
      if (f.direction) confidence -= 5;  // Changepoints add uncertainty (has direction property)
      if (f.type === 'consistency' && f.team) confidence += 5;
    });

    return Math.max(0, Math.min(100, Math.round(confidence)));
  }

  /**
   * Find high-value betting opportunities
   * @param {Object} db - sql.js database instance
   * @param {number} season - Season year
   * @param {number} week - Week number (optional)
   * @returns {Array} Sorted list of value opportunities
   */
  function findValueOpportunities(db, season, week = null) {
    const matchups = computeAllOdds(db, season, week);
    const opportunities = [];

    matchups.forEach(matchup => {
      const enhanced = calculateEnhancedOdds(matchup.homeStats, matchup.awayStats);

      // Check moneyline value
      const homeValue = detectValue(enhanced.homeWinProb, matchup.homeMoneyline || enhanced.homeMoneyline);
      const awayValue = detectValue(enhanced.awayWinProb, matchup.awayMoneyline || enhanced.awayMoneyline);

      if (homeValue.hasValue || awayValue.hasValue) {
        opportunities.push({
          matchup: `${matchup.away_team} @ ${matchup.home_team}`,
          week: matchup.week,
          date: matchup.game_date,
          bet: homeValue.hasValue ? matchup.home_team : matchup.away_team,
          betType: 'moneyline',
          odds: homeValue.hasValue ? enhanced.homeMoneyline : enhanced.awayMoneyline,
          modelProb: homeValue.hasValue ? homeValue.modelProb : awayValue.modelProb,
          impliedProb: homeValue.hasValue ? homeValue.impliedProb : awayValue.impliedProb,
          edge: homeValue.hasValue ? homeValue.edge : awayValue.edge,
          ev: homeValue.hasValue ? homeValue.ev : awayValue.ev,
          rating: homeValue.hasValue ? homeValue.rating : awayValue.rating,
          factors: enhanced.factors,
          confidence: enhanced.confidence,
        });
      }
    });

    // Sort by edge (highest first)
    return opportunities.sort((a, b) => b.edge - a.edge);
  }

  // Public API
  return {
    // Core functions
    calculateMatchupOdds,
    calculateEnhancedOdds,
    calculatePowerRating,
    getHomeFieldAdvantage,

    // Advanced stats
    loadAdvancedStats,
    getAdvancedStats,

    // Odds utilities
    probToAmericanOdds,
    applyVig,
    formatOdds,
    formatSpread,
    oddsToProb,
    expectedValue,

    // Database helpers
    getTeamStats,
    getUpcomingMatchups,
    computeAllOdds,

    // Analysis
    monteCarloSimulation,
    detectValue,
    findValueOpportunities,
    analyzeMatchupFactors,

    // Constants exposed for reference
    DEFAULT_HFA,
    LOGISTIC_K,
  };
})();

// Export for Node.js if available
if (typeof module !== 'undefined' && module.exports) {
  module.exports = OddsEngine;
}
