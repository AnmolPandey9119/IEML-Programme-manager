"""Loads a ready-to-review demo event (Section 10 of the requirements).

    python -m scripts.seed_demo            # creates demo@example.com / demo12345 and the demo event
    python -m scripts.seed_demo --reset    # removes the earlier demo event first

Contains on purpose: a same-hall time overlap, a plenary that clashes with a parallel session, and a speaker
booked in two halls at once, so every warning can be seen working.
"""
import sys
from datetime import date, time, timedelta

from app.database import Base, SessionLocal, engine
from app.migrate import add_missing_columns
from app.models import (Attendance, Event, EventDay, EventMember, EventStatus, Group, GroupMember, GroupType, Hall,
                        Meeting, MeetingAttendance, MeetingStatus, PublishStatus, Role, Session, SessionRole,
                        SessionSpeaker, SessionSubtopic, SessionType, Speaker, SpeakerStatus, User)
from app.security import hash_password

EMAIL, PASSWORD, NAME = "demo@example.com", "demo12345", "Demo Admin"
T = time


def next_monday() -> date:
    d = date.today() + timedelta(days=60)
    return d + timedelta(days=(7 - d.weekday()) % 7)


SPEAKERS = [  # name, designation, organisation, status, bio
    ("Dr. Ananya Rao", "Managing Director", "GreenGrid Energy", SpeakerStatus.confirmed,
     "Ananya leads GreenGrid Energy, one of India's fastest-growing renewable utilities, with 22 years in power and climate finance."),
    ("Rajiv Mehta", "Secretary", "Ministry of New and Renewable Energy", SpeakerStatus.confirmed,
     "Rajiv oversees national solar and green hydrogen missions and chairs the inter-ministerial energy transition group."),
    ("Prof. Kavita Iyer", "Director", "Centre for Climate Policy, IIT Delhi", SpeakerStatus.confirmed,
     "Kavita researches carbon markets and urban resilience. She advises several state governments on adaptation planning."),
    ("Sandeep Kulkarni", "Chief Sustainability Officer", "Bharat Steel Ltd", SpeakerStatus.tentative,
     "Sandeep runs decarbonisation for a 20 MTPA steel producer, including India's first hydrogen-based pilot line."),
    ("Meera Nair", "Founder", "Tidal Labs", SpeakerStatus.confirmed,
     "Meera founded Tidal Labs, a startup turning coastal waste plastics into construction materials."),
    ("Arjun Bansal", "Partner", "Evergreen Capital", SpeakerStatus.invited,
     "Arjun invests in climate and agri-tech at growth stage and sits on four sustainability boards."),
    ("Farah Khan", "Journalist and Moderator", "The Climate Desk", SpeakerStatus.declined, ""),
]


