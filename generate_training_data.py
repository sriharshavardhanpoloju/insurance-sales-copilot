# ============================================================
# generate_training_data.py
# Generates 500+ synthetic client scenarios with ground-truth
# policy labels. Run this FIRST before train_model.py.
#
# Usage:  python generate_training_data.py
# Output: training_data.json
#         training_data.jsonl
#         training_data_claude.jsonl  ← used by train_model.py
# ============================================================

import json, random, os

random.seed(42)

POLICY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "policies.json")
with open(POLICY_FILE) as f:
    ALL_POLICIES = json.load(f)

POLICIES_BY_TYPE = {}
for p in ALL_POLICIES:
    POLICIES_BY_TYPE.setdefault(p["type"], []).append(p)
for t in POLICIES_BY_TYPE:
    POLICIES_BY_TYPE[t].sort(key=lambda p: p["profit_score"], reverse=True)

# ── Client building blocks ──────────────────────────────────

NAMES = [
    "Rahul Sharma","Priya Patel","Amit Verma","Sunita Reddy","Vikram Singh",
    "Anita Joshi","Ravi Kumar","Deepa Nair","Suresh Gupta","Kavitha Menon",
    "Arjun Mehta","Pooja Iyer","Sanjay Chopra","Neha Agarwal","Rohit Tiwari",
    "Divya Pillai","Manoj Rao","Sneha Desai","Vijay Shah","Rekha Bhat",
    "Kiran Patil","Meena Choudhary","Ajay Saxena","Geeta Kulkarni","Tarun Malhotra",
]

OCCUPATIONS = {
    "family":     ["software engineer","school teacher","government employee","bank officer","doctor"],
    "health":     ["IT professional","factory worker","nurse","accountant","sales executive"],
    "investment": ["senior manager","CA","businessman","entrepreneur","consultant"],
    "child":      ["engineer","teacher","manager","government officer","HR professional"],
    "business":   ["business owner","startup founder","SME director","trader","manufacturer"],
    "term":       ["fresher","junior executive","call center agent","delivery driver","factory worker"],
}

BUDGET_MAP = {
    "family":     [(800,1500),(1200,2000),(2000,3500)],
    "health":     [(400,800),(800,1500),(1500,2500)],
    "investment": [(1500,3000),(3000,5000),(5000,8000)],
    "child":      [(700,1200),(1000,1800),(1800,3000)],
    "business":   [(2000,4000),(4000,7000),(7000,12000)],
    "term":       [(400,700),(600,1000),(900,1500)],
}

AGE_MAP = {
    "family":(25,45), "health":(22,65), "investment":(28,55),
    "child":(25,45),  "business":(28,58), "term":(20,45),
}

