import os
import sys
import math
import json
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import datetime

# =====================================================================
# API KEY ROTATION SETUP
# =====================================================================
API_KEYS = []
key1 = os.environ.get("CFBD_API_KEY", "").strip()
key2 = os.environ.get("CFBD_API_KEY_SECONDARY", "").strip()

if key1: API_KEYS.append(key1)
if key2: API_KEYS.append(key2)

if not API_KEYS:
    print("CRITICAL: CFBD_API_KEY environment variable is missing. Set it before running.")
    sys.exit(1)

CURRENT_KEY_IDX = 0

# Multi-Year Era Engine Limits
HISTORICAL_START_YEAR = 1995

# Dynamic Season Detection
def get_cfb_seasons():
    now = datetime.datetime.now()
    if now.month in [1, 2]:
        cur_season = now.year - 1
    else:
        cur_season = now.year
    prev_season = cur_season - 1
    return cur_season, prev_season

CUR_YEAR, PREV_YEAR = get_cfb_seasons()

# Safe Web Request Session
session = requests.Session()
retries = Retry(total=5, backoff_factor=1.0, status_forcelist=[500, 502, 503, 504])
session.mount("https://", HTTPAdapter(max_retries=retries))

def cfbd_get(endpoint, params=None):
    global CURRENT_KEY_IDX
    base_url = "https://api.collegefootballdata.com"
    url = f"{base_url}{endpoint}"
    
    max_attempts = len(API_KEYS) * 3
    for attempt in range(max_attempts):
        key = API_KEYS[CURRENT_KEY_IDX]
        headers = {"Authorization": f"Bearer {key}", "Accept": "application/json"}
        
        try:
            r = session.get(url, headers=headers, params=params or {}, timeout=60)
            
            if r.status_code == 429:
                print(f"Rate limit (429) hit on Key {CURRENT_KEY_IDX + 1}. Swapping to backup key...")
                CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(API_KEYS)
                time.sleep(1.0)
                continue
                
            if r.status_code == 401:
                print(f"Unauthorized (401) hit on Key {CURRENT_KEY_IDX + 1}. Swapping to backup key...")
                CURRENT_KEY_IDX = (CURRENT_KEY_IDX + 1) % len(API_KEYS)
                time.sleep(0.5)
                continue
            
            time.sleep(0.2)
            
            if r.status_code != 200:
                return []
            return r.json()
            
        except Exception as e:
            print(f"Network error on {endpoint}: {e}")
            time.sleep(1.0)
            
    return []

def get_fbs_teams_and_confs(year):
    cache_dir = "data/cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_file = os.path.join(cache_dir, f"fbs_teams_{year}.json")
    
    if os.path.exists(cache_file):
        with open(cache_file, "r", encoding="utf-8") as f:
            return json.load(f)
            
    raw_data = cfbd_get("/teams/fbs", {"year": str(year)})
    
    if raw_data:
        teams = {t["school"]: t.get("conference", "Independent") for t in raw_data}
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(teams, f, indent=2)
        return teams
        
    print(f"\n🚨 CRITICAL ERROR: Failed to fetch FBS teams for {year} from API.")
    sys.exit(1)

def extract_game(g):
    # We DO NOT return None if completed is False anymore!
    # We need the full schedule to calculate unplayed SOS.
    
    h = g.get("home_team") or g.get("homeTeam")
    a = g.get("away_team") or g.get("awayTeam")
    hp = g.get("home_points") if g.get("home_points") is not None else g.get("homePoints")
    ap = g.get("away_points") if g.get("away_points") is not None else g.get("awayPoints")
    wk = g.get("week", 1)
    neutral = g.get("neutral_site", False) or g.get("neutralSite", False)
    gid = g.get("id", 0)
    completed = g.get("completed", False)

    if h and a:
        hp_int = int(hp) if hp is not None else None
        ap_int = int(ap) if ap is not None else None
        
        # If the game is marked completed but has no score, it's not actually completed.
        if completed and (hp_int is None or ap_int is None):
            completed = False

        if completed and hp_int == 0 and ap_int == 0:
             return None # Ignore 0-0 ties / cancellations that are marked complete

        return {
            "id": gid,
            "week": int(wk),
            "home_team": h,
            "away_team": a,
            "home_points": hp_int,
            "away_points": ap_int,
            "neutral_site": bool(neutral),
            "completed": completed
        }
    return None

