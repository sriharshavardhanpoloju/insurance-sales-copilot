# ============================================================
# ai_engine.py — Client Intelligence Engine v4
#
# Upgrades over v3:
#   + Weighted multi-signal intent scoring (primary keywords 3x)
#   + Extended keyword map covering Indian insurance terminology
#   + Income level detection
#   + More granular urgency scoring
#   + Better persona matching using multiple signals
#   + Richer Claude prompt with specific sales intelligence
# ============================================================

import os
import json
import re

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


# ============================================================
# INTENT KEYWORDS — weighted (primary = 3pts, secondary = 1pt)
# ============================================================

KEYWORD_MAP = {
    "family": {
        "primary":   ["family protection","life insurance","whole life","sole earner","breadwinner",
                      "income replacement","family cover","dependents","legacy","estate planning"],
        "secondary": ["wife","husband","children","kids","child","spouse","parents","newborn","baby",
                      "married","marriage","family","protect my family","provide for"]
    },
    "health": {
        "primary":   ["health insurance","medical insurance","hospitalization","cashless hospital",
                      "critical illness","icu","surgery","cancer treatment","medical bills","health cover"],
        "secondary": ["health","medical","hospital","sick","illness","disease","doctor",
                      "treatment","cancer","diabetes","heart","medicine","prescription","aging","senior"]
    },
    "investment": {
        "primary":   ["investment plan","wealth creation","ulip","mutual fund","returns","portfolio",
                      "compound interest","wealth management","financial planning","equity"],
        "secondary": ["invest","investment","savings","grow","retire","retirement","pension",
                      "sip","financial","returns","wealth","income","passive income"]
    },
    "child": {
        "primary":   ["child plan","education plan","child future","college fund","school fees",
                      "daughter education","son education","child education","child savings"],
        "secondary": ["child","children","kids","daughter","son","18 years","maturity",
                      "my kid","child's future","education fund","baby","toddler"]
    },
    "business": {
        "primary":   ["keyman insurance","business insurance","business continuity","director insurance",
                      "buy-sell agreement","partnership protection","key person"],
        "secondary": ["business","company","entrepreneur","startup","sme","firm","owner",
                      "employee","commercial","liability","proprietor","director","partner"]
    },
    "term": {
        "primary":   ["term plan","pure term","term life","maximum coverage","cheap life insurance",
                      "affordable life cover","basic life insurance","simple term"],
        "secondary": ["term","pure","affordable","cheap","low premium","basic cover",
                      "simple insurance","just coverage","minimum premium"]
    }
}

# Urgency signals with weights
URGENCY_SIGNALS = {
    "critical": ["diagnosed","terminal","surgery scheduled","heart attack","cancer","hospitalized",
                 "accident","emergency","icu","critical condition"],
    "high":     ["urgent","asap","immediately","worried sick","scared","anxious","panic",
                 "deadline","expire","lapse","last chance"],
    "medium":   ["soon","thinking about","should i","worried","concerned","getting older",
                 "turning 40","turning 50","just had a baby","just got married","new job"],
    "low":      ["exploring","considering","just curious","someday","when i have time"]
}

# Positive/negative sentiment signals
POSITIVE_SIGNALS = ["great","good","happy","excited","interested","love","perfect","yes","ready",
                    "definitely","absolutely","sure","want to","let's do it"]
NEGATIVE_SIGNALS = ["worried","scared","anxious","nervous","confused","expensive","doubt",
                    "not sure","can't afford","too costly","think about it","maybe later"]