def main(reset: bool) -> None:
    Base.metadata.create_all(bind=engine)
    add_missing_columns()
    with SessionLocal() as db:
        user = db.query(User).filter_by(email=EMAIL).first()
        if not user:
            user = User(email=EMAIL, full_name=NAME, password_hash=hash_password(PASSWORD))
            db.add(user)
            db.flush()
        old = [m.event for m in db.query(EventMember).filter_by(user_id=user.id) if m.event.name == "Bharat Sustainability Summit"]
        if old and not reset:
            print("Demo event already exists. Use --reset to rebuild it.")
            return
        for ev in old:
            db.delete(ev)
        db.flush()

        d1 = next_monday()
        ev = Event(name="Bharat Sustainability Summit", edition="2027", venue_name="Bharat Mandapam", venue_city="New Delhi",
                   theme_line="Powering a Net-Zero Bharat", website_url="https://example.com/summit", status=EventStatus.active)
        db.add(ev)
        db.flush()
        db.add(EventMember(event_id=ev.id, user_id=user.id, role=Role.admin))
        days = []
        for i in range(2):
            d = d1 + timedelta(days=i)
            row = EventDay(event_id=ev.id, day_date=d, label=f"Day {i + 1} — {d.strftime('%A')}, {d.strftime('%b')} {d.day}")
            db.add(row)
            days.append(row)
        halls = [Hall(event_id=ev.id, name=n, position=i) for i, n in enumerate(("Hall 4", "Hall 5"))]
        db.add_all(halls)
        sp = []
        for n, des, org, st, bio in SPEAKERS:
            s = Speaker(event_id=ev.id, full_name=n, designation=des, organisation=org, status=st, bio=bio,
                        email=n.split()[-1].lower() + "@example.com", phone="+91 98100 00000",
                        status_remark="Awaiting travel approval" if st == SpeakerStatus.tentative else "")
            db.add(s)
            sp.append(s)
        db.flush()
        h4, h5 = halls
        ananya, rajiv, kavita, sandeep, meera, arjun, farah = sp
        P, D = PublishStatus.published, PublishStatus.draft
        R = SessionRole

        def add(day, start, end, title, typ, hall, people=(), status=P, merged=False, writeup="", subs=(), notes=""):
            s = Session(event_id=ev.id, day_id=days[day].id, hall_id=None if merged else hall.id if hall else None,
                        is_merged=merged, title=title, session_type=typ, start_time=start, end_time=end, status=status,
                        writeup=writeup, internal_notes=notes)
            for i, t in enumerate(subs):
                s.subtopics.append(SessionSubtopic(text=t, position=i))
            for i, (who, role) in enumerate(people):
                s.speaker_links.append(SessionSpeaker(speaker_id=who.id, role=role, position=i))
            db.add(s)

        # ---- Day 1
        add(0, T(9, 0), T(9, 45), "Registration and Welcome Tea", SessionType.networking, None, merged=True)
        add(0, T(10, 0), T(11, 0), "Inaugural Ceremony", SessionType.inaugural, None, [(rajiv, R.speaker), (ananya, R.speaker)], merged=True,
            writeup="The summit opens with a welcome address, the release of the Net-Zero Bharat Report and the ceremonial lamp lighting.")
        add(0, T(11, 0), T(11, 30), "Tea Break", SessionType.break_, None, merged=True)
        add(0, T(11, 30), T(12, 30), "Keynote: Financing the Energy Transition", SessionType.keynote, h4, [(ananya, R.speaker)],
            writeup="How India can mobilise USD 250 billion of private capital for renewables, storage and grids by 2030.",
            subs=["The cost of capital gap for clean energy", "Role of blended finance and green bonds"])
        add(0, T(12, 0), T(13, 0), "Workshop: Measuring Scope 3 Emissions", SessionType.workshop, h5, [(kavita, R.speaker)],
            writeup="A hands-on session on building a defensible Scope 3 inventory.",
            notes="Needs a projector and extra power strips. Runs parallel to the Hall 4 panel; Prof. Iyer is booked in both (demo of the speaker clash).")
        add(0, T(12, 0), T(13, 0), "Panel: Green Hydrogen, Hype or Reality?", SessionType.panel, h4,
            [(kavita, R.moderator), (sandeep, R.panelist), (meera, R.panelist)],
            writeup="Industry and policy voices debate whether green hydrogen can be cost-competitive this decade.",
            subs=["Electrolyser costs and local manufacturing", "Offtake guarantees for steel and fertiliser", "Water and land constraints"],
            notes="Overlaps the Hall 4 keynote on purpose (demo of the same-hall overlap warning).")
        add(0, T(13, 30), T(14, 30), "Networking Lunch", SessionType.networking, None, merged=True)
        add(0, T(14, 30), T(15, 15), "Fireside Chat: Building Climate Startups", SessionType.fireside, h5, [(meera, R.speaker), (arjun, R.moderator)],
            status=D, writeup="Draft: speaker line-up still being finalised.")
        # ---- Day 2
        add(1, T(10, 0), T(11, 0), "Plenary: The Road to 2070", SessionType.plenary, None, [(rajiv, R.speaker), (kavita, R.speaker)], merged=True,
            writeup="A whole-venue session on India's net-zero roadmap, bringing together government, industry and research.")
        add(1, T(10, 30), T(11, 30), "Roundtable: Carbon Markets", SessionType.roundtable, h5, [(kavita, R.speaker)],
            notes="Clashes with the merged plenary and double-books Prof. Iyer. Demo of both warnings.")
        add(1, T(11, 30), T(12, 0), "Tea Break", SessionType.break_, None, merged=True)
        add(1, T(12, 0), T(12, 20), "Lightning Talk: Plastic to Pavement", SessionType.lightning, h4, [(meera, R.speaker)],
            writeup="Five minutes of slides, fifteen minutes of questions on turning waste plastic into roads.")
        add(1, T(15, 0), T(16, 0), "Leadership Address: Steel Without Carbon", SessionType.leadership, h4, [(sandeep, R.speaker)])
        add(1, T(16, 0), T(16, 30), "Valedictory and Vote of Thanks", SessionType.talk, None, [(ananya, R.speaker)], merged=True)

        # ---- Organising committee
        oc = Group(event_id=ev.id, name="Organising Committee", group_type=GroupType.oc)
        db.add(oc)
        db.flush()
        people = [("Dr. Ananya Rao", "Managing Director", "GreenGrid Energy", "Chair"),
                  ("Vikram Sethi", "Programme Director", "Summit Secretariat", "Convenor"),
                  ("Pooja Menon", "Head of Operations", "Summit Secretariat", "Member"),
                  ("Imran Sheikh", "Partnerships Lead", "Summit Secretariat", "Member")]
        members = []
        for i, (n, des, org, role) in enumerate(people):
            m = GroupMember(group_id=oc.id, name=n, designation=des, organisation=org, role_in_group=role, position=i,
                            email=n.split()[-1].lower() + "@example.com", phone="+91 98200 11111")
            db.add(m)
            members.append(m)
        db.flush()
        meet = Meeting(group_id=oc.id, title="Programme review meeting", meeting_date=date.today() + timedelta(days=7),
                       start_time=T(15, 0), duration_minutes=60, location="Secretariat boardroom, 3rd floor",
                       agenda="1. Status of speaker confirmations\n2. Day 1 hall allocation\n3. Sponsor deliverables\n4. Open items",
                       status=MeetingStatus.scheduled)
        done = Meeting(group_id=oc.id, title="Kick-off meeting", meeting_date=date.today() - timedelta(days=21),
                       start_time=T(11, 0), duration_minutes=90, location="Online (shared link by email)",
                       agenda="1. Roles and responsibilities\n2. Theme and tracks\n3. Timeline", status=MeetingStatus.completed,
                       minutes="Theme finalised as 'Powering a Net-Zero Bharat'. Two parallel halls approved. Vikram to circulate the speaker wish-list by Friday.")
        db.add_all([meet, done])
        db.flush()
        marks = [Attendance.attended, Attendance.attended, Attendance.apologies, Attendance.absent]
        for m, a in zip(members, marks):
            db.add(MeetingAttendance(meeting_id=done.id, member_id=m.id, status=a))
        db.commit()
        print(f"Demo ready. Sign in with {EMAIL} / {PASSWORD}")


if __name__ == "__main__":
    main("--reset" in sys.argv)