def get_year_games(target_year):
    cache_dir = "data/cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"games_{target_year}.json")

    # Only load from cache if it's a past year where the schedule is fully set in stone
    if target_year < CUR_YEAR and os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)

    if target_year == CUR_YEAR and os.path.exists(cache_path):
        try:
            os.remove(cache_path)
        except Exception:
            pass

    raw_data = cfbd_get("/games", {"year": str(target_year), "seasonType": "both"})
    if not raw_data or not isinstance(raw_data, list):
        return []
    
    clean_games = []
    for item in raw_data:
        g = extract_game(item)
        if g:
            clean_games.append(g)

    clean_games.sort(key=lambda x: x.get("start_date", ""))
    
    if target_year < CUR_YEAR:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(clean_games, f)

    return clean_games

def get_ap_polls(target_year):
    raw = cfbd_get("/rankings", {"year": str(target_year), "seasonType": "regular"})
    ap_map = {}
    if isinstance(raw, list):
        for week_data in raw:
            wk = week_data.get("week", 1)
            for poll in week_data.get("polls", []):
                if poll.get("poll") == "AP Top 25":
                    for item in poll.get("ranks", []):
                        school = item.get("school")
                        rank = item.get("rank")
                        if school and rank:
                            ap_map[(wk, school)] = rank
    return ap_map

# =====================================================================
# V3.5 MATHEMATICS (Proportional Decay Future Blended SOS & Variable Loss Tax)
# =====================================================================

def get_margin_multiplier(score_diff):
    diff = max(1, abs(score_diff))
    mult = 1.00 + 0.25 * (math.log(diff) / math.log(45.0))
    return max(1.00, min(1.25, mult))

def get_opp_k_multiplier(opp_elo):
    return max(0.65, min(1.35, 1.0 + (opp_elo - 1500.0) / 600.0))

def compute_win_expectancy(elo_home, elo_away):
    return 1.0 / (1.0 + 10.0 ** ((elo_away - elo_home) / 400.0))

