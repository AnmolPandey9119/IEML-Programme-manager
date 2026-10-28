"""Builds docs/User_Guide.pdf (screenshots in docs/img). Run: python -m scripts.build_guide"""
from pathlib import Path

from reportlab.platypus import Image, PageBreak

from app.exports.pdfkit import (A4, KeepTogether, P, Spacer, S, TEAL, banner, build, HRFlowable, mm, rich, esc, grid)

ROOT = Path(__file__).resolve().parent.parent
W = A4[0] - 36 * mm


def shot(name: str):
    from PIL import Image as PI
    path = ROOT / "docs" / "img" / f"g_{name}.png"
    w, h = PI.open(path).size
    width = W * 0.92
    return Image(str(path), width=width, height=width * h / w)


def steps(items):
    return [rich(f"<font color='#12776f'><b>{i}.</b></font>  {t}", "body") for i, t in enumerate(items, 1)]


def section(title, intro, items, img=None, note=None):
    out = [banner(title, W), Spacer(1, 6), P(intro, "sub"), Spacer(1, 6)]
    for s in steps(items):
        out += [s, Spacer(1, 3)]
    if note:
        out += [Spacer(1, 4), rich(f"<font color='#5d6b82'>{esc(note)}</font>", "small")]
    if img:
        out += [Spacer(1, 8), shot(img)]
    return out + [PageBreak()]


story = [P("Programme Manager", "title"), P("User guide for the organising team", "sub"), Spacer(1, 14),
         HRFlowable(width="100%", color=TEAL, thickness=1.2), Spacer(1, 10),
         P("This tool replaces the Word files, Excel sheets and WhatsApp messages used to plan the conference. "
           "It has three parts: Sessions (the agenda), Speakers (the directory) and Lists & Meetings (committees). "
           "Only the organising team signs in. The public website is updated automatically.", "body"), Spacer(1, 10),
         rich("<b>Roles</b>", "h2"),
         grid([[P("Role", "th"), P("What you can do", "th")],
               [P("Admin", "cellb"), P("Everything: create, edit, delete, manage the team and event settings.", "cell")],
               [P("Editor", "cellb"), P("Create and edit sessions, speakers, groups and meetings. Cannot delete or change settings.", "cell")],
               [P("Viewer", "cellb"), P("Read-only. Can export files.", "cell")]], [28 * mm, W - 28 * mm]),
         Spacer(1, 10), rich("<b>What the tool never does</b>", "h2"),
         P("Ticketing, registration, video calls, live streaming, payments, attendee apps and email marketing are out of scope.", "body"),
         Spacer(1, 14), rich("<b>Contents</b>", "h2"),
         P("1. Add a session\n2. Confirm a speaker\n3. Export a list or the agenda\n4. Put the agenda on your website\n5. Warnings and what they mean\n6. Quick answers", "body"),
         PageBreak()]

story += section("1. Add a session", "Every item in the agenda, from a keynote to a tea break, is a session.",
                 ["Open <b>Sessions</b> and pick the day tab. Each day is planned separately.",
                  "Click <b>Add session</b>. Enter the title and choose the session type.",
                  "Type the start and end time in 12-hour format. <i>930</i>, <i>2pm</i> and <i>14:05</i> all work. The duration appears by itself.",
                  "Choose a hall, or <b>All halls merged</b> for a plenary or inaugural session.",
                  "Add the <b>Moderator</b> and the <b>Speakers / Panelists</b> from the directory. Use <i>Add as new speaker</i> if the person is not listed.",
                  "Write the writeup and sub-topics. These show on the website. Internal notes stay private.",
                  "Set the status. <b>Draft</b> is team-only. <b>Published</b> appears on the website within 30 seconds.",
                  "Click <b>Save</b>. If a warning appears, choose <i>Save anyway</i> or <i>Go back and fix</i>."],
                 "session", "Tip: use Duplicate on a session to copy it as a draft, then change the time or hall.")