# Persona detection — multi-signal approach
PERSONA_SIGNALS = {
    "young_professional": {
        "ages": list(range(22, 32)),
        "keywords": ["single","just started working","first job","new job","fresher","just graduated",
                     "no dependents","renting","early career","young professional"]
    },
    "young_parent": {
        "ages": list(range(28, 42)),
        "keywords": ["newborn","baby","toddler","kids","children","school","wife","husband",
                     "married recently","new parent","just had","expecting","pregnant"]
    },
    "mid_career": {
        "ages": list(range(35, 50)),
        "keywords": ["promotion","own house","home loan","mortgage","growing family","car loan",
                     "manager","senior","established","mid career","second income"]
    },
    "pre_retiree": {
        "ages": list(range(48, 60)),
        "keywords": ["retire","retirement","pension","savings for retirement","winding down",
                     "last few working years","near retirement","plan for retirement"]
    },
    "senior": {
        "ages": list(range(58, 81)),
        "keywords": ["retired","grandchildren","senior","aging","health issue","fixed income",
                     "pension income","senior citizen","old age"]
    },
    "business_owner": {
        "ages": list(range(25, 70)),
        "keywords": ["business","company","firm","entrepreneur","startup","sme","owner",
                     "director","founder","proprietor","self employed","running a business"]
    }
}


# ============================================================
# RULE-BASED ANALYSIS
# ============================================================

def detect_age_from_text(text):
    t = text.lower()
    patterns = [
        r"\b(\d{2})\s*(?:years?\s*old|yr\s*old|yrs?\s*old)",
        r"(?:age[d\s:]+)(\d{2})\b",
        r"(?:i\'?m|i am)\s+(\d{2})\b",
        r"(?:just\s+turned|turned)\s+(\d{2})\b",
    ]
    for pat in patterns:
        m = re.search(pat, t)
        if m:
            age = int(m.group(1))
            if 18 <= age <= 80:
                return age
    return None

def analyze_client_rules(text):
    t = text.lower()

    # Weighted intent scoring
    scores = {}
    for intent, data in KEYWORD_MAP.items():
        primary_hits   = sum(3 for kw in data["primary"]   if kw in t)
        secondary_hits = sum(1 for kw in data["secondary"] if kw in t)
        scores[intent] = primary_hits + secondary_hits

    best_intent = max(scores, key=scores.get)
    best_score  = scores[best_intent]

    if best_score == 0:
        best_intent = "family"

    total_hits     = max(sum(scores.values()), 1)
    confidence_pct = round((scores[best_intent] / total_hits) * 100)
    confidence     = "high" if confidence_pct >= 65 else "medium" if confidence_pct >= 35 else "low"

    matched_signals = [kw for kw in KEYWORD_MAP[best_intent]["primary"] + KEYWORD_MAP[best_intent]["secondary"] if kw in t]

    secondary_intents = [
        intent for intent, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
        if score > 0 and intent != best_intent
    ][:2]

    # Urgency scoring
    urgency_score = 0
    for level, words in URGENCY_SIGNALS.items():
        hits = sum(1 for w in words if w in t)
        if level == "critical":
            urgency_score += hits * 4
        elif level == "high":
            urgency_score += hits * 3
        elif level == "medium":
            urgency_score += hits * 2
        elif level == "low":
            urgency_score += hits * 1
    urgency_score = min(urgency_score, 10)
    urgency_level = "high" if urgency_score >= 7 else "medium" if urgency_score >= 3 else "low"

    # Sentiment
    pos_hits = sum(1 for w in POSITIVE_SIGNALS if w in t)
    neg_hits = sum(1 for w in NEGATIVE_SIGNALS if w in t)
    if pos_hits > neg_hits * 1.5:
        sentiment = "positive"
    elif neg_hits > pos_hits * 1.5:
        sentiment = "anxious" if urgency_score >= 5 else "concerned"
    else:
        sentiment = "neutral"

    # Persona detection — score by age + keywords
    detected_age = detect_age_from_text(t)
    persona_scores = {}
    for persona, data in PERSONA_SIGNALS.items():
        kw_hits = sum(2 for kw in data["keywords"] if kw in t)
        age_hit = 1 if (detected_age and detected_age in data["ages"]) else 0
        persona_scores[persona] = kw_hits + age_hit

    top_persona = max(persona_scores, key=persona_scores.get)
    if persona_scores[top_persona] == 0:
        # Fallback: guess from age if available
        if detected_age:
            if detected_age < 30:       top_persona = "young_professional"
            elif detected_age < 40:     top_persona = "young_parent"
            elif detected_age < 50:     top_persona = "mid_career"
            elif detected_age < 60:     top_persona = "pre_retiree"
            else:                       top_persona = "senior"
        else:
            top_persona = "general_client"

    word_count = len(text.split())
    engagement = "high" if word_count > 80 else "medium" if word_count > 30 else "low"

    # Build a more useful summary
    intent_labels = {"family":"family protection","health":"health coverage","investment":"wealth investment",
                     "child":"child education planning","business":"business protection","term":"term life cover"}
    summary = (f"Client's primary need is {intent_labels.get(best_intent, best_intent)} "
               f"({confidence} confidence, {confidence_pct}% signal strength). "
               f"Urgency is {urgency_level} — {urgency_score}/10 on urgency scale.")

    return {
        "intent":            best_intent,
        "secondary_intents": secondary_intents,
        "confidence":        confidence,
        "confidence_pct":    confidence_pct,
        "all_scores":        scores,
        "key_signals":       matched_signals[:5],
        "urgency":           urgency_level,
        "urgency_score":     urgency_score,
        "sentiment":         sentiment,
        "persona":           top_persona,
        "detected_age":      detected_age,
        "engagement":        engagement,
        "word_count":        word_count,
        "summary":           summary,
        "coaching_tips":     [],
        "objections_to_expect": [],
        "opening_line":      "",
        "deal_strategy":     "",
        "mode":              "rule-based v4"
    }


