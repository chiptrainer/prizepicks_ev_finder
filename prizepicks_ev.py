#!/usr/bin/env python3
"""
PrizePicks +EV Finder
=====================
Finds profitable props by comparing PrizePicks lines to sharp sportsbooks (FanDuel).
Uses line comparison strategy to identify +EV plays.

Strategy based on:
- Line comparison to sharp books (FanDuel)
- No-vig calculation to find true odds
- Break-even threshold filtering by slip type

Author: Built for Nolan's Discord betting tool
"""

import os
import json
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import math

# =============================================================================
# CONFIGURATION
# =============================================================================

class Config:
    """Configuration settings - modify these for your setup"""
    
    # The Odds API key (get free key at https://the-odds-api.com/)
    ODDS_API_KEY = os.environ.get('ODDS_API_KEY', 'YOUR_API_KEY_HERE')
    
    # Discord webhook URL for sending alerts
    DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL', '')
    
    # Sports to scan (The Odds API sport keys)
    # Reference: https://the-odds-api.com/sports-odds-data/sports-apis.html
    SPORTS = [
        'basketball_nba',
        'basketball_ncaab',
        'americanfootball_nfl',
        'americanfootball_ncaaf',
        'baseball_mlb',
        'icehockey_nhl',
        'soccer_epl',
        'tennis_atp_french_open',
    ]
    
    # Markets to check (player props)
    MARKETS = [
        'player_points',
        'player_rebounds', 
        'player_assists',
        'player_threes',
        'player_blocks',
        'player_steals',
        'player_points_rebounds_assists',
        'player_points_rebounds',
        'player_points_assists',
        'player_rebounds_assists',
        'pitcher_strikeouts',
        'batter_hits',
        'batter_total_bases',
        'batter_rbis',
        'batter_runs',
        'player_shots_on_goal',
        'player_goals',
    ]
    
    # Minimum EV% to consider a play (0.05 = 5% edge)
    MIN_EV_PERCENT = 0.02
    
    # Time window - only show games starting within X hours
    MAX_HOURS_UNTIL_GAME = 12
    
    # Optimal betting window - prioritize games within X hours (1-2 hours ideal)
    OPTIMAL_HOURS = 2

# =============================================================================
# BREAK-EVEN THRESHOLDS (from PrizePicks analysis)
# =============================================================================

class SlipType(Enum):
    """PrizePicks slip types with break-even thresholds"""
    POWER_2 = ("2 Power", 0.5774, 2.0)
    POWER_3 = ("3 Power", 0.5848, 3.0)
    FLEX_3 = ("3 Flex", 0.5980, 2.25)
    POWER_4 = ("4 Power", 0.5623, 5.0)
    FLEX_4 = ("4 Flex", 0.5689, 3.0)
    FLEX_5 = ("5 Flex", 0.5434, 5.0)  # Most profitable long-term
    FLEX_6 = ("6 Flex", 0.5434, 10.0)  # Most profitable long-term
    
    def __init__(self, display_name: str, break_even: float, payout_multiplier: float):
        self.display_name = display_name
        self.break_even = break_even
        self.payout_multiplier = payout_multiplier

# Break-even lookup table
BREAK_EVEN_TABLE = {
    '2_power': 0.5774,
    '3_power': 0.5848,
    '3_flex': 0.5980,
    '4_power': 0.5623,
    '4_flex': 0.5689,
    '5_flex': 0.5434,
    '6_flex': 0.5434,
}

# =============================================================================
# DATA STRUCTURES
# =============================================================================

@dataclass
class PropBet:
    """Represents a player prop bet"""
    player_name: str
    team: str
    opponent: str
    sport: str
    market: str  # e.g., 'points', 'rebounds'
    line: float  # e.g., 17.5
    over_odds: int  # American odds, e.g., -110
    under_odds: int  # American odds, e.g., -118
    game_time: datetime
    sportsbook: str
    
