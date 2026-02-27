# ============================================================
# session_manager.py — Session & Performance Manager (v3)
#
# Upgrades over v2:
#   + Daily streak tracking
#   + Performance grade / leaderboard
#   + Session tagging (won / lost / pending)
#   + Export sessions to CSV
# ============================================================

import json
import os
from datetime import datetime, timedelta

SESSION_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "session_log.json")


def load_sessions():
    if not os.path.exists(SESSION_FILE):
        return []
    try:
        with open(SESSION_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def save_session(client_name, conversation_text, analysis_result, recommended_policies, deal_status="pending"):
    sessions = load_sessions()

    new_session = {
        "id":                   len(sessions) + 1,
        "timestamp":            datetime.now().isoformat(),
        "date":                 datetime.now().strftime("%b %d, %Y"),
        "time":                 datetime.now().strftime("%I:%M %p"),
        "date_key":             datetime.now().strftime("%Y-%m-%d"),
        "client_name":          client_name if client_name.strip() else "Unknown Client",
        "conversation_snippet": conversation_text[:200] + ("..." if len(conversation_text) > 200 else ""),
        "intent":               analysis_result.get("intent", "family"),
        "secondary_intents":    analysis_result.get("secondary_intents", []),
        "confidence":           analysis_result.get("confidence", "medium"),
        "urgency":              analysis_result.get("urgency", "low"),
        "sentiment":            analysis_result.get("sentiment", "neutral"),
        "persona":              analysis_result.get("persona", "general_client"),
        "summary":              analysis_result.get("summary", ""),
        "analysis_mode":        analysis_result.get("mode", "rule-based"),
        "policies_shown":       [p["name"] for p in recommended_policies],
        "top_policy":           recommended_policies[0]["name"] if recommended_policies else "N/A",
        "top_profit_score":     recommended_policies[0]["profit_score"] if recommended_policies else 0,
        "top_smart_score":      recommended_policies[0].get("smart_score", 0) if recommended_policies else 0,
        "total_premium_value":  sum(p["premium"] for p in recommended_policies),
        "estimated_commission": round(sum(p["premium"] for p in recommended_policies) * 0.15),
        "deal_status":          deal_status,   # "pending", "won", "lost"
    }

    sessions.append(new_session)
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f, indent=2)

    return new_session


def update_deal_status(session_id, status):
    """Updates a session's deal status (won / lost / pending)."""
    sessions = load_sessions()
    for s in sessions:
        if s["id"] == session_id:
            s["deal_status"] = status
            break
    with open(SESSION_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


def clear_sessions():
    if os.path.exists(SESSION_FILE):
        os.remove(SESSION_FILE)


def get_performance_stats(sessions):
    """Comprehensive performance stats from session history."""
    if not sessions:
        return {
            "total_sessions": 0, "sessions_today": 0,
            "total_premium_value": 0, "total_commission": 0,
            "avg_profit_score": 0, "avg_smart_score": 0,
            "top_intent": "N/A", "intent_breakdown": {},
            "deals_won": 0, "deals_lost": 0, "deals_pending": 0,
            "win_rate": 0, "daily_streak": 0, "best_session_value": 0
        }

    today     = datetime.now().strftime("%Y-%m-%d")
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    intent_counts = {}
    for s in sessions:
        intent = s.get("intent", "unknown")
        intent_counts[intent] = intent_counts.get(intent, 0) + 1

    top_intent = max(intent_counts, key=intent_counts.get) if intent_counts else "N/A"

    total_premium   = sum(s.get("total_premium_value", 0) for s in sessions)
    total_commission = sum(s.get("estimated_commission", 0) for s in sessions)
    avg_profit       = sum(s.get("top_profit_score", 0) for s in sessions) / len(sessions)
    avg_smart        = sum(s.get("top_smart_score", 0) for s in sessions) / len(sessions)

    sessions_today = sum(1 for s in sessions if s.get("date_key") == today)

    deals_won     = sum(1 for s in sessions if s.get("deal_status") == "won")
    deals_lost    = sum(1 for s in sessions if s.get("deal_status") == "lost")
    deals_pending = sum(1 for s in sessions if s.get("deal_status") == "pending")
    closed_deals  = deals_won + deals_lost
    win_rate      = round((deals_won / closed_deals) * 100) if closed_deals > 0 else 0

    best_session = max(sessions, key=lambda s: s.get("total_premium_value", 0))

    # Daily streak: consecutive days with at least 1 session
    date_set = set(s.get("date_key", "") for s in sessions)
    streak   = 0
    check_date = datetime.now()
    while check_date.strftime("%Y-%m-%d") in date_set:
        streak += 1
        check_date -= timedelta(days=1)

    return {
        "total_sessions":      len(sessions),
        "sessions_today":      sessions_today,
        "total_premium_value": total_premium,
        "total_commission":    total_commission,
        "avg_profit_score":    round(avg_profit, 1),
        "avg_smart_score":     round(avg_smart, 1),
        "top_intent":          top_intent,
        "intent_breakdown":    intent_counts,
        "deals_won":           deals_won,
        "deals_lost":          deals_lost,
        "deals_pending":       deals_pending,
        "win_rate":            win_rate,
        "daily_streak":        streak,
        "best_session_value":  best_session.get("total_premium_value", 0),
    }


def export_sessions_csv(sessions):
    """Converts sessions list to CSV string for download."""
    if not sessions:
        return ""

    headers = ["ID", "Date", "Client", "Intent", "Top Policy", "Premium", "Commission", "Status", "Confidence"]
    rows    = [",".join(headers)]

    for s in sessions:
        row = [
            str(s.get("id", "")),
            s.get("date", ""),
            s.get("client_name", ""),
            s.get("intent", ""),
            s.get("top_policy", ""),
            str(s.get("total_premium_value", 0)),
            str(s.get("estimated_commission", 0)),
            s.get("deal_status", "pending"),
            s.get("confidence", ""),
        ]
        rows.append(",".join(row))

    return "\n".join(rows)
