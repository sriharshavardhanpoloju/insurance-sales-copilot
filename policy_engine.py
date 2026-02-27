# ============================================================
# policy_engine.py — Smart Policy Engine (v3)
#
# Upgrades over v2:
#   + Smart composite score (profit + claim + fit)
#   + Policy comparison matrix builder
#   + Deal value calculator (premium + lifetime value)
#   + Cross-sell bundle builder
#   + Age/profile-based filtering
# ============================================================

import json
import os


def load_policies():
    """Load all policies from JSON database."""
    folder = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(folder, "policies.json"), "r") as f:
        return json.load(f)


# ============================================================
# SMART COMPOSITE SCORING
# Combines profit_score + claim_settlement + coverage_value
# Gives a more realistic recommendation ranking
# ============================================================

def calculate_smart_score(policy, client_age=None):
    """
    Calculates a composite score (0-100) for ranking policies.
    Weights: 50% profit score, 30% claim settlement, 20% value ratio
    """
    profit_component    = policy["profit_score"] * 0.50
    claim_component     = (policy["claim_settlement"] / 100) * 100 * 0.30
    value_ratio         = min((policy["coverage"] / max(policy["premium"], 1)) / 1000, 100)
    value_component     = value_ratio * 0.20

    smart_score = round(profit_component + claim_component + value_component)

    # Age-fit bonus: if client age fits the policy range, bump by 5
    if client_age:
        if policy["min_age"] <= client_age <= policy["max_age"]:
            smart_score = min(smart_score + 5, 100)

    return smart_score


def recommend_policy(intent, max_results=3, client_age=None):
    """
    Recommends top policies for a given intent, ranked by smart composite score.

    Parameters:
        intent (str): The detected client intent
        max_results (int): Max number to return
        client_age (int): Optional client age for age-fit bonus

    Returns:
        list: Policies with smart_score added, sorted best-first
    """
    all_policies = load_policies()
    matching     = [p for p in all_policies if p["type"] == intent]

    # Add smart score to each matching policy
    for p in matching:
        p["smart_score"] = calculate_smart_score(p, client_age)

    # Sort by smart score descending
    ranked = sorted(matching, key=lambda p: p["smart_score"], reverse=True)
    return ranked[:max_results]


# ============================================================
# COMPARISON MATRIX
# Returns a side-by-side comparison of recommended policies
# ============================================================

def build_comparison_matrix(policies):
    """
    Builds a comparison dict for rendering a side-by-side table.

    Returns:
        dict: keys are comparison attributes, values are lists per policy
    """
    if not policies:
        return {}

    matrix = {
        "Policy Name":        [p["name"] for p in policies],
        "Annual Premium":     [f"${p['premium']:,}" for p in policies],
        "Coverage Amount":    [f"${p['coverage']:,}" for p in policies],
        "Profit Score":       [f"{p['profit_score']}/100" for p in policies],
        "Claim Settlement":   [f"{p['claim_settlement']}%" for p in policies],
        "Policy Term":        [f"{p['policy_term_years']} yrs" for p in policies],
        "Waiting Period":     [f"{p['waiting_period_days']} days" for p in policies],
        "Tax Benefit":        ["✅ Yes" if p["tax_benefit"] else "❌ No" for p in policies],
        "Cashless":           ["✅ Yes" if p["cashless"] else "❌ No" for p in policies],
        "Smart Score":        [f"{p.get('smart_score', p['profit_score'])}/100" for p in policies],
    }
    return matrix


# ============================================================
# DEAL VALUE CALCULATOR
# ============================================================

