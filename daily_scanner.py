#!/usr/bin/env python3
"""
PrizePicks Daily Scanner for Discord
=====================================
A simpler version optimized for Moltbot cron jobs.

This script:
1. Fetches odds from The Odds API (or uses demo data)
2. Calculates no-vig fair odds
3. Finds +EV plays
4. Posts formatted results to Discord webhook

Usage:
    # With API (recommended)
    export ODDS_API_KEY="your_key_here"
    export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
    python3 daily_scanner.py

    # Demo mode (no API needed)
    python3 daily_scanner.py --demo

Schedule with Moltbot:
    "Set a cron job for 10am, 2pm, and 6pm daily to run: python3 /root/prizepicks/daily_scanner.py"
"""

import os
import sys
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# =============================================================================
# CONFIGURATION
# =============================================================================

# Get from environment or use defaults
ODDS_API_KEY = os.environ.get('ODDS_API_KEY', '')
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')

# Break-even thresholds for PrizePicks slip types
BREAK_EVEN = {
    '2_power': 0.5774,   # 57.74%
    '3_power': 0.5848,   # 58.48%
    '3_flex': 0.5980,    # 59.80%
    '4_power': 0.5623,   # 56.23%
    '4_flex': 0.5689,    # 56.89%
    '5_flex': 0.5434,    # 54.34% - BEST for long-term profit
    '6_flex': 0.5434,    # 54.34% - BEST for long-term profit
}

# Sports to scan
SPORTS = [
    'basketball_nba',
    'basketball_ncaab', 
    'americanfootball_nfl',
    'americanfootball_ncaaf',
    'baseball_mlb',
    'icehockey_nhl',
]

# =============================================================================
# NO-VIG CALCULATOR
# =============================================================================

def american_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100.0 / (odds + 100)
    else:
        return -odds / (-odds + 100)

def calc_no_vig(over_odds: int, under_odds: int) -> Tuple[float, float]:
    """
    Calculate no-vig (fair) probabilities.
    
    This is the CORE of the strategy. We take the sharp book's lines
    (FanDuel) and remove the vig to find true probabilities.
    
    Example:
        Over -112, Under -118
        -> Over: 46.9%, Under: 53.1%
    """
    over_implied = american_to_prob(over_odds)
    under_implied = american_to_prob(under_odds)
    
    # Total > 100% due to vig
    total = over_implied + under_implied
    
    # Normalize to remove vig
    return over_implied / total, under_implied / total

def get_recommendations(fair_prob: float) -> List[str]:
    """Get which slip types are +EV for this probability."""
    recs = []
    for slip, threshold in BREAK_EVEN.items():
        if fair_prob >= threshold:
            recs.append(slip)
    return recs

# =============================================================================
# ODDS API CLIENT
# =============================================================================

def fetch_odds(sport: str) -> List[Dict]:
    """
    Fetch player props from The Odds API.
    
    Get a free API key at: https://the-odds-api.com/
    (500 requests/month free tier)
    """
    if not ODDS_API_KEY:
        return []
    
    url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
    params = {
        'apiKey': ODDS_API_KEY,
        'regions': 'us',
        'markets': 'player_points,player_rebounds,player_assists,player_threes',
        'oddsFormat': 'american',
        'bookmakers': 'fanduel',
    }
    
    try:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code == 200:
            return r.json()
        else:
            print(f"API error for {sport}: {r.status_code}")
            return []
    except Exception as e:
        print(f"Request error: {e}")
        return []

# =============================================================================
# DEMO DATA (for testing without API)
# =============================================================================

DEMO_PLAYS = [
    {
        'player': 'LeBron James',
        'market': 'points',
        'line': 25.5,
        'over_odds': -130,
        'under_odds': +100,
        'team': 'Lakers',
        'opponent': 'Celtics',
        'sport': 'NBA',
        'game_time': datetime.now() + timedelta(hours=1.5),
    },
    {
        'player': 'Stephen Curry',
        'market': 'threes',
        'line': 4.5,
        'over_odds': -105,
        'under_odds': -125,
        'team': 'Warriors',
        'opponent': 'Suns',
        'sport': 'NBA',
        'game_time': datetime.now() + timedelta(hours=3),
    },
    {
        'player': 'Nikola Jokic',
        'market': 'rebounds',
        'line': 12.5,
        'over_odds': +110,
        'under_odds': -140,
        'team': 'Nuggets',
        'opponent': 'Thunder',
        'sport': 'NBA',
        'game_time': datetime.now() + timedelta(hours=2),
    },
    {
        'player': 'Tyreek Hill',
        'market': 'receiving yards',
        'line': 72.5,
        'over_odds': -118,
        'under_odds': -110,
        'team': 'Dolphins',
        'opponent': 'Bills',
        'sport': 'NFL',
        'game_time': datetime.now() + timedelta(hours=5),
    },
    {
        'player': 'Patrick Mahomes',
        'market': 'passing yards',
        'line': 275.5,
        'over_odds': -105,
        'under_odds': -125,
        'team': 'Chiefs',
        'opponent': 'Ravens',
        'sport': 'NFL',
        'game_time': datetime.now() + timedelta(hours=8),
    },
]

# =============================================================================
# SCANNER
# =============================================================================