@dataclass
class EVPlay:
    """Represents a +EV play to bet"""
    player_name: str
    team: str
    opponent: str
    sport: str
    market: str
    line: float
    direction: str  # 'over' or 'under'
    fair_odds_pct: float  # True probability (0-1)
    ev_percent: float  # Expected value percentage
    recommended_slips: List[str]  # Which slip types are +EV
    game_time: datetime
    hours_until_game: float
    
# =============================================================================
# NO-VIG CALCULATOR (Core Math)
# =============================================================================

class NoVigCalculator:
    """
    Calculates fair odds by removing the vig (juice) from sportsbook lines.
    
    The vig is the sportsbook's commission built into the odds. By removing it,
    we get the "true" probability of each outcome.
    
    Example:
        Over: -112, Under: -118
        After removing vig: Over = 47.2%, Under = 52.8%
    """
    
    @staticmethod
    def american_to_implied_prob(american_odds: int) -> float:
        """
        Convert American odds to implied probability.
        
        Positive odds (underdog): prob = 100 / (odds + 100)
        Negative odds (favorite): prob = -odds / (-odds + 100)
        """
        if american_odds > 0:
            return 100.0 / (american_odds + 100)
        else:
            return -american_odds / (-american_odds + 100)
    
    @staticmethod
    def implied_prob_to_american(prob: float) -> int:
        """Convert probability back to American odds."""
        if prob <= 0 or prob >= 1:
            return 0
        if prob >= 0.5:
            return int(-100 * prob / (1 - prob))
        else:
            return int(100 * (1 - prob) / prob)
    
    @staticmethod
    def calculate_no_vig(over_odds: int, under_odds: int) -> Tuple[float, float]:
        """
        Calculate the no-vig (fair) probabilities for over/under.
        
        This is the core of the strategy - we use FanDuel's sharp lines
        to determine the TRUE probability of each outcome.
        
        Args:
            over_odds: American odds for over
            under_odds: American odds for under
            
        Returns:
            Tuple of (over_fair_prob, under_fair_prob)
        """
        over_implied = NoVigCalculator.american_to_implied_prob(over_odds)
        under_implied = NoVigCalculator.american_to_implied_prob(under_odds)
        
        # Total implied probability (includes vig)
        total_implied = over_implied + under_implied
        
        # Remove vig by normalizing
        over_fair = over_implied / total_implied
        under_fair = under_implied / total_implied
        
        return over_fair, under_fair
    
    @staticmethod
    def calculate_ev(fair_prob: float, prizepicks_payout: float = 1.0) -> float:
        """
        Calculate expected value percentage.
        
        PrizePicks pays even money (1:1) for each leg, so:
        EV = (fair_prob * 1) - ((1 - fair_prob) * 1) = 2*fair_prob - 1
        
        For a 5-flex, the compounded EV is what matters.
        """
        return (2 * fair_prob) - 1

# =============================================================================
# ODDS API CLIENT
# =============================================================================

