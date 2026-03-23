"""
AI analysis module for sentiment and market projection.

Uses Groq LLM (llama3) when API key is available, falls back to
keyword-based heuristic otherwise.
"""
from __future__ import annotations

import json
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("analytics.ai")


def analyze_sentiment(texts: List[str]) -> List[Dict[str, Optional[str]]]:
    """Keyword-based sentiment analysis (fast, no API call).

    Used as fallback when Groq is unavailable or for bulk processing.
    """
    res = []
    for t in texts:
        lower = (t or "").lower()
        if any(w in lower for w in ("pump", "surge", "rally", "moon", "bullish", "breakout", "ath")):
            res.append({"sentiment": "bullish", "confidence": 0.6})
        elif any(w in lower for w in ("dump", "crash", "selloff", "bearish", "liquidat", "fud", "scam")):
            res.append({"sentiment": "bearish", "confidence": 0.6})
        else:
            res.append({"sentiment": "neutral", "confidence": 0.3})
    return res


async def analyze_sentiment_ai(symbol: str, market_data: Optional[Dict] = None) -> Dict:
    """
    AI-powered sentiment analysis using Groq LLM.

    Returns: {score: float(-1..1), label: str, confidence: float(0..1), reasoning: str}
    Falls back to neutral if Groq API key is not configured.
    """
    try:
        from app.core.config import settings
        if not settings.groq_api_key:
            logger.info("GROQ_API_KEY not set, returning neutral sentiment")
            return {"score": 0.0, "label": "neutral", "confidence": 0.3, "reasoning": "AI not configured"}

        from groq import Groq

        client = Groq(api_key=settings.groq_api_key)

        # Build context from market data if available
        context_parts = [f"Symbol: {symbol}"]
        if market_data:
            if "price" in market_data:
                context_parts.append(f"Current Price: ${market_data['price']}")
            if "change_24h" in market_data:
                context_parts.append(f"24h Change: {market_data['change_24h']}%")
            if "volume_24h" in market_data:
                context_parts.append(f"24h Volume: ${market_data['volume_24h']}")
            if "rsi" in market_data:
                context_parts.append(f"RSI(14): {market_data['rsi']}")
            if "macd_signal" in market_data:
                context_parts.append(f"MACD Signal: {market_data['macd_signal']}")

        market_context = "\n".join(context_parts)

        completion = client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a crypto market analyst. Analyze the given market data and provide sentiment analysis. "
                        "Return ONLY valid JSON with these exact fields:\n"
                        '{"score": <float from -1.0 (very bearish) to 1.0 (very bullish)>, '
                        '"label": "<bearish|neutral|bullish>", '
                        '"confidence": <float from 0.0 to 1.0>, '
                        '"reasoning": "<brief 1-2 sentence explanation>"}'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Analyze the current market sentiment for:\n{market_context}",
                },
            ],
            temperature=0.3,
            max_tokens=256,
        )

        response_text = completion.choices[0].message.content.strip()
        # Extract JSON from response (handle markdown code blocks)
        if "```" in response_text:
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)
        # Validate and clamp values
        result["score"] = max(-1.0, min(1.0, float(result.get("score", 0))))
        result["confidence"] = max(0.0, min(1.0, float(result.get("confidence", 0.5))))
        result["label"] = result.get("label", "neutral")
        if result["label"] not in ("bearish", "neutral", "bullish"):
            result["label"] = "neutral"
        return result

    except json.JSONDecodeError:
        logger.warning(f"Failed to parse Groq response for {symbol}")
        return {"score": 0.0, "label": "neutral", "confidence": 0.2, "reasoning": "Failed to parse AI response"}
    except Exception as e:
        logger.warning(f"Groq sentiment analysis failed for {symbol}: {e}")
        return {"score": 0.0, "label": "neutral", "confidence": 0.2, "reasoning": f"AI error: {str(e)}"}


def project_market_scenario(symbol: str, features: Dict) -> Dict:
    """Returns a market projection structure based on available features.

    Uses simple technical indicators when available, neutral otherwise.
    """
    score = 0.0
    reasons = []

    rsi = features.get("rsi")
    if rsi is not None:
        if rsi < 30:
            score += 0.3
            reasons.append(f"RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 0.3
            reasons.append(f"RSI overbought ({rsi:.1f})")

    macd_hist = features.get("macd_histogram")
    if macd_hist is not None:
        if macd_hist > 0:
            score += 0.2
            reasons.append("MACD bullish")
        else:
            score -= 0.2
            reasons.append("MACD bearish")

    change_24h = features.get("change_24h")
    if change_24h is not None:
        if change_24h > 5:
            score += 0.2
            reasons.append(f"Strong 24h up ({change_24h:.1f}%)")
        elif change_24h < -5:
            score -= 0.2
            reasons.append(f"Strong 24h down ({change_24h:.1f}%)")

    score = max(-1.0, min(1.0, score))
    if score > 0.2:
        scenario = "bullish"
    elif score < -0.2:
        scenario = "bearish"
    else:
        scenario = "neutral"

    return {
        "symbol": symbol,
        "scenario": scenario,
        "confidence": round(min(abs(score) + 0.3, 1.0), 2),
        "score": round(score, 2),
        "reasons": reasons or ["Insufficient data for projection"],
    }