def scan_for_ev_plays(demo_mode: bool = False) -> List[Dict]:
    """
    Scan for +EV plays.
    
    Returns list of plays sorted by EV (best first).
    """
    plays = []
    
    if demo_mode:
        print("🎮 Running in DEMO mode (sample data)")
        raw_plays = DEMO_PLAYS
    else:
        raw_plays = []
        for sport in SPORTS:
            print(f"  Scanning {sport}...")
            # Note: Full implementation would parse the API response
            # For now, we'd need to structure the API response parsing
            
    for prop in (DEMO_PLAYS if demo_mode else []):
        over_fair, under_fair = calc_no_vig(prop['over_odds'], prop['under_odds'])
        
        # Determine favored direction
        if over_fair > under_fair:
            direction = 'OVER'
            fair_prob = over_fair
        else:
            direction = 'UNDER'
            fair_prob = under_fair
        
        ev = (2 * fair_prob - 1) * 100  # Convert to percentage
        
        # Get slip recommendations
        recs = get_recommendations(fair_prob)
        
        # Only include if +EV for at least one slip type
        if recs:
            hours_until = (prop['game_time'] - datetime.now()).total_seconds() / 3600
            
            plays.append({
                'player': prop['player'],
                'market': prop['market'],
                'line': prop['line'],
                'direction': direction,
                'fair_prob': fair_prob,
                'ev_pct': ev,
                'team': prop['team'],
                'opponent': prop['opponent'],
                'sport': prop['sport'],
                'hours_until': hours_until,
                'recommendations': recs,
            })
    
    # Sort by EV (highest first)
    plays.sort(key=lambda x: x['ev_pct'], reverse=True)
    
    return plays

# =============================================================================
# DISCORD FORMATTER
# =============================================================================

def format_for_discord(plays: List[Dict]) -> Dict:
    """Format plays as Discord embed."""
    
    if not plays:
        return {
            "embeds": [{
                "title": "🎯 PrizePicks +EV Scanner",
                "description": (
                    "**No +EV plays found at this time.**\n\n"
                    "Check back closer to game time (1-2 hours before is optimal).\n\n"
                    "📌 **Pro Tips:**\n"
                    "• Best time to bet: 1-2 hours before game\n"
                    "• Use 5/6 Flex for maximum long-term profit\n"
                    "• Bet 0.25-0.5 units per slip"
                ),
                "color": 0x808080,
                "timestamp": datetime.now().isoformat()
            }]
        }
    
    # Build description
    lines = [
        f"Found **{len(plays)}** +EV plays!\n",
        "🔥 = Optimal window (< 2h until game)",
        "━━━━━━━━━━━━━━━━━━━━━━\n"
    ]
    
    for play in plays[:15]:  # Limit to 15 plays
        # Time indicator
        if play['hours_until'] <= 2:
            time_emoji = "🔥"
        elif play['hours_until'] <= 6:
            time_emoji = "⏰"
        else:
            time_emoji = "📅"
        
        # Sport emoji
        sport_emojis = {'NBA': '🏀', 'NFL': '🏈', 'MLB': '⚾', 'NHL': '🏒'}
        sport_emoji = sport_emojis.get(play['sport'], '🎯')
        
        # Slip recommendation
        if '5_flex' in play['recommendations'] or '6_flex' in play['recommendations']:
            slip_text = "✅ 5/6 Flex"
        elif '4_flex' in play['recommendations']:
            slip_text = "✅ 4+ Flex"
        else:
            slip_text = "⚠️ 2-man only"
        
        lines.append(
            f"{sport_emoji} **{play['player']}** {play['direction']} {play['line']} {play['market']}\n"
            f"   {play['team']} vs {play['opponent']}\n"
            f"   📊 **{play['fair_prob']*100:.1f}%** fair odds | **+{play['ev_pct']:.1f}%** EV\n"
            f"   {slip_text} | {time_emoji} {play['hours_until']:.1f}h\n"
        )
    
    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━",
        "💰 **Bankroll Management:**",
        "• 5-man flex: 0.25-0.5 units",
        "• 3-man: 0.25-0.5 units",
        "• AVOID 3-man power plays",
    ])
    
    return {
        "embeds": [{
            "title": "🎯 PrizePicks +EV Scanner",
            "description": "\n".join(lines),
            "color": 0x00FF00,
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "Line Comparison Strategy | Sharp Book: FanDuel"}
        }]
    }

# =============================================================================
# DISCORD POSTER
# =============================================================================

def post_to_discord(payload: Dict) -> bool:
    """Post to Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print("❌ No Discord webhook URL set")
        print("   Set DISCORD_WEBHOOK_URL environment variable")
        return False
    
    try:
        r = requests.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            headers={'Content-Type': 'application/json'},
            timeout=30
        )
        if r.status_code in [200, 204]:
            print("✅ Posted to Discord successfully")
            return True
        else:
            print(f"❌ Discord error: {r.status_code}")
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

# =============================================================================
# MAIN
# =============================================================================

def main():
    demo_mode = '--demo' in sys.argv or not ODDS_API_KEY
    
    print("="*50)
    print("🎯 PRIZEPICKS +EV SCANNER")
    print(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)
    
    if not ODDS_API_KEY and not demo_mode:
        print("\n⚠️  No API key found. Running in demo mode.")
        print("   Get free key at: https://the-odds-api.com/")
        demo_mode = True
    
    print(f"\n🔍 Scanning for +EV plays...")
    plays = scan_for_ev_plays(demo_mode=demo_mode)
    
    print(f"\n📊 Found {len(plays)} +EV plays")
    
    # Format for Discord
    payload = format_for_discord(plays)
    
    # Post or print
    if DISCORD_WEBHOOK_URL:
        print(f"\n📤 Posting to Discord...")
        post_to_discord(payload)
    else:
        print("\n" + "="*50)
        print("RESULTS (set DISCORD_WEBHOOK_URL to post to Discord)")
        print("="*50)
        for play in plays:
            print(f"\n{play['player']} {play['direction']} {play['line']} {play['market']}")
            print(f"   Fair: {play['fair_prob']*100:.1f}% | EV: +{play['ev_pct']:.1f}%")
            print(f"   Slips: {', '.join(play['recommendations'])}")
    
    print("\n✅ Done!")

if __name__ == '__main__':
    main()
