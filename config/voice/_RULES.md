# Shared copy rules

These apply to every brand and outrank any individual voice pack. Most exist because
something shipped wrong once. When a pack disagrees with this file, this file wins and the
conflict gets flagged.

Edit freely. This is a starting position, not doctrine.

## Rules

1. **Verify every factual claim before it ships.** A statistic gets a source. If the verified
   number differs from what was said on camera, use the verified number, attribute it, and
   say the delta out loud.
2. **No claim without a source.** Cut it or source it.
3. **Write one caption per channel.** Copying one caption across surfaces wastes the only
   real advantage of per channel publishing.
4. **The first line is the whole hook.** Most surfaces truncate. Front load it.
5. **Numbers instead of adjectives.** "Finished 48 drafts" beats "hugely productive".
6. **Specific calls to action.** Name the thing. Vague instructions get ignored.
7. **No hashtag piles.** Put keywords in the prose. Set `allow_hashtags` in
   `pipeline.json` if a brand genuinely needs them.
8. **Links go where the platform allows them.** X strips URLs from the body, so links belong
   in the first comment.
9. **No credentials or social proof inside the content itself.** Those belong in the bio,
   the site, or an email.

## Configurable

`config/pipeline.json` under `captions` holds the machine checkable half: `allow_hashtags`,
`allow_dashes`, `banned_words`, `proper_noun_exceptions`. The linter reads that file, so
adding a banned word there enforces it across every brand.
