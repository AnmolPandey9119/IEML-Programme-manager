# Session, Speaker & List Management System

Internal tool for conference organising teams (Sessions · Speakers · Lists & Meetings).

## Run (local)
```
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env              # Windows: copy .env.example .env
uvicorn app.main:app --reload
```
- App: http://localhost:8000
- API docs: http://localhost:8000/docs
- Tests: `pip install -r requirements-dev.txt && python -m pytest -q tests`
- Demo data (recommended for first look): `python -m scripts.seed_demo` then sign in with `demo@example.com` / `demo12345` (`--reset` rebuilds it)
- Optional `.env` keys: `SECRET_KEY` (set a long random value in production), `EVENT_TIMEZONE`, `SMTP_*`

Pehli baar kholne par app "Create the first admin" screen dikhayegi (sirf ek baar). Uske baad sab log invitation se judte hain.
SMTP set nahi hai to emails console mein log hoti hain, aur invite link Team tab mein copy kar sakte hain.

## Build progress
- [x] **Phase 1** — Auth, invites, roles (Admin/Editor/Viewer), multi-event isolation, Event setup (days, halls, status), Team + notification toggles
- [x] **Phase 2** — Module B: Speakers (profile, photo, status with remark, confirmation email to team) + new design system
- [x] **Phase 3** — Module A: Sessions + conflict detection (Overview, timetable list, hall grid, session editor)
- [x] **Phase 4** — Module C: Lists & Meetings (groups, members, meeting planner, attendance, minutes, read-only share link)
- [x] **Phase 5** — Live website publishing (public API + one-line embed) + late-change alerts
- [x] **Phase 6** — Exports (PDF / Word / Excel) + demo seed data
- [x] **Phase 8** — Speaker invitations: personal form link per speaker, public speaker form, admin review (add / reject), assign to sessions
- [x] **Phase 7** — User guide (`docs/User_Guide.pdf`) + staging checklist (all phases complete)

## Staging checklist (Section 10 of the requirements)
- [x] Sample event: 2 days, 2 halls, 14 sessions (plenary, panel and more), 7 speakers, one committee with members and a meeting: `python -m scripts.seed_demo`
- [x] Pre-loaded time overlap (Day 1, Hall 4) and plenary vs parallel session (Day 2): see **Overview → Needs attention**
- [x] Website sync: **Website** tab live preview, or `/preview.html?event=<key>`
- [x] User guide: `docs/User_Guide.pdf` (rebuild with `python -m scripts.build_guide`)
- [ ] Before production: set a long random `SECRET_KEY`, a Postgres `DATABASE_URL`, `SMTP_*` and `FRONTEND_URL` in `.env`, and do not run the demo seed there.

## Phase 8 — what to check
1. **Speaker Invites** tab -> *Invite speakers* has two options.
   **Invite by link**: *Create invite link*, then *Copy link* and send it yourself to anyone (WhatsApp, LinkedIn, personal email). One shared link for everyone, `/#/speaker-form/open/<token>`. Responses still land in Pending and nothing is added automatically. *Replace link* kills the old address, *Switch off* closes it (responses already received are kept). The same email sending twice updates one response, no duplicates.
   **Invite by email**: paste emails (`Name <email>` or just the email), optional note. Each person gets a personal link. With no SMTP the email is only logged: use **Copy link** in *Invitations sent*.
2. Open the link in a private window (`/#/speaker-form/<token>`, no login): name, designation, bio, expertise, topics, session idea, formats, days, requirements. Submitting again edits the response while it is still *Pending*.
3. The response appears under **Pending** (team admins and editors with alerts on get an email). Click it to read everything.
4. **Add as speaker** creates the Speaker (same email already in the directory = linked, not duplicated). Choose status (Tentative by default, so nothing goes public by accident) and optionally assign a session right away. **Reject** keeps the response and can be restored.
5. In an *Added* response: **Add to a session** (Speaker / Panelist / Moderator) or **Remove**. Schedule clashes come back as a warning, never a block. Late-change alerts still apply.
6. Only Admin invites, adds, rejects and deletes; Editor can assign sessions; Viewer is read-only. Deleting an invitation switches its link off but keeps any response.
7. New tables are created on start-up (`create_all`), nothing to run by hand. Tests: `python -m pytest -q tests/test_phase8.py`.

## Phase 6 — what to check
Run `python -m scripts.seed_demo`, sign in as `demo@example.com` / `demo12345`.
1. **Sessions → Export**: choose Writeups / Sub-topics / Draft sessions / Internal notes, then *Agenda PDF*, *Agenda Word* or *Speaker runsheet PDF*.
   With notes and drafts off (the default) neither appears in the file. Unconfirmed speakers are marked "(Tentative)" etc.
2. **Speakers → Export**: full list as PDF (photos, bios, sessions; no contact details) or Excel (every field, one row each); *All statuses* or *Confirmed only*.
   Open a speaker and use **Profile PDF** for the one-page card.
