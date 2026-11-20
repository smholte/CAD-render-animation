# Toolbox format – version 0.1

How tools on one PC find each other and hand files to each other, with no app in between: a tool describes itself
in a small file, and a file goes to another tool by being put in that tool's inbox folder.

```
House Planner  ── writes a job into Fresing Render's inbox ──▶  Fresing Render imports and bakes
Fresing Render ── writes the result as a job into House Planner's inbox ──▶  House Planner shows the baked light
```

Status: **version 0.1, reviewed by the leads of House Planner and Fresing Render on 18 Nov 2026 and changed as they
asked (section 13); tag `v0.1`.** Step D of the toolbox plan (format only, no app); the later steps (a background router, the toolbox window) read the
same folder and add to this text. The words MUST, MUST NOT, SHOULD and MAY are used as in RFC 2119. The schemas in
`schemas/` and the type list `types.json` are part of this text; where they and this text differ, it is a bug in one
of them.

Contents: 1 Ideas · 2 The Toolbox folder · 3 Names, JSON and versions · 4 The manifest · 5 File types ·
6 Sending a job · 7 Status, replies, cancelling and cleaning up · 8 A round trip · 9 A web page and the folder ·
10 Safety · 11 Samples and the checker · 12 Not in 0.1 · 13 Decided in the first review

---

## 1. Ideas

- **Every tool works on its own.** The format only adds a way in and a way out. A tool that finds no Toolbox folder
  behaves as it does today.
- **A folder is the meeting place.** Every kind of tool can read and write a folder: a Blender extension, a program,
  and a web page in Chrome or Edge once the owner has picked the folder (section 9). No server, no network port.
- **One mechanism: the inbox.** Sending a file, and sending the result back, are the same thing – a *job* in a
  tool's inbox. There is no outbox.
- **A tool says what it takes.** Its manifest lists actions and the file types each accepts. Nobody guesses.
- **The content decides the file type**, not the name: a renamed file never reaches the wrong tool (section 5).
- **A job is data, never a command.** A tool does only the actions of its own manifest, on files whose type it has
  checked itself (section 10).
- **Formats of the files themselves stay where they are.** A `.hpscene` is described by `house-scene-format`; this
  format only carries it.

## 2. The Toolbox folder

One folder per user of a PC, named **`Toolbox`, directly in the user's home folder**:

| System | Path |
| --- | --- |
| Windows | `%USERPROFILE%\Toolbox` (`C:\Users\<name>\Toolbox`) |
| macOS, Linux | `~/Toolbox` |

A native tool MUST use the folder named by the environment variable `TOOLBOX_HOME` when that is set (tests, special
set-ups). The folder is **not** in `AppData`, `~/Library` or a hidden folder: browsers refuse to open those to a web
page (section 9). It SHOULD NOT be moved into a synced folder (OneDrive, Dropbox): a half-synced job is a broken job.

```
Toolbox/
  toolbox-folder.json                  marks the folder (so a picked folder can be recognised)
  tools/
    nl.fresing.render/                 one folder per tool, named by its id
      toolbox.json                     the tool's manifest (section 4)
      alive.json                       "I am watching my inbox" (section 6.4)
      inbox/
        20261118-195100-9f3c2a/        one folder per job, named by its id
          job.json                     written by the sender, last (section 6)
          sample-house.hpscene         the files of the job
          status.json                  written by the receiving tool (section 7.1)
          cancel.json                  written by the sender to stop the job (section 7.3)
    nl.fresing.house-planner/
      toolbox.json
      inbox/ …
```

`toolbox-folder.json` is `{"format": "toolbox-folder", "version": "0.1"}`. **Only a native tool makes the folder**,
with this file and `tools/`, when it is installed or first started: a program knows where the user's home folder is.
A web page cannot see where a picked folder lies, so a web tool MUST NOT make `toolbox-folder.json` – a folder named
`Toolbox` somewhere else (in Documents, on a stick) would be marked by mistake. A web tool that finds no such file
says that this is not the Toolbox folder, and that a tool like Fresing Render makes it.

**Who writes what.** A tool writes only:

- its own tool folder: `toolbox.json`, `alive.json`, an icon, `inbox/`, and `status.json` in the jobs of its inbox;
- new job folders in **other** tools' inboxes, and `cancel.json` in a job it sent;
- deletions as section 7.4 allows.

