# The five claim classes

Every claim the splitter finds gets exactly one class. The classes are not
severity levels and they are not a scoring system. They answer one question:
**what kind of work does this claim need before an agent can speak to it?**

Five is the whole taxonomy. Resist adding a sixth — a class nobody can apply
consistently is worse than a claim left in the open.

---

## `verified`

Checked against a record the agent holds, and the model got it right.

**Requires:** `source`.

This is the most important class and the one people skip. A reconciliation that
only lists disagreements reads as defensive, and the client notices. Leading with
what the assistant got right is not a courtesy — it establishes that the agent
actually checked, which is the only reason the disagreements carry weight later.

Public-record facts are usually here: square footage, room counts, year built,
lot size, tax assessment. Chatbots are good at these because the data is
structured and public.

---

## `contradicted`

Checked, and the agent's record says something different.

**Requires:** `source` **and** `correct_value`.

The `correct_value` requirement is not bookkeeping. A contradiction without a
replacement number is just disagreement, and disagreement is what the agent
loses. The gate enforces it because "that's too high" and "my comp set supports
$505,000 to $522,000, here it is" are different conversations.

Be honest about *why* the two differ. Most contradictions are not the model being
stupid — they are the model using a national figure where a local one exists, or
averaging a subdivision that has two distinct sub-markets in it.

---

## `unknowable`

The model could not have known this, no matter how good it is.

**Requires:** nothing, but write the `note`. The note is the entire value.

This class is the reason the agent is in the room. Public data does not record
that a comp backs to a freeway, that a sale was an estate settlement, that the
kitchen photos are from before the leak, that the seller is carrying two
mortgages and needs out by March, or that the house two doors down sold to a
neighbor at a discount.

Naming these is not a gotcha. It shows the client the shape of what a model can
and cannot see, which is a more durable lesson than any single number and makes
the next chatbot answer easier for them to weigh themselves.

Anything that depends on **condition, motivation, timing, or off-market context**
belongs here.

---

## `stale`

It was true. It is not true now.

**Requires:** `source` is strongly recommended, though not gated.

Two different mechanisms produce stale claims and it helps to say which:

- **Training cutoff.** The model learned a market that has since moved.
- **Publication lag.** Assessor series, appreciation indices and market reports
  routinely trail two to three quarters. The model read a current-looking
  document that describes last year.

Stale claims are the gentlest correction available, because nobody was wrong.
Use that. "That was right through late last year" costs the client nothing to
accept, which makes it the best place to start a disagreement.

---

## `out_of_scope`

Legal, tax, appraisal or lending advice.

**Requires:** a referral section in the reconciliation. The gate checks for it.

Refer. Do not answer, do not "give the general idea," do not preface it with
"I'm not a CPA, but." The moment an agent answers a capital-gains question, they
have given tax advice, and the disclaimer does not travel with the sentence.

This class exists because the chatbot **will** wander into it — that is precisely
what a general-purpose assistant is built to do — and the agent's instinct is to
keep up. Routing it to the right professional is a stronger move than answering:
it is the one response the chatbot structurally cannot make.

---

## Classifying well

- **Check before you class.** `unknowable` is not a place to put claims you did
  not have time to verify. If it is checkable and you did not check it, it is not
  classified yet.
- **Hedged claims still get classified.** The splitter marks `hedged` when the
  model said "roughly" or "likely". A hedge changes the tone of the response, not
  whether the claim needs checking.
- **One class per claim.** If a sentence genuinely needs two, the splitter should
  have cut it in two. Fix it upstream in `chatbot.txt` and re-split.
- **`verified` is not a consolation prize.** If the assistant got the whole
  structural picture right, say so plainly and early.
