# Source-led spatial diagrams

Use an illustrated dollhouse only as an explicitly identified explanation of a supplied floor plan. It is a supporting visual, not a measured scan, a photorealistic world reconstruction, or a substitute for requested property footage.

Trace the plan's exterior footprint, interior walls, opening gaps, stair position and floor alignment into private run data. Record the source and assumptions. Keep approximate scale and furniture illustrative. Do not infer hidden rooms from a single photograph. Label the result while it appears.

The reusable `assets/spatial-diagram/index.html` accepts floors with polygons, wall segments and simple semantic furnishings. `scripts/render_spatial_diagram.mjs` renders deterministic camera movement; preview the same scene interactively to inspect plan alignment. Keep client geometry, brand, labels and media in private configuration. The renderer does not validate their truth.

Before use, compare each floor with its supplied plan and inspect every camera passage for clipping, false room connections, disappearing walls and floating furniture. Confirm the camera reveals useful spatial information. A successful render does not establish cinematic or campaign completion.
