# PrizePicks +EV Finder - Complete Setup Guide

A Discord tool that automatically finds +EV (profitable) props on PrizePicks using the line comparison strategy.

## 📊 Strategy Overview

This tool implements the **line comparison strategy** from the video:

1. **Compare Lines**: Check PrizePicks props against sharp sportsbook (FanDuel)
2. **Calculate No-Vig**: Remove the vig to find true probabilities
3. **Filter +EV Plays**: Only bet props that beat the break-even threshold
4. **Optimal Slip Types**: Use the correct slip type based on probability

### Break-Even Thresholds

| Slip Type | Break-Even % | When to Use |
|-----------|-------------|-------------|
| 2 Power | 57.74% | Only for 58%+ plays |
| 3 Power | 58.48% | AVOID - bad value |
| 3 Flex | 59.80% | AVOID - bad value |
| 4 Power | 56.23% | Occasional use |
| 4 Flex | 56.89% | Occasional use |
| **5 Flex** | **54.34%** | **BEST for profit** |
| **6 Flex** | **54.34%** | **BEST for profit** |

### Key Rules

1. **Play close to game time** (1-2 hours before is optimal)
2. **Use 5/6 Man Flex** for best long-term profit
3. **Bet 0.25-0.5 units** per slip
4. **Stay away from 3-mans** - they have poor expected value
5. **Trust the process** - variance happens, but math wins long-term

---

## 🚀 Quick Setup (5 minutes)

### Step 1: Get API Key (Free)

1. Go to [The Odds API](https://the-odds-api.com/)
2. Sign up for free account
3. Copy your API key (500 requests/month free)

### Step 2: Create Discord Webhook

1. Open your Discord server
2. Go to Server Settings → Integrations → Webhooks
3. Click "New Webhook"
4. Name it "PrizePicks Scanner"
5. Select the channel for alerts
6. Copy the webhook URL

### Step 3: Upload to Your Server

Upload these files to your server (e.g., `/root/prizepicks/`):

```bash
mkdir -p /root/prizepicks
# Upload the Python files
```

### Step 4: Install Dependencies

```bash
pip install requests --break-system-packages
```

### Step 5: Set Environment Variables

```bash
# Add to ~/.bashrc or run directly
export ODDS_API_KEY="your_api_key_here"
export DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

### Step 6: Test It

```bash
cd /root/prizepicks
python3 daily_scanner.py --demo
```

---

## 🤖 Moltbot Cron Integration

### Option A: Tell Moltbot Directly

In Discord, message Moltbot:

```
Set up a cron job to run every 3 hours from 10am to 10pm daily.
The command should be: python3 /root/prizepicks/daily_scanner.py
This will scan for +EV PrizePicks plays and post them here.
```

### Option B: Manual Cron Setup

If Moltbot's cron is having issues, set up a system cron:

```bash
# Edit crontab
crontab -e

# Add these lines (adjust times for your timezone):
# Run at 10am, 1pm, 4pm, 7pm, 10pm daily
0 10,13,16,19,22 * * * cd /root/prizepicks && python3 daily_scanner.py >> /var/log/prizepicks.log 2>&1
```

### Option C: Create a Moltbot Skill

Create a custom Moltbot skill for on-demand scanning:

1. Create `/path/to/moltbot/skills/prizepicks.py`:

```python
"""
PrizePicks Scanner Skill for Moltbot
Usage: "scan prizepicks" or "find +ev plays"
"""

import subprocess
import os

def run():
    """Run the PrizePicks scanner."""
    result = subprocess.run(
        ['python3', '/root/prizepicks/daily_scanner.py'],
        capture_output=True,
        text=True,
        env={**os.environ, 
             'ODDS_API_KEY': 'your_key',
             'DISCORD_WEBHOOK_URL': 'your_webhook'}
    )
    return result.stdout

# Skill metadata
TRIGGERS = ['scan prizepicks', 'prizepicks', 'find ev', 'find +ev']
```

2. Tell Moltbot to load the skill

---

## 📱 Manual Mode (No API)

If you want to check individual props manually:

### Using the Script

```bash
python3 prizepicks_ev.py --manual -112 -118
```

Output:
```
NO-VIG CALCULATION
Over odds: -112
Under odds: -118

Fair Odds:
  Over:  48.6%  (EV: -2.8%)
  Under: 51.4%  (EV: +2.8%)

Favored: UNDER

Recommended Slip Types:
  ❌ Below all thresholds - SKIP this prop
```

### Using OddsJam Calculator

1. Go to [OddsJam No-Vig Calculator](https://oddsjam.com/no-vig-calculator)
2. Enter the over/under odds from FanDuel
3. Compare the fair probability to break-even thresholds:
   - **54.34%+** → Good for 5/6 Flex ✅
   - **56.23%+** → Good for 4+ ✅
   - **57.74%+** → Good for 2 Power ✅

---

## 🧮 How the Math Works

### No-Vig Calculation

When FanDuel shows:
- Over 17.5 points: **-112**
- Under 17.5 points: **-118**

Step 1: Convert to implied probability
```
Over:  112 / (112 + 100) = 52.83%
Under: 118 / (118 + 100) = 54.13%
Total: 106.96% (the extra 6.96% is the vig)
```

Step 2: Remove the vig
```
Over:  52.83 / 106.96 = 49.4%
Under: 54.13 / 106.96 = 50.6%
```

Step 3: Compare to threshold
```
Under at 50.6% < 54.34% threshold
Result: SKIP (not +EV for any slip type)
```

### Expected Value Formula

```
EV = (Win Probability × Payout) - (Loss Probability × Stake)

For PrizePicks (even money):
EV = (fair_prob × 1) - ((1 - fair_prob) × 1)
EV = 2 × fair_prob - 1
```

---

## 📈 Sample Output

When the scanner finds plays, it posts to Discord:

```
🎯 PrizePicks +EV Scanner

Found 5 +EV plays!

🔥 = Optimal window (< 2h until game)
━━━━━━━━━━━━━━━━━━━━━━

🏀 LeBron James OVER 25.5 points
   Lakers vs Celtics
   📊 56.5% fair odds | +13.0% EV
   ✅ 5/6 Flex | 🔥 1.5h

🏀 Nikola Jokic UNDER 12.5 rebounds
   Nuggets vs Thunder
   📊 58.3% fair odds | +16.6% EV
   ✅ 5/6 Flex | ⏰ 3.0h

━━━━━━━━━━━━━━━━━━━━━━
💰 Bankroll Management:
• 5-man flex: 0.25-0.5 units
• 3-man: 0.25-0.5 units
• AVOID 3-man power plays
```

---

## 🔧 Troubleshooting

### "No +EV plays found"

This is normal! Not every scan finds profitable plays. The best time to scan:
- 1-2 hours before game time
- When multiple games are about to start
- During heavy sports days (NBA nights, NFL Sundays)

### API Key Not Working

1. Check your key at [the-odds-api.com/account](https://the-odds-api.com/account)
2. Make sure you haven't exceeded 500 requests/month
3. Verify the environment variable is set: `echo $ODDS_API_KEY`

### Discord Not Posting

1. Test the webhook manually:
```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"content": "Test message"}' \
  YOUR_WEBHOOK_URL
