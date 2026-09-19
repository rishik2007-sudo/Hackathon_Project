# teamcoders

**PolicyLens** — a policy reasoning agent.

Pragyaan 2.0 · Keshav Memorial Institute of Technology · CSE (AI & ML)

Problem statement: *The Company That Forgot What Its Own Policies Said*

---

## The problem

A company rulebook nobody ever cleaned up. Old versions are still sitting there, a general
rule and a specific rule disagree, and exceptions live in a separate document.

So when someone asks *"can I share this with Vendor X?"*, three documents all look like the
answer — and two of them are wrong. Normal search returns the most **similar** document.
It has no idea one of them expired in 2026.

## The fix, in four steps

| Step | What happens | Who does it |
|------|--------------|-------------|
| 1 | Read region / department / vendor out of the question | Python |
| 2 | **Hard filter** — drop expired, superseded and out-of-scope policies | Python |
| 3 | **Rank** what survives by TF-IDF similarity, then by specificity | Python |
| 4 | Decide which surviving rule governs, and write the answer | the AI |

**Why the split matters.** Dates and versions are maths, so Python does them and is right
every time. "Which rule really governs here" is judgement, so the AI does that. Let the AI
do step 2 and it will quote a dead 2024 policy with total confidence.

## Why retrieval runs in two passes

Ordinary RAG ranks every document by similarity and hands the model the top few. That is
exactly wrong here. The closest-matching document is very often a version that was
replaced two years ago, and the model will quote it without hesitating.

So the hard filter runs **first**:

- **expired / superseded** — `effective_date` in the future, or a version another policy
  supersedes
- **out of scope** — a rule written for EU when you are in India, for Support when you are
  in Analytics, or a vendor exception naming a vendor you never mentioned

A rule that cannot possibly apply is never retrieved, however well the words match. Only
then does TF-IDF cosine similarity rank what is left, so *"can I use my own laptop"* finds
`DEVICE-ACCESS` even though neither word appears in it.

Finally the retrieved set is re-sorted by **specificity** — a rule naming your exact region
and department beats `GLOBAL`/`ALL`, and a vendor exception beats everything.

A real run: **41 policies searched → 12 dropped as out of scope → 4 retrieved**, with the
similarity score shown next to each one in the UI.

## Data

`policies.json` holds 41 policies across data sharing, retention, device access, vendors,
access control, incidents, travel and expenses, spanning four regions and five departments,
with several deliberately superseded versions and two vendor exceptions.

`db.py` seeds these into SQLite (`policies` table, indexed on region/department/date) and
writes every answer to a `decisions` table — question, resolved context, verdict, the
policies used and the ones discarded — so any answer can be audited afterwards.

```bash
python db.py        # create the tables and seed them
```

## Run it

```bash
pip install -r requirements.txt
python app.py
```

Open <http://127.0.0.1:8000>


The AI step is optional. Without a key it falls back to the deterministic result, so the
demo always works. To turn the AI on:

```bash
set ANTHROPIC_API_KEY=your-key-here      # Windows
export ANTHROPIC_API_KEY=your-key-here   # macOS / Linux
```

Logic only, no server:

```bash
python agent.py
```

## The three test cases

**A — an old version plus a hidden exception**

> Can the Analytics team share Dataset Y with Vendor X in India today?

`DATA-SHARING v3.0` is dropped (v5.0 supersedes it). v5.0 allows approved vendors, but
`VENDOR-EXCEPTION v1.0` names Vendor-X, so the exception wins.
→ **No**

**B — general versus specific**

> How long can customer data be retained for the EU Support team?

Both rules are live. `EU-RETENTION v2.0` names your exact region and department, so it
beats the GLOBAL/ALL rule.
→ **2 years**

**C — the question is missing something**

> Can I share this customer dataset with an external vendor?

The answer changes by region and the user never said theirs.
→ **Asks which region you are in**, instead of guessing.

## Files

```
agent.py        the four steps — context, retrieve, decide, log
rag.py          the retrieval layer — hard filter, then TF-IDF ranking
db.py           SQLite schema, seed, and the decision log
policies.json   41 policies
app.py          serves the page, one /ask endpoint
index.html      the whole frontend
```

## Team

| Name | Roll | Role |
|------|------|------|
| Jakkula Vikas Yadav | 245325733422 | Agent Whisperer — team lead |
| Likith | 245325733430 | Backend |
| Chintu | 245325733420 | Frontend |
| Sameer | 245325733441 | Data |
| Rishik | 245325733049 | Product & Pitch |
