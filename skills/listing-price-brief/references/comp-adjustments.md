# Adjustments

## The rule

**Python does the arithmetic. The model writes the sentences.**

Every adjustment is a ledger line — feature, subject value, comp value, rate,
dollars, and the formula that produced it — so a seller can follow it on paper
and an agent can defend it out loud. `brief_gate.py` re-derives every ledger and
refuses one that does not sum to its own net.

An adjustment nobody can explain is worse than no adjustment. It converts a
defensible range into a number the agent has to take on faith in front of the one
person least inclined to grant it.

## Direction

Comps are adjusted **toward the subject**. A positive adjustment means the comp
was inferior, so its price moves up to stand in for the subject property.

If the subject has 2,400 finished square feet and the comp has 2,310, the comp is
adjusted up by the difference times the rate: `(2400 - 2310) x 85 = +$7,650`.

## Rates

The built-in rates are a starting point and nothing more. Real rates come from
paired-sales analysis in the agent's own market, supplied through
`--rates rates.json`. The brief records which set was used, because the range is
only as defensible as the rates behind it.

| Rate | Applies to |
| --- | --- |
| `sqft` | finished living area difference |
| `beds`, `baths`, `garage` | count differences |
| `lot_sqft` | lot area difference |
| `year_built` | per year of effective age |
| `condition` | per grade step on poor / fair / average / good / excellent |
| `market_trend_pct_per_month` | time adjustment; **0 until measured locally** |

`market_trend_pct_per_month` defaults to zero on purpose. A guessed trend
compounds across every comp and quietly moves the whole range. Measure it or
leave it off.

## The ceiling

`max_net_adjustment_pct` defaults to 25%. A comp adjusted past that is not
comparable — the adjustments are doing more work than the sale is.

Over-adjusted comps are **reported, not silently dropped**. An agent who can see
why a comp fell out can defend the ones that stayed.

## The floor

`min_comps` defaults to 3. Below it, `comps.py` marks the set as insufficient and
`net_sheet.py` refuses to build at all. A net sheet on an unsupported price is a
number the seller will hold the agent to for the rest of the listing.

## The range is the middle, not the extremes

The supported range is the interquartile span of the adjusted values, not
min-to-max. Quoting the extremes hands the seller the top number and then argues
with it for six weeks.

Comps with the largest adjustments carry the least weight, and the brief should
say which one that is. The comp that needed almost nothing is the one that
anchors the range, and naming it is more persuasive than any adjective.

## Exclusions are the most important section

`EXCLUSIONS` refuses a comp dropped without a reason, because an unexplained
exclusion is indistinguishable from cherry-picking.

Write them into the brief on purpose. The new-construction sale backing the golf
course is exactly the comp an online estimate will find first, and the seller has
probably already seen it. Naming it, with the reason, does more for the agent's
credibility than the four included comps combined.

The same discipline applies downward. An estate sale that drags the range down
gets excluded and named too. A comp set is worth what its exclusions are worth.

## Rounding

A seller-facing brief quotes round numbers. Those are **computed** —
`supported_low_rounded`, `median_rounded`, `estimated_net_to_seller_rounded` —
not rounded in prose. A number the model rounded is a number the model produced,
and the gate cannot trace it.
