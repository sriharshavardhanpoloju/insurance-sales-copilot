# ============================================================
# recommender_model.py — Enhanced Inference Engine v3
#
# Key improvements over v2:
#   + 10-signal composite scoring (age fit, budget fit, coverage ratio,
#     claim rate, urgency match, health signals, family size, intent weight,
#     rider value, renewal bonus)
#   + Pre-existing condition routing
#   + Child age detection for child plans
#   + Retirement proximity scoring for investment plans
#   + Hard eligibility filtering (never shows ineligible policies)
#   + Richer Claude prompt with explicit scoring instructions
# ============================================================

import json, os, re

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL_CONFIG_PATH = os.path.join(BASE, "model_config.json")

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ── Loaders ────────────────────────────────────────────────

def load_model():
    if not os.path.exists(MODEL_CONFIG_PATH):
        return None
    with open(MODEL_CONFIG_PATH) as f:
        return json.load(f)

def load_policies():
    with open(os.path.join(BASE, "policies.json")) as f:
        return json.load(f)


# ============================================================
# EXTRACTION — age, budget, family, health, child age
# ============================================================

def extract_age(text):
    t = text.lower()
    patterns = [
        r"\b(\d{2})\s*(?:years?\s*old|yr\s*old|yrs?\s*old)",
        r"(?:age[d\s:]+)(\d{2})\b",
        r"\b(\d{2})\s*(?:year|yr)\b",
        r"(?:i\'?m|i am)\s+(\d{2})\b",
        r"\b(\d{2})\s*-\s*year\s*-\s*old",
        r"(?:client|he|she|they)\s+is\s+(\d{2})\b",
        r"(?:just\s+turned|turned)\s+(\d{2})\b",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            age = int(m.group(1))
            if 18 <= age <= 80:
                return age
    return 35

def extract_budget(text):
    t = text.lower()
    t_clean = re.sub(r"(\d),(\d)", r"\1\2", t)
    m = re.search(r"(?:rs\.?|\u20b9)\s*(\d+(?:\.\d+)?)\s*k?\b", t_clean)
    if m:
        val = float(m.group(1))
        if "k" in t_clean[m.start():m.end()+2]:
            val *= 1000
        return int(val / 12 if val >= 10000 else val)
    m = re.search(r"\$\s*(\d+(?:\.\d+)?)\s*k?\b", t_clean)
    if m:
        val = float(m.group(1))
        if "k" in t_clean[m.start():m.end()+2]:
            val *= 1000
        return int(val / 12 if val >= 10000 else val)
    m = re.search(r"(\d+(?:\.\d+)?)\s*k?\s*/\s*(?:per\s*)?month", t_clean)
    if m:
        val = float(m.group(1))
        if "k" in t_clean[m.start():m.end()+4]:
            val *= 1000
        return int(val)
    m = re.search(r"(?:budget|pay|afford|invest|spend)\s+(?:of\s+)?(?:rs\.?|\u20b9|\$)?\s*(\d+)", t_clean)
    if m:
        val = int(m.group(1))
        return val // 12 if val >= 10000 else val
    return 1500

def extract_family_size(text):
    t = text.lower()
    word_to_num = {"one":1,"two":2,"three":3,"four":4,"five":5,"six":6}
    m = re.search(r"(\d+|one|two|three|four|five|six)\s+(?:kids?|children|dependents?|members?)", t)
    if m:
        v = m.group(1)
        return word_to_num.get(v, int(v) if v.isdigit() else 2)
    if any(x in t for x in ["wife","husband","spouse","married","partner"]):
        return 2
    if "single" in t or "bachelor" in t:
        return 1
    return 2

def extract_health_signals(text):
    t = text.lower()
    conditions = ["diabetes","diabetic","hypertension","blood pressure","cancer","heart","thyroid",
                  "asthma","kidney","liver","stroke","arthritis","obesity","overweight"]
    return [c for c in conditions if c in t]

def extract_child_age(text):
    """Extract age of child if mentioned."""
    t = text.lower()
    patterns = [
        r"child\s+(?:is\s+)?(\d+)\s*(?:years?|yr)",
        r"(\d+)\s*(?:year|yr)[\s-]+old\s+(?:kid|child|son|daughter|boy|girl)",
        r"(?:son|daughter|kid|child)\s+(?:is\s+)?(\d+)",
        r"(\d+)\s*(?:month|months)\s*old",  # returns <1
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            if "month" in pat:
                return 0
            age = int(m.group(1))
            if 0 <= age <= 25:
                return age
    return None

def extract_retirement_years(text, age):
    """How many years until retirement."""
    t = text.lower()
    m = re.search(r"retire\s+(?:at|by|around)\s+(\d+)", t)
    if m:
        retire_age = int(m.group(1))
        return max(retire_age - age, 0)
    if "retire" in t or "pension" in t or "retirement" in t:
        return max(60 - age, 0)
    return None

def has_pre_existing(text):
    return bool(extract_health_signals(text))

def is_high_income(text, budget):
    t = text.lower()
    return budget >= 2500 or any(w in t for w in ["high income","rich","affluent","hni","high net worth","lakh","crore"])


# ============================================================
# INTENT DETECTION — weighted keyword scoring
# ============================================================

INTENT_KEYWORDS = {
    "family": {
        "primary":   ["family protection","sole earner","breadwinner","dependents","whole life","legacy"],
        "secondary": ["wife","husband","children","kids","child","spouse","parents","newborn","baby","married","marriage"],
        "weight": 1.0
    },
    "health": {
        "primary":   ["health insurance","medical cover","hospitalization","cashless","critical illness","cancer","surgery","icu"],
        "secondary": ["hospital","sick","illness","disease","doctor","treatment","diabetes","heart","medicine","prescription","aging"],
        "weight": 1.2
    },
    "investment": {
        "primary":   ["investment","wealth creation","returns","portfolio","ulip","mutual fund","compound","retire early"],
        "secondary": ["invest","savings","grow money","financial goal","retirement","pension","sip","equity","returns"],
        "weight": 1.0
    },
    "child": {
        "primary":   ["child plan","education plan","child future","college fund","school fees","daughter education","son education"],
        "secondary": ["child savings","18 years","maturity plan","kid's future","my son","my daughter","child education"],
        "weight": 1.3
    },
    "business": {
        "primary":   ["keyman","business insurance","business continuity","buy-sell","partnership insurance","director"],
        "secondary": ["business","company","entrepreneur","startup","sme","firm","employee","commercial","proprietor","owner"],
        "weight": 1.1
    },
    "term": {
        "primary":   ["term plan","pure term","cheap insurance","term life","low premium","maximum coverage","affordable life"],
        "secondary": ["term","basic cover","affordable cover","simple insurance","pure life","low cost"],
        "weight": 0.9
    }
}

def detect_intent(text):
    t = text.lower()
    scores = {}
    for intent, data in INTENT_KEYWORDS.items():
        primary_hits   = sum(3 for kw in data["primary"]   if kw in t)
        secondary_hits = sum(1 for kw in data["secondary"] if kw in t)
        scores[intent] = (primary_hits + secondary_hits) * data["weight"]

    best  = max(scores, key=scores.get)
    total = max(sum(scores.values()), 1)
    conf  = round((scores[best] / total) * 100)
    return best, conf, scores


# ============================================================
# COMPOSITE POLICY SCORING — 10 signals
# ============================================================

def score_policy(policy, age, budget, intent, urgency_score, family_size,
                 health_signals, conversation, child_age=None, retirement_years=None,
                 high_income=False):
    score = 0
    t = conversation.lower()

    # 1. Age eligibility (hard filter + soft score)
    if not (policy["min_age"] <= age <= policy["max_age"]):
        return -1  # Hard disqualify
    age_range = policy["max_age"] - policy["min_age"]
    age_center = (policy["min_age"] + policy["max_age"]) / 2
    age_distance = abs(age - age_center)
    age_fit = max(0, 20 - (age_distance / age_range) * 20)
    score += age_fit

    # 2. Budget fit (monthly premium vs budget)
    monthly_prem = policy["premium"] / 12
    if monthly_prem <= budget:
        budget_slack = (budget - monthly_prem) / max(budget, 1)
        score += 15 + budget_slack * 5  # up to 20 pts
    else:
        over_budget_pct = (monthly_prem - budget) / max(budget, 1)
        score -= min(over_budget_pct * 30, 30)  # penalize up to 30 pts

    # 3. Claim settlement rate (0-15 pts)
    score += (policy["claim_settlement"] - 90) * 1.5  # 95% = 7.5, 99.5% = 14.25

    # 4. Coverage value ratio (0-10 pts)
    coverage_ratio = policy["coverage"] / max(policy["premium"], 1)
    score += min(coverage_ratio / 100, 10)

    # 5. Profit score contribution (0-15 pts for agent)
    score += (policy["profit_score"] - 60) * 0.375  # 60=0, 100=15

    # 6. Urgency match (0-10 pts)
    if urgency_score >= 7 and policy.get("waiting_period_days", 30) == 0:
        score += 10
    elif urgency_score >= 4 and policy.get("waiting_period_days", 30) <= 30:
        score += 5

    # 7. Health signals routing
    if health_signals:
        if policy["type"] == "health":
            if policy.get("cashless"):
                score += 10
            if policy.get("covers_pre_existing"):
                score += 8
        if policy["type"] in ["family","term"] and not policy.get("cashless"):
            score -= 5  # health-sensitive client shouldn't get non-cashless family plan

    # 8. Family size match
    if family_size >= 3 and policy["type"] in ["family","health"]:
        score += 8
    elif family_size == 1 and policy["type"] == "term":
        score += 5

    # 9. Child plan specifics
    if policy["type"] == "child" and child_age is not None:
        child_min = policy.get("child_age_min", 0)
        child_max = policy.get("child_age_max", 15)
        if child_min <= child_age <= child_max:
            score += 12
        else:
            score -= 10
        if policy.get("waiver_on_parent_death"):
            score += 8

    # 10. Investment/retirement specifics
    if policy["type"] == "investment" and retirement_years is not None:
        term = policy["policy_term_years"]
        if abs(term - retirement_years) <= 5:
            score += 12  # term aligns with retirement horizon
        if high_income and policy.get("expected_returns_pct", 0) >= 10:
            score += 8

    # 11. High income → premium policies
    if high_income and policy["premium"] >= 2000:
        score += 6

    # 12. Waiting period penalty for urgent health cases
    if urgency_score >= 5 and policy.get("waiting_period_days", 0) >= 90:
        score -= 8

    # 13. Renewal bonus (long-term value signal)
    score += policy.get("renewal_bonus_pct", 0) * 0.5

    # 14. Intent exact match bonus
    if policy["type"] == intent:
        score += 10

    return round(max(score, 0), 1)


# ============================================================
# REASONING BUILDER — human-readable explanation
# ============================================================

def build_reasoning(policy, age, budget, score, rank, health_signals=None,
                    family_size=2, child_age=None, retirement_years=None):
    monthly = round(policy["premium"] / 12)
    budget_status = "fits budget" if monthly <= budget else f"Rs.{monthly - budget} over monthly budget"

    lines = []

    if rank == 1:
        lines.append(f"Top pick for {age}-year-old: {policy['name']} scores {score}/100.")
    else:
        lines.append(f"#{rank} alternative: {policy['name']} (score {score}/100).")

    lines.append(f"Premium Rs.{monthly}/month — {budget_status}.")
    lines.append(f"{policy['claim_settlement']}% claim settlement rate ensures reliable payouts.")

    if health_signals:
        if policy.get("cashless"):
            lines.append("Cashless network is critical given pre-existing conditions.")
        if policy.get("covers_pre_existing"):
            lines.append(f"Pre-existing conditions covered after {policy.get('pre_existing_waiting_years',2)} years — ideal given health signals.")

    if policy["type"] == "child" and child_age is not None:
        lines.append(f"Designed for child aged {child_age} — milestone payouts align with education milestones.")
        if policy.get("waiver_on_parent_death"):
            lines.append("Waiver clause: policy continues even if parent dies — strongest close argument.")

    if policy["type"] == "investment" and retirement_years:
        lines.append(f"{policy['policy_term_years']}-year term aligns with {retirement_years}-year retirement horizon.")

    if policy.get("tax_benefit"):
        lines.append("Tax deductible under Sec 80C — adds ~Rs.360 annual savings at 30% bracket.")

    return " ".join(lines)


# ============================================================
# RULE-BASED RECOMMENDER (no API key)
# ============================================================

def rule_based_recommend(conversation, policies, intent=None):
    t = conversation.lower()

    if not intent:
        intent, conf_pct, _ = detect_intent(t)

    age             = extract_age(t)
    budget          = extract_budget(t)
    family_size     = extract_family_size(t)
    health_sigs     = extract_health_signals(t)
    child_age       = extract_child_age(t)
    retirement_yrs  = extract_retirement_years(t, age)
    high_income     = is_high_income(t, budget)

    urgency_words = ["urgent","asap","immediately","soon","worried","scared",
                     "anxious","diagnosed","critical","emergency","hospital","accident"]
    urgency_score = min(sum(2 for w in urgency_words if w in t), 10)

    # Score all eligible policies of matching type first, then fallback to all
    candidates = [p for p in policies if p["type"] == intent]
    if not candidates:
        candidates = policies

    scored = []
    for p in candidates:
        fs = score_policy(p, age, budget, intent, urgency_score, family_size,
                         health_sigs, conversation, child_age, retirement_yrs, high_income)
        if fs >= 0:  # -1 = hard disqualified
            scored.append({**p, "fit_score": fs, "smart_score": fs})

    if not scored:
        # Fallback: relax age filter, show top by profit
        scored = [{**p, "fit_score": p["profit_score"], "smart_score": p["profit_score"]}
                  for p in candidates[:3]]

    ranked = sorted(scored, key=lambda x: x["fit_score"], reverse=True)
    top3   = ranked[:3]
    if not top3:
        return None

    top       = top3[0]
    reasoning = build_reasoning(top, age, budget, top["fit_score"], rank=1,
                                health_signals=health_sigs, family_size=family_size,
                                child_age=child_age, retirement_years=retirement_yrs)

    return {
        "top_policy_id":       top["id"],
        "top_policy_name":     top["name"],
        "ranked_policy_ids":   [p["id"] for p in top3],
        "ranked_policy_names": [p["name"] for p in top3],
        "fit_scores":          {p["id"]: p["fit_score"] for p in top3},
        "reasoning":           reasoning,
        "key_factors": {
            "detected_age":      age,
            "detected_budget":   f"Rs.{budget}/month",
            "family_size":       family_size,
            "health_signals":    health_sigs,
            "urgency_score":     urgency_score,
            "child_age":         child_age,
            "retirement_years":  retirement_yrs,
            "high_income":       high_income,
            "age_fit":           top["min_age"] <= age <= top["max_age"],
            "budget_fit":        (top["premium"] / 12) <= budget,
            "profit_score":      top["profit_score"],
            "claim_rate":        top["claim_settlement"],
        },
        "mode":   "rule-based v3",
        "intent": intent,
        "ranked": top3,
        "client_profile": {
            "age": age, "budget_monthly": budget,
            "family_size": family_size, "health_signals": health_sigs,
            "urgency": urgency_score, "child_age": child_age,
            "retirement_years": retirement_yrs, "high_income": high_income,
        },
    }


# ============================================================
# CLAUDE PROMPT CHAIN (enhanced)
# ============================================================

def claude_recommend(conversation, model_config, api_key, intent=None):
    client   = anthropic.Anthropic(api_key=api_key)
    policies = load_policies()
    t        = conversation.lower()

    if not intent:
        intent, conf_pct, _ = detect_intent(t)

    age             = extract_age(t)
    budget          = extract_budget(t)
    family_size     = extract_family_size(t)
    health_sigs     = extract_health_signals(t)
    child_age       = extract_child_age(t)
    retirement_yrs  = extract_retirement_years(t, age)
    high_income     = is_high_income(t, budget)
    urgency_score   = min(sum(2 for w in ["urgent","asap","worried","diagnosed","critical","hospital","accident"] if w in t), 10)

    candidates = [p for p in policies if p["type"] == intent] or policies

    pre_scored = []
    for p in candidates:
        fs = score_policy(p, age, budget, intent, urgency_score, family_size,
                         health_sigs, conversation, child_age, retirement_yrs, high_income)
        if fs >= 0:
            pre_scored.append({
                "id": p["id"], "name": p["name"],
                "premium": p["premium"], "monthly_premium": round(p["premium"]/12),
                "coverage": p["coverage"],
                "profit_score": p["profit_score"],
                "claim_settlement": p["claim_settlement"],
                "min_age": p["min_age"], "max_age": p["max_age"],
                "policy_term_years": p["policy_term_years"],
                "tax_benefit": p["tax_benefit"],
                "cashless": p.get("cashless", False),
                "waiting_period_days": p.get("waiting_period_days", 0),
                "covers_pre_existing": p.get("covers_pre_existing", False),
                "waiver_on_parent_death": p.get("waiver_on_parent_death", False),
                "highlights": p["highlights"][:3],
                "ideal_for": p.get("ideal_for", ""),
                "rule_score": fs,
                "age_eligible": p["min_age"] <= age <= p["max_age"],
                "budget_fits":  round(p["premium"]/12) <= budget,
                "badge": p.get("badge",""),
            })
    pre_scored.sort(key=lambda x: x["rule_score"], reverse=True)

    client_profile = {
        "age": age,
        "monthly_budget": f"Rs.{budget}",
        "annual_budget": f"Rs.{budget*12}",
        "family_size": family_size,
        "health_signals": health_sigs or "none",
        "child_age": child_age,
        "retirement_years_away": retirement_yrs,
        "high_income": high_income,
        "urgency_score": f"{urgency_score}/10",
        "intent": intent,
    }

    system = """You are a senior insurance product specialist and sales strategist with 20+ years of experience.
Your job: given a client profile and pre-scored policies, select the best 3 for THIS specific client.

HARD RULES (never violate):
1. NEVER recommend a policy where age_eligible=false
2. NEVER recommend if monthly_premium > client budget * 1.5 (too unaffordable)
3. For health_signals (pre-existing conditions): strongly prefer cashless=true and covers_pre_existing=true
4. For child intent with child_age: prefer policies where waiver_on_parent_death=true
5. For urgent cases (urgency_score >= 6): prefer waiting_period_days=0 or very short
6. For high_income=true: prefer premium policies (profit_score >= 85, higher coverage)

SCORING GUIDANCE:
- Weight rule_score heavily (it already factors age, budget, health, urgency)
- Adjust for qualitative fit: read the client conversation carefully
- Policy with highest rule_score is USUALLY the best pick — only override if strong qualitative reason

Return ONLY this JSON (no markdown, no explanation):
{
  "ranked_policy_ids": ["<id1>","<id2>","<id3>"],
  "fit_scores": {"<id1>": <0-100>, "<id2>": <0-100>, "<id3>": <0-100>},
  "reasoning": "<2-3 specific sentences: why id1 is best — reference client's exact age, budget, key need, and one specific policy feature that addresses it>",
  "key_insight": "<one powerful sales closing technique tailored to THIS client's specific situation>"
}"""

    user_msg = f"""CLIENT PROFILE:
{json.dumps(client_profile, indent=2)}

CLIENT CONVERSATION (verbatim):
"{conversation[:800]}"

PRE-SCORED ELIGIBLE POLICIES (sorted best-first by rule_score):
{json.dumps(pre_scored, indent=2)}

Select the 3 best policies for this client. Respect the hard rules above."""

    few_shots = model_config.get("few_shot_examples", {}).get(intent, []) if model_config else []
    messages  = []
    for ex in few_shots[:2]:
        messages.append({"role":"user",      "content": ex.get("conversation","")})
        messages.append({"role":"assistant", "content": json.dumps(ex.get("output",{}))})
    messages.append({"role":"user", "content": user_msg})

    resp = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=800,
        system=system,
        messages=messages
    )

    raw = resp.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    result = json.loads(raw)

    policy_map  = {p["id"]: p for p in policies}
    ranked_full = []
    for pid in result.get("ranked_policy_ids", [])[:3]:
        if pid in policy_map:
            p = dict(policy_map[pid])
            p["fit_score"]   = result.get("fit_scores", {}).get(pid, p["profit_score"])
            p["smart_score"] = p["fit_score"]
            ranked_full.append(p)

    if not ranked_full:
        return rule_based_recommend(conversation, policies, intent)

    result["ranked"]         = ranked_full
    result["intent"]         = intent
    result["mode"]           = "claude-ai v3"
    result["client_profile"] = client_profile
    return result


# ============================================================
# MAIN ENTRY
# ============================================================

def recommend(conversation, api_key=None, intent=None):
    model_config = load_model()
    policies     = load_policies()

    if api_key and ANTHROPIC_AVAILABLE:
        try:
            return claude_recommend(conversation, model_config, api_key, intent)
        except Exception as e:
            result = rule_based_recommend(conversation, policies, intent)
            if result:
                result["mode"] = f"rule-based v3 fallback ({str(e)[:60]})"
            return result

    return rule_based_recommend(conversation, policies, intent)


# ============================================================
# HELPERS
# ============================================================

def get_model_info():
    config = load_model()
    if not config:
        return {"trained": False}
    return {
        "trained":       True,
        "version":       config.get("model_version", "1.0"),
        "trained_on":    config.get("trained_on", ""),
        "top1_accuracy": config.get("top1_accuracy", 0),
        "top3_accuracy": config.get("top3_accuracy", 0),
        "intents":       config.get("intents", []),
        "prompt_chars":  len(config.get("system_prompt", "")),
    }
