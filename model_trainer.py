# ============================================================
# model_trainer.py
#
# Builds a Claude prompt-chain "model" trained on the synthetic
# dataset. Because we're using Claude (not training weights),
# "training" means:
#
#   1. Loading all training examples
#   2. Selecting the best few-shot examples per intent (in-context learning)
#   3. Building an optimised system prompt from patterns in the data
#   4. Evaluating accuracy on the val set
#   5. Saving the final model config to model_config.json
#
# Run: python model_trainer.py --api_key sk-ant-...
#      (API key optional — runs eval without it)
# ============================================================

import json
import os
import random
import argparse
from collections import defaultdict

BASE = os.path.dirname(os.path.abspath(__file__))


# ── Load data ─────────────────────────────────────────────

def load_jsonl(path):
    examples = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                examples.append(json.loads(line))
    return examples


def load_full_json(path):
    with open(path) as f:
        return json.load(f)


# ── Step 1: Analyse training data patterns ─────────────────

def analyse_dataset(examples):
    """Extract patterns from training data to inform the system prompt."""
    print("\n📊 Analysing training data patterns...")

    intent_policy_map  = defaultdict(list)    # intent → most recommended policies
    budget_policy_map  = defaultdict(list)    # budget tier → policy ids
    age_policy_map     = defaultdict(list)    # age group → policy ids

    for ex in examples:
        intent  = ex["intent"]
        top_id  = ex["correct_output"]["top_policy_id"]
        client  = ex["client"]

        intent_policy_map[intent].append(top_id)

        # Budget tiers
        budget = client["monthly_budget"]
        tier = "low" if budget < 1000 else "mid" if budget < 3000 else "high"
        budget_policy_map[f"{intent}_{tier}"].append(top_id)

        # Age groups
        age = client["age"]
        age_grp = "young" if age < 35 else "mid" if age < 50 else "senior"
        age_policy_map[f"{intent}_{age_grp}"].append(top_id)

    # Compute most common policy per intent
    patterns = {}
    for intent, policy_ids in intent_policy_map.items():
        from collections import Counter
        counter  = Counter(policy_ids)
        patterns[intent] = {
            "top_policy":    counter.most_common(1)[0][0],
            "distribution":  dict(counter.most_common()),
        }

    print(f"   Intents found : {list(patterns.keys())}")
    for intent, pat in patterns.items():
        print(f"   {intent:12s}: top={pat['top_policy']}, dist={pat['distribution']}")

    return patterns, intent_policy_map, budget_policy_map, age_policy_map


# ── Step 2: Select best few-shot examples per intent ──────

def select_few_shot_examples(full_examples, n_per_intent=2):
    """
    Pick the best n examples per intent to use as few-shot demonstrations.
    Selects examples with the highest fit_score for the top policy.
    """
    print(f"\n🎯 Selecting {n_per_intent} few-shot examples per intent...")

    by_intent = defaultdict(list)
    for ex in full_examples:
        by_intent[ex["intent"]].append(ex)

    few_shot = {}
    for intent, exs in by_intent.items():
        # Sort by top policy fit score descending
        sorted_exs = sorted(
            exs,
            key=lambda e: e["correct_output"]["ranked"][0]["fit_score"],
            reverse=True
        )
        # Pick diverse examples (different budgets)
        selected = []
        seen_budgets = set()
        for ex in sorted_exs:
            budget_tier = "low" if ex["client"]["monthly_budget"] < 1000 else \
                          "mid" if ex["client"]["monthly_budget"] < 3000 else "high"
            if budget_tier not in seen_budgets or len(selected) < n_per_intent:
                selected.append(ex)
                seen_budgets.add(budget_tier)
            if len(selected) >= n_per_intent:
                break
        few_shot[intent] = selected
        print(f"   {intent:12s}: selected {len(selected)} examples")

    return few_shot


# ── Step 3: Build the optimised system prompt ──────────────

