/**
 * NFL Betting Odds Engine
 * Computes moneyline, spread, and over/under for matchups
 */

const OddsEngine = (function() {
  // Constants
  const HOME_FIELD_ADVANTAGE = 2.5;  // Points
  const LOGISTIC_K = 0.145;          // Calibration constant for win probability
  const VIG_PERCENT = 0.0476;        // Standard juice (~4.76% = -110/-110)

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
  function applyVig(fairProb, vig = VIG_PERCENT) {
    const adjusted = Math.min(fairProb * (1 + vig), 0.99);
    return probToAmericanOdds(adjusted);
  }

  /**
   * Calculate team power rating from stats
   * @param {Object} teamStats - Team statistics object
   * @returns {number} Power rating (point differential)
   */
  function calculatePowerRating(teamStats) {
    if (!teamStats) return 0;

    const ppg = teamStats.ppg_scored || 21.0;
    const ppgAllowed = teamStats.ppg_allowed || 21.0;

    // Base power rating is point differential
    const base = ppg - ppgAllowed;

    // Weight recent form slightly more
    const last5Ppg = teamStats.last_5_ppg || ppg;
    const last5Allowed = teamStats.last_5_ppg_allowed || ppgAllowed;
    const recentDiff = last5Ppg - last5Allowed;

    // Blend: 70% season, 30% recent
    return 0.7 * base + 0.3 * recentDiff;
  }

  /**
   * Calculate full matchup odds
   * @param {Object} homeStats - Home team statistics
   * @param {Object} awayStats - Away team statistics
   * @returns {Object} Odds object with all betting lines
   */
  function calculateMatchupOdds(homeStats, awayStats) {
    const homePower = calculatePowerRating(homeStats);
    const awayPower = calculatePowerRating(awayStats);

    // Expected point differential (home perspective)
    const expectedDiff = (homePower - awayPower) + HOME_FIELD_ADVANTAGE;

    // Win probability using logistic function
    const homeWinProb = 1 / (1 + Math.exp(-LOGISTIC_K * expectedDiff));

    // Moneyline odds with vig
    const homeMl = applyVig(homeWinProb);
    const awayMl = applyVig(1 - homeWinProb);

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
      expectedDiff: Math.round(expectedDiff * 10) / 10
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

  // Public API
  return {
    calculateMatchupOdds,
    calculatePowerRating,
    probToAmericanOdds,
    applyVig,
    formatOdds,
    formatSpread,
    oddsToProb,
    expectedValue,
    getTeamStats,
    getUpcomingMatchups,
    computeAllOdds,

    // Constants exposed for reference
    HOME_FIELD_ADVANTAGE,
    LOGISTIC_K,
    VIG_PERCENT
  };
})();

// Export for Node.js if available
if (typeof module !== 'undefined' && module.exports) {
  module.exports = OddsEngine;
}