3. **Lists & Meetings → Export** (per group): member list PDF / Excel and meeting schedule PDF. Open a meeting and use **Record PDF** (details, agenda, attendance, minutes).
4. All roles, including Viewer, can export. Other events' data is never reachable (404).
5. The demo event deliberately contains a same-hall overlap, a plenary clashing with a parallel session and a speaker booked in two halls: see them on **Overview**.
Fonts: DejaVu Sans is bundled in `app/assets/fonts` so PDFs render accents and symbols on any machine.

## Phase 5 — what to check
1. Set the event to **Active** (Event setup). Open the **Website** tab: it shows how many sessions/speakers are public and a one-line embed code with a live preview.
2. Only **Published** sessions and **Confirmed** speakers appear. Draft sessions, unconfirmed speakers, emails, phones and internal notes are never exposed. Draft events return 404.
3. Change a session or speaker and reload the preview: the change is visible on the next request (the feed is cached for 5 s at most, well inside the 30 s promise).
4. Public feed: `GET /api/public/events/<key>/agenda` (ETag + 304, GET-only CORS). Embed script: `/embed.js`; demo page: `/preview.html?event=<key>`.
5. Late-change alert: edit the time, hall or speakers of a Published session when the event day is within 48 hours (Asia/Kolkata) and the team gets an email. Admin can switch it off per event and per person (Team tab).

## Phase 4 — what to check
1. **Lists & Meetings** tab: create groups (OC, Advisory Council, Sub-committee, Working Group, Custom).
2. Add members; use *Find someone already in this event* to reuse a person from another group or the speaker directory
   (same person, different role per group). Reorder with the arrows (Chair first).
3. **Meetings**: schedule with title, date, time, duration, plain-text location; write the agenda, mark attendance
   (attended / absent / sent apologies, or *Mark all attended*), record minutes, set Scheduled / Completed / Cancelled.
4. **Archive** a group: read-only and hidden from the main list (*Show archived* to see it, *Restore* to bring it back).
5. **Share link** (admin): read-only member list that opens without login. Email/phone are hidden unless the admin switches
   them on. Meetings, minutes and notes are never shared. The link can be replaced or switched off at any time.
6. Editors create and edit; only Admins delete members, meetings and groups or create share links.

## Phase 3 — what to check
1. **Sessions** tab: pick a day, filter by hall or status, switch between **List** and **Hall grid**.
2. **Add session**: type 12-hour times freely (`9:30 AM`, `930`, `2pm`, `14:05`); duration is calculated live.
3. Choose a hall, or **All halls merged (plenary)**. Attach a **Moderator** and **Speakers / Panelists** from the directory
   (or "Add as new speaker" on the spot). Add, edit, reorder and remove **sub-topics**.
4. Warnings (never blocking, shown live in the editor and again as a "Save anyway / Go back and fix" prompt):
   same-hall overlap, speaker double-booked (any role), merged-hall conflict, end before start, past midnight,
   shorter than 5 min / longer than 4 h, and a soft notice for less than 5 minutes changeover.
   Parallel sessions in different halls are *not* a conflict.
5. **Overview** tab: programme-at-a-glance timeline per day, issues list, speaker status, setup checklist.
6. Editor can create/edit sessions; only Admin can delete; Viewer is read-only. Duplicate creates a draft copy.

## Phase 2 — what to check
1. **Speakers** tab: add a speaker (name is the only required field), search, filter by status.
2. Upload a JPG/PNG photo (stored in the database, resized to 800 px) and remove it again.
3. Set status to **Confirmed** and save: every team member with email alerts on receives an email
   (without SMTP the email is printed in the server console). Turn it off per person or per type in **Team**.
4. Viewer sees everything read-only; Editor can add/edit but not delete; only Admin can delete a speaker.
5. A speaker of another event is never visible (404).
6. The database upgrades itself on start-up (new columns are added automatically), so Phase 1 data is kept.

## Phase 1 — what to check
1. First-admin setup, login/logout.
2. Create an event with a date range -> days auto-created ("Day 1 — Monday, Feb 8").
3. Event Setup: edit details, add/rename/delete/reorder halls, add/rename/delete days, change status (Draft/Active/Archived).
4. Archived event -> everything read-only (admin can switch status back).
5. Team: invite by email (editor/viewer), accept link in a private window, change roles, per-person email toggle, remove member, per-type notification toggles.
6. Permissions: Editor/Viewer cannot change event settings or invite; the last admin cannot be removed/demoted.
7. Isolation: a second user's event is invisible to the first (404).

## Decisions taken where the PDF was silent
- Past-midnight vs end-before-start: a PM start with an AM end (e.g. 11 PM to 1 AM) is reported as *past midnight*;
  any other end-earlier-than-start is *end before start*.
- Changeover notice is skipped when either session is a Break or Networking slot.
- A session may be saved without a hall ("Hall to be confirmed"), for example while the venue plan is still open.
- Share links hide contact details by default (a public link should not leak phone numbers).
- Speakers are sorted ignoring titles (Dr., Prof., ...).
- Merged hall = `is_merged=True` + `hall_id=NULL` (one representation).
- Anyone logged in can create an event and becomes its Admin.
- A hall / day that still has sessions cannot be deleted.
- Re-inviting the same email replaces the earlier pending invite.
- Invite links expire after 7 days (`INVITE_EXPIRE_DAYS`).