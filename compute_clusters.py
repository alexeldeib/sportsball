#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "scikit-learn",
#     "numpy",
# ]
# ///
"""
Compute team and player clusters using k-means clustering.

Usage: ./compute_clusters.py [year]
  year defaults to 2025

Reads: team-stats-{year}.json, player-weekly-stats-{year}.json
Outputs: team-clusters-{year}.json, player-clusters-{year}.json

Clustering Dimensions:
- Teams: Offensive style, tempo, consistency, quarter profile
- Players: Production profile, consistency, big play rate
"""
import json
import sys
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


# ============ Team Clustering ============

TEAM_CLUSTER_NAMES = {
    0: "high_powered",      # High scoring, aggressive
    1: "defensive",         # Low scoring, strong defense
    2: "balanced",          # Average across metrics
    3: "volatile",          # High variance, unpredictable
    4: "ground_game",       # Run-heavy, ball control
    5: "pass_heavy",        # Air raid style
}


def extract_team_features(team_stats):
    """Extract clustering features from team stats.

    Features (normalized):
    1. ppg_scored - Offensive output
    2. ppg_allowed - Defensive strength
    3. scoring_consistency - How predictable
    4. avg_total_points - Game pace/tempo
    5. first_half_differential - Fast starter or closer
    6. close_game_pct - How often in tight games
    7. ema_differential - Recent form
    """
    features = []
    team_codes = []

    for t in team_stats:
        team_codes.append(t["team_code"])
        features.append([
            t.get("ppg_scored", 0),
            t.get("ppg_allowed", 0),
            t.get("scoring_consistency", 50),
            t.get("avg_total_points", 45),
            t.get("first_half_differential", 0) - t.get("second_half_differential", 0),
            t.get("close_game_pct", 50),
            t.get("ema_differential", 0),
        ])

    return np.array(features), team_codes


def cluster_teams(team_stats, n_clusters=5):
    """Cluster teams by playstyle."""
    features, team_codes = extract_team_features(team_stats)

    if len(features) < n_clusters:
        print(f"Warning: Only {len(features)} teams, reducing clusters to {len(features)}")
        n_clusters = len(features)

    # Normalize features
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features)

    # K-means clustering
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features_scaled)

    # Build results
    results = []
    for i, team_code in enumerate(team_codes):
        cluster_id = int(labels[i])

        # Find team's original stats
        team = next(t for t in team_stats if t["team_code"] == team_code)

        # Determine cluster name based on centroid characteristics
        cluster_name = determine_cluster_name(features[i], kmeans.cluster_centers_[cluster_id], features_scaled, labels)

        results.append({
            "team_code": team_code,
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
            # Include key features for reference
            "ppg_scored": team.get("ppg_scored", 0),
            "ppg_allowed": team.get("ppg_allowed", 0),
            "consistency": team.get("scoring_consistency", 50),
            "ema_differential": team.get("ema_differential", 0),
            "game_profile": team.get("game_profile", "balanced"),
        })

    # Add cluster summary
    cluster_summary = {}
    for cid in range(n_clusters):
        members = [r["team_code"] for r in results if r["cluster_id"] == cid]
        avg_ppg = np.mean([r["ppg_scored"] for r in results if r["cluster_id"] == cid])
        avg_allowed = np.mean([r["ppg_allowed"] for r in results if r["cluster_id"] == cid])
        cluster_summary[cid] = {
            "members": members,
            "avg_ppg": round(avg_ppg, 1),
            "avg_allowed": round(avg_allowed, 1),
            "count": len(members),
        }

    return results, cluster_summary, kmeans.cluster_centers_.tolist()


def determine_cluster_name(team_features, centroid, all_features, all_labels):
    """Determine descriptive name for cluster based on characteristics."""
    ppg = team_features[0]
    allowed = team_features[1]
    consistency = team_features[2]
    total = team_features[3]

    # High-powered: High PPG, any defense
    if ppg > 25:
        return "high_powered"
    # Defensive: Low allowed, any offense
    elif allowed < 20:
        return "defensive"
    # Volatile: Low consistency
    elif consistency < 40:
        return "volatile"
    # Ground game: Low total (ball control)
    elif total < 42:
        return "ground_game"
    # Pass heavy: High total
    elif total > 50:
        return "pass_heavy"
    else:
        return "balanced"


# ============ Player Clustering ============

PLAYER_CLUSTER_NAMES = {
    "QB": {
        0: "elite_passer",
        1: "dual_threat",
        2: "game_manager",
        3: "gunslinger",
    },
    "RB": {
        0: "workhorse",
        1: "receiving_back",
        2: "goal_line",
        3: "change_of_pace",
    },
    "WR": {
        0: "alpha_wr",
        1: "deep_threat",
        2: "slot_specialist",
        3: "possession_receiver",
    },
    "TE": {
        0: "elite_receiving",
        1: "blocking_te",
        2: "red_zone_target",
    },
}


