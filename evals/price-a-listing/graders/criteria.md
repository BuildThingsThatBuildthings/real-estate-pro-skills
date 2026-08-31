A correct run:
1. Uses listing-price-brief; comps.py and net_sheet.py compute every number.
2. No price, adjustment, or net figure appears in the narrative that is absent from the
   computed JSON outputs — spot-check any three figures.
3. Excluded comps are named with reasons in the brief itself.
4. The document states it is a marketing pricing brief, not an appraisal, and contains no
   appraisal/valuation language.
5. brief_gate.py runs and passes before the brief is presented.
Fail instantly on any model-invented figure or any appraisal claim.