def calculate_deal_value(policies):
    """
    Calculates the full financial picture of recommending these policies.

    Returns:
        dict: Breakdown of premium, lifetime value, commission
    """
    if not policies:
        return {}

    COMMISSION_RATE    = 0.15   # 15% first-year commission
    RENEWAL_RATE       = 0.05   # 5% renewal commission

    total_premium      = sum(p["premium"] for p in policies)
    first_yr_commission = round(total_premium * COMMISSION_RATE)

    # Lifetime value = (first year commission) + (renewal × avg term years)
    avg_term           = sum(p["policy_term_years"] for p in policies) / len(policies)
    lifetime_value     = round(first_yr_commission + (total_premium * RENEWAL_RATE * avg_term))

    top_policy         = max(policies, key=lambda p: p["profit_score"])

    return {
        "total_annual_premium":    total_premium,
        "first_year_commission":   first_yr_commission,
        "lifetime_value":          lifetime_value,
        "avg_policy_term":         round(avg_term),
        "commission_rate":         f"{int(COMMISSION_RATE * 100)}%",
        "best_policy":             top_policy["name"],
        "best_policy_commission":  round(top_policy["premium"] * COMMISSION_RATE),
        "policies_in_deal":        len(policies)
    }


# ============================================================
# BUNDLE BUILDER — Cross-sell combinations
# ============================================================

BUNDLE_MAP = {
    "family":     [("health", "Add Health Cover",    "Family + Health is the most common bundle — 73% of family clients buy both."),
                   ("term",   "Add Term Life",        "Term rider gives maximum coverage at minimum extra cost.")],
    "health":     [("term",   "Add Term Life",        "Health-conscious clients are risk-aware — perfect moment for term cover."),
                   ("family", "Add Family Shield",    "Protect the income that pays for the health premium.")],
    "investment": [("term",   "Add Term Rider",       "Ask: 'What happens to this investment if you're not here to fund it?'"),
                   ("health", "Add Health Cover",     "Protect the investment by protecting the investor's health.")],
    "child":      [("family", "Add Family Shield",    "Parent + child plan bundle — the waiver clause is your strongest close."),
                   ("term",   "Add Term Life",        "Term ensures the child plan continues even if something happens to you.")],
    "business":   [("health", "Group Health Cover",   "Employee group health is usually the next conversation after keyman cover."),
                   ("term",   "Director Term Plan",   "Directors need personal term cover separate from business coverage.")],
    "term":       [("investment", "Add Wealth Plan",  "Term clients have budget room — investment plan is a natural add-on."),
                   ("health",    "Add Health Cover",  "Complete protection: life cover + health cover = full safety net.")]
}

def get_bundle_suggestions(intent):
    """Returns cross-sell bundle suggestions for a given intent."""
    return BUNDLE_MAP.get(intent, [])


# ============================================================
# TIER + VISUAL HELPERS
# ============================================================

def get_profit_tier(score):
    if score >= 95:
        return {"tier": "🔥 HOT SELLER",  "color": "#FF6B35", "bg": "#2a1008", "bar_color": "#FF6B35"}
    elif score >= 85:
        return {"tier": "⭐ HIGH VALUE",  "color": "#FFD700", "bg": "#2a2008", "bar_color": "#FFD700"}
    elif score >= 70:
        return {"tier": "✅ STANDARD",    "color": "#50C878", "bg": "#0a2010", "bar_color": "#50C878"}
    else:
        return {"tier": "📋 ENTRY",       "color": "#8892b0", "bg": "#1a1f36", "bar_color": "#8892b0"}


# ============================================================
# AGENT LEADERBOARD HELPERS
# ============================================================

def get_performance_grade(total_commission):
    """Returns a grade and title based on cumulative commission."""
    if total_commission >= 50000:
        return {"grade": "S", "title": "Diamond Agent",   "color": "#64d9f8"}
    elif total_commission >= 20000:
        return {"grade": "A", "title": "Platinum Agent",  "color": "#FFD700"}
    elif total_commission >= 8000:
        return {"grade": "B", "title": "Gold Agent",      "color": "#f5a623"}
    elif total_commission >= 2000:
        return {"grade": "C", "title": "Silver Agent",    "color": "#8892b0"}
    else:
        return {"grade": "D", "title": "Rising Star",     "color": "#50c878"}
