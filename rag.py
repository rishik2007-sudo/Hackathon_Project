"""The retrieval half of the project.

Ordinary RAG ranks every document by similarity and hands the top few to the model.
That is exactly wrong here: the closest-matching document is often a version that
was replaced two years ago, and the model will quote it with total confidence.

So retrieval runs in two passes:

  hard filter   drop anything expired, superseded, or scoped to a region or
                department that is not yours. A rule that cannot apply can
                never be retrieved, no matter how well the words match.

  soft rank     TF-IDF cosine similarity over what survives, so "can I use my
                own laptop" finds DEVICE-ACCESS without the word "device"
                appearing in the question.
"""

import json
import os

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

HERE = os.path.dirname(__file__)


# ---------------------------------------------------------------- chunking
def to_chunk(p):
    """One policy = one chunk. Title and content both go in, so the words a
    person would actually use are searchable, not just the policy body."""
    return f'{p["title"]}. {p["content"]}'


class Index:
    """A tiny vector store. Built once at import, queried per question."""

    def __init__(self, policies):
        self.policies = policies
        self.chunks = [to_chunk(p) for p in policies]
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
        self.matrix = self.vec.fit_transform(self.chunks)

    def rank(self, question, subset):
        """Cosine similarity between the question and each policy in subset."""
        if not subset:
            return []
        rows = [self.policies.index(p) for p in subset]
        sims = cosine_similarity(self.vec.transform([question]), self.matrix[rows])[0]
        return sorted(zip(subset, sims), key=lambda t: t[1], reverse=True)


POLICIES = json.load(open(os.path.join(HERE, "policies.json"), encoding="utf-8"))
INDEX = Index(POLICIES)


# ---------------------------------------------------------------- pass 1
def drop_dead(policies, today):
    """Remove policies that are not in force. Plain arithmetic, no model."""
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


def in_scope(policy, ctx):
    """False if the policy is written for a region, department or vendor that is not ours."""
    # A vendor exception only applies when that exact vendor is the one being asked about.
    # Without this, the Vendor-Z exception would surface on any EU Support question.
    want_vendor = policy.get("vendor")
    if want_vendor not in (None, "ALL") and ctx.get("vendor") != want_vendor:
        return False

    for field in ("region", "department"):
        want, got = policy.get(field), ctx.get(field)
        if want in (None, "ALL", "GLOBAL"):
            continue
        if got and want != got:
            return False
    return True


# ---------------------------------------------------------------- pass 2
def specificity(policy, ctx):
    """How precisely this rule targets our situation. An exception outranks everything."""
    s = 0
    if policy.get("vendor") not in (None, "ALL"):
        s += 10
    if ctx.get("region") and policy["region"] == ctx["region"]:
        s += 2
    if ctx.get("department") and policy["department"] == ctx["department"]:
        s += 2
    return s


def retrieve(question, ctx, today, k=4, floor=0.04):
    """Return the policies the model is allowed to reason over, plus what was discarded."""
    live, dropped = drop_dead(POLICIES, today)

    out_of_scope = [p for p in live if not in_scope(p, ctx)]
    candidates = [p for p in live if in_scope(p, ctx)]

    ranked = [(p, sim) for p, sim in INDEX.rank(question, candidates) if sim >= floor]
    top = [p for p, _ in ranked[:k]]
    sims = dict((id(p), sim) for p, sim in ranked)

    # among the retrieved, the most specific rule is the one that governs
    top.sort(key=lambda p: (specificity(p, ctx), sims.get(id(p), 0)), reverse=True)

    return {
        "top": top,
        "scores": {f'{p["policy_id"]} v{p["version"]}': round(sims.get(id(p), 0), 3) for p in top},
        "dropped": dropped,
        "out_of_scope": out_of_scope,
    }
