"""PolicyLens - the whole agent, in three steps.

Step 1  drop_dead()   - throw away expired and superseded policies   (plain Python)
Step 2  score()       - rank what is left by how specific it is      (plain Python)
Step 3  decide()      - the judgement call                           (the AI part)
"""

import json
import os
import re
from datetime import date

POLICIES = json.load(open(os.path.join(os.path.dirname(__file__), "policies.json")))


# ---------------------------------------------------------------- step 1
def drop_dead(policies, today):
    """Keep only policies that are live today and not replaced by a newer version."""
    replaced = {(p["policy_id"], p["supersedes"]) for p in policies if p.get("supersedes")}
    live, dropped = [], []
    for p in policies:
        if p["effective_date"] > today:
            dropped.append((p, "not in effect yet"))
        elif (p["policy_id"], p["version"]) in replaced:
            dropped.append((p, "superseded by a newer version"))
        else:
            live.append(p)
    return live, dropped


# ---------------------------------------------------------------- step 2
def score(policy, ctx):
    """More specific policy = higher score. An exception always wins."""
    s = 0
    if policy.get("vendor") not in (None, "ALL"):
        s += 10                                   # a named vendor means it is an exception
    if ctx.get("region") and policy["region"] == ctx["region"]:
        s += 1
    if ctx.get("department") and policy["department"] == ctx["department"]:
        s += 1
    return s


def applies(policy, ctx):
    """A policy is relevant unless it names a region/department/vendor that is not ours."""
    for field in ("region", "department", "vendor"):
        want, got = policy.get(field), ctx.get(field)
        if want in (None, "ALL", "GLOBAL"):
            continue
        if got and want != got:
            return False
    return True


# ---------------------------------------------------------------- context
def read_context(question):
    """Pull region / department / vendor out of the question."""
    q = question.lower()
    ctx = {}
    for word, region in [("india", "IN"), ("eu", "EU"), ("europe", "EU"), ("us", "US")]:
        if re.search(rf"\b{word}\b", q):
            ctx["region"] = region
            break
    for dept in ["Analytics", "Support", "Finance", "Legal"]:
        if dept.lower() in q:
            ctx["department"] = dept
            break
    m = re.search(r"vendor[- ]([a-z0-9]+)", q)
    if m:
        ctx["vendor"] = "Vendor-" + m.group(1).upper()
    return ctx


# ---------------------------------------------------------------- step 3
def decide(question, today=None):
    today = today or date.today().isoformat()
    ctx = read_context(question)

    live, dropped = drop_dead(POLICIES, today)
    candidates = [p for p in live if applies(p, ctx)]
    candidates.sort(key=lambda p: score(p, ctx), reverse=True)

    topic = "retention" if "retain" in question.lower() else "sharing"
    candidates = [p for p in candidates if (topic == "retention") == ("RETENTION" in p["policy_id"])]

    if not candidates:
        return out("Cannot answer", "No policy covers this question.", [], dropped, ctx)

    # missing context: two rules of different scope disagree and we do not know which is ours
    regions = {p["region"] for p in candidates}
    if len(regions) > 1 and not ctx.get("region"):
        return out("Need more info", "Which region are you in? The answer differs by region.",
                   candidates, dropped, ctx)

    answer = llm(question, candidates, ctx) if os.getenv("ANTHROPIC_API_KEY") else fallback(candidates)
    return out(answer["verdict"], answer["reason"], candidates, dropped, ctx)


def fallback(candidates):
    """Runs when there is no API key, so the demo always works."""
    top = candidates[0]
    exception = top.get("vendor") not in (None, "ALL")
    years = re.search(r"(\d+) years", top["content"])
    if years:
        verdict = years.group(1) + " years"
    else:
        verdict = "No" if exception or "prohibited" in top["content"] else "Yes"
    return {"verdict": verdict, "reason": top["content"]}


def llm(question, candidates, ctx):
    from anthropic import Anthropic

    rules = "\n".join(f'{p["policy_id"]} v{p["version"]}: {p["content"]}' for p in candidates)
    msg = Anthropic().messages.create(
        model="claude-sonnet-5",
        max_tokens=300,
        messages=[{"role": "user", "content": (
            f"Question: {question}\nContext: {ctx}\n\nThese policies are live "
            f"(most specific first; a named vendor means it is an exception that overrides "
            f"the general rule):\n{rules}\n\n"
            'Reply as JSON only: {"verdict": "Yes|No|Cannot answer", "reason": "one sentence"}'
        )}],
    )
    return json.loads(re.search(r"\{.*\}", msg.content[0].text, re.S).group())


def out(verdict, reason, used, dropped, ctx):
    return {
        "verdict": verdict,
        "reason": reason,
        "context": ctx,
        "sources": [f'{p["policy_id"]} v{p["version"]}' for p in used],
        "dropped": [f'{p["policy_id"]} v{p["version"]} - {why}' for p, why in dropped],
    }


if __name__ == "__main__":
    for q in [
        "Can the Analytics team share Dataset Y with Vendor X in India today?",
        "How long can customer data be retained for the EU Support team?",
        "Can I share this customer dataset with an external vendor?",
    ]:
        print("\nQ:", q)
        print(json.dumps(decide(q), indent=2))