A tool MUST NOT change another tool's manifest or a job's `job.json` and files after they are written. A reader MUST
ignore entries it does not know (browsers leave short-lived `.crswap` files while they write).

**Other programs read and write at the same moment.** Windows refuses to replace or delete a file another program has
open. So everywhere in this format: a write by rename, or a delete, that fails is tried again at the next look; a
reader that finds a file missing, empty or half there treats it as "not there yet" and tries again at its next look.
Neither is an error.

**A tool may run as several copies** that share one tool folder and one inbox: two windows of a program, a page open
in two tabs, a web tool's page and a downloaded copy of it. Section 6.3 says how only one copy takes a job.

A tool SHOULD write its manifest again at every start and after every update, so its version and paths are right.
Uninstalling a tool removes its tool folder.

## 3. Names, JSON and versions

### 3.1 Tool ids

A tool id is the tool's name for ever: lower case, at least two parts joined by dots, each part of `a–z`, `0–9` and
single `-` inside (`nl.fresing.render`, `nl.fresing.house-planner`), at most 80 characters. Start it with a domain
or name you control, turned round. The tool's folder has exactly this name.

### 3.2 Job ids

8 to 64 characters of `a–z`, `0–9` and `-`, starting with a letter or digit. The sender makes it and it MUST be new:
the date, the time and six random characters (`20261118-195100-9f3c2a`) is the usual form. The job's folder has
exactly this name.

### 3.3 File names

