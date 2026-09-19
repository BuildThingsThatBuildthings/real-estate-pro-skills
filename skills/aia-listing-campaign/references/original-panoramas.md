# Original panorama editing with basic tools

When a listing includes its own real panoramic tour, inspect and identify the actual rooms before acquiring media. Use browser page-asset inventory to export only the observed panorama image for each selected room; exclude tracking pixels, unrelated listing images and application code. Record the listing URL, room label, actual asset URL, acquisition evidence and reuse authority. A tour button alone proves no acquired footage. Preserve the original panorama and any required credit; do not present a panorama from another home as this listing.

Use `scripts/render_panorama_clip.py` through the AIA workflow runner. It projects an original equirectangular photograph into a normal perspective viewport with continuously authored yaw, pitch and field of view using the installed FFmpeg v360 filter. It uses no model, subscription or service credits. This is a virtual rotation within an actual panoramic photograph, not camera translation, a measured 3D reconstruction or permission to invent unseen rooms. Cut between real capture positions. Keep a consistent direction when actual doorways establish continuity.

Author each private clip config with source, source identity and SHA-256, rights basis, width, height, fps, seconds, horizontal/vertical field of view, start/end yaw and pitch, private working directory and output MP4. Declare the config and original panorama as workflow inputs. Inspect each resulting clip's opening, midpoint and ending against the original tour; reject warped features, misidentified rooms or irrelevant camera directions. Incorporate accepted clips into the full story through the shared AIA editor with current-run parent provenance. Keep the rest of the campaign inventory intact. All acquisition records, configs, commands and intermediate clips remain private.

If the browser's asset exporter refuses a panorama because its response is labeled
`application/octet-stream`, record that actual failure and use AIA
`acquire_media.py` with only the exact asset URLs observed on the authorized listing
tour. Never guess IDs, crawl neighboring assets or report an exporter failure as a
successful browser download. Preserve each original and its source URL/hash. Decode
and inspect the actual file before describing it as an image. Pending source IDs
remain pending room identification until matched against the tour.

Use `inspect_panorama_sources.py` through the workflow runner to build a private,
ID-labeled contact sheet of the original equirectangular images. It verifies the
manifest's original hashes and 2:1 geometry and does not assign room labels. This is
an intake review aid, never client campaign artwork or a measured reconstruction.

Before a room batch, compare actual projected starting, middle and ending views
with the intended source features. The shared renderer must use `reset_rot=1`
when runtime commands specify absolute yaw/pitch. Without it, FFmpeg accumulates
successive rotations; changing the sign does not correct that bug. The regression
test compares decoded frames against independently projected planned viewpoints.
Reject a technically valid clip aimed at blank walls or the wrong feature.

Use `inspect_panorama_views.py` through the AIA runner for inexpensive static
perspective calibration before full clips. Its private spec lists actual source
paths/hashes and explicit label, yaw, pitch and horizontal field of view. Review
the resulting labeled PNG grid against the intended room features. The grid is
internal framing evidence, never a finished listing graphic. Author accepted
motion endpoints only after these actual projected views make sense.