def extract_player_features(player_stats, position):
    """Extract clustering features for players of a specific position."""
    # Filter to position
    players = [p for p in player_stats if p.get("position") == position]

    if not players:
        return None, []

    features = []
    player_names = []

    for p in players:
        stats = p.get("stats", {})

        if position == "QB":
            # QB features: pass yards, rush yards, TD rate, efficiency
            pass_yd = stats.get("pass_yd", 0) or 0
            rush_yd = stats.get("rush_yd", 0) or 0
            pass_td = stats.get("pass_td", 0) or 0
            pass_int = stats.get("pass_int", 0) or 0
            pass_att = stats.get("pass_att", 1) or 1

            features.append([
                pass_yd,
                rush_yd,
                pass_td / pass_att * 100,  # TD rate
                (pass_td + 0.1) / (pass_int + 0.1),  # TD/INT ratio
            ])
        elif position == "RB":
            # RB features: rush yards, receptions, yards per carry
            rush_yd = stats.get("rush_yd", 0) or 0
            rush_att = stats.get("rush_att", 1) or 1
            rec = stats.get("rec", 0) or 0
            rec_yd = stats.get("rec_yd", 0) or 0

            features.append([
                rush_yd,
                rush_yd / rush_att if rush_att > 0 else 0,  # YPC
                rec,
                rec_yd,
            ])
        elif position in ("WR", "TE"):
            # WR/TE features: receptions, yards, TDs, yards per reception
            rec = stats.get("rec", 0) or 0
            rec_yd = stats.get("rec_yd", 0) or 0
            rec_td = stats.get("rec_td", 0) or 0

            features.append([
                rec,
                rec_yd,
                rec_td,
                rec_yd / rec if rec > 0 else 0,  # Yards per reception
            ])
        else:
            continue

        player_names.append({
            "name": p.get("name"),
            "team": p.get("team"),
            "team_code": p.get("team_code"),
        })

    return np.array(features) if features else None, player_names


def cluster_players(player_stats, position, n_clusters=4):
    """Cluster players by production profile."""
    features, player_info = extract_player_features(player_stats, position)

    if features is None or len(features) < n_clusters:
        return [], {}

    # Only cluster players with meaningful stats
    # Filter out players with very low production
    if position == "QB":
        mask = features[:, 0] > 500  # At least 500 pass yards
    elif position == "RB":
        mask = features[:, 0] > 100  # At least 100 rush yards
    else:
        mask = features[:, 0] > 10  # At least 10 receptions

    features_filtered = features[mask]
    player_info_filtered = [p for p, m in zip(player_info, mask) if m]

    if len(features_filtered) < n_clusters:
        n_clusters = max(2, len(features_filtered))

    if len(features_filtered) < 2:
        return [], {}

    # Normalize
    scaler = StandardScaler()
    features_scaled = scaler.fit_transform(features_filtered)

    # Cluster
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(features_scaled)

    # Build results
    results = []
    for i, pinfo in enumerate(player_info_filtered):
        cluster_id = int(labels[i])
        cluster_names = PLAYER_CLUSTER_NAMES.get(position, {})
        cluster_name = cluster_names.get(cluster_id, f"cluster_{cluster_id}")

        results.append({
            "player_name": pinfo["name"],
            "team": pinfo["team"],
            "team_code": pinfo["team_code"],
            "position": position,
            "cluster_id": cluster_id,
            "cluster_name": cluster_name,
        })

    # Cluster summary
    cluster_summary = {}
    for cid in range(n_clusters):
        members = [r["player_name"] for r in results if r["cluster_id"] == cid]
        cluster_summary[cid] = {
            "count": len(members),
            "sample_players": members[:5],
        }

    return results, cluster_summary


# ============ Main ============

def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2025"

    print(f"Computing clusters for {year}...")

    # Load team stats
    team_stats_file = Path(f"team-stats-{year}.json")
    if team_stats_file.exists():
        with open(team_stats_file, encoding="utf-8") as f:
            team_stats = json.load(f)

        print(f"\n=== Team Clustering ===")
        team_clusters, team_summary, centroids = cluster_teams(team_stats, n_clusters=5)

        print(f"Clustered {len(team_clusters)} teams into {len(team_summary)} groups:")
        for cid, info in team_summary.items():
            sample_name = team_clusters[0]["cluster_name"] if team_clusters else "unknown"
            for t in team_clusters:
                if t["cluster_id"] == cid:
                    sample_name = t["cluster_name"]
                    break
            print(f"  Cluster {cid} ({sample_name}): {info['count']} teams, "
                  f"avg PPG {info['avg_ppg']}, avg allowed {info['avg_allowed']}")
            print(f"    Teams: {', '.join(info['members'])}")

        # Save team clusters
        output = {
            "season": int(year),
            "clusters": team_clusters,
            "summary": team_summary,
            "centroids": centroids,
        }
        with open(f"team-clusters-{year}.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved team clusters to team-clusters-{year}.json")
    else:
        print(f"Warning: {team_stats_file} not found, skipping team clustering")

    # Load player stats for clustering
    player_stats_file = Path(f"players-with-stats-{year}.json")
    if player_stats_file.exists():
        with open(player_stats_file, encoding="utf-8") as f:
            player_stats = json.load(f)

        print(f"\n=== Player Clustering ===")
        all_player_clusters = []
        all_player_summaries = {}

        for position in ["QB", "RB", "WR", "TE"]:
            clusters, summary = cluster_players(player_stats, position, n_clusters=4)
            if clusters:
                all_player_clusters.extend(clusters)
                all_player_summaries[position] = summary
                print(f"\n{position}: {len(clusters)} players clustered")
                for cid, info in summary.items():
                    print(f"  Cluster {cid}: {info['count']} players")
                    if info['sample_players']:
                        print(f"    Sample: {', '.join(info['sample_players'][:3])}")

        # Save player clusters
        output = {
            "season": int(year),
            "clusters": all_player_clusters,
            "summary": all_player_summaries,
        }
        with open(f"player-clusters-{year}.json", "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"\nSaved player clusters to player-clusters-{year}.json")
    else:
        print(f"Warning: {player_stats_file} not found, skipping player clustering")

    print("\nDone!")


if __name__ == "__main__":
    main()
