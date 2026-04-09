"""
Adaptive Position Sizing — v3
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Replaces fixed risk % with confidence-based, volatility-adjusted sizing.

Sizing logic (in order):
  1. Base risk determined by signal SCORE
     score 5     → 1.0% of capital
     score 6-7   → 1.5%
     score 8+    → 2.0%
  2. ATR multiplier (volatility adjustment)
     ATR > 1.5% of price → reduce by 30% (high vol = expensive + risky options)
     ATR < 0.5% of price → normal size
  3. Loss streak penalty
     2 consecutive losses → cut base risk by 50%
     (streak resets on win)
  4. Final quantity rounded to nearest lot size
  5. Hard cap: never risk > 2% regardless of anything

Returns: {quantity, risk_pct_applied, lot_size, confidence_label, sizing_notes}
"""

import math
from typing import Dict, Tuple
from loguru import logger
from config import settings


# ─── Confidence tiers ─────────────────────────────────────────────────────────

def _score_to_base_risk(score: int) -> Tuple[float, str]:
    """Map signal score to base risk % and confidence label."""
    if score >= 8:
        return settings.RISK_SCORE_HIGH, "HIGH"
    elif score >= 6:
        return settings.RISK_SCORE_MID, "MEDIUM"
    else:
        return settings.RISK_SCORE_LOW, "LOW"


# ─── ATR volatility multiplier ────────────────────────────────────────────────

def _atr_multiplier(atr_val: float, price: float) -> Tuple[float, str]:
    """
    High ATR = options are expensive and moves are unpredictable.
    Reduce size to compensate.
    """
    if price <= 0:
        return 1.0, "NORMAL_VOL"
    atr_pct = (atr_val / price) * 100
    if atr_pct > 1.5:
        return settings.RISK_HIGH_ATR_MULT, f"HIGH_VOL({atr_pct:.1f}%)"
    elif atr_pct > 1.0:
        return 0.85, f"ELEVATED_VOL({atr_pct:.1f}%)"
    return 1.0, f"NORMAL_VOL({atr_pct:.1f}%)"


# ─── Loss streak penalty ──────────────────────────────────────────────────────

def _streak_multiplier(consecutive_losses: int) -> Tuple[float, str]:
    """
    After a loss streak: reduce size to protect capital.
    Systematic size reduction prevents blowing up during bad runs.
    """
    if consecutive_losses >= 2:
        mult = settings.RISK_LOSS_STREAK_MULT  # 50% cut
        return mult, f"LOSS_STREAK({consecutive_losses}→-50%)"
    elif consecutive_losses == 1:
        return 0.75, "LOSS_STREAK(1→-25%)"
    return 1.0, "NO_STREAK"


# ─── Lot size helper ──────────────────────────────────────────────────────────

def _get_lot_size(symbol: str) -> int:
    s = symbol.upper()
    if "BANKNIFTY" in s:
        return settings.LOT_SIZE_BANKNIFTY
    elif "SENSEX" in s:
        return settings.LOT_SIZE_SENSEX
    return settings.LOT_SIZE_NIFTY


# ─── Main sizing function ─────────────────────────────────────────────────────

def calculate_adaptive_size(
    capital:             float,
    signal_score:        int,
    option_ltp:          float,
    sl_pct:              float,
    atr_val:             float,
    spot_price:          float,
    consecutive_losses:  int,
    symbol:              str = "NIFTY",
) -> Dict:
    """
    Calculate adaptive position size.

    Returns dict:
    {
        quantity:           int,
        lots:               int,
        lot_size:           int,
        risk_pct_applied:   float,
        risk_amount:        float,
        confidence:         str,
        sizing_notes:       list[str],
        base_risk:          float,
        atr_mult:           float,
        streak_mult:        float,
    }
    """
    notes = []

    # 1. Base risk from score
    base_risk, confidence = _score_to_base_risk(signal_score)
    notes.append(f"Score {signal_score} → base risk {base_risk}% ({confidence})")

    # 2. ATR volatility adjustment
    atr_mult, atr_note = _atr_multiplier(atr_val, spot_price)
    notes.append(f"ATR adj: ×{atr_mult:.2f} [{atr_note}]")

    # 3. Loss streak adjustment
    streak_mult, streak_note = _streak_multiplier(consecutive_losses)
    notes.append(f"Streak adj: ×{streak_mult:.2f} [{streak_note}]")

    # 4. Final risk %
    final_risk_pct = base_risk * atr_mult * streak_mult

    # Hard cap: never exceed 2% risk
    final_risk_pct = min(final_risk_pct, 2.0)
    # Floor: minimum 0.5% risk
    final_risk_pct = max(final_risk_pct, 0.5)
    notes.append(f"Final risk: {final_risk_pct:.2f}% of ₹{capital:,.0f}")

    # 5. Risk amount → quantity
    risk_amount  = capital * (final_risk_pct / 100)
    sl_per_unit  = option_ltp * (sl_pct / 100)

    if sl_per_unit <= 0:
        qty = 1
    else:
        qty = int(risk_amount / sl_per_unit)

    # 6. Round to lot size
    lot_size = _get_lot_size(symbol)
    lots     = max(1, qty // lot_size)
    quantity = lots * lot_size

    # Safety cap: max 200 units
    quantity = min(quantity, 200)
    lots     = quantity // lot_size

    actual_risk = sl_per_unit * quantity
    notes.append(f"Qty={quantity} ({lots} lots × {lot_size}) | Actual risk ₹{actual_risk:.0f}")

    logger.info(
        f"📐 Position size: {quantity} units ({lots} lots) | "
        f"Risk {final_risk_pct:.2f}% = ₹{risk_amount:.0f} | "
        f"Score={signal_score} Conf={confidence}"
    )

    return {
        "quantity":          quantity,
        "lots":              lots,
        "lot_size":          lot_size,
        "risk_pct_applied":  round(final_risk_pct, 3),
        "risk_amount":       round(risk_amount, 2),
        "confidence":        confidence,
        "sizing_notes":      notes,
        "base_risk":         base_risk,
        "atr_mult":          atr_mult,
        "streak_mult":       streak_mult,
    }