class OddsAPIClient:
    """
    Client for The Odds API to fetch sportsbook odds.
    
    Free tier: 500 requests/month
    Get API key: https://the-odds-api.com/
    """
    
    BASE_URL = "https://api.the-odds-api.com/v4"
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.requests_remaining = None
        
    def get_player_props(self, sport: str, markets: List[str]) -> List[PropBet]:
        """
        Fetch player props for a sport from The Odds API.
        
        Args:
            sport: Sport key (e.g., 'basketball_nba')
            markets: List of market types (e.g., ['player_points', 'player_rebounds'])
            
        Returns:
            List of PropBet objects
        """
        props = []
        
        # First get list of games
        games_url = f"{self.BASE_URL}/sports/{sport}/odds"
        params = {
            'apiKey': self.api_key,
            'regions': 'us',
            'markets': 'h2h',  # Just to get game list
            'oddsFormat': 'american',
            'bookmakers': 'fanduel',
        }
        
        try:
            response = requests.get(games_url, params=params, timeout=30)
            self.requests_remaining = response.headers.get('x-requests-remaining')
            
            if response.status_code != 200:
                print(f"Error fetching games for {sport}: {response.status_code}")
                return props
                
            games = response.json()
            
            # For each game, get player props
            for game in games:
                game_id = game.get('id')
                if not game_id:
                    continue
                    
                game_time = datetime.fromisoformat(game.get('commence_time', '').replace('Z', '+00:00'))
                home_team = game.get('home_team', '')
                away_team = game.get('away_team', '')
                
                # Skip games too far in the future
                hours_until = (game_time - datetime.now(game_time.tzinfo)).total_seconds() / 3600
                if hours_until > Config.MAX_HOURS_UNTIL_GAME or hours_until < 0:
                    continue
                
                # Fetch props for this game
                for market in markets:
                    props_url = f"{self.BASE_URL}/sports/{sport}/events/{game_id}/odds"
                    props_params = {
                        'apiKey': self.api_key,
                        'regions': 'us',
                        'markets': market,
                        'oddsFormat': 'american',
                        'bookmakers': 'fanduel',
                    }
                    
                    try:
                        props_response = requests.get(props_url, params=props_params, timeout=30)
                        if props_response.status_code != 200:
                            continue
                            
                        props_data = props_response.json()
                        
                        # Parse the props
                        for book in props_data.get('bookmakers', []):
                            if book.get('key') != 'fanduel':
                                continue
                                
                            for mkt in book.get('markets', []):
                                outcomes = mkt.get('outcomes', [])
                                
                                # Group by player/line
                                player_lines = {}
                                for outcome in outcomes:
                                    player = outcome.get('description', '')
                                    line = outcome.get('point', 0)
                                    direction = outcome.get('name', '').lower()
                                    odds = outcome.get('price', 0)
                                    
                                    key = f"{player}_{line}"
                                    if key not in player_lines:
                                        player_lines[key] = {'player': player, 'line': line}
                                    
                                    if direction == 'over':
                                        player_lines[key]['over_odds'] = odds
                                    elif direction == 'under':
                                        player_lines[key]['under_odds'] = odds
                                
                                # Create PropBet objects
                                for key, data in player_lines.items():
                                    if 'over_odds' in data and 'under_odds' in data:
                                        props.append(PropBet(
                                            player_name=data['player'],
                                            team=home_team,  # We'd need more logic for correct team
                                            opponent=away_team,
                                            sport=sport,
                                            market=market.replace('player_', ''),
                                            line=data['line'],
                                            over_odds=data['over_odds'],
                                            under_odds=data['under_odds'],
                                            game_time=game_time,
                                            sportsbook='fanduel'
                                        ))
                                        
                    except Exception as e:
                        print(f"Error fetching props for {market}: {e}")
                        continue
                        
        except Exception as e:
            print(f"Error in get_player_props: {e}")
            
        return props

# =============================================================================
# EV ANALYZER
# =============================================================================