def compute_historical_baselines(cur_year, fbs_teams):
    print("--- Dynamically Computing Historical Baselines & Conferences (4-Year Window) ---")
    hist_years = [cur_year - 4, cur_year - 3, cur_year - 2, cur_year - 1]
    
    home_margins = {team: [] for team in fbs_teams}
    away_margins = {team: [] for team in fbs_teams}
    
    hist_elo = {t: 1500.0 for t in fbs_teams}

    for y in hist_years:
        games = get_year_games(y)
        for g in games:
            h, a = g.get("home_team"), g.get("away_team")
            hp, ap = g.get("home_points"), g.get("away_points")
            completed = g.get("completed", False)
            
            if not completed or hp is None or ap is None:
                continue
            if h not in fbs_teams and a not in fbs_teams:
                continue
            
            if not g.get("neutral_site", False):
                if h in fbs_teams and a in fbs_teams:
                    home_margins[h].append(hp - ap)
                    away_margins[a].append(ap - hp)
            
            if h not in hist_elo: hist_elo[h] = 1200.0
            if a not in hist_elo: hist_elo[a] = 1200.0

            eh = compute_win_expectancy(hist_elo[h], hist_elo[a])
            ea = 1.0 - eh
            mult = get_margin_multiplier(hp - ap)

            if hp > ap:
                k_adj_h = get_opp_k_multiplier(hist_elo[a])
                k_adj_a = get_opp_k_multiplier(hist_elo[h])
                hist_elo[h] += max(6.0, 64.0 * k_adj_h * ea * mult)
                hist_elo[a] += -64.0 * k_adj_a * ea * mult
            elif ap > hp:
                k_adj_a = get_opp_k_multiplier(hist_elo[h])
                k_adj_h = get_opp_k_multiplier(hist_elo[a])
                hist_elo[a] += max(6.0, 64.0 * k_adj_a * eh * mult)
                hist_elo[h] += -64.0 * k_adj_h * eh * mult

    venue_stats = {}
    for team in fbs_teams:
        hm = sum(home_margins[team]) / len(home_margins[team]) if home_margins[team] else 0.0
        am = sum(away_margins[team]) / len(away_margins[team]) if away_margins[team] else 0.0
        spread = hm - am
        denom = abs(hm) + abs(am)
        w_away = (abs(am) / denom) if denom > 0 else 0.5
        w_home = 1.0 - w_away

        d_h = max(0.0, min(40.0, 16.0 * (1.0 + (spread - 8.0) * w_home * 0.25)))
        d_a = min(0.0, max(-50.0, -16.0 * (1.0 + (spread - 8.0) * w_away * 0.25)))
        venue_stats[team] = {
            "hm": round(hm, 1),
            "am": round(am, 1),
            "spread": round(spread, 1),
            "d_h": round(d_h, 1),
            "d_a": round(d_a, 1)
        }

    sorted_venues = sorted(fbs_teams.keys(), key=lambda t: venue_stats[t]["d_h"], reverse=True)
    for rank, t in enumerate(sorted_venues, start=1):
        venue_stats[t]["venue_rank"] = rank

    conf_base_4yr = {}
    for conf in set(fbs_teams.values()):
        # HARDCODE INDEPENDENT OVERRIDE
        if conf == "FBS Independents":
             conf_base_4yr[conf] = 1450.0
             continue

        conf_teams = [t for t, c in fbs_teams.items() if c == conf]
        if len(conf_teams) > 2:
            avg_elo = sum(hist_elo.get(t, 1500.0) for t in conf_teams) / len(conf_teams)
            conf_base_4yr[conf] = round(avg_elo, 1)
        else:
            conf_base_4yr[conf] = 1450.0 # Fallback for bizarre micro-conferences

    return venue_stats, conf_base_4yr

def get_prior_decay_weight(w):
    if w <= 12:
        return 0.05 + 0.30 * (((12.0 - w) / 11.0) ** 2.0)
    elif w <= 16:
        return 0.05 * (((16.0 - w) / 4.0) ** 1.5)
    return 0.0

def ensure_team_in_elo(team, elo_dict, rec_dict):
    if team not in elo_dict:
        elo_dict[team] = 1200.0
        rec_dict[team] = {
            "w": 0, 
            "l": 0, 
            "played_opps": [], 
            "unplayed_opps": [],
            "loss_elos": []
        }

