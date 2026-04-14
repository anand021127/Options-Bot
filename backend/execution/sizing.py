"""
Adaptive Position Sizing — v3.1 (Zero-Assumption)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
STRICT RULE: lot_size MUST come from the option object (Upstox API).
             It is NEVER read from config or hardcoded.

Caller (bot_engine._enter_trade) passes:
    lot_size_from_api = option["lot_size"]   ← integer from Upstox instruments

If lot_size_from_api is None or 0 → sizing returns None → trade is blocked.

Sizing steps:
  1. Base risk% from signal score  (configurable in DB)
  2. ATR multiplier                (high vol → smaller size)
  3. Loss-streak penalty           (2+ losses → 50% cut)
  4. Risk amount → raw quantity
  5. Round to actual lot_size from API
  6. Hard cap at 2% and 200 units
"""

from typing import Dict, Optional, Tuple
from loguru import logger
from config import settings


# ─── Risk tiers by score ──────────────────────────────────────────────────────

def _score_to_base_risk(score: int) -> Tuple[float, str]:
    if score >= 8:
        return settings.RISK_SCORE_HIGH, "HIGH"
    elif score >= 6:
        return settings.RISK_SCORE_MID, "MEDIUM"
    return settings.RISK_SCORE_LOW, "LOW"


# ─── ATR multiplier ───────────────────────────────────────────────────────────

def _atr_multiplier(atr_val: float, spot_price: float) -> Tuple[float, str]:
    if spot_price <= 0:
        return 1.0, "NORMAL_VOL"
    atr_pct = (atr_val / spot_price) * 100
    if atr_pct > 1.5:
        return settings.RISK_HIGH_ATR_MULT, f"HIGH_VOL({atr_pct:.1f}%)"
    elif atr_pct > 1.0:
        return 0.85, f"ELEVATED_VOL({atr_pct:.1f}%)"
    return 1.0, f"NORMAL_VOL({atr_pct:.1f}%)"


# ─── Loss-streak multiplier ────────────────────────────────────────────────────

def _streak_multiplier(consecutive_losses: int) -> Tuple[float, str]:
    if consecutive_losses >= 2:
        return settings.RISK_LOSS_STREAK_MULT, f"STREAK({consecutive_losses}→-50%)"
    elif consecutive_losses == 1:
        return 0.75, "STREAK(1→-25%)"
    return 1.0, "NO_STREAK"


# ─── Main sizing ──────────────────────────────────────────────────────────────

def calculate_adaptive_size(
    capital:            float,
    signal_score:       int,
    option_ltp:         float,
    sl_pct:             float,
    atr_val:            float,
    spot_price:         float,
    consecutive_losses: int,
    lot_size_from_api:  Optional[int],     # ← MUST come from Upstox API
) -> Optional[Dict]:
    """
    Calculate adaptive position size using the actual lot_size from Upstox.

    Returns None if lot_size_from_api is missing/zero — caller MUST block trade.

    Returns dict:
    {
        quantity, lots, lot_size, risk_pct_applied, risk_amount,
        confidence, sizing_notes, base_risk, atr_mult, streak_mult
    }
    """
    notes = []

    # ── HARD GATE: lot_size must come from API ─────────────────────────────────
    if not lot_size_from_api or int(lot_size_from_api) <= 0:
        logger.error(
            "❌ SIZING BLOCKED: lot_size missing or zero. "
            "Cannot calculate position size without API lot_size. NOT TRADING."
        )
        return None

    lot_size = int(lot_size_from_api)

    # ── Risk calculation ───────────────────────────────────────────────────────
    base_risk,   confidence  = _score_to_base_risk(signal_score)
    atr_mult,    atr_note    = _atr_multiplier(atr_val, spot_price)
    streak_mult, streak_note = _streak_multiplier(consecutive_losses)

    notes.append(f"Score {signal_score} → base_risk={base_risk}% ({confidence})")
    notes.append(f"ATR adj ×{atr_mult:.2f} [{atr_note}]")
    notes.append(f"Streak adj ×{streak_mult:.2f} [{streak_note}]")

    final_risk_pct = base_risk * atr_mult * streak_mult
    final_risk_pct = max(0.5, min(final_risk_pct, 2.0))   # 0.5%–2% hard bounds
    notes.append(f"Final risk={final_risk_pct:.2f}%")

    risk_amount = capital * (final_risk_pct / 100)
    sl_per_unit = option_ltp * (sl_pct / 100)

    if sl_per_unit <= 0:
        logger.error("❌ SIZING BLOCKED: SL per unit is zero — cannot calculate qty")
        return None

    raw_qty = int(risk_amount / sl_per_unit)

    # Round down to nearest full lot (must be whole lots)
    lots     = max(1, raw_qty // lot_size)
    quantity = lots * lot_size

    # Safety cap
    if quantity > 500:
        quantity = (500 // lot_size) * lot_size
        lots     = quantity // lot_size

    actual_risk = round(sl_per_unit * quantity, 2)
    notes.append(
        f"Qty={quantity} ({lots} lots × {lot_size} from API) | "
        f"Risk=₹{actual_risk}"
    )

    logger.info(
        f"📐 Size: {quantity}u ({lots}L × {lot_size}) | "
        f"Risk={final_risk_pct:.2f}%=₹{risk_amount:.0f} | "
        f"Score={signal_score} {confidence}"
    )

    return {
        "quantity":         quantity,
        "lots":             lots,
        "lot_size":         lot_size,           # from Upstox API
        "risk_pct_applied": round(final_risk_pct, 3),
        "risk_amount":      round(risk_amount, 2),
        "confidence":       confidence,
        "sizing_notes":     notes,
        "base_risk":        base_risk,
        "atr_mult":         atr_mult,
        "streak_mult":      streak_mult,
    }