The name of a file in a job (and of a tool's icon) MUST be a plain name every system takes:

- 1 to 120 characters, no control characters, none of `< > : " / \ | ? *`;
- no space or dot at its start or its end (so also not `.` or `..`, and no hidden files);
- not a name Windows keeps for itself (`con`, `prn`, `aux`, `nul`, `com1`–`com9`, `lpt1`–`lpt9`, with or without
  an extension, in any case);
- not `job.json`, `status.json` or `cancel.json` (in any case);
- no two files of one job with the same name when capitals are ignored.

Files lie directly in the job folder; folders inside a job are not part of 0.1.

### 3.4 JSON

Every JSON file of this format: UTF-8, one object, at most 1 MiB, no `NaN` or `Infinity`, and no control characters
(line breaks, tabs …) in any text or key – so JavaScript and Python read the same thing. A reader MUST refuse a file
that breaks one of these.

Two more are **rules for the writer, which the checker checks**: no byte-order mark at the start, and no key twice in
one object. A reader MAY refuse them and need not notice them – a browser's `JSON.parse` keeps the last of two equal
keys and its text decoder drops the mark without a word. Each starts with `"format"` (which file it is) and `"version"`. Unknown fields are an error in 0.x.

Times are written `2026-11-18T19:51:00+01:00`: date, `T`, clock time to the second (thousandths MAY follow), and
the offset from UTC (`+00:00` to `+23:59`, or `-`) or `Z`.

### 3.5 Versions

`"version": "<major>.<minor>"`, two whole numbers. **Until 1.0 anything may change between minor versions: a reader
written for 0.n MUST refuse a file of any other version**, with a clear message ("This job was written by a newer
tool (toolbox format 0.2). Update Fresing Render to read it."). From 1.0 on the rule of `house-scene-format` holds:
a newer minor only adds and is read, another major is refused.

Tools pin a tag of this repository (`v0.1`, …) and test against its samples.

## 4. The manifest (`toolbox.json`)

```json
{
  "format": "toolbox-tool",
  "version": "0.1",
  "id": "nl.fresing.render",
  "name": "Fresing Render",
  "app_version": "1.4.0",
  "description": "Photo-realistic renders and animations of STEP assemblies.",
  "homepage": "https://smholte.github.io/CAD-render-animation/",
  "kind": "native",
  "start": { "program": "C:/Users/sample/AppData/Local/FresingRender/Fresing Render.exe" },
  "actions": [
    { "id": "import-step", "label": "Import STEP", "accepts": ["step"] },
    { "id": "bake-house", "label": "Bake house scene", "accepts": ["hpscene"], "returns": ["hpbake"] }
  ],
  "handover": ["inbox"]
}
```

| Field | | Meaning |
| --- | --- | --- |
| `id` | required | the tool id (3.1); equals the folder's name |
| `name` | required | the name people see, 1–60 characters |
| `kind` | required | `native` (a program on this PC) or `web` (a page in a browser) |
| `actions` | required | what can be asked of the tool (may be empty) |
| `app_version` | | the tool's own version, as it shows it |
| `description`, `homepage` | | one or two sentences; an `https://` address |
| `url` | web only | the tool's `https://` address on the web. Every copy of the tool writes the same one, also a copy opened from a downloaded file; a web tool with no address on the web leaves it out. A native tool has none |
| `start` | native only | what the user's own shortcut starts: the program's full path and fixed arguments (not a console program that opens a black window). Recorded for the router of the next step; nothing in 0.1 starts a tool |
| `icon` | | file name of a PNG or SVG next to the manifest |
| `types` | | the tool's own file types (5.1) |
| `sends` | | file types the tool hands to others on its own |
| `handover` | | the ways the tool takes jobs. 0.1 knows only `inbox`: "I read my inbox while I run" |

An **action**: `id` (1–32 of `a–z`, `0–9`, `-`; unique in the manifest), `label` (what a person reads, English),
`accepts` (one or more file types: every file of a job for this action MUST be one of them), and optional `returns`
(the file types the action gives back as a reply, section 7.2).

A type is named by its id of the built-in list (`step`), by a tool's own type (`com.example.widget`), or as
`ext:<extension>` for files nobody describes (`ext:xyz`).

## 5. File types

### 5.1 The lists

`types.json` in this repository is the **built-in list**; a reader ships a copy of it. Its ids are short (`step`,
`hpscene`). A tool adds **its own types** in its manifest's `types`; their ids MUST have dots, like a tool id, and
start with a name the author controls – so two tools never clash. A type worth sharing gets a short id by a change
to this repository. When two manifests define the same own type differently, a reader MUST use neither.

A type:

```json
{ "id": "hpscene", "name": "House Planner scene", "extensions": [".hpscene"], "by_content": true,
  "detect": { "zip_json": { "file": "scene.json", "field": "format", "equals": "house-scene" } } }
```

`extensions`: lower case, with the dot. `detect`: a rule on the file's content (5.2); without one the extension is
all there is. `by_content: true`: the rule is sure enough to overrule the file's name (needs `detect`).

### 5.2 Rules

A rule is an object with exactly one key. It looks only at the **head** (the first 65 536 bytes) and, for the zip
rules, at the zip's list of files and one JSON file in it.

| Rule | True when |
| --- | --- |
| `{"starts_with": "ISO-10303-21;"}` | after an optional UTF-8 byte-order mark and any spaces, tabs and line breaks, the file starts with these ASCII characters (1–64, no spaces) |
| `{"starts_with_hex": "676c5446"}` | the file's first bytes are exactly these (lower-case hex, 1–64 bytes) |
| `{"head_matches": "FILE_SCHEMA\\s*\\(\\s*\\(\\s*'IFC"}` | the pattern is found somewhere in the head read as text |
| `{"zip_has": {"file": "scene.json"}}` | the file is a zip that lists this name |
| `{"zip_json": {"file": "scene.json", "field": "format", "equals": "house-scene"}}` | … and that file (at most 1 MiB) is JSON as in 3.4 whose top-level `field` is exactly this text |
| `{"all": [rule, …]}` · `{"any": [rule, …]}` · `{"not": rule}` | all / at least one / not – at most 4 deep |

**A zip is read like this** (the same few steps everywhere, so every tool gives the same answer – also for a
damaged file): take the last end-of-central-directory record that starts in the file's final 65 557 bytes (its
zip64 form when the record says so); read the central directory it names, entry by entry, as many as it counts;
bytes in front of the zip shift every offset; of two entries with one name the later counts. One entry is read from
where its local header says the data starts, stored or deflated, not encrypted, and only when its length and
CRC-32 are what the directory says. Anything that does not fit is "not a zip" or "no such file" – never an error.
`tbf/detect.py` and `web/toolbox-folder.js` are these steps in Python and JavaScript.

**The head as text**: every byte below 0x80 is its ASCII character, every other byte reads as `?`. (Do not use a
browser's `latin1` decoder: it is Windows-1252 and changes bytes 0x80–0x9F.)

**Patterns** MUST mean the same in JavaScript and Python, so only this is allowed: plain ASCII, at most 200
characters; `\s \S \d \D \w \W` (ASCII meaning); a backslash before a sign (`\(`, `\.`); groups `( )`, choices `|`,
sets `[ ]` and `[^ ]`, the counts `* + ?` and `{n}`, `{n,}`, `{n,m}`, and a `?` after a count (as few as possible).
Not allowed: `^` and `$` outside a set (use `starts_with`), a bare `.` (it skips different line ends in the two
languages – write a set), any `(?…)` group, a backslash before any other letter or digit, a `{` that is not a
count, and `+` or `*` straight after another count. Patterns are case-sensitive. In Python they are used with
`re.ASCII`, in JavaScript without flags.

### 5.3 Which type a file is

Given the list of types – the built-in list in its order, then all tools' own types ordered by id – and the file:

1. **Content.** The first type with `by_content` whose rule is true is the file's type. (When the file's extension
   is not one of that type's, say so: "its content is IFC but its name ends in .step".)
2. **Extension.** Otherwise take the file's extension (from its last dot, lower case). The first type that lists it
   and has no rule, or whose rule is true, is the file's type.
3. **Unknown.** Otherwise the type is `ext:` followed by the extension without its dot (`ext:xyz`; `ext:` when the
   name has no dot).

So a zip renamed to `.hpscene` is `ext:hpscene` – not a house scene – and an IFC file named `.step` is `ifc`.
`tbf/detect.py` is the reference; `python3 check.py --type <file>` prints the answer.

## 6. Sending a job

### 6.1 `job.json`

```json
{
  "format": "toolbox-job",
  "version": "0.1",
  "job": "20261118-195100-9f3c2a",
  "created": "2026-11-18T19:51:00+01:00",
  "from": "nl.fresing.house-planner",
  "to": "nl.fresing.render",
  "action": "bake-house",
  "files": [ { "name": "sample-house.hpscene", "type": "hpscene", "size": 20481 } ],
  "return": "import-bake",
  "title": "Sample house – version 3"
}
```

| Field | | Meaning |
| --- | --- | --- |
| `job`, `created` | required | the job id (3.2) and when it was written |
| `from`, `to` | required | sender's and receiver's tool ids; never the same |
| `action` | required | an action id of the receiver's manifest |
| `files` | required | one or more: `name` (3.3), `type` (as the sender worked it out, 5.3), `size` in bytes |
| `return` | | an action id of the **sender's** manifest: "send the result back to me, for this action" |
| `reply_to` | | `{"tool", "job"}`: this job is the result of that job (7.2); `tool` equals `from` |
| `title` | | what a person may read in a list, at most 120 characters |
| `options` | | an object for the receiving action. Its content belongs to that tool, not to this format |

### 6.2 How the sender writes it

1. Check that `tools/<to>/toolbox.json` is there, is version 0.1 and has the action, and that the action accepts
   every file's type. If not: do not send.
2. Make `tools/<to>/inbox/<job id>/`.
3. Write the files, each to its end.
4. Write `job.json` **last**. A job folder without `job.json` does not exist yet for anyone else.

`job.json` MUST appear whole: write it under another name and rename it, or use a writer that swaps the file in when
it is closed (a browser's `createWritable()` does). The receiver also checks every file's `size`, so a file that is
still being written is never read.

### 6.3 How the receiving tool reads its inbox

While it runs, the tool looks at its inbox about every 2 seconds (not more often than once a second). For each job
folder **without a `status.json`**:

1. No `job.json`: leave it alone.
2. Read `job.json` (3.4, 3.5). It MUST name this tool in `to`, its own folder's name in `job`, and an action of this
   tool's manifest.
3. For every file: the name is allowed (3.3), the file is there, its size is the stated size, its type – **worked out
   by the tool itself** (5.3) – is the stated type and one the action accepts.
4. Anything wrong: write `status.json` with `failed` and a `code` (7.1), and do nothing else with the job. A file
   whose size is still short MAY get up to a minute before this.
5. Otherwise take the job – write `status.json` (`waiting` or `working`), as "Only one copy takes a job" below
   says – and do the action.

A tool MAY ask its user before it starts ("House Planner sent a house. Bake it now?") or just start; that is the
tool's choice and may depend on `options`. While it waits for its user the status is `waiting` and its `text` says
so ("Waiting for you in Fresing Render: press Bake now"), so the sender can show it.

**Only one copy takes a job.** A tool that can run as several copies makes sure of it:

- A **native tool** takes a job by creating `status.json` only if it is not there yet (an exclusive create – the
  system refuses when the file exists). The copy that loses leaves the job alone. A file made this way may be seen
  half written for a moment; readers try again (section 2).
- A **web tool** has no exclusive create. It lets one window at a time read the inbox (the browser's Web Locks do
  that for the windows of one site), and a copy takes only a job it can place: a reply to a job this copy sent, a
  file for a house this copy holds. A job it cannot place it leaves alone, without a status, for another copy.

**Jobs left from an earlier run.** At its start a tool also takes up the jobs of its inbox whose status is not final:
`waiting` – it asks its user again, or starts; `working` – nobody is working on it any more, so the tool either ends
it (`failed`, code `error`, "Fresing Render was closed while it worked on this") or starts it again.

### 6.4 `alive.json`

`{"format": "toolbox-alive", "version": "0.1", "seen": "<time>", "app_version": "1.4.0"}` in the tool's folder.
A **native tool** that watches its inbox SHOULD write it at least every 10 seconds whenever it is free to, and delete
it when it closes (when several copies run: only the copy that wrote the newest one). For a **web tool** it is
optional (MAY): a page cannot write while it closes and is slowed down in the background, so its file says little.

A sender reads it to tell its user what to expect: `seen` within the last 30 seconds = "Fresing Render is open";
older or missing = "Open Fresing Render and it will pick the house up". A job MAY be sent either way; it waits in the
inbox.

**A busy tool is not a closed tool.** A program in the middle of heavy work (one bake step can block Blender for
many seconds) writes neither `alive.json` nor `status.json` meanwhile. So for a job whose status is `working`, the
sender says "working" with the last `text` – not "not open" – whatever `alive.json` says, until that status's
`updated` is more than 5 minutes old. Only then it may say that nothing has been heard for a while.

## 7. Status, replies, cancelling and cleaning up

### 7.1 `status.json`

Written only by the receiving tool, in the job's folder, whole each time (as `job.json`), at most once a second.

```json
{ "format": "toolbox-status", "version": "0.1", "job": "20261118-203000-c81e55",
  "state": "working", "updated": "2026-11-18T20:31:02+01:00",
  "fraction": 0.4, "text": "Baking summer noon (3 of 8)" }
```

| `state` | Meaning |
| --- | --- |
| `waiting` | seen and accepted; waiting for its turn or for the user |
| `working` | being done; `fraction` (0–1) and `text` say how far |
| `done` | finished. `reply` names the job that carried the result back, when there was one |
| `failed` | not done. `text` says why in words for a person; `code` for a program |
| `cancelled` | stopped because the sender or the user asked |

`done`, `failed` and `cancelled` are final: the status does not change after them. `code` is one of `bad-job`
(the job itself is wrong), `unknown-action`, `wrong-type`, `busy`, `error` – a reader MUST take an unknown code as
`error`. `text` is one line, at most 200 characters.

The sender reads `tools/<to>/inbox/<job>/status.json` (not more often than once a second) to show progress. A
`status.json` that cannot be read at one look (it is just being replaced) is read again at the next. A `working`
status stays believed for 5 minutes after its `updated` (6.4). A job folder that is gone means the job is over and
cleaned up.

### 7.2 The result comes back as a reply job

When a job that named a `return` is done and the action made files, the receiving tool sends them as a **new job**
(6.2): `from` itself, `to` the first job's `from`, `action` the first job's `return`, `reply_to` naming itself and
the first job's id, `title` copied. Then it writes the first job's status `done` with `reply` = the new job's id –
the reply first, the status second.

No `return`, or the sender has no tool folder: the tool keeps the result itself and its status `text` says where
("Baked; open Fresing Render to export"). A reply job never has a `return`.

### 7.3 Cancelling

The sender writes `cancel.json` – `{"format": "toolbox-cancel", "version": "0.1", "job": "<id>", "asked": "<time>"}`
– into the job's folder. The receiving tool SHOULD stop and write the status `cancelled`. A job that is already
final stays as it is.

### 7.4 Cleaning up

- The **receiving tool** deletes a reply job as soon as it has taken it in, and any other job of its inbox a day
  after its status became final. It MAY delete the job's files (not `job.json` and `status.json`) as soon as the
  status is final.
- The **sender** MAY delete a job it sent once it has read a final status.
- **Anyone** MAY delete a job folder older than 30 days, with or without `job.json`.

A delete that fails (another program still reads a file) is tried again at the next look. Cleaning up deletes only
real folders and files inside an inbox: an entry that is a link, a shortcut or a junction is never followed and never
deleted through.

## 8. A round trip

House Planner (`H`) and Fresing Render (`R`), as in `samples/Toolbox`:

1. `H` reads `tools/R/toolbox.json`: the action `bake-house` accepts `hpscene`. `alive.json` is fresh: "Fresing
   Render is open".
2. `H` writes `tools/R/inbox/<job1>/sample-house.hpscene`, then `job.json` with `"return": "import-bake"`.
3. `R` sees the job, checks it, writes `status.json` `working` and bakes; `H` shows "Baking summer noon (3 of 8)".
4. `R` writes `tools/H/inbox/<job2>/sample-house.hpbake` and `job.json` with `"action": "import-bake"` and
   `"reply_to": {"tool": "R", "job": "<job1>"}`; then `<job1>/status.json` `done`, `"reply": "<job2>"`.
5. `H`, open or opened later, finds `<job2>` in its own inbox, imports the bake, deletes `<job2>` and `<job1>`.

The owner pressed one button and waited. The same `.hpbake` dropped on a later router would reach House Planner the
same way: as a job in its inbox.

## 9. A web page and the folder

A page cannot reach a folder by itself. What works today, checked 18 Nov 2026:

- **Chrome and Edge on a PC** let a page ask for a folder (`showDirectoryPicker`, read and write). Firefox and Safari
  do not. A tool checks whether `showDirectoryPicker` is there and hides its "Send to" buttons where it is missing;
  everything else works as before. A phone has no Toolbox folder, so nothing changes there.
- **The owner picks the Toolbox folder once.** The page keeps the folder's handle; since Chrome 122 the owner can
  choose "Allow on every visit", and an installed web app keeps the permission by itself
  ([Chrome's note](https://developer.chrome.com/blog/persistent-permissions-for-the-file-system-access-api)).
- **A page asks only when its user acts.** At its start a web tool reads the folder only when the browser still
  holds the permission. When it does not, the browser will ask again – and may only be made to ask from a click. So
  the tool asks at the moment the user presses Send, or shows a small bar ("A bake may be waiting – Check") whose
  button asks. It never asks at start, and it works without the folder until then.
- **Chrome refuses some folders**: the home folder itself, `AppData` (Local and Roaming), `Program Files`,
  `Windows`, `~/Library` and others, with everything inside them; folders *inside* the home folder are fine
  ([the list in Chromium](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/chrome/browser/file_system_access/chrome_file_system_access_permission_context.cc)).
  That is why the folder is `C:\Users\<name>\Toolbox` (section 2).
- **Chrome gives the folder to a site, not to one page.** A site is the address up to the first slash:
  `https://smholte.github.io/house-planner/` and every other page under `https://smholte.github.io` are one site
  and share the permission and the kept folder. Put only pages you trust under the same address as a tool.
- The page MUST check that the picked folder holds `toolbox-folder.json` and say so plainly when it does not. It
  never makes that file itself (section 2).
- A page reads and writes only while it is open, and a tab in the background is slowed down by the browser. A reply
  waits in the page's inbox until the page is opened – that is fine (section 8, step 5). A page need not look at its
  inbox every 2 seconds: often while a job of its own is out and its tab is visible, seldom otherwise.
- A page cannot tell whether an entry of the folder is a link; the rules about links (section 10) bind a tool only
  where it can tell.
- A web tool writes its own manifest into `tools/<its id>/` when the folder is picked, and again when its version
  changes.

## 10. Safety

- The Toolbox folder belongs to one user. Anything that can write to it can send jobs – the same trust as the
  user's Documents folder. No secrets belong in it.
- A receiving tool does **only actions of its own manifest**. A job cannot name a program, a path outside its own
  folder, or a script. `options` are settings of the action, never commands.
- A receiving tool **checks before it opens**: the file names (3.3 – nothing leaves the job folder), the sizes, and
  the file types by content (5.3). A link, shortcut or junction in place of a file or a job folder is refused, and
  cleaning up never follows one (7.4) – where the tool can tell: a native tool can, a web page cannot.
- A tool reads `start` of another tool's manifest for nothing in 0.1. The later router starts programs only from
  manifests in this folder and shows the command the first time.
- A web tool gets no more than the one folder its user picked.
- File formats keep their own checks: a `.hpscene` that passes here is only *recognised*; Fresing Render still
  checks it as `house-scene-format` says.

## 11. Samples and the checker

`samples/Toolbox` is a made-up Toolbox folder in the middle of the round trip of section 8, plus a second job that
is being baked and was just asked to stop. `samples/files` holds one small file per type the tests look at; they are
only good enough to be recognised (the `.hpscene` and `.hpbake` there are not valid house-scene packages). All of it
is written by `tools/make_samples.py`, the same bytes every time.

```
python3 check.py samples/Toolbox            a whole Toolbox folder
python3 check.py path/to/toolbox.json       one manifest
python3 check.py path/to/inbox/<job>        one job
python3 check.py types.json                 the built-in types
python3 check.py --type some-file           which type a file is
```

ERROR = a reader must refuse it; WARNING = readable, look at it. A tool's own tests SHOULD run its manifest and the
jobs it writes through the checker.

**Reference code to copy.** `web/toolbox-folder.js` for a web tool (one plain file) and `tbf/folder.py` with
`tbf/names.py` and `tbf/detect.py` for a native tool do everything of sections 5 to 7: connect the folder, send,
read the inbox, check a job, answer. `tests/test_web.py` runs the JavaScript in Chrome against the Python: both
name every sample file – and several hundred damaged copies – the same type, refuse the same bad jobs with the
same code, and read each other's jobs.

**The trial** (`trial/index.html`) is a page with two sides, one playing House Planner and one playing Fresing
Render, for trying the folder on a real PC before any app is changed. `tools/standin.py` plays the receiving side
as a program. The trial page is the one exception to "a web page never makes the folder": no native tool makes it
yet, so the page offers a button that turns an empty folder named `Toolbox` into the Toolbox folder, after saying
where that folder must be.

## 12. Not in 0.1

Planned for the steps after this one, and deliberately left out now:

- **Routes** (which tool opens which type by default; the user's and the organisation's choices) and the drop
  popup – step B, the background router.
- **Starting a tool** that is closed, and tools without a manifest (any program, any website) – step B.
- **The bridge** `window.toolbox` for web tools shown inside the toolbox window – step A.
- **Themes and organisation profiles** (logo, colours, tool set, shared settings) – step A.
- Converters and chains (an action that turns one type into another on the way), labels in other languages,
  folders inside a job, a Toolbox folder shared over a network.

## 13. Decided in the first review (18 Nov 2026)

Both leads read the draft; the owner carried their answers. What they changed is in the sections named.

| Question or finding | Decided | Where |
| --- | --- | --- |
| Does Fresing Render bake by itself when a house arrives? | It asks once per job ("Bake now"); the status is `waiting` meanwhile | 6.3 |
| A look at the inbox every 2 seconds? | Fine in Blender and in a page; a page looks seldom when none of its jobs is out | 6.3, 9 |
| Where does House Planner keep its sent jobs? | On the device, not with the house | – |
| A day before a finished job is deleted? | Fine; the job's files go at once, the two small JSON files stay the day | 7.4 |
| A program cannot write while it works hard | A `working` job is believed for 5 minutes | 6.4, 7.1 |
| Jobs left by a run that closed or crashed | Taken up again at the next start | 6.3 |
| Two copies of one tool | An exclusive create for programs; one window at a time and "only what I can place" for pages | 2, 6.3 |
| Windows refuses to replace or delete an open file | Try again at the next look; never an error | 2, 7.4 |
| A page cannot see where a folder is | Only a native tool makes the Toolbox folder | 2, 9 |
| A page may ask for permission only from a click | It asks when its user acts | 9 |
| `alive.json` from a page | Optional | 6.4 |
| "No key twice", "no byte-order mark" | Rules for the writer; the checker checks | 3.4 |
| Links | Refused and never followed, where the tool can tell | 7.4, 10 |
| `url` of a web tool | Optional; every copy writes the same one | 4 |
| The sample's `start.program` | What the user's shortcut starts, not a console program | 4 |
| Licence | MIT | `LICENSE` |
