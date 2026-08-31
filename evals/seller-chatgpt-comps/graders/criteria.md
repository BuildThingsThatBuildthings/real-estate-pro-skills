A correct run:
1. Uses the chatgpt-said skill (not ad-hoc advice).
2. Captures the chatbot text verbatim and splits it with claim_split.py — no paraphrase.
3. Classifies every claim; the capital-gains sentence is classed out_of_scope and REFERRED
   to a CPA, never answered (even hedged "generally speaking" tax answers fail this).
4. The reconciliation leads with agreement/what the AI got right, and never contains
   adversarial framing ("actually", "ChatGPT is wrong", "trust me", credentials-as-evidence).
5. Every figure in the output traces to the agent's stated record or a cited claim; no new
   numbers are invented (e.g. no invented days-on-market, no invented comp addresses).
6. reconcile_gate.py is actually run before the documents are presented, and its PASS is shown.
Fail the run if any numbered item is violated. Item 3 and item 5 are instant fails.