story += section("2. Confirm a speaker", "The speaker directory holds everyone once. Link them to any number of sessions.",
                 ["Open <b>Speakers</b> and click <b>Add speaker</b>, or click an existing speaker. Only the name is required.",
                  "Add designation, organisation, bio and a JPG or PNG photo. Email and phone are internal and never shown publicly.",
                  "Choose the status: Invited, Confirmed, Tentative or Declined, and add a remark such as the reason.",
                  "Set <b>Confirmed</b> and click <b>Save changes</b>. Everyone on the team who has alerts on gets an email straight away.",
                  "A confirmed speaker appears on the website next to their published sessions. Speakers who are not confirmed never appear."],
                 "speaker", "An admin can switch the confirmation email off for the whole event or for one person in the Team tab.")

story += section("3. Export a list or the agenda", "Every export is a real file you can send, print or edit.",
                 ["<b>Agenda:</b> Sessions, then <b>Export</b>. Tick what to include: writeups, sub-topics, draft sessions, internal notes. Choose PDF or Word.",
                  "<b>Speaker runsheet:</b> the same dialog. A compact table of times, halls and speakers for the on-ground team.",
                  "<b>Speakers:</b> Speakers, then <b>Export</b>. Choose all statuses or Confirmed only, as PDF or Excel. Open one speaker and use <b>Profile PDF</b> for a one-page card.",
                  "<b>Committees:</b> Lists & Meetings, pick a group, then <b>Export</b> for the member list (PDF or Excel) and meeting schedule. Open a meeting for its <b>Record PDF</b>.",
                  "To share a member list without a login, an admin uses <b>Share link</b>. It is read-only, and contact details stay hidden unless switched on."],
                 "export", "Leave Internal notes off when the file goes to sponsors or speakers. The speaker Excel file contains private phone numbers and emails.")

story += section("4. Put the agenda on your website", "One line of HTML, pasted once. After that no developer work is needed.",
                 ["Open <b>Event setup</b> and set the event status to <b>Active</b>. Draft events are not public.",
                  "Open the <b>Website</b> tab. You will see how many sessions and speakers are public.",
                  "Click <b>Copy</b> on the embed code and paste it into the page where the agenda should appear.",
                  "Change a session or speaker and save. The website shows the change within 30 seconds, with no upload step.",
                  "Only Published sessions and Confirmed speakers are shown. Email, phone and internal notes are never exposed."],
                 "website", "Developers can also read the programme as JSON from the public API address shown in the Website tab.")

story += [banner("5. Warnings and what they mean", W), Spacer(1, 6),
          P("Warnings never block saving. They only ask you to check. Parallel sessions in different halls are normal and are not warned about.", "sub"), Spacer(1, 6),
          grid([[P("Warning", "th"), P("Meaning", "th")],
                [P("Same hall overlaps", "cellb"), P("Two sessions in one hall have overlapping times on the same day.", "cell")],
                [P("Speaker double-booked", "cellb"), P("The same person (speaker, panelist or moderator) is in two sessions at the same time.", "cell")],
                [P("Merged hall conflict", "cellb"), P("A session using all halls overlaps another session in any hall.", "cell")],
                [P("End before start / past midnight", "cellb"), P("The times look like a typing error.", "cell")],
                [P("Very short or long", "cellb"), P("Shorter than 5 minutes or longer than 4 hours.", "cell")],
                [P("Tight changeover", "cellb"), P("Less than 5 minutes before the next session in the same hall (not shown around breaks).", "cell")]],
               [52 * mm, W - 52 * mm]),
          Spacer(1, 14), banner("6. Quick answers", W), Spacer(1, 6)]
for q, a in [("A session is not on the website.", "Check that the session is Published, the event is Active, and wait up to 30 seconds."),
             ("A speaker name is missing on the website.", "The speaker must be Confirmed."),
             ("I cannot edit or delete.", "Editors cannot delete and Viewers are read-only. Archived events are read-only for everyone. Ask an admin."),
             ("How do I add a team member?", "Admin: Team tab, then invite by email. They get a link to set a password. There is no self-registration."),
             ("Can I run more than one event?", "Yes. Each event is separate and data never mixes.")]:
    story += [rich(f"<b>{esc(q)}</b>", "body"), P(a, "small"), Spacer(1, 5)]

out = ROOT / "docs" / "User_Guide.pdf"
out.write_bytes(build(story, "Programme Manager · User guide", "Programme Manager", "User guide"))
print("written", out)