```

2. Check the URL is correct
3. Make sure the webhook channel still exists

### Moltbot Cron Not Running

1. Check Moltbot logs: `docker logs moltbot-container --tail 50`
2. Verify the cron was created: Ask Moltbot "show cron jobs"
3. Fall back to system cron if needed

---

## 📚 Additional Resources

- [OddsJam No-Vig Calculator](https://oddsjam.com/no-vig-calculator)
- [The Odds API Documentation](https://the-odds-api.com/liveapi/guides/v4/)
- [PrizePicks Rules](https://support.prizepicks.com/)
- [Derek's Discord Guide](https://discord.gg/beatthesportsbooks)

---

## ⚠️ Disclaimer

This tool is for educational and entertainment purposes. Sports betting involves risk. Only bet what you can afford to lose. Past performance does not guarantee future results. Please gamble responsibly.

---

## 📝 Quick Reference Card

```
┌─────────────────────────────────────────────────┐
│           PRIZEPICKS +EV CHEAT SHEET            │
├─────────────────────────────────────────────────┤
│ BEST SLIP: 5/6 Man Flex (54.34% break-even)     │
│ AVOID: All 3-man slips                          │
│ BET SIZE: 0.25-0.5 units per slip               │
│ BEST TIME: 1-2 hours before game                │
├─────────────────────────────────────────────────┤
│ BREAK-EVEN THRESHOLDS:                          │
│   54.34% → 5/6 Flex ✅                          │
│   56.23% → 4 Power ✅                           │
│   57.74% → 2 Power ✅                           │
├─────────────────────────────────────────────────┤
│ QUICK COMMANDS:                                 │
│   python3 daily_scanner.py        # Auto scan   │
│   python3 prizepicks_ev.py --manual -112 -118   │
│                                   # Manual calc │
└─────────────────────────────────────────────────┘
```
