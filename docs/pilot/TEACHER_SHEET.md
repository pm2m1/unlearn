# Fractions practice pilot: teacher sheet

Items in ⟨angle brackets⟩ are for Parth to fill in before this sheet goes to the school.

## What it is

A short fractions activity that students do on a phone or computer, in two sessions of about 20 minutes, 7 to 14 days apart. It is a small first test (20 to 30 students) of one question: when a student gets fractions wrong, can the program work out which earlier skill (for example, finding a common multiple) is causing the mistakes?

- **Session 1:** 5 check questions, then up to 6 follow-up questions on earlier skills, then one practice question on the skill the program picked.
- **Session 2:** 5 different check questions on the same skills. Afterwards the student sees which skill was practised last time.

It is not a test. It gives no marks and says nothing about you or your teaching. Every question and every sentence a student sees was written in advance and checked by Parth; nothing is generated on the spot by an AI model. The pilot makes no claim that students learn more from it.

## What data is collected

| Collected | Not collected |
| --- | --- |
| A random code per student (like `K7Q2-M3XAP`) | Names, photos, emails, phone numbers |
| For each answer: the code, session 1 or 2, which question, which option (A–D), right or wrong, the mistake that option usually shows, the time, and how long the answer took | Anything typed by a student (there are no text boxes) |
| Whether the student agreed to start ("yes" or "no" on the first screen) | Device details, location |
| Your optional 1–5 rating per code, and your "I went through the practice topic" tick | IP addresses: the program does not log them |

**The code-to-name list stays with you, on paper.** Never type a student's name into the program or send the list to Parth.

**IP addresses.** The program does not store IP addresses. The two hosting companies it runs on, Render (the website) and Neon (the database, in Singapore), see IP addresses in their own server logs, as any website host does. We do not collect, see or control those logs.

## Consent

- A student takes part only if a parent has signed the opt-in slip ([PARENT_NOTE.md](PARENT_NOTE.md)) and the principal has given written permission. The school keeps the signed slips; Parth never sees them.
- Only students with a signed slip get a code.
- At the start of each session the student sees a short explanation in English and Hindi, with a "Yes, I'm happy to do this" button and an "I don't want to do this" button. "No" ends it there; nothing but that "no" is saved.
- A student can stop at any time by closing the page.

## How a session runs

Parth's [RUNBOOK.md](RUNBOOK.md) has the full checklist. In short:

1. **Before class:** open the teacher page (`⟨site⟩/pilot/teacher`) with your class code and teacher key. 5–10 minutes before class, open `⟨site⟩/pilot` on any phone and wait until it says **Ready**.
2. **Hand out the code slips** (printed from the teacher page; codes only).
3. **Start row by row, about 30 seconds apart.** If everyone taps Start in the same second, the first answers can take several seconds.
4. Students type their code and follow the screens. If a student sees **Try again**, they tap it; their answer was not lost.
5. **Session 2:** on the day, press **Open session 2** on the teacher page before students start. Until then, a student who logs in again sees "Your teacher will tell you when session 2 starts".

## The teacher view

For each code: progress, check scores, the earlier skill the program picked, the mistakes the student's answers showed, and the approach the program would suggest (with steps, written for teachers).

Two optional inputs per code, both stored as just the code and the answer:

- **"Matches your view?" (1–5):** does the program's diagnosis match what you know about this student?
- **"I went through the practice topic":** tick it if you went over the picked skill with the student between the sessions. The pilot does not ask you to, and does not control it; this tick is the only record of it.

You can download two spreadsheets (codes only): every answer, and a one-line summary per code.

## Deleting data

- **One student** (for example, a parent withdraws): press **Delete** next to the code. Every answer and tick for that code is removed and the code stops working.
- **The whole class:** type the class code at the bottom of the teacher page and press **Delete class**.
- **At the end of the pilot** Parth deletes all pilot data by ⟨date agreed with the school⟩.
- **Backups:** deleted data may remain in backups for up to 7 days. Neon, the database company, can restore the database to any point in the last 6 hours, and can recover a deleted database for 7 days; after that it is gone. Parth does not take any extra copies or snapshots.

## Contact

Parth Mishra, ⟨contact⟩.