# ============================================================
# CLAUDE AI ANALYSIS
# ============================================================

def analyze_client_ai(text, api_key):
    client = anthropic.Anthropic(api_key=api_key)

    system_prompt = """You are an elite insurance sales coach, behavioral analyst, and product specialist with 25+ years of experience in Indian and global insurance markets.

Analyze the client conversation below and return ONLY a JSON object — no markdown, no explanation, just raw JSON.

ANALYSIS GUIDELINES:
- Read between the lines: what is the client REALLY worried about?
- Detect SPECIFIC life triggers: new baby, job change, illness diagnosis, loan, divorce, business risk
- Intent should reflect PRIMARY need, but note secondary needs too
- Urgency is not just about words — infer from life stage and situation
- Coaching tips must be hyper-specific to THIS client, not generic advice
- Objections should reflect what THIS client will actually say
- Opening line should make the client feel understood immediately
- Deal strategy should name specific products and techniques

Return exactly this structure:
{
  "intent": "<family | health | investment | child | business | term>",
  "secondary_intents": ["<up to 2 other relevant intents>"],
  "confidence": "<high | medium | low>",
  "confidence_pct": <0-100>,
  "summary": "<2 crisp sentences: what this client REALLY needs and the emotional driver behind it>",
  "key_signals": ["<3-5 EXACT phrases from the text that reveal intent — quote them directly>"],
  "client_profile": "<one vivid sentence: age/life stage/income level/family situation/specific risk>",
  "persona": "<young_professional | young_parent | mid_career | pre_retiree | senior | business_owner | general_client>",
  "sentiment": "<positive | neutral | concerned | anxious>",
  "urgency": "<high | medium | low>",
  "urgency_score": <1-10>,
  "urgency_reason": "<one sentence: WHY this is urgent for this specific client>",
  "engagement": "<high | medium | low>",
  "coaching_tips": [
    "<Tip 1: specific question or statement that addresses this client's exact fear or desire>",
    "<Tip 2: a data point or scenario that creates emotional urgency for THIS client>",
    "<Tip 3: exact framing technique or anchoring strategy for this client's budget/profile>"
  ],
  "objections_to_expect": [
    "<Most likely objection word-for-word as client would say it>",
    "<Second likely objection>",
    "<Third likely objection>"
  ],
  "objection_responses": {
    "<objection 1>": "<exact response to use>",
    "<objection 2>": "<exact response to use>",
    "<objection 3>": "<exact response to use>"
  },
  "opening_line": "<the single most powerful, empathetic opening sentence that will make this client say 'yes exactly'>",
  "deal_strategy": "<one paragraph: step-by-step how to structure THIS specific sales conversation — anchor price, product sequence, close technique>",
  "cross_sell_hint": "<one sentence: which complementary product to introduce and the exact moment/trigger to mention it>",
  "life_trigger": "<the key life event or situation driving this need right now>",
  "mode": "claude-ai v4"
}"""

    message = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=1500,
        system=system_prompt,
        messages=[{"role": "user", "content": f"Client conversation:\n\n{text}"}]
    )

    raw = message.content[0].text.strip()
    raw = re.sub(r"^```json\s*", "", raw)
    raw = re.sub(r"\s*```$",    "", raw)

    return json.loads(raw)