def run_season_pipeline(year, fbs_teams, venue_stats, regressed_priors, prior_diagnostics, conf_base_4yr, max_week=None):
    all_games = get_year_games(year)
    ap_polls = get_ap_polls(year)
    
    elo = {t: 1500.0 for t in fbs_teams}
    prior_elo = {t: regressed_priors.get(t, 1500.0) for t in fbs_teams}
    records = {t: {"w": 0, "l": 0, "played_opps": [], "unplayed_opps": [], "loss_elos": []} for t in fbs_teams}

    active_week = max_week if max_week is not None else 12

    # Step 1: Iterate through ALL games to separate played vs unplayed and execute played games
    for g in all_games:
        h, a = g.get("home_team"), g.get("away_team")
        hp, ap = g.get("home_points"), g.get("away_points")
        wk = g.get("week", 1)
        completed = g.get("completed", False)
        
        if h not in fbs_teams and a not in fbs_teams:
            continue

        ensure_team_in_elo(h, elo, records)
        ensure_team_in_elo(a, elo, records)
        
        if h not in prior_elo: prior_elo[h] = 1200.0
        if a not in prior_elo: prior_elo[a] = 1200.0

        # Categorize the game based on the requested max_week horizon
        if wk <= active_week and completed and hp is not None and ap is not None:
             # PLAYED GAME - Execute standard math
             records[h]["played_opps"].append(a)
             records[a]["played_opps"].append(h)

             is_neutral = g.get("neutral_site", False)
             d_h = 0.0 if is_neutral else venue_stats.get(h, {}).get("d_h", 16.0)
             d_a = 0.0 if is_neutral else venue_stats.get(a, {}).get("d_a", -16.0)

             eff_h = elo[h] + d_h
             eff_a = elo[a] + d_a
             eh = compute_win_expectancy(eff_h, eff_a)
             ea = 1.0 - eh
             mult = get_margin_multiplier(hp - ap)

             if hp > ap:
                 records[h]["w"] += 1
                 records[a]["l"] += 1
                 records[a]["loss_elos"].append(elo[h])
                 k_adj_h = get_opp_k_multiplier(elo[a])
                 k_adj_a = get_opp_k_multiplier(elo[h])
                 delta_w = max(6.0, 64.0 * k_adj_h * ea * mult)
                 delta_l = -64.0 * k_adj_a * ea * mult
                 elo[h] += delta_w
                 elo[a] += delta_l
                 prior_elo[h] += delta_w
                 prior_elo[a] += delta_l
             elif ap > hp:
                 records[a]["w"] += 1
                 records[h]["l"] += 1
                 records[h]["loss_elos"].append(elo[a])
                 k_adj_a = get_opp_k_multiplier(elo[h])
                 k_adj_h = get_opp_k_multiplier(elo[a])
                 delta_w = max(6.0, 64.0 * k_adj_a * eh * mult)
                 delta_l = -64.0 * k_adj_h * eh * mult
                 elo[a] += delta_w
                 elo[h] += delta_l
                 prior_elo[a] += delta_w
                 prior_elo[h] += delta_l
                 
        else:
             # UNPLAYED GAME (either in future week, or uncompleted)
             records[h]["unplayed_opps"].append(a)
             records[a]["unplayed_opps"].append(h)


    pure_sos_dict = {}
    blended_sos_dict = {}

    for t in fbs_teams:
        p_opps = records[t]["played_opps"]
        u_opps = records[t]["unplayed_opps"]
        
        # Calculate Base Averages
        avg_played = sum(elo[o] for o in p_opps) / len(p_opps) if p_opps else 1500.0
        avg_unplayed = sum(elo[o] for o in u_opps) / len(u_opps) if u_opps else 1500.0

        pure_sos_dict[t] = avg_played
        
        # 3% Decay Future SOS Blend Logic
        n_played = len(p_opps)
        
        if n_played == 0:
             # Preseason: SOS is bypassed anyway, just set to 1500
             blended_sos_dict[t] = 1500.0
        elif active_week > 12:
             # Postseason: Future unplayed games carry 0 weight
             blended_sos_dict[t] = avg_played
        else:
             # Regular Season: 3% decay rule
             w_unplayed = max(0.0, 0.36 - (0.03 * n_played))
             w_played = 1.0 - w_unplayed
             blended_sos_dict[t] = (w_played * avg_played) + (w_unplayed * avg_unplayed)


    pure_sos_sorted = sorted(fbs_teams.keys(), key=lambda t: pure_sos_dict[t], reverse=True)
    pure_sos_ranks = {t: rank for rank, t in enumerate(pure_sos_sorted, start=1)}

    blended_sos_sorted = sorted(fbs_teams.keys(), key=lambda t: blended_sos_dict[t], reverse=True)
    blended_sos_ranks = {t: rank for rank, t in enumerate(blended_sos_sorted, start=1)}

    pure_sorted = sorted(fbs_teams.keys(), key=lambda t: elo[t], reverse=True)
    pure_ranks = {t: rank for rank, t in enumerate(pure_sorted, start=1)}

    prior_sorted = sorted(fbs_teams.keys(), key=lambda t: prior_elo[t], reverse=True)
    prior_ranks = {t: rank for rank, t in enumerate(prior_sorted, start=1)}

    w_prior = get_prior_decay_weight(active_week)

    results = []
    for t in fbs_teams:
        pure_val = elo[t]
        prior_val = prior_elo[t]
        pure_sos_val = pure_sos_dict[t]
        blended_sos_val = blended_sos_dict[t]
        losses = records[t]["l"]
        n_played = len(records[t]["played_opps"])

        # Preseason bypass
        if n_played == 0:
             sos_offset = 0.0
        else:
             # Huber-Style Hybrid SOS Offset (Clamp 50, Linear 0.10) using Blended SOS
             sos_diff = blended_sos_val - 1500.0
             sos_sign = 1.0 if sos_diff >= 0 else -1.0
             exp_part = 35.0 * sos_sign * ((abs(sos_diff) / 50.0) ** 2.0)
             clamped_exp = max(-50.0, min(50.0, exp_part))
             linear_part = 0.10 * sos_diff
             sos_offset = clamped_exp + linear_part

        composite = ((1.0 - w_prior) * pure_val) + (w_prior * prior_val) + sos_offset

        # Variable Quality-of-Loss Tax Multiplier
        loss_multiplier = 1.0
        for opp_elo in records[t]["loss_elos"]:
            opp_quality_factor = 2.0 / (1.0 + 10.0 ** ((opp_elo - 1500.0) / 400.0))
            single_loss_tax = 0.0075 * opp_quality_factor
            loss_multiplier *= (1.0 - single_loss_tax)

        loss_tax_pct = (1.0 - loss_multiplier) * 100.0
        full_score = composite * loss_multiplier

        conf = fbs_teams[t]
        c_4yr = conf_base_4yr.get(conf, 1450.0) # independent baseline is 1450
        c_1yr_prior = c_4yr - 8.0
        c_cur = c_4yr - 27.0

        diag = prior_diagnostics.get(t, {"prev_raw": 1500.0, "reg_rate": 28.0, "prior_shift": 0.0})
        v_stat = venue_stats.get(t, {"hm": 0.0, "am": 0.0, "spread": 0.0, "d_h": 16.0, "d_a": -16.0, "venue_rank": 100})

        home_elo_str = f"{(pure_val + v_stat['d_h']):.1f} (+{v_stat['d_h']:.1f})"
        away_elo_str = f"{(pure_val + v_stat['d_a']):.1f} ({v_stat['d_a']:.1f})"
        
        ap_r = ap_polls.get((active_week, t), None)

        results.append({
            "team": t,
            "conf": conf,
            "record": f"{records[t]['w']}–{records[t]['l']}",
            "full_score": round(full_score, 1),
            "ap_rank": ap_r if ap_r is not None else "-",
            "delta_wk": 0.0,
            "loss_tax_pct": round(loss_tax_pct, 2),
            "sos": round(blended_sos_val, 1),
            "sos_rank": blended_sos_ranks[t],
            "sos_offset": round(sos_offset, 1),
            "pure_sos": round(pure_sos_val, 1),
            "pure_sos_rank": pure_sos_ranks[t],
            "conf_4yr": round(c_4yr, 1),
            "conf_1yr_prior": round(c_1yr_prior, 1),
            "conf_cur": round(c_cur, 1),
            "score_w_prior_rank": prior_ranks[t],
            "score_w_prior": round(prior_val, 1),
            "pure_elo_rank": pure_ranks[t],
            "pure_elo": round(pure_val, 1),
            "venue_rank": v_stat["venue_rank"],
            "margin_str": f"{v_stat['hm']:+.1f} / {v_stat['am']:+.1f} ({v_stat['spread']:+.1f})",
            "home_elo_str": home_elo_str,
            "away_elo_str": away_elo_str,
            "spread": v_stat["spread"],
            "d_h": v_stat["d_h"],
            "d_a": v_stat["d_a"],
            "prev_raw_elo": round(diag["prev_raw"], 1),
            "reg_rate_pct": round(diag["reg_rate"], 1),
            "prior_shift": round(diag["prior_shift"], 1),
            "w_prior_pct": round(w_prior * 100.0, 1),
            "opponents": records[t]["played_opps"]
        })

    results.sort(key=lambda x: x["full_score"], reverse=True)
    for rank, row in enumerate(results, start=1):
        row["rank"] = rank

    return results, elo

