# 0208 – Learn as you go: an unused function gets "Learn it" as well as "Hide it", a personal learning list, one quiet "next to learn"

**Who:** worker · **Status:** waiting – **after 0181** (builds on its counts, its declutter question and its file)
· **Branch:** `task/0208-learn-as-you-go`
**Started by:** lead chat, 18 Nov 2026 (owner, after seeing 0181's "Unused panels" box: "a user might not know about a
function or know how to use it – not just offer to hide it, but also offer the user guide or this function in the test
tour, or add it to a to-do list for learning, so a user learns the app adaptively over time")
· **Lane:** Usage (0181's module, the declutter question) + Learning (the list is where the lessons plug in later)
**Area:** new `fresing_render/core/learning.py` (the list and the rules, no Blender), `fresing_render/blender/learning.py`
+ its operators / panel or window; additive: 0181's usage module (the declutter question's buttons, the file's
`learning` part), `ui_topbar.py` (one Fresing-menu item), the What's next card (0062) and What's new (0199) – one
button each, `core/functions.py` (entries), the guide, the tour, the PC check
**Model:** Opus · effort Medium · **Place:** Claude Code on the web, environment "CAD-render-animation"

## Goal

A function a user never uses may be one he does not know or does not know how to use – not one he does not want. The
app then offers to **teach** it as readily as to **hide** it, keeps a short personal learning list, and now and then
suggests one next function that fits the work he already does. Over weeks each user learns the part of the app he
needs, at his own pace. Everything stays on the PC, as in 0181.

## Background

- 0181 (read its design part and report first): counts per function id and per panel in `<config>/fresing_usage.json`,
  sessions = app starts, the declutter question after `threshold` sessions without a use (one per session, each panel
  once, never for what the open project uses; Hide / Not now / Don't ask again), "Back to the workspace as it came",
  profiles, "Clear my usage data", "Track my usage" switch, no network code (tested).
- `core/functions.py` already gives each function its **`guide`** anchor and its **`tour`** stop ids (0124, 0199), and
  `since=` / `changed=`. So "Show it in the guide" and "Show it in the test tour" need no new data.
- The test tour: Help › Make test tour project, sets of stops with Go + check (0059, 0123). The lesson highlight (0062,
  Preferences › Lesson highlight, look C bright, Fresing Green) points at a button.
- The What's next card (0062) and What's new after an update (0199, a tour of only the new and changed test models).
- The lessons Show me / Build it yourself are the next Learning task (lead briefs it); this task leaves a place for them.

## What to build

1. **The declutter question teaches first.** The box says the panel or function name and its one-line "what it does"
   (from the function list), then: **Show me in the guide** (opens the guide at its anchor – offline copy if there is
   one, else the GitHub page) · **Show me in the test tour** (makes or opens the tour project at the first stop of its
   `tour` ids and runs Go, the lesson highlight on the button; a function with no stop: the button is greyed with the
   reason in its tooltip) · **Add to my learning list** · **Hide it** · Not now · Don't ask again. Same rules as 0181
   (one per session, never for what the project uses). 0181's box in Preferences gets an "Offer to teach unused
   functions" tick beside "Offer to hide unused panels" (both on by default – owner may change).
2. **My learning list** (Fresing menu › My learning list…, a small window or panel – worker proposes, the Set-up
   window style of 0062 if it fits): each item = name, one line, **Guide**, **Tour**, (later **Show me** / **Build it
   yourself** when a lesson exists – a hook, greyed now), **Done**, remove. Items come from the question, from a right-
   click "Add to my learning list" on any button that has a function entry, from What's new ("Add the new functions to
   my learning list"), and from the suggestion (3). **Learned by itself:** an item is ticked when the user has used the
   function on N different days (default 3, a setting), and the list says so once ("You've got the hang of Hook to
   here"). Kept in 0181's file under `learning`; in the profile export only when "include my usage counts" is ticked;
   "Clear my usage data" asks whether to clear the list too.
3. **Next to learn (quiet, at most one a session):** on the What's next card, one line "Next to learn: [function] –
   [why]" with Learn / Not interested. Picked by plain rules (no AI, no network): functions in the families and
   workspace the user works in that he has never used, a step after what he uses (the function list's order and
   families; the worker proposes a small `next_after` field or a rule from families + order – keep it simple), never
   what he hid or turned down, never what the open project already uses. A setting turns it off.
4. **Rules for a visible change** (CLAUDE.md section 6): tooltips; function-list entries + guide anchors with `since=`
   (0199's `changed=` on 0181's entries if they change); guide part "Learn as you go"; a test-tour stop; PC-check line.

## Done when

- [ ] Tests (no Blender) for the list and the rules: the question's choices, learned after N days, next-to-learn never
      offers hidden / turned-down / project-used / Full-access-only items, the file round trip with 0181's file
      (older file without `learning` reads fine), no network imports.
- [ ] Real-app test: a question with the three learn buttons; Show me in the test tour lands on the right stop with
      the highlight; the list window opens from the menu and from a right-click; What's new adds the new functions.
- [ ] Screenshots checked with `tools/ui_screens.py`; the box and the list fit at 100–200 % display scaling.
- [ ] Version raised, CHANGELOG, full GitHub run green, merged, main contains the commit; report with the proposals
      the owner should look at (default N, the next-to-learn rule, what the box says).

## Not in this task

The lessons themselves (Show me / Build it yourself – next Learning task; only the greyed hook here). Changes to the
tour's stops. Anything sent off the PC.

---

## Report (filled in by the chat that did the task)

**Chat / date:**

**What changed:**

**Tested and measured:**

**Owner decides:**

**Open points / follow-up tasks:**
