"""
Marcus J. Elliot — 10 Orbs to Better Treatment Plan
Clean clinical format matching the ICANotes-style sample
Black/grey only, no color, structured for document processing
"""
import os
from reportlab.pdfgen import canvas as C
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor, white, black

OUT = "/mnt/user-data/outputs/Marcus_Elliot_Treatment_Plan_v2.pdf"
W, H = letter

# Pure greyscale palette
BLACK  = HexColor('#000000')
DARK   = HexColor('#1a1a1a')
MID    = HexColor('#444444')
GREY   = HexColor('#777777')
LGREY  = HexColor('#aaaaaa')
RULE   = HexColor('#bbbbbb')
BGFILL = HexColor('#f2f2f2')
WHITE  = white

LM = 50   # left margin
RM = W - 50  # right margin
TW = RM - LM

def line(c, y, lw=0.5, col=RULE):
    c.setStrokeColor(col); c.setLineWidth(lw)
    c.line(LM, y, RM, y)

def hline(c, y, col=BLACK, lw=1.2):
    c.setStrokeColor(col); c.setLineWidth(lw)
    c.line(LM, y, RM, y)

def txt(c, x, y, s, font="Helvetica", size=9, col=DARK, anchor="left"):
    c.setFillColor(col); c.setFont(font, size)
    if anchor == "center": c.drawCentredString(x, y, s)
    elif anchor == "right": c.drawRightString(x, y, s)
    else: c.drawString(x, y, s)

def wrap(c, x, y, mw, s, font="Helvetica", size=9, col=DARK, lh=13):
    c.setFillColor(col); c.setFont(font, size)
    words = s.split(); line_ = ""
    for w_ in words:
        t = (line_ + " " + w_).strip()
        if c.stringWidth(t, font, size) <= mw: line_ = t
        else:
            if line_: c.drawString(x, y, line_)
            y -= lh; line_ = w_
    if line_: c.drawString(x, y, line_); y -= lh
    return y

def wrap_h(c, mw, s, font="Helvetica", size=9, lh=13):
    words = s.split(); line_ = ""; lines = 1
    for w_ in words:
        t = (line_ + " " + w_).strip()
        if c.stringWidth(t, font, size) <= mw: line_ = t
        else: lines += 1; line_ = w_
    return lines * lh

def section_head(c, y, text):
    """Bold underlined section heading like the sample"""
    c.setFillColor(BLACK); c.setFont("Helvetica-Bold", 10)
    c.drawString(LM, y, text)
    hline(c, y - 3, BLACK, 0.8)
    return y - 16

def field_row(c, y, label, value, label_w=120):
    """Label: Value on same line"""
    txt(c, LM, y, label, "Helvetica-Bold", 9, DARK)
    txt(c, LM + label_w, y, value, "Helvetica", 9, DARK)
    return y - 13

def blank_field(c, y, label, width=200):
    """Label followed by blank line"""
    txt(c, LM, y, label + " ", "Helvetica-Bold", 9, DARK)
    lw_ = c.stringWidth(label + " ", "Helvetica-Bold", 9)
    c.setStrokeColor(GREY); c.setLineWidth(0.5)
    c.line(LM + lw_, y - 1, LM + lw_ + width, y - 1)
    return y - 13

def pg_hdr(c, pg, tot):
    """Clinic header — top of every page"""
    if pg == 1:
        txt(c, W/2, H-40, "AUSTIN FAMILY MEDICINE", "Helvetica-Bold", 13, BLACK, "center")
        txt(c, W/2, H-53, "2847 Riverside Drive, Austin, TX 78701", "Helvetica", 9, DARK, "center")
        txt(c, W/2, H-64, "Phone: (512) 472-1100   Fax: (512) 472-1199", "Helvetica", 9, DARK, "center")
        hline(c, H-70, BLACK, 1.0)
        txt(c, W/2, H-80, "OUTPATIENT TREATMENT PLAN", "Helvetica-Bold", 11, BLACK, "center")
        hline(c, H-84, BLACK, 0.5)
        return H - 94
    else:
        txt(c, LM, H-35, "Austin Family Medicine — Treatment Plan (continued)", "Helvetica", 8, GREY)
        txt(c, RM, H-35, f"Marcus J. Elliot  ·  Page {pg} of {tot}", "Helvetica", 8, GREY, "right")
        hline(c, H-40, RULE, 0.5)
        return H - 52