def build_multiyear_index(cur_year, fbs_teams, venue_stats):
    print(f"--- Building Multi-Year Index ({HISTORICAL_START_YEAR} to Present) ---")
    start_year = max(HISTORICAL_START_YEAR, cur_year - 50)
    index_data = {t: {} for t in fbs_teams}

    for y in range(start_year, cur_year + 1):
        games = get_year_games(y)
        elo = {t: 1500.0 for t in fbs_teams}
        rec = {t: {"w": 0, "l": 0, "played_opps": [], "unplayed_opps": [], "loss_elos": []} for t in fbs_teams}

        for g in games:
            h, a = g.get("home_team"), g.get("away_team")
            hp, ap = g.get("home_points"), g.get("away_points")
            completed = g.get("completed", False)
            if not completed or hp is None or ap is None:
                 continue
            if h not in fbs_teams and a not in fbs_teams:
                continue
            
            ensure_team_in_elo(h, elo, rec)
            ensure_team_in_elo(a, elo, rec)
            
            rec[h]["played_opps"].append(a)
            rec[a]["played_opps"].append(h)
            
            mult = get_margin_multiplier(hp - ap)
            eh = compute_win_expectancy(elo[h], elo[a])
            ea = 1.0 - eh
            
            if hp > ap:
                rec[h]["w"] += 1
                rec[a]["l"] += 1
                rec[a]["loss_elos"].append(elo[h])
                elo[h] += max(6.0, 64.0 * ea * mult)
                elo[a] += -64.0 * ea * mult
            elif ap > hp:
                rec[a]["w"] += 1
                rec[h]["l"] += 1
                rec[h]["loss_elos"].append(elo[a])
                elo[a] += max(6.0, 64.0 * eh * mult)
                elo[h] += -64.0 * eh * mult

        for t in fbs_teams:
            opps = rec[t]["played_opps"]
            avg_sos = sum(elo[o] for o in opps) / len(opps) if opps else 1500.0
            
            loss_multiplier = 1.0
            for opp_elo in rec[t]["loss_elos"]:
                opp_quality_factor = 2.0 / (1.0 + 10.0 ** ((opp_elo - 1500.0) / 400.0))
                single_loss_tax = 0.0075 * opp_quality_factor
                loss_multiplier *= (1.0 - single_loss_tax)

            score = elo[t] * loss_multiplier
            index_data[t][str(y)] = {
                "score": round(score, 1),
                "w": rec[t]["w"],
                "l": rec[t]["l"],
                "sos": round(avg_sos, 1)
            }

    with open(os.path.join("data", "yearly_index.json"), "w", encoding="utf-8") as f:
        json.dump(index_data, f, indent=2)