class EVAnalyzer:
    """
    Analyzes props to find +EV plays.
    
    Strategy:
    1. Get FanDuel lines (sharp book)
    2. Calculate no-vig fair odds
    3. Compare to PrizePicks break-even thresholds
    4. Return plays that beat the threshold
    """
    
    def __init__(self, min_ev: float = Config.MIN_EV_PERCENT):
        self.min_ev = min_ev
        self.calculator = NoVigCalculator()
        
    def analyze_prop(self, prop: PropBet) -> Optional[EVPlay]:
        """
        Analyze a single prop for +EV.
        
        Args:
            prop: PropBet to analyze
            
        Returns:
            EVPlay if +EV, None otherwise
        """
        # Calculate fair odds
        over_fair, under_fair = self.calculator.calculate_no_vig(
            prop.over_odds, 
            prop.under_odds
        )
        
        # Determine which direction is favored
        if over_fair > under_fair:
            direction = 'over'
            fair_prob = over_fair
        else:
            direction = 'under'
            fair_prob = under_fair
            
        # Calculate EV
        ev_percent = self.calculator.calculate_ev(fair_prob)
        
        # Find which slip types are +EV
        recommended_slips = []
        for slip_name, break_even in BREAK_EVEN_TABLE.items():
            if fair_prob >= break_even:
                recommended_slips.append(slip_name)
                
        # Only return if we beat minimum EV threshold
        if ev_percent < self.min_ev:
            return None
            
        # Calculate hours until game
        now = datetime.now(prop.game_time.tzinfo) if prop.game_time.tzinfo else datetime.now()
        hours_until = (prop.game_time - now).total_seconds() / 3600
        
        return EVPlay(
            player_name=prop.player_name,
            team=prop.team,
            opponent=prop.opponent,
            sport=prop.sport,
            market=prop.market,
            line=prop.line,
            direction=direction,
            fair_odds_pct=fair_prob,
            ev_percent=ev_percent,
            recommended_slips=recommended_slips,
            game_time=prop.game_time,
            hours_until_game=hours_until
        )
    
    def find_ev_plays(self, props: List[PropBet]) -> List[EVPlay]:
        """
        Find all +EV plays from a list of props.
        
        Returns plays sorted by:
        1. Hours until game (prefer games starting soon)
        2. EV percentage (higher is better)
        """
        plays = []
        
        for prop in props:
            play = self.analyze_prop(prop)
            if play and play.recommended_slips:  # Must beat at least one threshold
                plays.append(play)
                
        # Sort by hours until game (ascending), then by EV (descending)
        plays.sort(key=lambda x: (x.hours_until_game, -x.ev_percent))
        
        return plays

# =============================================================================
# DISCORD FORMATTER
# =============================================================================

class DiscordFormatter:
    """Formats +EV plays for Discord posting."""
    
    @staticmethod
    def format_play(play: EVPlay) -> str:
        """Format a single play for Discord."""
        # Emoji based on sport
        sport_emojis = {
            'basketball_nba': '🏀',
            'basketball_ncaab': '🏀',
            'americanfootball_nfl': '🏈',
            'americanfootball_ncaaf': '🏈',
            'baseball_mlb': '⚾',
            'icehockey_nhl': '🏒',
            'soccer_epl': '⚽',
            'tennis': '🎾',
        }
        emoji = sport_emojis.get(play.sport, '🎯')
        
        # Format slips recommendation
        if '5_flex' in play.recommended_slips or '6_flex' in play.recommended_slips:
            slip_rec = "✅ 5/6 Flex"
        elif '4_flex' in play.recommended_slips:
            slip_rec = "✅ 4+ Flex"
        elif '2_power' in play.recommended_slips:
            slip_rec = "⚠️ 2-Man Power only"
        else:
            slip_rec = "❌ Below threshold"
            
        # Time indicator
        if play.hours_until_game <= 2:
            time_emoji = "🔥"  # Optimal betting window
        elif play.hours_until_game <= 6:
            time_emoji = "⏰"
        else:
            time_emoji = "📅"
            
        return (
            f"{emoji} **{play.player_name}** {play.direction.upper()} {play.line} {play.market}\n"
            f"   {play.team} vs {play.opponent}\n"
            f"   📊 Fair Odds: **{play.fair_odds_pct*100:.1f}%** | EV: **+{play.ev_percent*100:.1f}%**\n"
            f"   {slip_rec}\n"
            f"   {time_emoji} Starts in {play.hours_until_game:.1f}h"
        )
    
    @staticmethod
    def format_report(plays: List[EVPlay]) -> Dict:
        """
        Format a full report as Discord embed.
        
        Returns dict ready for Discord webhook.
        """
        if not plays:
            return {
                "embeds": [{
                    "title": "🎯 PrizePicks +EV Scanner",
                    "description": "No +EV plays found at this time.\n\nCheck back closer to game time (1-2 hours before tip-off is optimal).",
                    "color": 0x808080,  # Gray
                    "timestamp": datetime.utcnow().isoformat()
                }]
            }
        
        # Group by optimal vs regular
        optimal_plays = [p for p in plays if p.hours_until_game <= Config.OPTIMAL_HOURS]
        regular_plays = [p for p in plays if p.hours_until_game > Config.OPTIMAL_HOURS]
        
        description_parts = []
        
        # Header
        description_parts.append(
            f"Found **{len(plays)}** +EV plays\n"
            f"🔥 = Optimal window (1-2h before game)\n"
            f"━━━━━━━━━━━━━━━━━━━━━━"
        )
        
        # Optimal plays first
        if optimal_plays:
            description_parts.append("\n**🔥 PLAY NOW - Optimal Window:**")
            for play in optimal_plays[:10]:  # Limit to top 10
                description_parts.append(DiscordFormatter.format_play(play))
                
        # Regular plays
        if regular_plays:
            description_parts.append("\n**⏰ UPCOMING:**")
            for play in regular_plays[:10]:  # Limit to top 10
                description_parts.append(DiscordFormatter.format_play(play))
        
        # Footer
        description_parts.append(
            "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            "💡 **Strategy:**\n"
            "• Use 5/6 Man Flex for best long-term profit\n"
            "• Bet 0.25-0.5 units per slip\n"
            "• Bet closer to game time for best accuracy"
        )
        
        return {
            "embeds": [{
                "title": "🎯 PrizePicks +EV Scanner",
                "description": "\n".join(description_parts),
                "color": 0x00FF00 if optimal_plays else 0xFFFF00,  # Green if optimal plays exist
                "timestamp": datetime.utcnow().isoformat(),
                "footer": {
                    "text": "Line Comparison Strategy | Data from FanDuel"
                }
            }]
        }