def build_system_prompt(patterns, policies):
    """
    Build a rich system prompt that encodes learned patterns from training data.
    This IS the "trained" knowledge — embedded into the prompt chain.
    """

    # Build policy index
    policy_index = {p["id"]: p for p in policies}

    policy_summary = json.dumps([
        {
            "id":               p["id"],
            "name":             p["name"],
            "type":             p["type"],
            "premium_annual":   p["premium"],
            "coverage":         p["coverage"],
            "profit_score":     p["profit_score"],
            "claim_settlement": p["claim_settlement"],
            "min_age":          p["min_age"],
            "max_age":          p["max_age"],
            "highlights":       p["highlights"],
            "ideal_for":        p["ideal_for"],
        }
        for p in policies
    ], indent=2)

    # Learned pattern rules from training data
    pattern_rules = []
    for intent, pat in patterns.items():
        top_id     = pat["top_policy"]
        top_policy = policy_index.get(top_id, {})
        top_name   = top_policy.get("name", top_id)
        pattern_rules.append(
            f"- For {intent.upper()} clients: '{top_name}' is most frequently optimal "
            f"(profit_score={top_policy.get('profit_score','?')}, "
            f"claim={top_policy.get('claim_settlement','?')}%)"
        )

    rules_text = "\n".join(pattern_rules)

    system_prompt = f"""You are an expert insurance policy recommender with deep knowledge of client profiling.
You have been trained on 540 synthetic client profiles and know exactly which policies maximise both client fit and agent commission.

## POLICY DATABASE
{policy_summary}

## LEARNED PATTERNS (from training data)
{rules_text}

## SCORING FORMULA (use this to rank policies)
fit_score = (profit_score × 0.40) + (claim_settlement × 0.20) + age_fit_bonus(15) + budget_fit_bonus(15) + coverage_value_bonus(10)

## RULES
1. ALWAYS check age eligibility (min_age ≤ client_age ≤ max_age). A policy outside age range scores -20.
2. ALWAYS check budget fit. Annual premium ÷ 12 must be ≤ monthly_budget × 1.3. Else score -15.
3. Rank by fit_score descending. Top = best recommendation.
4. If client mentions specific concerns (hospital, family, retirement), weight matching policy type +10.
5. Return ONLY valid JSON — no markdown, no explanation outside the JSON.

## OUTPUT FORMAT
Return exactly this JSON structure:
{{
  "top_policy_id":      "<policy ID>",
  "top_policy_name":    "<policy name>",
  "ranked_policy_ids":  ["<id1>", "<id2>", "<id3>"],
  "ranked_policy_names":["<name1>", "<name2>", "<name3>"],
  "fit_scores":         {{"<id>": <score>, ...}},
  "reasoning":          "<2-3 sentences explaining the top recommendation>",
  "key_factors":        {{"age_fit": true/false, "budget_fit": true/false, "profit_score": <n>, "claim_rate": <n>}}
}}"""

    return system_prompt


# ── Step 4: Evaluate on validation set (with or without API) ─

def evaluate_rule_based(val_examples, few_shot_map, system_prompt):
    """
    Evaluate accuracy using rule-based simulation (no API key needed).
    Simulates what the Claude prompt chain would do.
    """
    print("\n🧪 Evaluating on validation set (rule-based simulation)...")

    with open(os.path.join(BASE, "policies.json")) as f:
        policies = json.load(f)

    from collections import Counter
    correct     = 0
    top3_correct = 0
    total        = len(val_examples)
    intent_acc   = defaultdict(lambda: [0, 0])   # [correct, total]

    for ex in val_examples:
        # Simulate scoring
        intent  = ex["messages"][1]["content"].split("(")[1].split(")")[0].strip()
        correct_top = None

        # Parse the assistant message (ground truth)
        try:
            gt = json.loads(ex["messages"][2]["content"])
            correct_top     = gt["top_policy_id"]
            correct_ranked  = gt["ranked_policy_ids"]
        except Exception:
            continue

        # Simulate our recommender: score all policies for this intent
        candidate_policies = [p for p in policies if p["type"] == intent]

        # Extract client info from user message
        user_msg = ex["messages"][1]["content"]
        age      = 35   # default if parsing fails
        budget   = 1500

        import re
        age_match    = re.search(r'(\d{2})\s*years?\s*old', user_msg)
        budget_match = re.search(r'Rs\.(\d+)', user_msg)
        if age_match:    age    = int(age_match.group(1))
        if budget_match: budget = int(budget_match.group(1))

        scored = []
        for p in candidate_policies:
            s = p["profit_score"] * 0.4
            s += (p["claim_settlement"] / 100) * 20
            if p["min_age"] <= age <= p["max_age"]: s += 15
            else: s -= 20
            monthly = p["premium"] / 12
            if monthly <= budget: s += 15
            elif monthly <= budget * 1.3: s += 8
            else: s -= 15
            scored.append((p["id"], s))

        scored.sort(key=lambda x: x[1], reverse=True)
        predicted_top   = scored[0][0] if scored else None
        predicted_top3  = [s[0] for s in scored[:3]]

        if predicted_top == correct_top:
            correct += 1
            intent_acc[intent][0] += 1
        if correct_top in predicted_top3:
            top3_correct += 1
        intent_acc[intent][1] += 1

    top1_acc = round(correct / total * 100, 1)
    top3_acc = round(top3_correct / total * 100, 1)

    print(f"\n   📈 Validation Results ({total} examples):")
    print(f"   Top-1 Accuracy : {top1_acc}%  ({correct}/{total})")
    print(f"   Top-3 Accuracy : {top3_acc}%  ({top3_correct}/{total})")
    print(f"\n   Per-intent accuracy:")
    for intent, (c, t) in sorted(intent_acc.items()):
        print(f"   {intent:12s}: {round(c/t*100,1)}%  ({c}/{t})")

    return top1_acc, top3_acc