TEMPLATES = {
    "family": [
        "{name} is {age} years old, married with {kids} kid(s), works as a {job}. "
        "Sole breadwinner earning Rs.{income}/month. Very worried about family's financial security if something happens. "
        "Budget Rs.{budget}/month for insurance.",

        "Client {name}, age {age}. Spouse and {kids} children depend entirely on {them}. "
        "{job} by profession. Recently lost a colleague and became serious about family protection. "
        "Budget Rs.{budget}/month.",

        "{name}, {age}, recently had a baby. Both partners anxious about the child's future. "
        "Works as {job}. Wants strong family protection plan. Monthly budget: Rs.{budget}.",

        "{name} is {age}, a {job} with {kids} dependents including aging parents. "
        "Only earner in the family. Needs comprehensive family cover. Budget Rs.{budget}/month.",

        "Met {name} today — {age} years old, married, {kids} kids. {job} profession. "
        "Said if something happens to {them}, family has no backup plan. Budget Rs.{budget}/month.",
    ],
    "health": [
        "{name}, age {age}, {job}. Had a health scare recently. No medical cover at all. "
        "Wants cashless hospitalization and zero co-pay. Budget Rs.{budget}/month.",

        "Client {name}, {age}. Family history of diabetes and heart disease. "
        "Works as {job}. Wants critical illness and pre-existing condition cover. Budget Rs.{budget}/month.",

        "{name}, {age}, was hospitalized last month. Bills wiped out savings. "
        "Now wants proper health insurance. {job}. Budget Rs.{budget}/month.",

        "{name} is {age}, a {job} with no employer health cover. "
        "Very worried about hospital costs. Needs cashless cover at good hospitals. Budget Rs.{budget}/month.",

        "{name}, {age}, senior client. Diagnosed with chronic condition. "
        "Wants plan covering pre-existing diseases. Retired {job}. Budget Rs.{budget}/month.",
    ],
    "investment": [
        "{name} is {age}, {job}. Has surplus income and wants to invest. "
        "Interested in market-linked returns with life cover. Planning to retire at 60. Budget Rs.{budget}/month.",

        "Client {name}, {age}. Works as {job} earning well. Wants ULIP or endowment plan with tax benefits. "
        "Focused on long-term wealth growth. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. Wants retirement corpus. Asking about pension and annuity options. "
        "Wants monthly income after retirement. Can invest Rs.{budget}/month.",

        "{name} is {age}, high-income {job}. Wants guaranteed returns and maturity benefit. "
        "Not interested in pure risk cover — wants investment component. Budget Rs.{budget}/month.",

        "Meeting with {name}, {age}. Worried about retirement savings gap. "
        "Works as {job}. Wants plan giving lifelong pension. Can commit Rs.{budget}/month.",
    ],
    "child": [
        "{name}, {age}, has a {child_age}-year-old child. Worried about education costs in 15 years. "
        "{job} profession. Wants plan maturing when child turns 18. Budget Rs.{budget}/month.",

        "Client {name}, {age}. Has young daughter. Wants to secure her education and marriage. "
        "Very emotional — wants protection even if something happens to {them}. {job}. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. Has two kids aged {child_age} and {child_age2}. "
        "Wants child savings plan with waiver benefit. Focused on education fund. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. Very focused on child's college fund. "
        "Wants guaranteed education payouts. Asked specifically about child plans. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. New parent — baby is {child_age} months old. "
        "Wants to start saving early. Needs parent death waiver feature. Budget Rs.{budget}/month.",
    ],
    "business": [
        "{name} owns a {business_size}-person {business_type}. Worried about business continuity "
        "if key person is lost. Wants keyman insurance and liability cover. Budget Rs.{budget}/month.",

        "Client {name}, {age}, startup founder. Company has {business_size} employees. "
        "Wants business protection, keyman cover, group health. Budget Rs.{budget}/month.",

        "{name}, {age}, runs a {business_type} with {business_size} staff. "
        "Wants cover if partner or director dies suddenly. Business must continue. Budget Rs.{budget}/month.",

        "{name}, {age}, owns {business_type}. Business has Rs.{loan}L bank loan. "
        "Wants policy to repay loan if {pronoun_lc} dies. Also needs group employee cover. Budget Rs.{budget}/month.",

        "{name}, {age}, built a {business_type} over 10 years. Wants to protect what was built. "
        "Interested in comprehensive business protection. Budget Rs.{budget}/month.",
    ],
    "term": [
        "{name}, {age}, just started working as {job}. Wants cheapest life insurance. "
        "Only needs basic cover — no investment component at all. Budget Rs.{budget}/month.",

        "Client {name}, {age}, {job}. Wants pure term with high coverage and low premium. "
        "Not interested in savings features. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. First-time insurance buyer. Wants simple affordable term plan. "
        "Said: just give me coverage, nothing else. Budget Rs.{budget}/month.",

        "{name}, {age}, {job}. Very price-sensitive. Wants maximum life cover for minimum premium. "
        "Specifically asking for term plan only. Budget Rs.{budget}/month.",

        "{name}, {age}, {job} on a modest salary. Needs basic life cover for family. "
        "Very clear: term only, nothing fancy, keep premium low. Budget Rs.{budget}/month.",
    ],
}

# ── Ground truth scoring ────────────────────────────────────

def get_best_policies(intent, age, budget_monthly, income_level):
    annual_budget = budget_monthly * 12
    candidates = POLICIES_BY_TYPE.get(intent, [])
    scored = []
    for p in candidates:
        if not (p["min_age"] <= age <= p["max_age"]):
            continue
        if p["premium"] > annual_budget * 1.3:
            continue
        fit = p["profit_score"]
        if p["premium"] <= annual_budget:
            fit += 5
        if income_level == "high" and p["profit_score"] >= 90:
            fit += 3
        scored.append((fit, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "policy_id":    p["id"],
            "policy_name":  p["name"],
            "premium":      p["premium"],
            "coverage":     p["coverage"],
            "profit_score": p["profit_score"],
            "reason": (
                f"Best fit for {intent} client aged {age}. "
                f"Profit score {p['profit_score']}/100. "
                f"Premium ${p['premium']:,}/yr within budget. "
                f"{p['claim_settlement']}% claim settlement rate."
            ),
        }
        for _, p in scored[:3]
    ]

