# Drive delivery — where finished work goes

**Every asset any skill in this bundle creates goes to the client's `01 Waiting`
folder and nowhere else.** The client moves it to Approved themselves. Nothing in
this bundle writes to Approved, and nothing publishes.

There are two ways to reach Drive. Use the connector unless you are pulling a
large media dump.

---

## The connector path (default — desktop app)

No install, no config, no rclone. The Google Drive connector is already
authenticated in the desktop app, so a skill just calls it.

### 1. Find the client's Waiting folder, once

```
search_files  query: title contains 'Waiting' and mimeType = 'application/vnd.google-apps.folder'
```

Narrow it if the account has several:

```
search_files  query: title contains 'Waiting' and mimeType = 'application/vnd.google-apps.folder' and parentId = '<client folder id>'
```

Or take the id straight from the folder URL the agent pastes —
`drive.google.com/drive/folders/`**`<THIS>`**.

Save it in `config/clients.json` under `drive.waiting_folder_id` so nobody has to
search for it again.

### 2. Make a folder for this delivery

One folder per delivery, named so a human scanning the queue knows what it is
without opening it.

```
create_file  title: "2026-08-29 — Pricing Brief — 412 Maple Ridge Dr"
             mimeType: "application/vnd.google-apps.folder"
             parentId: "<waiting folder id>"
```

Keep the returned folder id. **Loose files accumulating in one review queue
across weeks is how a client stops reviewing.**

### 3. Put the artifacts in it

Text — markdown, JSON, CSV. `disableConversionToGoogleType: true` keeps a `.md`
a `.md` instead of silently becoming a Google Doc:

```
create_file  title: "brief.md"
             parentId: "<delivery folder id>"
             textContent: "<the file>"
             contentMimeType: "text/markdown"
             disableConversionToGoogleType: true
```

If the client would rather read it as a Doc, drop
`disableConversionToGoogleType` and let it convert. That is a per-client
preference, not a rule.

Images and video — base64:

```
create_file  title: "listing-01.jpg"
             parentId: "<delivery folder id>"
             base64Content: "<...>"
             contentMimeType: "image/jpeg"
```

### 4. Clearing the drop folder

Once a weekly dump has been processed, clear it so next week's drop is
unambiguous:

```
search_files  query: parentId = '<drop folder id>'
trash_file    fileId: <each id>
```

`trash_file` moves to trash — it is **not** a permanent delete, and the client
can recover anything for 30 days. Never hard-delete a client's originals; they
may hold no other copy of that walkthrough footage.

**Confirm with the agent before trashing anything**, and only after the assets
have actually been produced. Clearing a drop folder whose contents were never
used loses the client's originals to a 30-day timer nobody is watching.

---

## The rclone path (bulk media only)

`content-foundry` also ships `scripts/drive_sync.py`, which uses rclone.

Use it for one job: **pulling a large weekly media dump**. The connector returns
file content into the model's context, which is right for a handful of documents
and wrong for forty listing photos and a walkthrough video.

```bash
python3 skills/content-foundry/scripts/drive_sync.py weekly  --client {slug}
python3 skills/content-foundry/scripts/drive_sync.py deliver --client {slug} --from output/ \
        --as "2026-08-29 — Listing Launch — 412 Maple Ridge" --yes
python3 skills/content-foundry/scripts/drive_sync.py clear   --client {slug} --yes
```

`deliver` and `clear` both dry-run by default and need `--yes` to act. `clear`
archives into `_archive/<week>` rather than deleting, and refuses to run at all
unless that week was synced locally first.

Requires `rclone` with a configured Drive remote. If you do not have that, use
the connector — it does everything except the bulk pull.

---

## The rule, restated

Waiting is the client's review queue. Anything a skill makes lands there, in its
own dated folder, and stops. The client decides what moves to Approved.