# ============================================================
# MAIN ENTRY POINT
# ============================================================

def analyze_client(text, api_key=None):
    if api_key and api_key.strip() and ANTHROPIC_AVAILABLE:
        try:
            return analyze_client_ai(text, api_key)
        except Exception as e:
            result          = analyze_client_rules(text)
            result["ai_error"] = str(e)
            result["mode"]  = "rule-based v4 (AI fallback)"
            return result

    return analyze_client_rules(text)


# ============================================================
# DISPLAY HELPERS
# ============================================================

def get_intent_label(intent):
    labels = {
        "family":     {"emoji": "👨‍👩‍👧‍👦", "label": "Family Protection",   "color": "#4a90e2", "gradient": "linear-gradient(135deg, #0d2040, #0a1828)"},
        "health":     {"emoji": "🏥",         "label": "Health Coverage",     "color": "#50c878", "gradient": "linear-gradient(135deg, #0a2010, #051408)"},
        "investment": {"emoji": "📈",         "label": "Investment & Wealth", "color": "#f5a623", "gradient": "linear-gradient(135deg, #2a1a00, #1a1000)"},
        "child":      {"emoji": "🎓",         "label": "Child Future Plan",   "color": "#bd10e0", "gradient": "linear-gradient(135deg, #1a0828, #0d0518)"},
        "business":   {"emoji": "🏢",         "label": "Business Protection", "color": "#e85d4a", "gradient": "linear-gradient(135deg, #2a0d08, #1a0804)"},
        "term":       {"emoji": "🛡️",         "label": "Term Life Cover",     "color": "#7ed321", "gradient": "linear-gradient(135deg, #122008, #0a1404)"},
    }
    return labels.get(intent, {"emoji": "📋", "label": "General Insurance", "color": "#8892b0", "gradient": "linear-gradient(135deg, #1a1f36, #0d1020)"})


def get_persona_label(persona):
    personas = {
        "young_professional": {"label": "Young Professional",  "emoji": "💼"},
        "young_parent":       {"label": "Young Parent",        "emoji": "👶"},
        "mid_career":         {"label": "Mid-Career Adult",    "emoji": "📊"},
        "pre_retiree":        {"label": "Pre-Retiree",         "emoji": "🏖️"},
        "senior":             {"label": "Senior Citizen",      "emoji": "👴"},
        "business_owner":     {"label": "Business Owner",      "emoji": "🏢"},
        "general_client":     {"label": "General Client",      "emoji": "👤"},
    }
    return personas.get(persona, {"label": persona.replace("_", " ").title(), "emoji": "👤"})


# ============================================================
# COACHING DATA (rule-based fallback — improved specificity)
# ============================================================