def pg_ftr(c, pg, tot):
    hline(c, 38, RULE, 0.5)
    txt(c, LM, 26, "CONFIDENTIAL MEDICAL RECORD", "Helvetica", 7.5, GREY)
    txt(c, W/2, 26, f"Page {pg} of {tot}", "Helvetica", 7.5, GREY, "center")
    txt(c, RM, 26, "Austin Family Medicine", "Helvetica", 7.5, GREY, "right")

def build():
    cv = C.Canvas(OUT, pagesize=letter)
    cv.setTitle("Outpatient Treatment Plan — Marcus J. Elliot")

    TOTAL = 3

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 1
    # ══════════════════════════════════════════════════════════════════════════
    y = pg_hdr(cv, 1, TOTAL)
    pg_ftr(cv, 1, TOTAL)

    # ── Patient Information ───────────────────────────────────────────────────
    txt(cv, LM, y, "Date of Plan:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "June 12, 2025", "Helvetica", 9, DARK)
    txt(cv, LM+240, y, "Plan Review Date:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+340, y, "July 8, 2025", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Patient Name:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "Marcus J. Elliot", "Helvetica", 9, DARK)
    txt(cv, LM+240, y, "Patient DOB:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+340, y, "March 14, 1971", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Address:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "2847 Riverside Drive, Austin, TX 78701", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Height:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "5'11\"", "Helvetica", 9, DARK)
    txt(cv, LM+160, y, "Weight:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+220, y, "218 lbs", "Helvetica", 9, DARK)
    txt(cv, LM+290, y, "BMI:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+340, y, "30.4 (Obese Class I)", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Provider:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "Dr. Priya Nair, MD — Family Medicine", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Meeting Start:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "10:00 AM", "Helvetica", 9, DARK)
    txt(cv, LM+200, y, "Meeting End:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+290, y, "10:40 AM", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Plan Type:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "Initial Treatment Plan — Two-Week Active Program", "Helvetica", 9, DARK)
    y -= 13

    txt(cv, LM, y, "Participants:", "Helvetica-Bold", 9, DARK)
    txt(cv, LM+90, y, "Dr. Priya Nair, MD (Physician)     Marcus J. Elliot (Patient)", "Helvetica", 9, DARK)
    y -= 18

    hline(cv, y, RULE, 0.6)
    y -= 14

    # ── Diagnoses ─────────────────────────────────────────────────────────────
    y = section_head(cv, y, "Diagnosis")

    diagnoses = [
        ("1.", "Type 2 Diabetes Mellitus without complications", "E11.9", "ICD-10", "Active"),
        ("2.", "Essential (Primary) Hypertension", "I10", "ICD-10", "Active"),
        ("3.", "Obesity, Unspecified", "E66.9", "ICD-10", "Active"),
    ]
    for num, desc, code, sys, status in diagnoses:
        txt(cv, LM, y, num, "Helvetica-Bold", 9, DARK)
        txt(cv, LM+14, y, desc, "Helvetica", 9, DARK)
        txt(cv, LM+260, y, f"{code} ({sys})", "Helvetica", 9, GREY)
        txt(cv, RM, y, f"({status})", "Helvetica-Oblique", 9, GREY, "right")
        y -= 13
    y -= 6

    # ── Current Medications ───────────────────────────────────────────────────
    y = section_head(cv, y, "Current Medications")

    meds = [
        ("#1)", "Metformin HCl 500mg PO BID (with meals) — NEW as of June 13, 2025"),
        ("#2)", "Lisinopril 10mg PO QD (morning) — NEW as of June 13, 2025"),
    ]
    for num, desc in meds:
        txt(cv, LM, y, num, "Helvetica-Bold", 9, DARK)
        txt(cv, LM+24, y, desc, "Helvetica", 9, DARK)
        y -= 13
    y -= 6

    # ── Vitamins / Supplements ─────────────────────────────────────────────────
    y = section_head(cv, y, "Recommended Supplements")
    supplements = [
        ("#1)", "Vitamin D3 2000 IU — daily with breakfast"),
        ("#2)", "Magnesium 400mg — daily with breakfast"),
        ("#3)", "Vitamin B12 1000mcg — daily with breakfast (Metformin depletes B12)"),
        ("#4)", "Omega-3 1000mg — daily with breakfast (cardiovascular support)"),
    ]
    for num, desc in supplements:
        txt(cv, LM, y, num, "Helvetica-Bold", 9, DARK)
        txt(cv, LM+24, y, desc, "Helvetica", 9, DARK)
        y -= 13
    y -= 6

    # ── Problems / Needs ──────────────────────────────────────────────────────
    y = section_head(cv, y, "Problems / Needs")
    problems = [
        ("Problem / Need #1:", "Uncontrolled Blood Sugar (Type 2 Diabetes)"),
        ("Problem / Need #2:", "Elevated Blood Pressure (Hypertension)"),
        ("Problem / Need #3:", "Obesity — BMI 30.4, contributing to both above conditions"),
        ("Problem / Need #4:", "Sedentary Lifestyle — insufficient physical activity"),
        ("Problem / Need #5:", "Nutritional Habits — high refined carbohydrate intake"),
    ]
    for label, val in problems:
        txt(cv, LM, y, label, "Helvetica-Bold", 9, DARK)
        txt(cv, LM+160, y, val, "Helvetica", 9, DARK)
        y -= 13
    y -= 6

    # ── Plan Timeline ─────────────────────────────────────────────────────────
    y = section_head(cv, y, "10 Orbs to Better — Plan Timeline")
    timeline = [
        ("Plan Name:", '"10 Orbs to Better" — 10 steps to complete before next visit'),
        ("Plan Start Date:", "June 13, 2025"),
        ("Preferred Completion:", "June 27, 2025  (2 weeks)"),
        ("Maximum Extension:", "July 4, 2025  (3 weeks — hard stop)"),
        ("Next Doctor Visit:", "July 8, 2025 — Dr. Priya Nair, MD"),
        ("Note:", "If all 10 orbs are not complete by June 27, a one-week grace period"),
        ("", "extends to July 4. No further extensions. Visit on July 8 is mandatory."),
    ]
    for label, val in timeline:
        if label:
            txt(cv, LM, y, label, "Helvetica-Bold", 9, DARK)
            txt(cv, LM+160, y, val, "Helvetica", 9, DARK)
        else:
            txt(cv, LM+160, y, val, "Helvetica", 9, DARK)
        y -= 13

    cv.showPage()

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 2 — Orbs 1–6
    # ══════════════════════════════════════════════════════════════════════════
    y = pg_hdr(cv, 2, TOTAL)
    pg_ftr(cv, 2, TOTAL)

    txt(cv, W/2, y, "THE 10 ORBS — SHORT TERM GOALS AND INTERVENTIONS", "Helvetica-Bold", 10, BLACK, "center")
    y -= 16
    hline(cv, y, BLACK, 1.0)
    y -= 14

    orbs_p2 = [
        {
            "num": "Orb 1", "title": "Blood Work — Baseline Labs",
            "code": "CPT: 83036, 80053",
            "dates": "Target Date: June 13–14, 2025",
            "goal": "Patient will complete baseline HbA1c and Comprehensive Metabolic Panel within 48 hours of plan start.",
            "interventions": [
                "Location: Quest Diagnostics, 1200 S Lamar Blvd, Austin TX 78405.",
                "HbA1c (83036): establishes diabetes baseline for 3-month tracking.",
                "CMP (80053): assesses kidney function, electrolytes, liver panel.",
                "Hard stop: must be completed by June 14. Results reviewed by Dr. Nair before next orb group.",
            ],
            "frequency": "One-time", "duration": "Same-day lab visit", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 2", "title": "Begin Metformin 500mg",
            "code": "Rx: Metformin HCl 500mg",
            "dates": "Target Date: June 13, 2025 (Day One)",
            "goal": "Patient will begin Metformin HCl 500mg twice daily with meals and maintain adherence throughout plan.",
            "interventions": [
                "Schedule: 8:00 AM with breakfast  and  7:00 PM with dinner.",
                "Always take with food to reduce gastrointestinal side effects.",
                "Patient to set phone reminders for both doses.",
                "Report any persistent nausea, vomiting, or stomach pain to Dr. Nair.",
            ],
            "frequency": "Twice daily", "duration": "Ongoing", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 3", "title": "Begin Lisinopril 10mg",
            "code": "Rx: Lisinopril 10mg",
            "dates": "Target Date: June 13, 2025 (Day One)",
            "goal": "Patient will begin Lisinopril 10mg once daily and monitor for side effects.",
            "interventions": [
                "Schedule: once every morning at the same time, with water.",
                "Monitor for dry persistent cough — report to Dr. Nair immediately if it occurs.",
                "Do NOT take with potassium supplements or potassium-rich salt substitutes.",
                "Do not stop medication without consulting Dr. Nair.",
            ],
            "frequency": "Once daily", "duration": "Ongoing", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 4", "title": "Begin Daily Vitamin Protocol",
            "code": "OTC Supplements",
            "dates": "Target Date: June 13, 2025 (Day One)",
            "goal": "Patient will begin all four daily supplements and maintain consistency throughout the two-week plan.",
            "interventions": [
                "Vitamin D3 2000 IU: deficiency common in T2DM patients.",
                "Magnesium 400mg: supports blood sugar regulation and sleep quality.",
                "Vitamin B12 1000mcg: Metformin depletes B12 over time — essential to supplement.",
                "Omega-3 1000mg: cardiovascular support for hypertension management.",
                "All four to be taken together with breakfast. Use a weekly pill organiser.",
            ],
            "frequency": "Once daily", "duration": "Ongoing", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 5", "title": "Complete First 20-Minute Walk",
            "code": "Exercise — Aerobic",
            "dates": "Target Date: June 14–15, 2025",
            "goal": "Patient will complete one 20-minute moderate-intensity walk as the first exercise milestone.",
            "interventions": [
                "Moderate pace: patient should be able to hold a conversation while walking.",
                "Morning walks before breakfast are optimal for blood sugar management in T2DM.",
                "Outdoors or treadmill — patient's choice.",
                "This orb must be completed before the 7-day exercise streak (Orb 6) begins.",
                "Log completion in the patient app or paper log.",
            ],
            "frequency": "One-time milestone", "duration": "20 minutes", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 6", "title": "Complete 7-Day Exercise Streak",
            "code": "Exercise — Aerobic / Resistance",
            "dates": "Target Date: June 14–20, 2025",
            "goal": "Patient will complete 7 consecutive days of 20-minute moderate exercise, totalling 140 minutes.",
            "interventions": [
                "Approved activities: walking, cycling, swimming, light resistance training.",
                "Avoid high-impact exercise until blood pressure is confirmed stable.",
                "Target: 140 minutes total across 7 days (ADA recommendation: 150 min/week).",
                "If a full 20 minutes is difficult, split into two 10-minute sessions.",
                "All 7 days must be logged for orb to be marked complete.",
            ],
            "frequency": "Daily", "duration": "20 minutes per session", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
    ]

    for orb in orbs_p2:
        # Estimate height needed
        needed = 14+13+13+13+len(orb["interventions"])*12+24
        if y - needed < 55:
            break

        # Orb heading
        txt(cv, LM, y, f"{orb['num']}: {orb['title']}", "Helvetica-Bold", 10, DARK)
        txt(cv, RM, y, orb["code"], "Helvetica-Oblique", 8.5, GREY, "right")
        line(cv, y-3, 0.4, LGREY)
        y -= 14

        # Goal
        txt(cv, LM, y, "Short Term Goal / Objective:", "Helvetica-Bold", 8.5, DARK)
        y -= 12
        y = wrap(cv, LM+8, y, TW-8, orb["goal"], "Helvetica", 9, DARK, 12)
        y -= 2

        # Dates row
        txt(cv, LM, y, orb["dates"], "Helvetica", 8.5, GREY)
        txt(cv, LM+200, y, f"Completion Date: {orb['completion']}", "Helvetica", 8.5, GREY)
        txt(cv, LM+360, y, f"Status: {orb['status']}", "Helvetica", 8.5, GREY)
        y -= 13

        # Interventions
        txt(cv, LM, y, "Intervention:", "Helvetica-Bold", 8.5, DARK)
        y -= 12
        for intv in orb["interventions"]:
            txt(cv, LM+8, y, "•", "Helvetica", 9, MID)
            y = wrap(cv, LM+18, y, TW-18, intv, "Helvetica", 9, DARK, 12)

        # Frequency/duration row
        txt(cv, LM, y, f"Frequency: {orb['frequency']}", "Helvetica", 8.5, GREY)
        txt(cv, LM+230, y, f"Duration: {orb['duration']}", "Helvetica", 8.5, GREY)
        y -= 11

        txt(cv, LM, y, f"Progress: {orb['progress']}", "Helvetica", 8.5, GREY)
        y -= 11

        # Divider
        line(cv, y, 0.5, RULE)
        y -= 12

    cv.showPage()

    # ══════════════════════════════════════════════════════════════════════════
    # PAGE 3 — Orbs 7–10 + Success Metrics + SNAP + Signatures
    # ══════════════════════════════════════════════════════════════════════════
    y = pg_hdr(cv, 3, TOTAL)
    pg_ftr(cv, 3, TOTAL)

    orbs_p3 = [
        {
            "num": "Orb 7", "title": "Blood Sugar Self-Monitoring — 7 Days",
            "code": "HCPCS: A4253",
            "dates": "Target Date: June 13–19, 2025",
            "goal": "Patient will log fasting and post-meal blood glucose readings every day for 7 consecutive days.",
            "interventions": [
                "Equipment: blood glucose monitor and test strips (HCPCS A4253 — 50 count).",
                "Fasting reading: every morning before breakfast.",
                "Post-meal reading: 2 hours after dinner each evening.",
                "Fasting target: 80–130 mg/dL.  Post-meal target: below 180 mg/dL.",
                "ALERT: any reading above 250 mg/dL — call Dr. Nair same day: (512) 472-1100.",
            ],
            "frequency": "Twice daily", "duration": "7 days", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 8", "title": "Diabetic-Friendly Nutrition — 7 Days",
            "code": "Diet / Nutrition",
            "dates": "Target Date: June 16–22, 2025",
            "goal": "Patient will follow diabetic-friendly meal guidelines for 7 consecutive days and log each meal.",
            "interventions": [
                "Remove: white bread, white rice, sugary drinks, processed snacks.",
                "Add: leafy greens, lean protein (chicken, fish, legumes), whole grains, healthy fats.",
                "Plate method: half plate vegetables, quarter plate lean protein, quarter plate whole grain.",
                "Carbohydrate target: under 45g per meal.",
                "Log each meal in the app. Dietitian referral available on request.",
            ],
            "frequency": "Every meal", "duration": "7 days", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 9", "title": "Book Both Specialist Referrals",
            "code": "ICD: Z01.01, Z01.89",
            "dates": "Target Date: By June 20, 2025",
            "goal": "Patient will book both specialist appointments (ophthalmology and podiatry) by June 20, 2025.",
            "interventions": [
                "Ophthalmology (Z01.01): Austin Eye Center, (512) 445-2020 — diabetic eye exam.",
                "Podiatry (Z01.89): Texas Foot Specialists, (512) 339-0800 — diabetic foot exam.",
                "Both must be BOOKED (not necessarily attended) by June 20 for orb to be complete.",
                "Appointments may be scheduled for a future date beyond the plan window.",
            ],
            "frequency": "One-time", "duration": "Phone/online booking", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
        {
            "num": "Orb 10", "title": "Final Self-Assessment and Submission",
            "code": "CPT: 99214",
            "dates": "Target Date: June 27, 2025  (Hard stop: July 4, 2025)",
            "goal": "Patient will complete and submit the 2-week self-assessment to Dr. Nair by June 27.",
            "interventions": [
                "Submit via patient portal OR call Austin Family Medicine: (512) 472-1100.",
                "Include: 7-day blood glucose log, medication adherence record, exercise log.",
                "Include: any symptoms, side effects, or questions for Dr. Nair.",
                "Next appointment: July 8, 2025 — orb review and lab results discussion.",
            ],
            "frequency": "One-time", "duration": "Self-report submission", "progress": "Plans to start",
            "completion": "______", "status": "______"
        },
    ]

    for orb in orbs_p3:
        needed = 14+13+13+len(orb["interventions"])*12+24
        if y - needed < 160:
            break

        txt(cv, LM, y, f"{orb['num']}: {orb['title']}", "Helvetica-Bold", 10, DARK)
        txt(cv, RM, y, orb["code"], "Helvetica-Oblique", 8.5, GREY, "right")
        line(cv, y-3, 0.4, LGREY)
        y -= 14

        txt(cv, LM, y, "Short Term Goal / Objective:", "Helvetica-Bold", 8.5, DARK)
        y -= 12
        y = wrap(cv, LM+8, y, TW-8, orb["goal"], "Helvetica", 9, DARK, 12)
        y -= 2

        txt(cv, LM, y, orb["dates"], "Helvetica", 8.5, GREY)
        txt(cv, LM+220, y, f"Completion Date: {orb['completion']}", "Helvetica", 8.5, GREY)
        txt(cv, LM+370, y, f"Status: {orb['status']}", "Helvetica", 8.5, GREY)
        y -= 13

        txt(cv, LM, y, "Intervention:", "Helvetica-Bold", 8.5, DARK)
        y -= 12
        for intv in orb["interventions"]:
            txt(cv, LM+8, y, "•", "Helvetica", 9, MID)
            y = wrap(cv, LM+18, y, TW-18, intv, "Helvetica", 9, DARK, 12)

        txt(cv, LM, y, f"Frequency: {orb['frequency']}     Duration: {orb['duration']}     Progress: {orb['progress']}", "Helvetica", 8.5, GREY)
        y -= 13
        line(cv, y, 0.5, RULE)
        y -= 12

    # ── Success Metrics ────────────────────────────────────────────────────────
    hline(cv, y, BLACK, 0.8)
    y -= 12
    txt(cv, LM, y, "SUCCESS METRICS — TO BE REVIEWED AT JULY 8, 2025 VISIT", "Helvetica-Bold", 9.5, DARK)
    y -= 13

    metrics = [
        ("HbA1c:", "Baseline set at plan start. Target below 7.0% at 3-month recheck."),
        ("Fasting Glucose:", "Target: 80–130 mg/dL  (7-day log average)."),
        ("Blood Pressure:", "Target: below 130/80 mmHg."),
        ("Exercise:", "Minimum 7 of 14 days completed with 20-minute sessions."),
        ("Medication Adherence:", "90%+ — no more than 1–2 missed doses across 2 weeks."),
        ("Referrals:", "Both ophthalmology and podiatry appointments booked."),
    ]
    for label, val in metrics:
        txt(cv, LM, y, label, "Helvetica-Bold", 8.5, DARK)
        txt(cv, LM+130, y, val, "Helvetica", 8.5, DARK)
        y -= 12
    y -= 6

    # ── Strengths / Goals ──────────────────────────────────────────────────────
    # Ensure enough room for SNAP + barriers + signatures (~160pt)
    if y < 220:
        cv.showPage()
        y = pg_hdr(cv, 3, TOTAL)
        pg_ftr(cv, 3, TOTAL)
    hline(cv, y, BLACK, 0.8)
    y -= 12
    txt(cv, LM, y, "PATIENT STRENGTHS, NEEDS, ABILITIES AND PREFERENCES (SNAP)", "Helvetica-Bold", 9.5, DARK)
    y -= 13

    snap = [
        ("Strengths:", ["Motivated to make lifestyle changes.", "Supportive home environment."]),
        ("Needs:", ["Medication management guidance.", "Structured exercise routine.", "Nutritional education."]),
        ("Abilities:", ["Able to self-monitor and log daily readings.", "Can follow structured daily routines."]),
        ("Preferences:", ["Individual plan with clear daily tasks.", "Minimal clinic visits during plan period."]),
        ("Goals:", ['"I want to get my blood sugar under control and feel more energy day to day."']),
    ]
    for label, items in snap:
        txt(cv, LM, y, label, "Helvetica-Bold", 8.5, DARK)
        y -= 12
        for item in items:
            txt(cv, LM+12, y, f"*{item}", "Helvetica", 8.5, DARK)
            y -= 12
    y -= 6

    # ── Barriers ───────────────────────────────────────────────────────────────
    hline(cv, y, BLACK, 0.8)
    y -= 12
    txt(cv, LM, y, "BARRIERS", "Helvetica-Bold", 9.5, DARK)
    y -= 13
    barriers = [
        ("Sedentary work schedule may limit daily exercise time.",
         "Plan accommodates split 2x10 min sessions as alternative to single 20-min walk."),
        ("Dietary habits — high refined carbohydrate diet established over many years.",
         "Plate method and simple substitutions provided to reduce behaviour change friction."),
    ]
    for barrier, mitigation in barriers:
        txt(cv, LM, y, barrier, "Helvetica", 9, DARK)
        y -= 12
        txt(cv, LM+12, y, f"- {mitigation}", "Helvetica-Oblique", 8.5, GREY)
        y -= 14
    y -= 4

    # ── Signatures ─────────────────────────────────────────────────────────────
    hline(cv, y, BLACK, 0.8)
    y -= 16

    txt(cv, LM, y, "STATUS:", "Helvetica-Bold", 9, DARK)
    y -= 12
    status_text = ("June 12, 2025: The undersigned clinician met with the patient in a face-to-face meeting "
                   "to work together in developing this Treatment Plan. The patient has reviewed, understood, "
                   "and agreed to participate in the 10 Orbs to Better program as described above.")
    y = wrap(cv, LM, y, TW, status_text, "Helvetica", 9, DARK, 13)
    y -= 14

    # Signature lines
    cv.setStrokeColor(DARK); cv.setLineWidth(0.7)
    cv.line(LM, y, LM+200, y)
    cv.line(W/2+10, y, W/2+210, y)

    y -= 12
    txt(cv, LM, y, "Dr. Priya Nair, MD — Physician", "Helvetica", 8.5, DARK)
    txt(cv, W/2+10, y, "Marcus J. Elliot — Patient", "Helvetica", 8.5, DARK)
    y -= 11
    txt(cv, LM, y, "Austin Family Medicine", "Helvetica", 8, GREY)
    txt(cv, W/2+10, y, "I have received and understood this treatment plan.", "Helvetica", 8, GREY)
    y -= 11
    txt(cv, LM, y, "Date: June 12, 2025", "Helvetica", 8, GREY)
    txt(cv, W/2+10, y, "Date: ___________________", "Helvetica", 8, GREY)

    cv.save()
    sz = os.path.getsize(OUT)
    print(f"Done: {OUT}  ({sz//1024} KB)  3 pages")

build()