def evaluate_with_api(val_examples, system_prompt, api_key, n_samples=20):
    """
    Evaluate a sample using the real Claude API.
    """
    try:
        import anthropic
    except ImportError:
        print("   anthropic not installed, skipping API eval")
        return None

    print(f"\n🤖 Evaluating {n_samples} examples with Claude API...")
    client   = anthropic.Anthropic(api_key=api_key)
    sample   = random.sample(val_examples, min(n_samples, len(val_examples)))
    correct  = 0

    for i, ex in enumerate(sample):
        try:
            gt = json.loads(ex["messages"][2]["content"])
            correct_top = gt["top_policy_id"]

            response = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=600,
                system=system_prompt,
                messages=[{"role": "user", "content": ex["messages"][1]["content"]}]
            )
            raw = response.content[0].text.strip()
            import re as re2
            raw = re2.sub(r'^```json\s*', '', raw)
            raw = re2.sub(r'\s*```$', '', raw)
            result = json.loads(raw)

            if result.get("top_policy_id") == correct_top:
                correct += 1
            print(f"   [{i+1}/{n_samples}] Predicted: {result.get('top_policy_id')} | Correct: {correct_top} {'✅' if result.get('top_policy_id') == correct_top else '❌'}")

        except Exception as e:
            print(f"   [{i+1}/{n_samples}] Error: {e}")

    api_acc = round(correct / len(sample) * 100, 1)
    print(f"\n   API Accuracy: {api_acc}% ({correct}/{len(sample)})")
    return api_acc


# ── Step 5: Save model config ──────────────────────────────

def save_model_config(system_prompt, few_shot_map, patterns, top1_acc, top3_acc):
    """Save the trained model config — this is what the app loads at runtime."""

    # Convert few_shot_map to serialisable format
    few_shot_serialisable = {}
    for intent, examples in few_shot_map.items():
        few_shot_serialisable[intent] = [
            {
                "conversation": ex["conversation"],
                "output": ex["correct_output"],
            }
            for ex in examples
        ]

    config = {
        "model_version":  "1.0",
        "trained_on":     "540 synthetic examples (90 per intent)",
        "intents":        list(patterns.keys()),
        "top1_accuracy":  top1_acc,
        "top3_accuracy":  top3_acc,
        "system_prompt":  system_prompt,
        "few_shot_examples": few_shot_serialisable,
        "learned_patterns":  patterns,
    }

    config_path = os.path.join(BASE, "model_config.json")
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"\n💾 Model config saved → {config_path}")
    print(f"   System prompt length: {len(system_prompt)} chars")
    print(f"   Few-shot examples:    {sum(len(v) for v in few_shot_serialisable.values())} total")
    return config_path


# ── Main ───────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train the insurance recommender prompt chain")
    parser.add_argument("--api_key", type=str, default=None, help="Anthropic API key for live eval")
    parser.add_argument("--n_per_intent", type=int, default=90, help="Training examples per intent")
    parser.add_argument("--few_shot", type=int, default=2, help="Few-shot examples per intent")
    args = parser.parse_args()

    print("=" * 60)
    print("  Insurance Recommender — Prompt Chain Trainer")
    print("=" * 60)

    # Check training data exists
    train_path = os.path.join(BASE, "train.jsonl")
    val_path   = os.path.join(BASE, "val.jsonl")
    full_path  = os.path.join(BASE, "training_data.json")

    if not os.path.exists(train_path):
        print("⚠️  Training data not found. Running generator first...")
        import generate_training_data as gen
        examples = gen.generate_dataset(n_per_intent=args.n_per_intent)
        gen.save_dataset(examples)

    train_examples = load_jsonl(train_path)
    val_examples   = load_jsonl(val_path)
    full_examples  = load_full_json(full_path)

    print(f"\n📂 Loaded {len(train_examples)} train, {len(val_examples)} val examples")

    # Load policies
    with open(os.path.join(BASE, "policies.json")) as f:
        policies = json.load(f)

    # Step 1: Analyse
    patterns, intent_map, budget_map, age_map = analyse_dataset(full_examples)

    # Step 2: Few-shot selection
    few_shot_map = select_few_shot_examples(full_examples, n_per_intent=args.few_shot)

    # Step 3: Build system prompt
    print("\n🔧 Building optimised system prompt...")
    system_prompt = build_system_prompt(patterns, policies)
    print(f"   System prompt: {len(system_prompt)} characters")

    # Step 4: Evaluate
    top1_acc, top3_acc = evaluate_rule_based(val_examples, few_shot_map, system_prompt)

    if args.api_key:
        evaluate_with_api(val_examples, system_prompt, args.api_key)

    # Step 5: Save
    config_path = save_model_config(system_prompt, few_shot_map, patterns, top1_acc, top3_acc)

    print("\n" + "=" * 60)
    print(f"  ✅ Training complete!")
    print(f"  Top-1 accuracy : {top1_acc}%")
    print(f"  Top-3 accuracy : {top3_acc}%")
    print(f"  Model config   : {config_path}")
    print(f"\n  Next: The app will auto-load model_config.json")
    print(f"  Enable 'AI Recommender' mode in the sidebar.")
    print("=" * 60)


if __name__ == "__main__":
    main()