COACHING_TIPS = {
    "family": [
        "💬 Ask: 'If you weren't here tomorrow, how long could your family maintain their current lifestyle on savings alone?' — let the silence work.",
        "📊 Run the income replacement math live: monthly expenses × 12 × years until youngest child is independent. Show it in writing.",
        "🎯 Anchor with Family Elite Protect ($2,200/yr = $183/month = $6/day), then offer Family Shield Plus as the 'smart middle ground' at 45% less cost."
    ],
    "health": [
        "💬 Ask: 'One ICU stay averages $40,000+ out of pocket — how many months of salary is that for you right now?'",
        "📊 Pull up a real hospital bill example for the city they're in. Concrete local numbers beat generic stats every time.",
        "🎯 Lead with Critical Illness Guard (lump-sum $1M, 50+ conditions) — the income replacement angle resonates more than just hospital bills."
    ],
    "investment": [
        "💬 Ask: 'If Rs.3,000/month starts today vs. 5 years later, the difference at retirement is over Rs.40 lakhs. Should I show you the projection?'",
        "📊 Draw the compound curve: show Retirement Income Plus's 25-year projection with and without the plan. The visual gap closes the deal.",
        "🎯 Retirement Income Plus (score 97) + Tax savings angle: 'You save Rs.90,000 in tax in year 1 alone — the plan essentially pays for itself.'"
    ],
    "child": [
        "💬 Ask: 'College fees are doubling every 8 years. What's your current plan when your child turns 18?' — then wait.",
        "📊 Show the education inflation calculator: today's Rs.20L degree = Rs.80L in 18 years. The gap number creates urgency no feature list can.",
        "🎯 Close on the waiver clause: 'Even if you're gone, this policy continues — your child gets their education funded no matter what.' That's the emotional anchor."
    ],
    "business": [
        "💬 Ask: 'If your most important person was out for 6 months tomorrow, what would that cost your business? Let's calculate it together.'",
        "📊 Revenue risk calculation: key person's contribution × 6 months realistic downtime. Show the number in writing — it's always bigger than expected.",
        "🎯 Business Continuity Shield (score 96): frame as 'business life insurance — every business owner needs it, just like they need fire insurance for their office.'"
    ],
    "term": [
        "💬 Ask: 'For Rs.50/day — less than your morning chai — you can give your family a Rs.1 crore safety net. Is that a trade-off worth making?'",
        "📊 Premium comparison table: term is 8-10x cheaper than whole life for identical coverage. Show the math side-by-side.",
        "🎯 Always upsell to Term Plus Rider Bundle — accidental death 2x payout + critical illness cover. It's 58% more premium for 300% more protection value."
    ]
}

OBJECTION_HANDLERS = {
    "too expensive":             "Reframe to daily cost: 'Rs.1,200/year = Rs.3.30/day — less than a coffee. Is your family's safety worth Rs.3/day?'",
    "i'll think about it":       "Soft urgency: 'Absolutely — take your time. Just so you know, your premium locks in at today's rate. Every year older adds Rs.X to the annual cost. Want me to show you?'",
    "i already have insurance":  "Gap analysis: 'Great — most people find their existing cover handles only 30-40% of actual needs after inflation. Can I run a 2-minute gap check at zero cost?'",
    "i don't need it":           "Third-party story: 'I had a client say the exact same thing. Six months later, his wife was diagnosed with stage 2 cancer. The Rs.900/year policy paid out Rs.10 lakhs. He calls it his best decision.'",
    "not the right time":        "Time-value flip: 'The best time to buy insurance is always when you're young and healthy — that's right now. Future-you will thank present-you for this decision.'",
    "let me discuss with wife":  "Include the spouse: 'Of course — she should absolutely be part of this decision since it protects her too. Can we set up a quick 15-minute call with both of you this week?'",
    "returns are low":           "Reframe insurance vs investment: 'Insurance isn't an investment — it's a risk transfer. You wouldn't expect your car insurance to give returns. The value is the Rs.1 crore when you need it most.'",
    "company may not pay claim": "Build trust with data: 'Fair concern. This company has a 98.5% claim settlement rate — that means 985 out of 1,000 claims are paid. I can show you the IRDAI data right now.'"
}
