#!/usr/bin/env python3
"""
Quick No-Vig Calculator
=======================
Standalone calculator for manual prop checking.

Usage:
    python3 quick_calc.py -112 -118
    python3 quick_calc.py +110 -140

This will tell you:
- The fair probability for each side
- Which direction is favored
- Which slip types are +EV
"""

import sys

# Break-even thresholds
THRESHOLDS = {
    '5/6 Flex': 0.5434,
    '4 Power': 0.5623,
    '4 Flex': 0.5689,
    '2 Power': 0.5774,
    '3 Power': 0.5848,
    '3 Flex': 0.5980,
}

def american_to_prob(odds: int) -> float:
    """Convert American odds to implied probability."""
    if odds > 0:
        return 100.0 / (odds + 100)
    return -odds / (-odds + 100)

def calc_no_vig(over: int, under: int):
    """Calculate and display no-vig odds."""
    over_impl = american_to_prob(over)
    under_impl = american_to_prob(under)
    total = over_impl + under_impl
    vig = (total - 1) * 100
    
    over_fair = over_impl / total
    under_fair = under_impl / total
    
    favored = 'OVER' if over_fair > under_fair else 'UNDER'
    best_prob = max(over_fair, under_fair)
    
    print("\n" + "="*50)
    print("🎯 NO-VIG CALCULATOR")
    print("="*50)
    print(f"\nInput Odds:")
    print(f"  Over:  {over:+d}")
    print(f"  Under: {under:+d}")
    print(f"  Vig:   {vig:.1f}%")
    
    print(f"\n📊 Fair Probabilities (no vig):")
    print(f"  Over:  {over_fair*100:.1f}%")
    print(f"  Under: {under_fair*100:.1f}%")
    
    print(f"\n⭐ Favored: {favored} ({best_prob*100:.1f}%)")
    
    print(f"\n✅ Recommended Slip Types:")
    found_any = False
    for slip, threshold in sorted(THRESHOLDS.items(), key=lambda x: x[1]):
        if best_prob >= threshold:
            ev = (2 * best_prob - 1) * 100
            print(f"   ✓ {slip} (min {threshold*100:.1f}%) → EV: +{ev:.1f}%")
            found_any = True
    
    if not found_any:
        print("   ❌ Below all thresholds - SKIP this prop")
    
    print("\n" + "="*50)
    
    return {
        'over_fair': over_fair,
        'under_fair': under_fair,
        'favored': favored,
        'best_prob': best_prob,
    }

if __name__ == '__main__':
    if len(sys.argv) != 3:
        print("Usage: python3 quick_calc.py <over_odds> <under_odds>")
        print("Example: python3 quick_calc.py -112 -118")
        print("Example: python3 quick_calc.py +110 -140")
        sys.exit(1)
    
    try:
        over = int(sys.argv[1])
        under = int(sys.argv[2])
        calc_no_vig(over, under)
    except ValueError:
        print("Error: Odds must be integers (e.g., -112, +110)")
        sys.exit(1)