# =============================================================================
# DISCORD POSTER
# =============================================================================

class DiscordPoster:
    """Posts to Discord via webhook."""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        
    def post(self, payload: Dict) -> bool:
        """
        Post to Discord webhook.
        
        Args:
            payload: Discord message payload (with embeds)
            
        Returns:
            True if successful
        """
        if not self.webhook_url:
            print("No Discord webhook URL configured")
            return False
            
        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=30
            )
            
            if response.status_code in [200, 204]:
                print("Successfully posted to Discord")
                return True
            else:
                print(f"Discord post failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            print(f"Error posting to Discord: {e}")
            return False

# =============================================================================
# MANUAL INPUT MODE (No API needed)
# =============================================================================

def manual_ev_check(over_odds: int, under_odds: int) -> Dict:
    """
    Calculate EV for manually entered odds.
    
    Use this with the OddsJam No-Vig Calculator website.
    
    Example:
        result = manual_ev_check(-112, -118)
        print(f"Over: {result['over_pct']:.1%}, Under: {result['under_pct']:.1%}")
    """
    calc = NoVigCalculator()
    over_fair, under_fair = calc.calculate_no_vig(over_odds, under_odds)
    
    # Determine recommendations
    recommendations = {
        'over': [],
        'under': []
    }
    
    for slip_name, break_even in BREAK_EVEN_TABLE.items():
        if over_fair >= break_even:
            recommendations['over'].append(slip_name)
        if under_fair >= break_even:
            recommendations['under'].append(slip_name)
    
    return {
        'over_pct': over_fair,
        'under_pct': under_fair,
        'over_ev': calc.calculate_ev(over_fair),
        'under_ev': calc.calculate_ev(under_fair),
        'favored': 'over' if over_fair > under_fair else 'under',
        'over_recommendations': recommendations['over'],
        'under_recommendations': recommendations['under'],
    }

# =============================================================================
# MAIN SCANNER
# =============================================================================

class PrizePicksScanner:
    """Main scanner that orchestrates the whole process."""
    
    def __init__(self, api_key: str = None, webhook_url: str = None):
        self.api_key = api_key or Config.ODDS_API_KEY
        self.webhook_url = webhook_url or Config.DISCORD_WEBHOOK_URL
        self.client = OddsAPIClient(self.api_key) if self.api_key != 'YOUR_API_KEY_HERE' else None
        self.analyzer = EVAnalyzer()
        self.formatter = DiscordFormatter()
        self.poster = DiscordPoster(self.webhook_url) if self.webhook_url else None
        
    def scan_and_post(self, sports: List[str] = None, markets: List[str] = None) -> List[EVPlay]:
        """
        Scan for +EV plays and post to Discord.
        
        Args:
            sports: List of sports to scan (defaults to Config.SPORTS)
            markets: List of markets to check (defaults to Config.MARKETS)
            
        Returns:
            List of EVPlay objects found
        """
        sports = sports or Config.SPORTS
        markets = markets or Config.MARKETS
        
        print(f"🔍 Scanning {len(sports)} sports for +EV plays...")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        
        all_props = []
        
        if self.client:
            for sport in sports:
                print(f"   Checking {sport}...")
                props = self.client.get_player_props(sport, markets)
                all_props.extend(props)
                print(f"      Found {len(props)} props")
        else:
            print("⚠️  No API key configured. Use manual_ev_check() instead.")
            return []
        
        print(f"\n📊 Analyzing {len(all_props)} props...")
        ev_plays = self.analyzer.find_ev_plays(all_props)
        print(f"   Found {len(ev_plays)} +EV plays")
        
        # Format and post
        report = self.formatter.format_report(ev_plays)
        
        if self.poster:
            print("\n📤 Posting to Discord...")
            self.poster.post(report)
        else:
            # Print to console if no webhook
            print("\n" + "="*50)
            print("PRIZEPICKS +EV PLAYS")
            print("="*50)
            for play in ev_plays:
                print(self.formatter.format_play(play))
                print("-"*40)
                
        return ev_plays

# =============================================================================
# CLI ENTRY POINT
# =============================================================================

def main():
    """Main entry point for CLI usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description='PrizePicks +EV Finder')
    parser.add_argument('--api-key', help='The Odds API key')
    parser.add_argument('--webhook', help='Discord webhook URL')
    parser.add_argument('--manual', nargs=2, type=int, metavar=('OVER', 'UNDER'),
                       help='Manual check: provide over and under odds')
    parser.add_argument('--sport', help='Single sport to scan')
    
    args = parser.parse_args()
    
    # Manual mode
    if args.manual:
        over_odds, under_odds = args.manual
        result = manual_ev_check(over_odds, under_odds)
        
        print(f"\n{'='*50}")
        print(f"NO-VIG CALCULATION")
        print(f"{'='*50}")
        print(f"Over odds: {over_odds:+d}")
        print(f"Under odds: {under_odds:+d}")
        print(f"\nFair Odds:")
        print(f"  Over:  {result['over_pct']*100:.1f}%  (EV: {result['over_ev']*100:+.1f}%)")
        print(f"  Under: {result['under_pct']*100:.1f}%  (EV: {result['under_ev']*100:+.1f}%)")
        print(f"\nFavored: {result['favored'].upper()}")
        print(f"\nRecommended Slip Types:")
        if result[f"{result['favored']}_recommendations"]:
            for slip in result[f"{result['favored']}_recommendations"]:
                print(f"  ✅ {slip}")
        else:
            print("  ❌ Below all thresholds - SKIP this prop")
        return
    
    # Scanner mode
    api_key = args.api_key or os.environ.get('ODDS_API_KEY')
    webhook = args.webhook or os.environ.get('DISCORD_WEBHOOK_URL')
    
    scanner = PrizePicksScanner(api_key, webhook)
    
    if args.sport:
        scanner.scan_and_post(sports=[args.sport])
    else:
        scanner.scan_and_post()

if __name__ == '__main__':
    main()