def main():
    print(f"Executing Engine for Current Season: {CUR_YEAR} (Previous Season: {PREV_YEAR})")
    
    fbs_teams = get_fbs_teams_and_confs(CUR_YEAR)
    if not fbs_teams:
        print("CRITICAL ERROR: Failed to load team data.")
        sys.exit(1)
        
    venue_stats, conf_base_4yr = compute_historical_baselines(CUR_YEAR, fbs_teams)

    print(f"--- Simulating Previous Season ({PREV_YEAR}) ---")
    prev_games = get_year_games(PREV_YEAR)
    prev_max_wk = max((g.get("week", 1) for g in prev_games), default=16)
    
    _, prev_elo = run_season_pipeline(
        PREV_YEAR, fbs_teams, venue_stats, {}, {}, conf_base_4yr, max_week=prev_max_wk
    )

    regressed_priors = {}
    prior_diagnostics = {}
    for t in fbs_teams:
        prev_raw = prev_elo.get(t, 1500.0)
        e_4yr = prev_raw
        conf = fbs_teams[t]
        conf_base = conf_base_4yr.get(conf, 1450.0) # independent baseline is 1450
        anchor = (0.60 * e_4yr) + (0.40 * conf_base)
        r_rate = max(0.18, min(0.42, 0.28 - 0.035 * ((e_4yr - 1500.0) / 100.0) + 0.050 * (abs(prev_raw - e_4yr) / 100.0)))
        reg_prior = ((1.0 - r_rate) * prev_raw) + (r_rate * anchor)
        regressed_priors[t] = reg_prior
        prior_diagnostics[t] = {
            "prev_raw": prev_raw,
            "reg_rate": r_rate * 100.0,
            "prior_shift": reg_prior - prev_raw
        }

    print(f"--- Writing Week Datasets for Previous Season ({PREV_YEAR}) ---")
    os.makedirs(os.path.join("data", str(PREV_YEAR)), exist_ok=True)
    prev_manifest_weeks = []
    
    prev_prev_priors = {t: 1500.0 for t in fbs_teams}
    prev_prev_diag = {t: {"prev_raw": 1500.0, "reg_rate": 28.0, "prior_shift": 0.0} for t in fbs_teams}
    
    prev_week_scores = {}
    for w in range(1, prev_max_wk + 1):
        prev_manifest_weeks.append(w)
        prev_data_w, _ = run_season_pipeline(PREV_YEAR, fbs_teams, venue_stats, prev_prev_priors, prev_prev_diag, conf_base_4yr, max_week=w)
        
        for r in prev_data_w:
            t = r["team"]
            prev_score = prev_week_scores.get(t, r["full_score"])
            r["delta_wk"] = round(r["full_score"] - prev_score, 1)
            prev_week_scores[t] = r["full_score"]
            
        with open(os.path.join("data", str(PREV_YEAR), f"week_{w}.json"), "w", encoding="utf-8") as f:
            json.dump(prev_data_w, f, indent=2)

    print(f"--- Writing Week Datasets for Current Season ({CUR_YEAR}) ---")
    os.makedirs(os.path.join("data", str(CUR_YEAR)), exist_ok=True)
    cur_games = get_year_games(CUR_YEAR)
    
    completed_weeks = sorted(list(set(g.get("week") for g in cur_games if g.get("completed") == True)))
    if not completed_weeks:
        completed_weeks = [1]
    
    max_completed_week = max(completed_weeks)
    print(f"Confirmed strictly completed weeks for {CUR_YEAR}: {completed_weeks}")

    manifest_cur_weeks = []
    latest_payload = None
    cur_week_scores = {}

    for w in completed_weeks:
        manifest_cur_weeks.append(w)
        cur_data_w, _ = run_season_pipeline(CUR_YEAR, fbs_teams, venue_stats, regressed_priors, prior_diagnostics, conf_base_4yr, max_week=w)
        
        for r in cur_data_w:
            t = r["team"]
            prev_score = cur_week_scores.get(t, r["full_score"])
            r["delta_wk"] = round(r["full_score"] - prev_score, 1)
            cur_week_scores[t] = r["full_score"]
            
        with open(os.path.join("data", str(CUR_YEAR), f"week_{w}.json"), "w", encoding="utf-8") as f:
            json.dump(cur_data_w, f, indent=2)
        if w == max_completed_week:
            latest_payload = cur_data_w

    if latest_payload:
        with open(os.path.join("data", "latest.json"), "w", encoding="utf-8") as f:
            json.dump(latest_payload, f, indent=2)

    manifest = {str(CUR_YEAR): manifest_cur_weeks, str(PREV_YEAR): prev_manifest_weeks}
    with open(os.path.join("data", "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    build_multiyear_index(CUR_YEAR, fbs_teams, venue_stats)
    print("Static build and JSON artifact generation complete.")

if __name__ == "__main__":
    main()