# ── Conversation builder ────────────────────────────────────

def build_example(intent):
    template = random.choice(TEMPLATES[intent])
    name     = random.choice(NAMES)
    age      = random.randint(*AGE_MAP[intent])
    job      = random.choice(OCCUPATIONS[intent])
    budget   = random.randint(*random.choice(BUDGET_MAP[intent]))
    income   = budget * random.randint(8, 15)
    kids     = random.randint(1, 3)
    child_age  = random.randint(1, 12)
    child_age2 = random.randint(1, max(1, child_age - 1))
    biz_size = random.choice([5, 10, 15, 20, 30, 50])
    biz_type = random.choice(["IT firm","trading company","manufacturing unit","retail chain","consultancy"])
    loan     = random.choice([20, 30, 50, 75, 100])
    gender   = random.choice(["male", "female"])
    pronoun    = "He" if gender == "male" else "She"
    pronoun_lc = pronoun.lower()
    them       = "him" if gender == "male" else "her"

    text = template.format(
        name=name, age=age, job=job, budget=budget, income=income,
        kids=kids, child_age=child_age, child_age2=child_age2,
        business_size=biz_size, business_type=biz_type, loan=loan,
        pronoun=pronoun, pronoun_lc=pronoun_lc, them=them,
    )

    income_level = "high" if budget > 2500 else "medium" if budget > 1000 else "low"
    best = get_best_policies(intent, age, budget, income_level)

    return {
        "conversation": text,
        "intent": intent,
        "client": {"name": name, "age": age, "job": job,
                   "budget_monthly": budget, "income_level": income_level},
        "ground_truth": {
            "top_policy":      best[0] if best else None,
            "all_recommended": best,
        },
    }

# ── Generate & save ─────────────────────────────────────────

def generate_dataset(n_per_intent=85):
    intents = ["family","health","investment","child","business","term"]
    data = []
    for intent in intents:
        for _ in range(n_per_intent):
            data.append(build_example(intent))
    random.shuffle(data)
    n = len(data)
    t, v = int(n * 0.80), int(n * 0.90)
    return {
        "train": data[:t], "val": data[t:v], "test": data[v:],
        "meta": {"total": n, "train_size": t, "val_size": v - t,
                 "test_size": n - v, "intents": intents,
                 "n_per_intent": n_per_intent},
    }

def save_dataset(ds, out_dir=None):
    out_dir = out_dir or os.path.dirname(os.path.abspath(__file__))

    # Full JSON
    p1 = os.path.join(out_dir, "training_data.json")
    with open(p1, "w") as f:
        json.dump(ds, f, indent=2)

    # JSONL (all splits)
    p2 = os.path.join(out_dir, "training_data.jsonl")
    with open(p2, "w") as f:
        for split in ["train","val","test"]:
            for ex in ds[split]:
                f.write(json.dumps({**ex, "split": split}) + "\n")

    # Claude prompt/completion format (train + val only)
    p3 = os.path.join(out_dir, "training_data_claude.jsonl")
    with open(p3, "w") as f:
        for ex in ds["train"] + ds["val"]:
            top = ex["ground_truth"]["top_policy"]
            if not top:
                continue
            prompt = (
                "You are an expert insurance policy recommender.\n\n"
                f"Client conversation:\n\"{ex['conversation']}\"\n\n"
                "Recommend the single best policy. Reply ONLY with JSON:\n"
                "{\"policy_id\": ..., \"policy_name\": ..., \"reason\": ..., \"confidence\": ...}"
            )
            completion = json.dumps({
                "policy_id":   top["policy_id"],
                "policy_name": top["policy_name"],
                "reason":      top["reason"],
                "confidence":  "high" if ex["client"]["income_level"] != "low" else "medium",
            })
            f.write(json.dumps({"prompt": prompt, "completion": completion,
                                "intent": ex["intent"]}) + "\n")

    return p1, p2, p3

if __name__ == "__main__":
    print("Generating synthetic training data...")
    ds = generate_dataset(n_per_intent=85)
    m  = ds["meta"]
    print(f"Generated {m['total']} examples  |  Train {m['train_size']} / Val {m['val_size']} / Test {m['test_size']}")

    p1, p2, p3 = save_dataset(ds)
    print(f"\nSaved:\n  {p1}\n  {p2}\n  {p3}")
    print("\nRun next:  python train_model.py")
