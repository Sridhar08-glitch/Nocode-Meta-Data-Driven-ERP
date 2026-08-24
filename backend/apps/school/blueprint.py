"""
School Management Solution blueprint (P3.1 — first industry package).

The ENTIRE School solution — academic structure, admissions, students/guardians, enrollment,
attendance, timetable, examinations, fees (with REAL accounting integration), library, transport
and hostel — is expressed here as a curated extended manifest and installed through the Solution
Package Platform. **Pure manifest: this app ships NO native code** (no models, no services). It
reuses every ERP Core engine:

  * metadata / dynamic forms / views          → entities, forms, views
  * workflow engine                           → admissions, fee posting, alerts
  * accounting (GLBus) via ``action_post_journal`` → fee invoice/payment → real journal entries
  * RBAC                                       → roles + permissions
  * reporting / dashboards                     → reports + dashboards
  * notifications                              → templates
  * package platform                           → the ``package`` block (deps / version / migrations)

Nothing here duplicates accounting, inventory, HR or any other engine.
"""
from __future__ import annotations


# ── field/entity helpers (same shape every package uses) ─────────────────────
def _f(slug, name, field_type, **kw):
    f = {"slug": slug, "name": name, "field_type": field_type, "is_promoted": True}
    f.update(kw)
    return f


def _lookup(slug, name, target):
    return _f(slug, name, "lookup", config={"target_entity_slug": target})


def _select(slug, name, *choices):
    return _f(slug, name, "select", config={"choices": list(choices)})


def _status(*choices):
    return _f("status", "Status", "status", config={"choices": list(choices)})


def _auto(slug, name, prefix):
    return _f(slug, name, "auto_number", is_unique=True, config={"prefix": prefix, "padding": 6})


def _entity(slug, name, plural, fields):
    return {"slug": slug, "name": name, "plural_name": plural, "fields": fields}


# ── business objects ─────────────────────────────────────────────────────────
SCHOOL_OBJECTS: dict[str, dict] = {
    "academic_year": _entity("academic_year", "Academic Year", "Academic Years", [
        _f("name", "Name", "text", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("is_current", "Current", "boolean"),
        _status("planning", "active", "closed"),
    ]),
    "grade_level": _entity("grade_level", "Grade Level", "Grade Levels", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("sequence", "Sequence", "integer"),
    ]),
    "subject": _entity("subject", "Subject", "Subjects", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("department", "Department", "text"),
        _f("credit_hours", "Credit Hours", "integer"),
    ]),
    "teacher": _entity("teacher", "Teacher", "Teachers", [
        _f("employee_no", "Employee No", "text", is_unique=True),
        _f("name", "Name", "text", is_required=True),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("qualification", "Qualification", "text"),
        _f("specialization", "Specialization", "text"),
        _f("join_date", "Join Date", "date"),
        _status("active", "on_leave", "left"),
    ]),
    "school_class": _entity("school_class", "Class", "Classes", [
        _f("name", "Name", "text", is_required=True),
        _lookup("grade_level", "Grade Level", "grade_level"),
        _f("section", "Section", "text"),
        _f("capacity", "Capacity", "integer"),
        _lookup("class_teacher", "Class Teacher", "teacher"),
        _lookup("campus", "Campus", "campus"),
        _lookup("academic_year", "Academic Year", "academic_year"),
    ]),
    "guardian": _entity("guardian", "Guardian", "Guardians", [
        _f("name", "Name", "text", is_required=True),
        _select("relationship", "Relationship", "father", "mother", "guardian", "other"),
        _f("phone", "Phone", "phone"),
        _f("email", "Email", "email"),
        _f("occupation", "Occupation", "text"),
        _f("address", "Address", "textarea"),
    ]),
    "student": _entity("student", "Student", "Students", [
        _auto("admission_no", "Admission No", "ADM-"),
        _f("first_name", "First Name", "text", is_required=True),
        _f("last_name", "Last Name", "text"),
        _f("dob", "Date of Birth", "date"),
        _select("gender", "Gender", "female", "male", "other"),
        _f("blood_group", "Blood Group", "text"),
        _f("nationality", "Nationality", "text"),
        _f("prior_school", "Prior School", "text"),
        _lookup("guardian", "Guardian", "guardian"),
        _lookup("school_class", "Class", "school_class"),
        _f("roll_no", "Roll No", "text"),
        _f("admission_date", "Admission Date", "date"),
        _f("emergency_contact", "Emergency Contact", "phone"),
        _f("uses_transport", "Uses Transport", "boolean"),
        _status("applicant", "enrolled", "graduated", "transferred", "withdrawn", "suspended"),
    ]),
    "admission_application": _entity(
        "admission_application", "Admission Application", "Admission Applications", [
            _auto("application_no", "Application No", "APP-"),
            _f("applicant_name", "Applicant Name", "text", is_required=True),
            _f("dob", "Date of Birth", "date"),
            _select("gender", "Gender", "female", "male", "other"),
            _f("guardian_name", "Guardian Name", "text"),
            _f("guardian_phone", "Guardian Phone", "phone"),
            _lookup("grade_applied", "Grade Applied", "grade_level"),
            _f("application_date", "Application Date", "date"),
            _status("submitted", "under_review", "approved", "rejected", "enrolled"),
        ]),
    "enrollment": _entity("enrollment", "Enrollment", "Enrollments", [
        _lookup("student", "Student", "student"),
        _lookup("school_class", "Class", "school_class"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("enrollment_date", "Enrollment Date", "date"),
        _status("active", "transferred", "completed"),
    ]),
    "attendance": _entity("attendance", "Attendance", "Attendance", [
        _lookup("student", "Student", "student"),
        _lookup("school_class", "Class", "school_class"),
        _f("date", "Date", "date", is_required=True),
        _status("present", "absent", "late", "excused"),
        _f("remarks", "Remarks", "text"),
    ]),
    "timetable_entry": _entity("timetable_entry", "Timetable Entry", "Timetable", [
        _lookup("school_class", "Class", "school_class"),
        _lookup("subject", "Subject", "subject"),
        _lookup("teacher", "Teacher", "teacher"),
        _select("day_of_week", "Day", "mon", "tue", "wed", "thu", "fri", "sat"),
        _f("period", "Period", "integer"),
        _f("start_time", "Start Time", "time"),
        _f("end_time", "End Time", "time"),
    ]),
    "exam": _entity("exam", "Exam", "Exams", [
        _f("name", "Name", "text", is_required=True),
        _select("exam_type", "Exam Type", "midterm", "final", "quiz", "assignment"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("scheduled", "ongoing", "completed", "published"),
    ]),
    "exam_result": _entity("exam_result", "Exam Result", "Exam Results", [
        _lookup("student", "Student", "student"),
        _lookup("exam", "Exam", "exam"),
        _lookup("subject", "Subject", "subject"),
        _f("marks_obtained", "Marks Obtained", "decimal"),
        _f("max_marks", "Max Marks", "decimal"),
        _f("grade", "Grade", "text"),
        _f("remarks", "Remarks", "text"),
    ]),
    "fee_structure": _entity("fee_structure", "Fee Structure", "Fee Structures", [
        _f("name", "Name", "text", is_required=True),
        _lookup("grade_level", "Grade Level", "grade_level"),
        _select("fee_type", "Fee Type", "tuition", "admission", "transport", "hostel",
                "exam", "library"),
        _f("amount", "Amount", "currency"),
        _select("frequency", "Frequency", "monthly", "term", "annual", "one_time"),
        _lookup("academic_year", "Academic Year", "academic_year"),
    ]),
    "fee_invoice": _entity("fee_invoice", "Fee Invoice", "Fee Invoices", [
        _auto("invoice_no", "Invoice No", "FEE-"),
        _lookup("student", "Student", "student"),
        _lookup("fee_structure", "Fee Structure", "fee_structure"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _status("draft", "issued", "paid", "partial", "overdue", "cancelled"),
    ]),
    "fee_payment": _entity("fee_payment", "Fee Payment", "Fee Payments", [
        _auto("receipt_no", "Receipt No", "RCPT-"),
        _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("payment_date", "Payment Date", "date"),
        _select("method", "Method", "cash", "bank", "card", "online", "cheque"),
        _f("reference", "Reference", "text"),
    ]),
    # ── Fee Management depth (Phase 1.3) — request/approval documents that consume the Core
    # Credit Engine (F3) and Collections Engine (F2) via workflow steps. NO School-private
    # accounting/collections/credit logic; the engines do all posting + numbering + GL. ────────
    "fee_category": _entity("fee_category", "Fee Category", "Fee Categories", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("fee_type", "Fee Type", "tuition", "admission", "registration", "transport",
                "hostel", "library", "laboratory", "exam", "activity", "other"),
        _select("frequency", "Frequency", "monthly", "term", "annual", "one_time"),
        _f("description", "Description", "textarea"),
    ]),
    "fee_installment_plan": _entity(
        "fee_installment_plan", "Installment Plan", "Installment Plans", [
            _auto("plan_ref", "Plan Ref", "SIP-"),
            _lookup("student", "Student", "student"),
            _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
            _f("total_amount", "Total Amount", "currency", is_required=True),
            _f("num_installments", "Installments", "integer", is_required=True),
            _select("frequency", "Frequency", "monthly", "weekly", "quarterly", "yearly"),
            _f("start_date", "Start Date", "date"),
            _f("grace_days", "Grace Days", "integer"),
            _select("late_fee_type", "Late Fee Type", "none", "flat", "percent"),
            _f("late_fee_value", "Late Fee Value", "currency"),
            _status("draft", "approved", "active", "cancelled"),
        ]),
    "fee_discount": _entity("fee_discount", "Fee Discount", "Fee Discounts", [
        _auto("discount_no", "Discount No", "DISC-"),
        _lookup("student", "Student", "student"),
        _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "applied", "rejected"),
    ]),
    "fee_scholarship": _entity("fee_scholarship", "Scholarship", "Scholarships", [
        _auto("scholarship_no", "Scholarship No", "SCHL-"),
        _lookup("student", "Student", "student"),
        _f("sponsor", "Sponsor", "text"),
        _f("amount", "Amount", "currency", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "awarded", "rejected"),
    ]),
    "fee_waiver": _entity("fee_waiver", "Fee Waiver", "Fee Waivers", [
        _auto("waiver_no", "Waiver No", "WVR-"),
        _lookup("student", "Student", "student"),
        _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "applied", "rejected"),
    ]),
    "fee_refund": _entity("fee_refund", "Fee Refund", "Fee Refunds", [
        _auto("refund_no", "Refund No", "REF-"),
        _lookup("student", "Student", "student"),
        _lookup("fee_payment", "Fee Payment", "fee_payment"),
        _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
        _f("amount", "Amount", "currency", is_required=True),
        _select("method", "Method", "cash", "bank", "card", "online"),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "processed", "rejected"),
    ]),
    "fee_writeoff": _entity("fee_writeoff", "Fee Write-off", "Fee Write-offs", [
        _auto("writeoff_no", "Write-off No", "WOF-"),
        _lookup("student", "Student", "student"),
        _lookup("fee_invoice", "Fee Invoice", "fee_invoice"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "written_off", "rejected"),
    ]),

    "library_book": _entity("library_book", "Library Book", "Library Books", [
        _f("title", "Title", "text", is_required=True),
        _f("author", "Author", "text"),
        _f("isbn", "ISBN", "text"),
        _f("category", "Category", "text"),
        _f("total_copies", "Total Copies", "integer"),
        _f("available_copies", "Available Copies", "integer"),
    ]),
    "book_loan": _entity("book_loan", "Book Loan", "Book Loans", [
        _lookup("library_book", "Book", "library_book"),
        _lookup("student", "Student", "student"),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("return_date", "Return Date", "date"),
        _status("issued", "returned", "overdue", "lost"),
    ]),
    "transport_route": _entity("transport_route", "Transport Route", "Transport Routes", [
        _f("name", "Name", "text", is_required=True),
        _f("vehicle_no", "Vehicle No", "text"),
        _f("driver_name", "Driver Name", "text"),
        _f("capacity", "Capacity", "integer"),
        _f("fee", "Fee", "currency"),
    ]),
    "hostel_room": _entity("hostel_room", "Hostel Room", "Hostel Rooms", [
        _f("hostel_name", "Hostel Name", "text", is_required=True),
        _f("room_no", "Room No", "text"),
        _f("capacity", "Capacity", "integer"),
        _f("occupied", "Occupied", "integer"),
        _f("warden", "Warden", "text"),
    ]),

    # ── Student lifecycle (Phase 1.1) ─────────────────────────────────────────
    "inquiry": _entity("inquiry", "Inquiry", "Inquiries", [
        _auto("inquiry_no", "Inquiry No", "INQ-"),
        _f("prospect_name", "Prospect Name", "text", is_required=True),
        _f("contact_email", "Email", "email"),
        _f("contact_phone", "Phone", "phone"),
        _lookup("grade_interested", "Grade Interested", "grade_level"),
        _select("source", "Source", "web", "walk_in", "referral", "event", "phone"),
        _f("inquiry_date", "Inquiry Date", "date"),
        _f("notes", "Notes", "textarea"),
        _status("new", "contacted", "qualified", "converted", "closed"),
    ]),
    "student_status_history": _entity(
        "student_status_history", "Status History", "Status History", [
            _lookup("student", "Student", "student"),
            _f("status", "Status", "text"),
            _f("effective_date", "Effective Date", "date"),
            _f("reason", "Reason", "text"),
            _f("changed_by", "Changed By", "user"),
        ]),
    "promotion": _entity("promotion", "Promotion", "Promotions", [
        _lookup("student", "Student", "student"),
        _lookup("from_class", "From Class", "school_class"),
        _lookup("to_class", "To Class", "school_class"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("promotion_date", "Promotion Date", "date"),
        _f("remarks", "Remarks", "text"),
        _status("pending", "approved", "completed"),
    ]),
    "transfer": _entity("transfer", "Transfer", "Transfers", [
        _lookup("student", "Student", "student"),
        _select("transfer_type", "Transfer Type", "internal", "external"),
        _f("to_school", "Destination School", "text"),
        _f("transfer_date", "Transfer Date", "date"),
        _f("reason", "Reason", "text"),
        _f("tc_issued", "TC Issued", "boolean"),
        _status("requested", "approved", "completed"),
    ]),
    "graduation_record": _entity("graduation_record", "Graduation", "Graduations", [
        _lookup("student", "Student", "student"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("graduation_date", "Graduation Date", "date"),
        _f("final_grade", "Final Grade", "text"),
        _f("certificate_issued", "Certificate Issued", "boolean"),
        _status("pending", "completed"),
    ]),
    "withdrawal": _entity("withdrawal", "Withdrawal", "Withdrawals", [
        _lookup("student", "Student", "student"),
        _f("withdrawal_date", "Withdrawal Date", "date"),
        _select("reason", "Reason", "relocation", "financial", "academic", "other"),
        _f("clearance_done", "Clearance Done", "boolean"),
        _status("requested", "approved", "completed"),
    ]),
    "alumni": _entity("alumni", "Alumni", "Alumni", [
        _lookup("student", "Student", "student"),
        _f("graduation_year", "Graduation Year", "text"),
        _f("current_occupation", "Current Occupation", "text"),
        _f("contact_email", "Email", "email"),
        _f("contact_phone", "Phone", "phone"),
        _f("notes", "Notes", "textarea"),
    ]),

    # ── Academic structure (Phase 1.2) — all Academic-Base candidates (generic names,
    # no School-only assumptions); see REUSE_MATRIX.md / PLATFORM_INHERITANCE.md ─────────
    "campus": _entity("campus", "Campus", "Campuses", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("address", "Address", "textarea"),
        _f("head", "Campus Head", "user"),
        _f("is_main", "Main Campus", "boolean"),
    ]),
    "term": _entity("term", "Term", "Terms", [
        _f("name", "Name", "text", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _select("term_type", "Term Type", "semester", "trimester", "quarter", "term"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("sequence", "Sequence", "integer"),
        _status("planning", "active", "closed"),
    ]),
    "academic_calendar_event": _entity(
        "academic_calendar_event", "Calendar Event", "Calendar Events", [
            _f("title", "Title", "text", is_required=True),
            _lookup("academic_year", "Academic Year", "academic_year"),
            _select("event_type", "Event Type", "holiday", "exam", "activity", "break", "meeting"),
            _f("start_date", "Start Date", "date"),
            _f("end_date", "End Date", "date"),
            _f("description", "Description", "textarea"),
        ]),
    "curriculum": _entity("curriculum", "Curriculum", "Curricula", [
        _f("name", "Name", "text", is_required=True),
        _lookup("grade_level", "Grade Level", "grade_level"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("description", "Description", "textarea"),
        _status("draft", "active", "archived"),
    ]),
    "subject_assignment": _entity(
        "subject_assignment", "Subject Assignment", "Subject Assignments", [
            _lookup("school_class", "Class", "school_class"),
            _lookup("subject", "Subject", "subject"),
            _lookup("teacher", "Teacher", "teacher"),
            _lookup("term", "Term", "term"),
            _f("hours_per_week", "Hours / Week", "integer"),
        ]),
    "lesson_plan": _entity("lesson_plan", "Lesson Plan", "Lesson Plans", [
        _f("title", "Title", "text", is_required=True),
        _lookup("subject", "Subject", "subject"),
        _lookup("school_class", "Class", "school_class"),
        _lookup("teacher", "Teacher", "teacher"),
        _lookup("term", "Term", "term"),
        _f("week", "Week", "integer"),
        _f("topic", "Topic", "text"),
        _f("objectives", "Objectives", "textarea"),
        _f("resources", "Resources", "textarea"),
        _status("draft", "submitted", "approved"),
    ]),
    "promotion_rule": _entity("promotion_rule", "Promotion Rule", "Promotion Rules", [
        _f("name", "Name", "text", is_required=True),
        _lookup("grade_level", "Grade Level", "grade_level"),
        _f("min_attendance_percent", "Min Attendance %", "decimal"),
        _f("min_pass_marks", "Min Pass Marks", "decimal"),
        _f("criteria", "Criteria", "textarea"),
        _f("is_active", "Active", "boolean"),
    ]),
    # Assignments / homework (Phase 1.5) — Academic-Base candidate. Teacher-authored, class-scoped;
    # students/parents view via the portal's indirect (class) scoping.
    "assignment": _entity("assignment", "Assignment", "Assignments", [
        _f("title", "Title", "text", is_required=True),
        _select("assignment_type", "Type", "homework", "assignment", "project"),
        _lookup("school_class", "Class", "school_class"),
        _lookup("subject", "Subject", "subject"),
        _lookup("teacher", "Teacher", "teacher"),
        _f("assigned_date", "Assigned Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("description", "Description", "textarea"),
        _status("draft", "published", "closed"),
    ]),

    # ══ STUDENT SERVICES (Phase 1.6) — pure manifest; reuses workflow/approval/notification/
    #    document/portal/audit Core. Many are Academic-Base candidates (see ACADEMIC_BASE_CANDIDATES.md).
    # ── Attendance depth ──────────────────────────────────────────────────────
    "leave_request": _entity("leave_request", "Leave Request", "Leave Requests", [
        _lookup("student", "Student", "student"),
        _select("leave_type", "Leave Type", "sick", "personal", "emergency", "vacation"),
        _f("from_date", "From", "date", is_required=True),
        _f("to_date", "To", "date"),
        _f("reason", "Reason", "textarea"),
        _status("requested", "approved", "rejected", "cancelled"),
    ]),
    "attendance_correction": _entity(
        "attendance_correction", "Attendance Correction", "Attendance Corrections", [
            _lookup("student", "Student", "student"),
            _f("attendance_date", "Date", "date", is_required=True),
            _select("requested_status", "Requested Status", "present", "absent", "late", "excused"),
            _f("reason", "Reason", "textarea"),
            _status("requested", "approved", "rejected"),
        ]),
    # ── Behaviour management ──────────────────────────────────────────────────
    "behaviour_category": _entity(
        "behaviour_category", "Behaviour Category", "Behaviour Categories", [
            _f("name", "Name", "text", is_required=True),
            _select("category_type", "Type", "merit", "demerit"),
            _f("default_points", "Default Points", "integer"),
            _f("description", "Description", "textarea"),
        ]),
    "behaviour_incident": _entity(
        "behaviour_incident", "Behaviour Incident", "Behaviour Incidents", [
            _auto("incident_no", "Incident No", "BHV-"),
            _lookup("student", "Student", "student"),
            _lookup("category", "Category", "behaviour_category"),
            _f("incident_date", "Date", "date"),
            _f("points", "Points", "integer"),
            _select("severity", "Severity", "low", "medium", "high"),
            _f("description", "Description", "textarea"),
            _f("reported_by", "Reported By", "user"),
            _status("logged", "reviewed", "actioned", "closed"),
        ]),
    "disciplinary_action": _entity(
        "disciplinary_action", "Disciplinary Action", "Disciplinary Actions", [
            _lookup("student", "Student", "student"),
            _lookup("incident", "Incident", "behaviour_incident"),
            _select("action_type", "Action", "warning", "detention", "suspension", "expulsion"),
            _f("start_date", "Start Date", "date"),
            _f("end_date", "End Date", "date"),
            _f("description", "Description", "textarea"),
            _status("pending", "active", "completed"),
        ]),
    # ── Counselling (confidential notes → is_pii masking, Core) ────────────────
    "counselling_referral": _entity(
        "counselling_referral", "Counselling Referral", "Counselling Referrals", [
            _lookup("student", "Student", "student"),
            _f("referred_by", "Referred By", "user"),
            _f("reason", "Reason", "textarea"),
            _select("priority", "Priority", "low", "medium", "high"),
            _f("referral_date", "Referral Date", "date"),
            _status("open", "assigned", "closed"),
        ]),
    "counselling_session": _entity(
        "counselling_session", "Counselling Session", "Counselling Sessions", [
            _lookup("student", "Student", "student"),
            _f("counsellor", "Counsellor", "user"),
            _f("session_date", "Session Date", "date"),
            _select("session_type", "Type", "individual", "group", "family"),
            _f("notes", "Notes", "textarea", config={"is_pii": True}),
            _status("scheduled", "completed", "cancelled"),
        ]),
    "counselling_action_plan": _entity(
        "counselling_action_plan", "Action Plan", "Action Plans", [
            _lookup("student", "Student", "student"),
            _lookup("session", "Session", "counselling_session"),
            _f("goals", "Goals", "textarea"),
            _f("actions", "Actions", "textarea"),
            _f("review_date", "Review Date", "date"),
            _status("active", "completed"),
        ]),
    # ── Medical (confidential → is_pii) ───────────────────────────────────────
    "medical_profile": _entity("medical_profile", "Medical Profile", "Medical Profiles", [
        _lookup("student", "Student", "student"),
        _f("blood_group", "Blood Group", "text"),
        _f("height_cm", "Height (cm)", "decimal"),
        _f("weight_kg", "Weight (kg)", "decimal"),
        _f("primary_physician", "Primary Physician", "text"),
        _f("insurance_provider", "Insurance Provider", "text"),
        _f("insurance_no", "Insurance No", "text"),
    ]),
    "medical_condition": _entity("medical_condition", "Medical Condition", "Medical Conditions", [
        _lookup("student", "Student", "student"),
        _f("condition_name", "Condition", "text", is_required=True),
        _select("severity", "Severity", "mild", "moderate", "severe"),
        _f("diagnosed_date", "Diagnosed", "date"),
        _f("notes", "Notes", "textarea", config={"is_pii": True}),
    ]),
    "allergy": _entity("allergy", "Allergy", "Allergies", [
        _lookup("student", "Student", "student"),
        _f("allergen", "Allergen", "text", is_required=True),
        _select("severity", "Severity", "mild", "moderate", "severe"),
        _f("reaction", "Reaction", "text"),
        _f("notes", "Notes", "textarea"),
    ]),
    "medication": _entity("medication", "Medication", "Medications", [
        _lookup("student", "Student", "student"),
        _f("medication_name", "Medication", "text", is_required=True),
        _f("dosage", "Dosage", "text"),
        _f("frequency", "Frequency", "text"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("prescriber", "Prescriber", "text"),
    ]),
    "vaccination_record": _entity(
        "vaccination_record", "Vaccination Record", "Vaccination Records", [
            _lookup("student", "Student", "student"),
            _f("vaccine_name", "Vaccine", "text", is_required=True),
            _f("dose", "Dose", "text"),
            _f("administered_date", "Administered", "date"),
            _f("administered_by", "Administered By", "text"),
            _f("next_due_date", "Next Due", "date"),
        ]),
    "medical_visit": _entity("medical_visit", "Medical Visit", "Medical Visits", [
        _auto("visit_no", "Visit No", "MV-"),
        _lookup("student", "Student", "student"),
        _f("visit_date", "Visit Date", "date"),
        _f("complaint", "Complaint", "textarea"),
        _f("treatment", "Treatment", "textarea", config={"is_pii": True}),
        _f("attended_by", "Attended By", "user"),
        _f("outcome", "Outcome", "text"),
        _status("waiting", "in_progress", "completed"),   # nurse queue via status
    ]),
    "medical_alert": _entity("medical_alert", "Medical Alert", "Medical Alerts", [
        _lookup("student", "Student", "student"),
        _f("alert_type", "Alert Type", "text"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _f("description", "Description", "textarea"),
        _f("is_active", "Active", "boolean"),
    ]),
    "emergency_medical_contact": _entity(
        "emergency_medical_contact", "Emergency Contact", "Emergency Contacts", [
            _lookup("student", "Student", "student"),
            _f("name", "Name", "text", is_required=True),
            _f("relationship", "Relationship", "text"),
            _f("phone", "Phone", "phone"),
            _f("is_primary", "Primary", "boolean"),
        ]),
    "health_screening": _entity("health_screening", "Health Screening", "Health Screenings", [
        _lookup("student", "Student", "student"),
        _select("screening_type", "Type", "vision", "dental", "hearing", "bmi", "general"),
        _f("screening_date", "Date", "date"),
        _f("result", "Result", "text"),
        _f("screened_by", "Screened By", "user"),
        _f("follow_up_required", "Follow-up Required", "boolean"),
    ]),
    # ── Special education ─────────────────────────────────────────────────────
    "learning_support": _entity("learning_support", "Learning Support", "Learning Support", [
        _lookup("student", "Student", "student"),
        _f("support_type", "Support Type", "text"),
        _f("provider", "Provider", "text"),
        _f("start_date", "Start Date", "date"),
        _status("active", "completed"),
    ]),
    "special_need": _entity("special_need", "Special Need", "Special Needs", [
        _lookup("student", "Student", "student"),
        _f("need_type", "Need Type", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _select("severity", "Severity", "mild", "moderate", "severe"),
        _status("active", "resolved"),
    ]),
    "accommodation_plan": _entity(
        "accommodation_plan", "Accommodation Plan", "Accommodation Plans", [
            _lookup("student", "Student", "student"),
            _f("accommodations", "Accommodations", "textarea"),
            _f("start_date", "Start Date", "date"),
            _f("review_date", "Review Date", "date"),
            _status("active", "review", "closed"),
        ]),
    "iep": _entity("iep", "Individual Education Plan", "IEPs", [
        _auto("iep_no", "IEP No", "IEP-"),
        _lookup("student", "Student", "student"),
        _f("goals", "Goals", "textarea"),
        _f("services", "Services", "textarea"),
        _f("case_manager", "Case Manager", "user"),
        _f("start_date", "Start Date", "date"),
        _f("review_date", "Review Date", "date"),
        _status("draft", "active", "review", "closed"),
    ]),
    # ── Activities / welfare ──────────────────────────────────────────────────
    "student_club": _entity("student_club", "Club", "Clubs", [
        _f("name", "Name", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("coordinator", "Coordinator", "user"),
        _f("description", "Description", "textarea"),
        _f("capacity", "Capacity", "integer"),
    ]),
    "club_membership": _entity("club_membership", "Club Membership", "Club Memberships", [
        _lookup("student", "Student", "student"),
        _lookup("club", "Club", "student_club"),
        _f("join_date", "Join Date", "date"),
        _f("member_role", "Role", "text"),
        _status("active", "inactive"),
    ]),
    "sport": _entity("sport", "Sport", "Sports", [
        _f("name", "Name", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("coach", "Coach", "user"),
        _f("season", "Season", "text"),
    ]),
    "sport_participation": _entity(
        "sport_participation", "Sport Participation", "Sport Participation", [
            _lookup("student", "Student", "student"),
            _lookup("sport", "Sport", "sport"),
            _f("season", "Season", "text"),
            _f("position", "Position", "text"),
            _status("active", "inactive"),
        ]),
    "competition": _entity("competition", "Competition", "Competitions", [
        _f("name", "Name", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("competition_date", "Date", "date"),
        _select("level", "Level", "school", "district", "state", "national", "international"),
        _f("organizer", "Organizer", "text"),
    ]),
    "competition_participation": _entity(
        "competition_participation", "Competition Entry", "Competition Entries", [
            _lookup("student", "Student", "student"),
            _lookup("competition", "Competition", "competition"),
            _f("result", "Result", "text"),
            _f("rank", "Rank", "integer"),
            _status("registered", "participated", "withdrawn"),
        ]),
    "achievement": _entity("achievement", "Achievement", "Achievements", [
        _lookup("student", "Student", "student"),
        _f("title", "Title", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("achievement_date", "Date", "date"),
        _f("description", "Description", "textarea"),
    ]),
    "award": _entity("award", "Award", "Awards", [
        _lookup("student", "Student", "student"),
        _f("award_name", "Award", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("award_date", "Date", "date"),
        _f("awarded_by", "Awarded By", "user"),
        _f("description", "Description", "textarea"),
    ]),
    "student_activity": _entity("student_activity", "Student Activity", "Student Activities", [
        _lookup("student", "Student", "student"),
        _f("activity_name", "Activity", "text", is_required=True),
        _f("activity_date", "Date", "date"),
        _f("hours", "Hours", "decimal"),
        _f("activity_type", "Type", "text"),
    ]),
    "volunteer_program": _entity("volunteer_program", "Volunteer Program", "Volunteer Programs", [
        _f("name", "Name", "text", is_required=True),
        _f("coordinator", "Coordinator", "user"),
        _f("description", "Description", "textarea"),
    ]),
    "volunteer_participation": _entity(
        "volunteer_participation", "Community Service", "Community Service", [
            _lookup("student", "Student", "student"),
            _lookup("program", "Program", "volunteer_program"),
            _f("hours", "Hours", "decimal"),
            _f("service_date", "Date", "date"),
            _status("registered", "completed"),
        ]),
    "student_leadership": _entity("student_leadership", "Student Leadership", "Student Leadership", [
        _lookup("student", "Student", "student"),
        _f("position", "Position", "text", is_required=True),
        _f("term", "Term", "text"),
        _f("responsibilities", "Responsibilities", "textarea"),
        _status("active", "completed"),
    ]),
    "house": _entity("house", "House", "Houses", [
        _f("name", "Name", "text", is_required=True),
        _f("color", "Color", "text"),
        _f("head", "House Head", "user"),
        _f("points", "Points", "integer"),
    ]),
    "house_membership": _entity("house_membership", "House Membership", "House Memberships", [
        _lookup("student", "Student", "student"),
        _lookup("house", "House", "house"),
        _f("join_date", "Join Date", "date"),
    ]),
    "student_election": _entity("student_election", "Student Election", "Student Elections", [
        _f("title", "Title", "text", is_required=True),
        _f("position", "Position", "text"),
        _f("election_date", "Election Date", "date"),
        _f("term", "Term", "text"),
        _status("nominations", "voting", "completed"),
    ]),
    # ── Career guidance ───────────────────────────────────────────────────────
    "career_counselling": _entity(
        "career_counselling", "Career Counselling", "Career Counselling", [
            _lookup("student", "Student", "student"),
            _f("counsellor", "Counsellor", "user"),
            _f("session_date", "Date", "date"),
            _f("interests", "Interests", "textarea"),
            _f("recommendations", "Recommendations", "textarea"),
            _status("scheduled", "completed"),
        ]),
    "internship": _entity("internship", "Internship", "Internships", [
        _lookup("student", "Student", "student"),
        _f("organization", "Organization", "text", is_required=True),
        _f("role", "Role", "text"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("supervisor", "Supervisor", "text"),
        _status("applied", "ongoing", "completed"),
    ]),
    "placement_prep": _entity("placement_prep", "Placement Prep", "Placement Prep", [
        _lookup("student", "Student", "student"),
        _f("activity", "Activity", "text", is_required=True),
        _f("prep_date", "Date", "date"),
        _f("notes", "Notes", "textarea"),
        _status("planned", "completed"),
    ]),
    # ── Notes / alerts / risk ─────────────────────────────────────────────────
    "student_note": _entity("student_note", "Student Note", "Student Notes", [
        _lookup("student", "Student", "student"),
        _f("note", "Note", "textarea", is_required=True),
        _f("category", "Category", "text"),
        _f("author", "Author", "user"),
        _f("note_date", "Date", "date"),
        _f("is_confidential", "Confidential", "boolean"),
    ]),
    "student_alert": _entity("student_alert", "Student Alert", "Student Alerts", [
        _lookup("student", "Student", "student"),
        _f("alert_type", "Type", "text"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _f("message", "Message", "textarea"),
        _f("is_active", "Active", "boolean"),
        _f("raised_by", "Raised By", "user"),
    ]),
    "student_risk_indicator": _entity(
        "student_risk_indicator", "Risk Indicator", "Risk Indicators", [
            _lookup("student", "Student", "student"),
            _f("risk_type", "Risk Type", "text"),
            _select("level", "Level", "low", "medium", "high", "critical"),
            _f("score", "Score", "decimal"),
            _f("factors", "Factors", "textarea"),
            _status("open", "monitoring", "resolved"),
        ]),
    # ── Enterprise Student Services (architect-added; reuse Core) ──────────────
    "visitor_log": _entity("visitor_log", "Visitor Log", "Visitor Log", [
        _auto("visitor_no", "Visitor No", "VIS-"),
        _f("visitor_name", "Visitor Name", "text", is_required=True),
        _f("purpose", "Purpose", "text"),
        _f("host", "Host", "user"),
        _lookup("student", "Student (if visiting)", "student"),
        _f("check_in", "Check In", "datetime"),
        _f("check_out", "Check Out", "datetime"),
        _f("badge_no", "Badge No", "text"),
        _status("checked_in", "checked_out"),
    ]),
    "parent_meeting": _entity("parent_meeting", "Parent Meeting", "Parent Meetings", [
        _lookup("student", "Student", "student"),
        _lookup("guardian", "Parent", "guardian"),
        _lookup("teacher", "Teacher", "teacher"),
        _f("meeting_date", "Meeting Date", "datetime"),
        _f("purpose", "Purpose", "textarea"),
        _status("requested", "scheduled", "completed", "cancelled"),
    ]),
    "lost_and_found": _entity("lost_and_found", "Lost & Found", "Lost & Found", [
        _f("item_name", "Item", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("found_date", "Found Date", "date"),
        _f("location", "Location", "text"),
        _f("claimed_by", "Claimed By", "text"),
        _status("found", "claimed", "disposed"),
    ]),
    "incident_report": _entity("incident_report", "Incident Report", "Incident Reports", [
        _auto("incident_ref", "Incident Ref", "INC-"),
        _select("incident_type", "Type", "safety", "security", "property", "medical", "other"),
        _f("incident_date", "Date", "datetime"),
        _f("location", "Location", "text"),
        _f("description", "Description", "textarea"),
        _f("reported_by", "Reported By", "user"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _status("open", "investigating", "closed"),
    ]),
    "safeguarding_record": _entity(
        "safeguarding_record", "Safeguarding Record", "Safeguarding Records", [
            _auto("case_no", "Case No", "SG-"),
            _lookup("student", "Student", "student"),
            _f("concern_type", "Concern Type", "text"),
            _select("severity", "Severity", "low", "medium", "high", "critical"),
            _f("reported_by", "Reported By", "user"),
            _f("report_date", "Report Date", "date"),
            _f("notes", "Notes", "textarea", config={"is_pii": True}),
            _status("open", "investigating", "referred", "closed"),
        ]),
    "meal_plan": _entity("meal_plan", "Meal Plan", "Meal Plans", [
        _lookup("student", "Student", "student"),
        _f("plan_type", "Plan Type", "text"),
        _f("start_date", "Start Date", "date"),
        _status("active", "suspended", "ended"),
    ]),
    "id_card_request": _entity("id_card_request", "ID Card Request", "ID Card Requests", [
        _lookup("student", "Student", "student"),
        _select("reason", "Reason", "new", "replacement", "renewal"),
        _f("request_date", "Request Date", "date"),
        _status("requested", "approved", "issued"),
    ]),
    "gate_pass": _entity("gate_pass", "Gate Pass", "Gate Passes", [
        _lookup("student", "Student", "student"),
        _select("pass_type", "Type", "check_in", "check_out", "gate_pass"),
        _f("pass_time", "Time", "datetime"),
        _f("reason", "Reason", "text"),
        _f("authorized_by", "Authorized By", "user"),
        _status("pending", "approved", "used"),
    ]),
}

_MAIN = list(SCHOOL_OBJECTS.keys())


# ── workflows (reuse the workflow engine + the action_post_journal capability) ─
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created"):
    return {"slug": slug, "name": name, "trigger_type": trigger_type, "trigger_config": {},
            "entity_slug": entity_slug, "steps": steps, "edges": edges}


SCHOOL_WORKFLOWS = [
    # Admission review → approval gate → notify.
    _wf("admission_review", "Admission Review", "admission_application", [
        {"slug": "start", "step_type": "condition", "name": "Submitted", "is_entry": True,
         "config": {}},
        {"slug": "review", "step_type": "approval", "name": "Admissions Review", "config": {}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "admission_approved"}},
    ], [{"source": "start", "target": "review"}, {"source": "review", "target": "notify"}]),

    # Application approved → auto-create the Student + close the application (idempotent: the
    # condition only matches "approved", and the application is moved to "enrolled" after).
    _wf("enroll_on_approval", "Enroll on Approval", "admission_application", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "create_student", "step_type": "action_create_record", "name": "Create Student",
         "config": {"entity_slug": "student", "data": {
             "first_name": "{{record.applicant_name}}", "gender": "{{record.gender}}",
             "dob": "{{record.dob}}", "status": "enrolled"}}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Enrolled",
         "config": {"field": "status", "value": "enrolled"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Admission Letter",
         "config": {"template_slug": "admission_letter"}},
    ], [{"source": "check", "target": "create_student", "condition_label": "true"},
        {"source": "create_student", "target": "mark"}, {"source": "mark", "target": "doc"}],
        trigger_type="record_updated"),

    # Promotion completed → move the student to the new class → generate promotion letter.
    _wf("promotion_processed", "Promotion Processed", "promotion", [
        {"slug": "check", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "move", "step_type": "action_update_record", "name": "Move Student",
         "config": {"entity_slug": "student", "record_id": "{{record.student}}",
                    "data": {"school_class": "{{record.to_class}}"}}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Promotion Letter",
         "config": {"template_slug": "promotion_letter"}},
    ], [{"source": "check", "target": "move", "condition_label": "true"},
        {"source": "move", "target": "doc"}], trigger_type="record_updated"),

    # Transfer completed → set the student's status to "transferred" → generate TC.
    _wf("transfer_processed", "Transfer Processed", "transfer", [
        {"slug": "check", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "upd", "step_type": "action_update_record", "name": "Update Student",
         "config": {"entity_slug": "student", "record_id": "{{record.student}}",
                    "data": {"status": "transferred"}}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Transfer Certificate",
         "config": {"template_slug": "transfer_certificate"}},
    ], [{"source": "check", "target": "upd", "condition_label": "true"},
        {"source": "upd", "target": "doc"}], trigger_type="record_updated"),

    # Withdrawal completed → set the student's status to "withdrawn".
    _wf("withdrawal_processed", "Withdrawal Processed", "withdrawal", [
        {"slug": "check", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "upd", "step_type": "action_update_record", "name": "Update Student",
         "config": {"entity_slug": "student", "record_id": "{{record.student}}",
                    "data": {"status": "withdrawn"}}},
    ], [{"source": "check", "target": "upd", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Graduation completed → set the student's status to "graduated" → generate certificate.
    _wf("graduation_processed", "Graduation Processed", "graduation_record", [
        {"slug": "check", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "upd", "step_type": "action_update_record", "name": "Update Student",
         "config": {"entity_slug": "student", "record_id": "{{record.student}}",
                    "data": {"status": "graduated"}}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Graduation Certificate",
         "config": {"template_slug": "graduation_certificate"}},
    ], [{"source": "check", "target": "upd", "condition_label": "true"},
        {"source": "upd", "target": "doc"}], trigger_type="record_updated"),

    # New inquiry → notify the admissions team to follow up.
    _wf("inquiry_followup", "Inquiry Follow-up", "inquiry", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "inquiry_received"}},
    ], []),

    # Lesson plan submitted → notify the academic coordinator for review (Phase 1.2).
    _wf("lesson_plan_review", "Lesson Plan Review", "lesson_plan", [
        {"slug": "check", "step_type": "condition", "name": "Submitted?", "is_entry": True,
         "config": {"condition_nql": 'status = "submitted"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Coordinator",
         "config": {"template_slug": "lesson_plan_submitted"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Exam results published → notify (Phase 1.2).
    _wf("publish_results", "Publish Results", "exam", [
        {"slug": "check", "step_type": "condition", "name": "Published?", "is_entry": True,
         "config": {"condition_nql": 'status = "published"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "results_published"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Fee invoice issued → POST TO GL (Dr A/R, Cr Service Revenue) → notify → generate invoice PDF.
    _wf("fee_invoice_posting", "Fee Invoice Posting", "fee_invoice", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receivable",
         "is_entry": True, "config": {
             "source_module": "school", "source_ref": "{{record.invoice_no}}",
             "memo": "Fee invoice {{record.invoice_no}}",
             "account_debit": "1100", "account_credit": "4100",
             "amount": "{{record.amount}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Guardian",
         "config": {"template_slug": "fee_invoice_issued"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Generate Invoice PDF",
         "config": {"template_slug": "fee_invoice_document"}},
    ], [{"source": "post", "target": "notify"}, {"source": "notify", "target": "doc"}]),

    # Fee payment received → POST TO GL (Dr Cash, Cr A/R) → notify → generate receipt PDF.
    _wf("fee_payment_posting", "Fee Payment Posting", "fee_payment", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receipt",
         "is_entry": True, "config": {
             "source_module": "school", "source_ref": "{{record.receipt_no}}",
             "memo": "Fee receipt {{record.receipt_no}}",
             "account_debit": "1000", "account_credit": "1100",
             "amount": "{{record.amount}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "fee_payment_received"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Generate Receipt",
         "config": {"template_slug": "fee_receipt"}},
    ], [{"source": "post", "target": "notify"}, {"source": "notify", "target": "doc"}]),

    # Attendance marked absent → alert guardian.
    _wf("attendance_alert", "Attendance Alert", "attendance", [
        {"slug": "alert", "step_type": "action_send_notification", "name": "Alert Guardian",
         "is_entry": True, "config": {"template_slug": "attendance_alert"}},
    ], []),

    # Exam scheduled → notify.
    _wf("exam_scheduled_notice", "Exam Scheduled Notice", "exam", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "exam_scheduled"}},
    ], []),

    # ── Fee-depth (Phase 1.3): approved request → CORE engine (Collections F2 / Credits F3) ──
    # Installment plan approved → build the due schedule via the Collections Engine, then activate.
    _wf("fee_plan_create", "Create Installment Plan", "fee_installment_plan", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "plan", "step_type": "action_create_installment_plan", "name": "Build Schedule",
         "config": {"total_amount": "{{record.total_amount}}",
                    "num_installments": "{{record.num_installments}}",
                    "frequency": "{{record.frequency}}", "start_date": "{{record.start_date}}",
                    "grace_days": "{{record.grace_days}}",
                    "late_fee_type": "{{record.late_fee_type}}",
                    "late_fee_value": "{{record.late_fee_value}}",
                    "subject_ref": "{{record.student}}",
                    "source_document_ref": "{{record.plan_ref}}",
                    "external_ref": "{{record.plan_ref}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Activate",
         "config": {"field": "status", "value": "active"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "installment_plan_created"}},
    ], [{"source": "check", "target": "plan", "condition_label": "true"},
        {"source": "plan", "target": "mark"}, {"source": "mark", "target": "notify"}],
        trigger_type="record_updated"),

    # Discount approved → post a credit (Dr Discounts / Cr A/R) via the Credit Engine.
    _wf("fee_discount_apply", "Apply Fee Discount", "fee_discount", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "discount", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}",
                    "applies_to_ref": "{{record.fee_invoice}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.discount_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Applied",
         "config": {"field": "status", "value": "applied"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "discount_applied"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}, {"source": "mark", "target": "notify"}],
        trigger_type="record_updated"),

    # Scholarship approved → post a credit (Dr Scholarships / Cr A/R) via the Credit Engine.
    _wf("fee_scholarship_apply", "Award Scholarship", "fee_scholarship", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "scholarship", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.scholarship_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Awarded",
         "config": {"field": "status", "value": "awarded"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "scholarship_awarded"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}, {"source": "mark", "target": "notify"}],
        trigger_type="record_updated"),

    # Waiver approved → post a credit (Dr Discounts / Cr A/R) via the Credit Engine.
    _wf("fee_waiver_apply", "Apply Fee Waiver", "fee_waiver", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "waiver", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}",
                    "applies_to_ref": "{{record.fee_invoice}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.waiver_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Applied",
         "config": {"field": "status", "value": "applied"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}], trigger_type="record_updated"),

    # Refund approved → post a refund (Dr revenue-refund / Cr Cash) via the Credit Engine.
    _wf("fee_refund_process", "Process Fee Refund", "fee_refund", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "refund", "step_type": "action_issue_refund", "name": "Issue Refund",
         "config": {"amount": "{{record.amount}}", "subject_ref": "{{record.student}}",
                    "applies_to_ref": "{{record.fee_invoice}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.refund_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Processed",
         "config": {"field": "status", "value": "processed"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "refund_processed"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Refund Document",
         "config": {"template_slug": "refund_document"}},
    ], [{"source": "check", "target": "refund", "condition_label": "true"},
        {"source": "refund", "target": "mark"}, {"source": "mark", "target": "notify"},
        {"source": "notify", "target": "doc"}], trigger_type="record_updated"),

    # Write-off approved → post a write-off (Dr Bad Debt / Cr A/R) via the Credit Engine.
    _wf("fee_writeoff_process", "Process Fee Write-off", "fee_writeoff", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Write Off",
         "config": {"kind": "write_off", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}",
                    "applies_to_ref": "{{record.fee_invoice}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.writeoff_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Written Off",
         "config": {"field": "status", "value": "written_off"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}], trigger_type="record_updated"),

    # ── Student Services (Phase 1.6) — reuse workflow + notification + document Core ──────────
    # Leave request approved → notify guardian.
    _wf("leave_request_approved", "Leave Request Approved", "leave_request", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Guardian",
         "config": {"template_slug": "leave_approved"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Attendance correction approved → notify.
    _wf("attendance_correction_applied", "Attendance Correction Applied", "attendance_correction", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "attendance_corrected"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Behaviour incident logged → alert guardian + update the student timeline (Core activity feed).
    _wf("behaviour_incident_logged", "Behaviour Incident Logged", "behaviour_incident", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Guardian",
         "is_entry": True, "config": {"template_slug": "behaviour_logged"}},
    ], []),

    # Counselling referral created → notify the counselling team.
    _wf("counselling_referral_created", "Counselling Referral", "counselling_referral", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Counsellor",
         "is_entry": True, "config": {"template_slug": "counselling_referral"}},
    ], []),

    # Medical alert raised → notify guardian.
    _wf("medical_alert_raised", "Medical Alert Raised", "medical_alert", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Guardian",
         "is_entry": True, "config": {"template_slug": "medical_alert"}},
    ], []),

    # Award granted → congratulate guardian.
    _wf("award_granted", "Award Granted", "award", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Guardian",
         "is_entry": True, "config": {"template_slug": "award_received"}},
    ], []),

    # Parent meeting scheduled → notify.
    _wf("parent_meeting_scheduled", "Parent Meeting Scheduled", "parent_meeting", [
        {"slug": "check", "step_type": "condition", "name": "Scheduled?", "is_entry": True,
         "config": {"condition_nql": 'status = "scheduled"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "meeting_scheduled"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Safeguarding record opened → confidential alert to the designated lead (in-app only).
    _wf("safeguarding_opened", "Safeguarding Case Opened", "safeguarding_record", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Lead",
         "is_entry": True, "config": {"template_slug": "safeguarding_alert"}},
    ], []),
]


# ── roles (reuse RBAC) ───────────────────────────────────────────────────────
def _role(slug, name, description, grants):
    perms = []
    for entity_slug, actions in grants:
        for action in actions:
            p = {"resource_type": "entity", "action": action}
            if entity_slug:
                p["entity_slug"] = entity_slug
            perms.append(p)
    return {"slug": slug, "name": name, "description": description, "permissions": perms}


_FULL = ["create", "read", "update", "delete", "export"]
_FEE_ENTITIES = ["fee_category", "fee_structure", "fee_invoice", "fee_payment",
                 "fee_installment_plan", "fee_discount", "fee_scholarship", "fee_waiver",
                 "fee_refund", "fee_writeoff"]
SCHOOL_ROLES = [
    _role("school_administrator", "School Administrator", "Full access to the school solution.",
          [(None, _FULL + ["admin"])]),
    _role("principal", "Principal", "Oversight + approvals across the school.",
          [(None, ["read", "export", "update"])]),
    _role("vice_principal", "Vice Principal", "Academic oversight + approvals.",
          [(None, ["read", "export", "update"])]),
    _role("transport_manager", "Transport Manager", "Transport routes and student transport.",
          [("transport_route", _FULL), ("student", ["read"])]),
    _role("hostel_manager", "Hostel Manager", "Hostel rooms and allocations.",
          [("hostel_room", _FULL), ("student", ["read"])]),
    _role("auditor", "Auditor", "Read-only oversight across the school and finance.",
          [(None, ["read", "export"])]),
    _role("registrar", "Registrar", "Admissions, students and the full lifecycle.",
          [("inquiry", _FULL), ("admission_application", _FULL), ("student", _FULL),
           ("guardian", _FULL), ("enrollment", _FULL), ("promotion", _FULL),
           ("transfer", _FULL), ("graduation_record", _FULL), ("withdrawal", _FULL),
           ("alumni", _FULL), ("student_status_history", ["read"]),
           ("school_class", ["read", "update"])]),
    _role("teacher", "Teacher", "Attendance, results, lesson plans, assignments and timetable.",
          [("attendance", _FULL), ("exam_result", _FULL), ("exam", ["read"]),
           ("lesson_plan", _FULL), ("assignment", _FULL), ("subject_assignment", ["read"]),
           ("timetable_entry", ["read"]), ("student", ["read"]), ("school_class", ["read"])]),
    _role("academic_coordinator", "Academic Coordinator",
          "Curriculum, terms, calendar, allocations and lesson plans.",
          [("term", _FULL), ("academic_calendar_event", _FULL), ("curriculum", _FULL),
           ("subject_assignment", _FULL), ("lesson_plan", _FULL), ("promotion_rule", _FULL),
           ("campus", ["read"]), ("school_class", ["read", "update"]), ("subject", ["read"])]),
    _role("accountant", "Accountant",
          "Fee structures, invoices, payments, plans, discounts, refunds and write-offs.",
          [(e, _FULL) for e in _FEE_ENTITIES] + [("student", ["read"])]),
    _role("finance_manager", "Finance Manager",
          "Approves discounts/scholarships/waivers/refunds/write-offs + full fee oversight.",
          [(e, _FULL) for e in _FEE_ENTITIES] + [("student", ["read"]), ("guardian", ["read"])]),
    _role("librarian", "Librarian", "Library catalogue and loans.",
          [("library_book", _FULL), ("book_loan", _FULL), ("student", ["read"])]),
    # ── Student Services roles (Phase 1.6) ────────────────────────────────────
    _role("class_teacher", "Class Teacher", "Attendance, leave, behaviour for the class.",
          [("attendance", _FULL), ("attendance_correction", _FULL), ("leave_request", _FULL),
           ("behaviour_incident", _FULL), ("behaviour_category", ["read"]),
           ("student_note", _FULL), ("student", ["read"]), ("exam_result", ["read"]),
           ("assignment", _FULL)]),
    _role("counsellor", "Counsellor",
          "Counselling, action plans, career guidance, risk indicators.",
          [("counselling_referral", _FULL), ("counselling_session", _FULL),
           ("counselling_action_plan", _FULL), ("career_counselling", _FULL),
           ("student_note", _FULL), ("student_risk_indicator", _FULL),
           ("student_alert", _FULL), ("student", ["read"])]),
    _role("school_nurse", "School Nurse",
          "Medical visits, alerts, health screenings, medications.",
          [("medical_visit", _FULL), ("medical_alert", _FULL), ("health_screening", _FULL),
           ("medication", _FULL), ("allergy", _FULL), ("vaccination_record", _FULL),
           ("emergency_medical_contact", _FULL), ("medical_profile", ["read", "update"]),
           ("medical_condition", ["read"]), ("student", ["read"])]),
    _role("medical_officer", "Medical Officer", "Full medical oversight.",
          [(e, _FULL) for e in ["medical_profile", "medical_condition", "allergy", "medication",
           "vaccination_record", "medical_visit", "medical_alert", "health_screening",
           "emergency_medical_contact"]] + [("student", ["read"])]),
    _role("sports_coordinator", "Sports Coordinator", "Sports, competitions, achievements.",
          [("sport", _FULL), ("sport_participation", _FULL), ("competition", _FULL),
           ("competition_participation", _FULL), ("achievement", _FULL), ("house", _FULL),
           ("house_membership", _FULL), ("student", ["read"])]),
    _role("club_coordinator", "Club Coordinator", "Clubs, activities, volunteering, leadership.",
          [("student_club", _FULL), ("club_membership", _FULL), ("student_activity", _FULL),
           ("volunteer_program", _FULL), ("volunteer_participation", _FULL),
           ("student_leadership", _FULL), ("student_election", _FULL), ("award", _FULL),
           ("student", ["read"])]),
]


# ── reports + dashboards (reuse reporting) ───────────────────────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


SCHOOL_REPORTS = [
    _report("student_roster_report", "Student Roster", "student"),
    _report("attendance_summary_report", "Attendance Summary", "attendance", "pivot"),
    _report("exam_results_report", "Exam Results", "exam_result", "pivot"),
    _report("fee_collection_report", "Fee Collection", "fee_payment"),
    _report("outstanding_fees_report", "Outstanding Fees", "fee_invoice"),
    # Lifecycle (Phase 1.1)
    _report("admissions_funnel_report", "Admissions Funnel", "admission_application", "pivot"),
    _report("inquiry_pipeline_report", "Inquiry Pipeline", "inquiry", "pivot"),
    _report("enrollment_trend_report", "Enrollment Trend", "enrollment"),
    _report("alumni_directory_report", "Alumni Directory", "alumni"),
    # Academic structure (Phase 1.2)
    _report("teacher_workload_report", "Teacher Workload", "subject_assignment", "pivot"),
    _report("curriculum_overview_report", "Curriculum Overview", "curriculum"),
    _report("academic_calendar_report", "Academic Calendar", "academic_calendar_event"),
    # Fee-depth (Phase 1.3)
    _report("fee_discounts_report", "Fee Discounts", "fee_discount", "pivot"),
    _report("scholarships_report", "Scholarships", "fee_scholarship", "pivot"),
    _report("fee_refunds_report", "Fee Refunds", "fee_refund"),
    _report("installment_plans_report", "Installment Plans", "fee_installment_plan"),
    _report("fee_writeoffs_report", "Fee Write-offs", "fee_writeoff"),
    # Services (Phase 1.3 role dashboards)
    _report("book_loans_report", "Book Loans", "book_loan", "pivot"),
    _report("transport_routes_report", "Transport Routes", "transport_route"),
    _report("hostel_rooms_report", "Hostel Rooms", "hostel_room"),
    # Student Services (Phase 1.6)
    _report("leave_requests_report", "Leave Requests", "leave_request", "pivot"),
    _report("behaviour_report", "Behaviour Incidents", "behaviour_incident", "pivot"),
    _report("medical_visits_report", "Medical Visits", "medical_visit", "pivot"),
    _report("counselling_report", "Counselling Sessions", "counselling_session", "pivot"),
    _report("activities_report", "Student Activities", "student_activity", "pivot"),
    _report("sports_report", "Sports Participation", "sport_participation", "pivot"),
    _report("awards_report", "Awards", "award", "pivot"),
    _report("risk_indicators_report", "Risk Indicators", "student_risk_indicator", "pivot"),
    _report("health_screenings_report", "Health Screenings", "health_screening", "pivot"),
    _report("safeguarding_report", "Safeguarding Cases", "safeguarding_record", "pivot"),
    # Reporting & Analytics (Phase 1.7) — cross-module management/executive/compliance coverage
    _report("student_lifecycle_report", "Student Lifecycle", "student", "pivot"),
    _report("discipline_report", "Disciplinary Actions", "disciplinary_action", "pivot"),
    _report("special_education_report", "Special Education (IEP)", "iep", "pivot"),
    _report("career_guidance_report", "Career Guidance", "career_counselling", "pivot"),
    _report("internships_report", "Internships", "internship", "pivot"),
    _report("parent_engagement_report", "Parent Engagement", "parent_meeting", "pivot"),
    _report("clubs_report", "Club Memberships", "club_membership", "pivot"),
    _report("competitions_report", "Competitions", "competition_participation", "pivot"),
    _report("volunteer_report", "Community Service", "volunteer_participation", "pivot"),
    _report("visitor_report", "Visitor Log", "visitor_log", "pivot"),
    _report("incidents_report", "Incident Reports", "incident_report", "pivot"),
    _report("id_card_requests_report", "ID Card Requests", "id_card_request", "pivot"),
]


# ── KPIs (Phase 1.7) — reuse the Analytics Engine (apps.analytics.KPIDefinition + KPIService).
# NQL-sourced aggregates over School entities; surfaced in the /analytics scorecard + KPI widgets.
def _kpi(code, name, category, nql_source, *, aggregate="count", value_field="",
         direction="higher_better", unit="", target=0):
    return {"code": code, "name": name, "category": category, "source_type": "nql",
            "nql_source": nql_source, "aggregate": aggregate, "value_field": value_field,
            "direction": direction, "unit": unit, "target": target}


SCHOOL_KPIS = [
    # Academic / enrollment
    _kpi("students_enrolled", "Students Enrolled", "academic",
         'FROM student WHERE status = "enrolled"'),
    _kpi("new_admissions", "New Admissions", "academic",
         'FROM admission_application WHERE status = "approved"'),
    _kpi("open_inquiries", "Open Inquiries", "operations",
         'FROM inquiry WHERE status = "new"'),
    _kpi("awards_granted", "Awards Granted", "academic", "FROM award"),
    # Financial
    _kpi("fee_collected", "Fee Collected", "financial", "FROM fee_payment",
         aggregate="sum", value_field="amount", unit="$"),
    _kpi("outstanding_invoices", "Overdue Invoices", "financial",
         'FROM fee_invoice WHERE status = "overdue"', direction="lower_better"),
    _kpi("scholarships_awarded", "Scholarships Awarded", "financial",
         'FROM fee_scholarship WHERE status = "awarded"', aggregate="sum", value_field="amount",
         unit="$"),
    # Operations
    _kpi("behaviour_incidents", "Behaviour Incidents", "operations", "FROM behaviour_incident",
         direction="lower_better"),
    _kpi("open_counselling", "Open Counselling Referrals", "operations",
         'FROM counselling_referral WHERE status = "open"'),
    _kpi("medical_visits", "Medical Visits", "operations", "FROM medical_visit"),
    _kpi("active_library_loans", "Active Library Loans", "operations",
         'FROM book_loan WHERE status = "issued"'),
    # Risk / early warning
    _kpi("high_risk_students", "High-Risk Students", "risk",
         'FROM student_risk_indicator WHERE level = "high"', direction="lower_better"),
    _kpi("open_safeguarding", "Open Safeguarding Cases", "risk",
         'FROM safeguarding_record WHERE status = "open"', direction="lower_better"),
]


# ── Validation / data-integrity rules (Phase 1.8) — reuse the Business Rules engine (apps.rules).
# block_save guards protect the GL/credit/collections posting paths from zero/negative amounts. ──
def _block_rule(entity, field, op, val, msg, trigger):
    return {"slug": f"validate_{entity}_{field}_{trigger}",
            "name": f"Validate {entity}.{field}", "entity_slug": entity, "trigger_on": trigger,
            "condition_nql": f"{field} {op} {val}",
            "actions": [{"type": "block_save", "message": msg}], "priority": 10}


SCHOOL_RULES = [
    _block_rule(e, f, "<=", "0", f"{f.replace('_', ' ').title()} must be greater than zero.", trig)
    for e, f in [("fee_invoice", "amount"), ("fee_payment", "amount"), ("fee_discount", "amount"),
                 ("fee_scholarship", "amount"), ("fee_refund", "amount"),
                 ("fee_writeoff", "amount"), ("fee_installment_plan", "total_amount")]
    for trig in ("before_create", "before_update")
] + [
    _block_rule("exam_result", "marks_obtained", "<", "0", "Marks cannot be negative.",
                "before_create"),
]


# ── SLA response-time policies (Phase 1.8) — reuse the SLA engine (apps.sla; auto-attached on
# record create). Enterprise child-safety / welfare responsiveness (wall-clock). ──────────────
def _sla(slug, name, entity, minutes, warn=75):
    return {"slug": slug, "name": name, "entity_slug": entity, "applies_when_nql": "",
            "targets": [{"metric": "resolution", "target_minutes": minutes,
                         "warning_at_percent": warn, "business_hours_only": False}]}


SCHOOL_SLA_POLICIES = [
    _sla("safeguarding_response", "Safeguarding Response", "safeguarding_record", 1440),   # 24h
    _sla("counselling_response", "Counselling Response", "counselling_referral", 4320, 80),  # 72h
    _sla("incident_response", "Incident Response", "incident_report", 2880),               # 48h
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


SCHOOL_DASHBOARDS = [
    {"slug": "principal_dashboard", "name": "Principal Dashboard", "is_default": True,
     "widgets": [
         _w("metric_card", "Enrolled Students", 0, 0, 3, 2),
         _w("metric_card", "Attendance %", 3, 0, 3, 2),
         _w("metric_card", "Fee Collection", 6, 0, 3, 2),
         _w("metric_card", "Outstanding Fees", 9, 0, 3, 2),
         _w("report", "Fee Collection", 0, 2, 6, 4, report_slug="fee_collection_report"),
         _w("report", "Outstanding Fees", 6, 2, 6, 4, report_slug="outstanding_fees_report"),
     ]},
    {"slug": "academic_dashboard", "name": "Academic Dashboard", "widgets": [
        _w("report", "Exam Results", 0, 0, 6, 4, report_slug="exam_results_report"),
        _w("report", "Attendance Summary", 6, 0, 6, 4, report_slug="attendance_summary_report"),
    ]},
    {"slug": "academic_planning_dashboard", "name": "Academic Planning Dashboard", "widgets": [
        _w("metric_card", "Active Terms", 0, 0, 3, 2),
        _w("metric_card", "Curricula", 3, 0, 3, 2),
        _w("metric_card", "Lesson Plans (Submitted)", 6, 0, 3, 2),
        _w("report", "Teacher Workload", 0, 2, 6, 4, report_slug="teacher_workload_report"),
        _w("report", "Academic Calendar", 6, 2, 6, 4, report_slug="academic_calendar_report"),
    ]},
    {"slug": "admissions_dashboard", "name": "Admissions Dashboard", "widgets": [
        _w("metric_card", "Open Inquiries", 0, 0, 3, 2),
        _w("metric_card", "Applications", 3, 0, 3, 2),
        _w("metric_card", "Enrolled (YTD)", 6, 0, 3, 2),
        _w("report", "Inquiry Pipeline", 0, 2, 6, 4, report_slug="inquiry_pipeline_report"),
        _w("report", "Admissions Funnel", 6, 2, 6, 4, report_slug="admissions_funnel_report"),
    ]},
    # Finance / Accountant dashboard (Phase 1.3) — fee collection + credits lifecycle.
    {"slug": "finance_dashboard", "name": "Finance Dashboard", "widgets": [
        _w("metric_card", "Fee Collection", 0, 0, 3, 2),
        _w("metric_card", "Outstanding Fees", 3, 0, 3, 2),
        _w("metric_card", "Discounts Applied", 6, 0, 3, 2),
        _w("metric_card", "Scholarships Awarded", 9, 0, 3, 2),
        _w("report", "Fee Collection", 0, 2, 6, 4, report_slug="fee_collection_report"),
        _w("report", "Outstanding Fees", 6, 2, 6, 4, report_slug="outstanding_fees_report"),
        _w("report", "Fee Discounts", 0, 6, 4, 4, report_slug="fee_discounts_report"),
        _w("report", "Scholarships", 4, 6, 4, 4, report_slug="scholarships_report"),
        _w("report", "Fee Refunds", 8, 6, 4, 4, report_slug="fee_refunds_report"),
    ]},
    # Service role dashboards (Phase 1.3).
    {"slug": "library_dashboard", "name": "Library Dashboard", "widgets": [
        _w("report", "Book Loans", 0, 0, 12, 5, report_slug="book_loans_report"),
    ]},
    {"slug": "transport_dashboard", "name": "Transport Dashboard", "widgets": [
        _w("report", "Transport Routes", 0, 0, 12, 5, report_slug="transport_routes_report"),
    ]},
    {"slug": "hostel_dashboard", "name": "Hostel Dashboard", "widgets": [
        _w("report", "Hostel Rooms", 0, 0, 12, 5, report_slug="hostel_rooms_report"),
    ]},
    # Student Services dashboards (Phase 1.6).
    {"slug": "counsellor_dashboard", "name": "Counsellor Dashboard", "widgets": [
        _w("report", "Counselling Sessions", 0, 0, 6, 4, report_slug="counselling_report"),
        _w("report", "Risk Indicators", 6, 0, 6, 4, report_slug="risk_indicators_report"),
    ]},
    {"slug": "medical_dashboard", "name": "Medical Dashboard", "widgets": [
        _w("report", "Medical Visits", 0, 0, 6, 4, report_slug="medical_visits_report"),
        _w("report", "Health Screenings", 6, 0, 6, 4, report_slug="health_screenings_report"),
    ]},
    {"slug": "activities_dashboard", "name": "Activities Dashboard", "widgets": [
        _w("report", "Student Activities", 0, 0, 4, 4, report_slug="activities_report"),
        _w("report", "Sports Participation", 4, 0, 4, 4, report_slug="sports_report"),
        _w("report", "Awards", 8, 0, 4, 4, report_slug="awards_report"),
    ]},
    {"slug": "welfare_dashboard", "name": "Student Welfare Dashboard", "widgets": [
        _w("report", "Behaviour Incidents", 0, 0, 6, 4, report_slug="behaviour_report"),
        _w("report", "Leave Requests", 6, 0, 6, 4, report_slug="leave_requests_report"),
        _w("report", "Risk Indicators", 0, 4, 6, 4, report_slug="risk_indicators_report"),
        _w("report", "Safeguarding Cases", 6, 4, 6, 4, report_slug="safeguarding_report"),
    ]},
    # Executive intelligence dashboard (Phase 1.7) — cross-module for administrator/leadership.
    {"slug": "executive_dashboard", "name": "Executive Dashboard", "widgets": [
        _w("metric_card", "Students Enrolled", 0, 0, 3, 2),
        _w("metric_card", "Fee Collection", 3, 0, 3, 2),
        _w("metric_card", "Outstanding Fees", 6, 0, 3, 2),
        _w("metric_card", "High-Risk Students", 9, 0, 3, 2),
        _w("report", "Enrollment (by status)", 0, 2, 6, 4, report_slug="student_lifecycle_report"),
        _w("report", "Fee Collection", 6, 2, 6, 4, report_slug="fee_collection_report"),
        _w("report", "Behaviour", 0, 6, 4, 4, report_slug="behaviour_report"),
        _w("report", "Attendance", 4, 6, 4, 4, report_slug="attendance_summary_report"),
        _w("report", "Risk Indicators", 8, 6, 4, 4, report_slug="risk_indicators_report"),
    ]},
]

# ── role → home dashboard (Phase 1.3, DG-5): each operational role auto-opens its dashboard
# after login via a role-scoped HomeLayout (the installer resolves role_slug → role id). Reuses
# the existing Studio resolve mechanism; a widget of type "dashboard" renders the referenced
# Dashboard through the F2.3 dashboard runtime. Owner/admin (system roles) fall back to the
# app-scoped home. Student/Parent are portal users (separate realm — not member home layouts).
_ROLE_HOME = [
    ("school_administrator", "executive_dashboard"),
    ("principal", "principal_dashboard"),
    ("vice_principal", "academic_dashboard"),
    ("registrar", "admissions_dashboard"),
    ("academic_coordinator", "academic_planning_dashboard"),
    ("accountant", "finance_dashboard"),
    ("finance_manager", "finance_dashboard"),
    ("teacher", "academic_dashboard"),
    ("librarian", "library_dashboard"),
    ("transport_manager", "transport_dashboard"),
    ("hostel_manager", "hostel_dashboard"),
    ("auditor", "finance_dashboard"),
    # Student Services roles (Phase 1.6)
    ("class_teacher", "welfare_dashboard"),
    ("counsellor", "counsellor_dashboard"),
    ("school_nurse", "medical_dashboard"),
    ("medical_officer", "medical_dashboard"),
    ("sports_coordinator", "activities_dashboard"),
    ("club_coordinator", "activities_dashboard"),
]


def _role_home(role_slug, dashboard_slug, name):
    return {"ref": f"home_{role_slug}", "name": name, "role_slug": role_slug,
            "widgets": [{"type": "dashboard", "title": name,
                         "config": {"dashboard_slug": dashboard_slug}}]}


_DASH_NAMES = {d["slug"]: d["name"] for d in SCHOOL_DASHBOARDS}
SCHOOL_ROLE_HOMES = [
    _role_home(rs, ds, _DASH_NAMES.get(ds, "Home")) for rs, ds in _ROLE_HOME
]

SCHOOL_NOTIFICATIONS = [
    {"slug": "inquiry_received", "name": "Inquiry Received", "channels": ["in_app"],
     "subject_template": "New inquiry", "body_template": "A new admission inquiry was received."},
    {"slug": "admission_approved", "name": "Admission Approved", "channels": ["in_app"],
     "subject_template": "Admission approved", "body_template": "The application is approved."},
    {"slug": "fee_invoice_issued", "name": "Fee Invoice Issued", "channels": ["in_app"],
     "subject_template": "Fee invoice issued", "body_template": "A new fee invoice is available."},
    {"slug": "fee_payment_received", "name": "Fee Payment Received", "channels": ["in_app"],
     "subject_template": "Payment received", "body_template": "Thank you for your payment."},
    {"slug": "attendance_alert", "name": "Attendance Alert", "channels": ["in_app"],
     "subject_template": "Attendance alert", "body_template": "Your child was marked absent."},
    {"slug": "exam_scheduled", "name": "Exam Scheduled", "channels": ["in_app"],
     "subject_template": "Exam scheduled", "body_template": "An exam has been scheduled."},
    {"slug": "lesson_plan_submitted", "name": "Lesson Plan Submitted", "channels": ["in_app"],
     "subject_template": "Lesson plan to review", "body_template": "A lesson plan was submitted."},
    {"slug": "results_published", "name": "Results Published", "channels": ["in_app"],
     "subject_template": "Results published", "body_template": "Exam results are now available."},
    # Fee-depth (Phase 1.3)
    {"slug": "installment_plan_created", "name": "Installment Plan Created", "channels": ["in_app"],
     "subject_template": "Installment plan ready",
     "body_template": "A fee installment plan has been set up."},
    {"slug": "discount_applied", "name": "Discount Applied", "channels": ["in_app"],
     "subject_template": "Fee discount applied", "body_template": "A discount was applied to fees."},
    {"slug": "scholarship_awarded", "name": "Scholarship Awarded", "channels": ["in_app"],
     "subject_template": "Scholarship awarded", "body_template": "A scholarship has been awarded."},
    {"slug": "refund_processed", "name": "Refund Processed", "channels": ["in_app"],
     "subject_template": "Refund processed", "body_template": "A fee refund has been processed."},
    # Student Services (Phase 1.6)
    {"slug": "leave_approved", "name": "Leave Approved", "channels": ["in_app"],
     "subject_template": "Leave approved", "body_template": "The leave request has been approved."},
    {"slug": "attendance_corrected", "name": "Attendance Corrected", "channels": ["in_app"],
     "subject_template": "Attendance corrected", "body_template": "An attendance record was corrected."},
    {"slug": "behaviour_logged", "name": "Behaviour Incident", "channels": ["in_app"],
     "subject_template": "Behaviour update", "body_template": "A behaviour incident was recorded."},
    {"slug": "counselling_referral", "name": "Counselling Referral", "channels": ["in_app"],
     "subject_template": "Counselling referral", "body_template": "A student was referred for counselling."},
    {"slug": "medical_alert", "name": "Medical Alert", "channels": ["in_app"],
     "subject_template": "Medical alert", "body_template": "A medical alert was raised for your child."},
    {"slug": "award_received", "name": "Award Received", "channels": ["in_app"],
     "subject_template": "Congratulations!", "body_template": "Your child received an award."},
    {"slug": "meeting_scheduled", "name": "Meeting Scheduled", "channels": ["in_app"],
     "subject_template": "Parent meeting scheduled", "body_template": "A parent meeting has been scheduled."},
    {"slug": "safeguarding_alert", "name": "Safeguarding Alert", "channels": ["in_app"],
     "subject_template": "Safeguarding case", "body_template": "A safeguarding case requires attention."},
]


# ── document templates (Phase 1.4) — reuse the Core Document Engine (apps.document_templates +
# action_generate_document). Pure metadata: header blocks map to record fields; an optional
# line-item table maps to a related entity. NO School-specific document/render code. ──────────
def _blocks(entity_slug, field_slugs):
    name_by = {f["slug"]: f["name"] for f in SCHOOL_OBJECTS[entity_slug]["fields"]}
    return [{"field": s, "label": name_by.get(s, s.replace("_", " ").title())} for s in field_slugs]


def _doc(slug, name, entity_slug, title, field_slugs, *, subtitle="", line_items=None):
    d = {"slug": slug, "name": name, "entity_slug": entity_slug,
         "page_config": {"title": title, "subtitle": subtitle},
         "blocks": _blocks(entity_slug, field_slugs)}
    if line_items:
        d["line_items"] = line_items
    return d


SCHOOL_DOCUMENTS = [
    # Admissions
    _doc("admission_application_pdf", "Admission Application", "admission_application",
         "Admission Application", ["application_no", "applicant_name", "dob", "gender",
         "guardian_name", "guardian_phone", "grade_applied", "application_date", "status"]),
    _doc("admission_letter", "Admission Letter", "admission_application", "Admission Letter",
         ["application_no", "applicant_name", "grade_applied", "status"]),
    _doc("offer_letter", "Offer Letter", "admission_application", "Offer of Admission",
         ["application_no", "applicant_name", "grade_applied"]),
    _doc("acceptance_letter", "Acceptance Letter", "admission_application", "Acceptance Letter",
         ["application_no", "applicant_name", "grade_applied"]),
    _doc("waiting_list_letter", "Waiting List Letter", "admission_application",
         "Waiting List Notification", ["application_no", "applicant_name", "grade_applied"]),
    # Student
    _doc("student_profile", "Student Profile", "student", "Student Profile",
         ["admission_no", "first_name", "last_name", "dob", "gender", "blood_group",
          "nationality", "guardian", "school_class", "roll_no", "admission_date", "status"]),
    _doc("student_id_card", "Student ID Card", "student", "Student ID Card",
         ["admission_no", "first_name", "last_name", "school_class", "roll_no", "blood_group"]),
    _doc("student_record", "Student Record", "student", "Student Record",
         ["admission_no", "first_name", "last_name", "dob", "admission_date", "status"]),
    _doc("student_portfolio", "Student Portfolio", "student", "Student Portfolio",
         ["admission_no", "first_name", "last_name", "school_class"]),
    _doc("medical_record", "Medical Record", "student", "Medical Record",
         ["admission_no", "first_name", "blood_group", "emergency_contact"]),
    _doc("emergency_contact_form", "Emergency Contact Form", "student", "Emergency Contact Form",
         ["admission_no", "first_name", "emergency_contact", "guardian"]),
    _doc("guardian_document", "Guardian Document", "guardian", "Guardian Details",
         ["name", "relationship", "phone", "email", "occupation", "address"]),
    # Academic
    _doc("report_card", "Report Card", "exam_result", "Report Card",
         ["student", "exam", "subject", "marks_obtained", "max_marks", "grade", "remarks"]),
    _doc("progress_report", "Progress Report", "student", "Progress Report",
         ["admission_no", "first_name", "last_name", "school_class"]),
    _doc("transcript", "Transcript", "student", "Academic Transcript",
         ["admission_no", "first_name", "last_name", "school_class"]),
    _doc("promotion_letter", "Promotion Letter", "promotion", "Promotion Letter",
         ["student", "from_class", "to_class", "academic_year", "promotion_date"]),
    _doc("transfer_certificate", "Transfer Certificate", "transfer", "Transfer Certificate",
         ["student", "transfer_type", "to_school", "transfer_date", "reason"]),
    _doc("leaving_certificate", "Leaving Certificate", "withdrawal", "Leaving Certificate",
         ["student", "withdrawal_date", "reason"]),
    _doc("graduation_certificate", "Graduation Certificate", "graduation_record",
         "Graduation Certificate", ["student", "academic_year", "graduation_date", "final_grade"]),
    _doc("enrollment_certificate", "Enrollment Certificate", "enrollment",
         "Enrollment Certificate", ["student", "school_class", "academic_year",
         "enrollment_date", "status"]),
    _doc("bonafide_certificate", "Bonafide Certificate", "student", "Bonafide Certificate",
         ["admission_no", "first_name", "last_name", "school_class", "status"]),
    _doc("conduct_certificate", "Conduct Certificate", "student", "Certificate of Conduct",
         ["admission_no", "first_name", "last_name", "status"]),
    _doc("attendance_report_doc", "Attendance Report", "attendance", "Attendance Report",
         ["student", "school_class", "date", "status", "remarks"]),
    _doc("exam_hall_ticket", "Exam Hall Ticket", "exam_result", "Examination Hall Ticket",
         ["student", "exam", "subject"]),
    # Fee Management
    _doc("fee_invoice_document", "Fee Invoice", "fee_invoice", "Fee Invoice",
         ["invoice_no", "student", "fee_structure", "amount", "issue_date", "due_date",
          "academic_year", "status"]),
    _doc("fee_receipt", "Fee Receipt", "fee_payment", "Fee Receipt",
         ["receipt_no", "fee_invoice", "amount", "payment_date", "method", "reference"]),
    _doc("statement_of_account", "Statement of Account", "student", "Statement of Account",
         ["admission_no", "first_name", "last_name"],
         line_items={"entity_slug": "fee_invoice", "relation_field": "student",
                     "title": "Invoices", "columns": [
                         {"key": "invoice_no", "label": "Invoice"},
                         {"key": "amount", "label": "Amount"},
                         {"key": "due_date", "label": "Due"},
                         {"key": "status", "label": "Status"}]}),
    _doc("installment_schedule_doc", "Installment Schedule", "fee_installment_plan",
         "Installment Schedule", ["plan_ref", "student", "total_amount", "num_installments",
         "frequency", "start_date", "status"]),
    _doc("scholarship_letter", "Scholarship Letter", "fee_scholarship", "Scholarship Award Letter",
         ["scholarship_no", "student", "sponsor", "amount", "academic_year", "status"]),
    _doc("discount_approval_doc", "Discount Approval", "fee_discount", "Fee Discount Approval",
         ["discount_no", "student", "fee_invoice", "amount", "reason", "status"]),
    _doc("refund_document", "Refund Document", "fee_refund", "Fee Refund",
         ["refund_no", "student", "amount", "method", "reason", "status"]),
    _doc("writeoff_approval_doc", "Write-off Approval", "fee_writeoff", "Fee Write-off Approval",
         ["writeoff_no", "student", "fee_invoice", "amount", "reason", "status"]),
    _doc("collections_notice", "Collections Notice", "fee_invoice", "Collections Notice",
         ["invoice_no", "student", "amount", "due_date", "status"]),
    _doc("reminder_letter", "Reminder Letter", "fee_invoice", "Payment Reminder",
         ["invoice_no", "student", "amount", "due_date"]),
    # Library
    _doc("library_card", "Library Card", "student", "Library Card",
         ["admission_no", "first_name", "last_name", "school_class"]),
    _doc("book_issue_receipt", "Book Issue Receipt", "book_loan", "Book Issue Receipt",
         ["library_book", "student", "issue_date", "due_date", "status"]),
    _doc("book_return_receipt", "Book Return Receipt", "book_loan", "Book Return Receipt",
         ["library_book", "student", "return_date", "status"]),
    _doc("fine_notice", "Fine Notice", "book_loan", "Library Fine Notice",
         ["library_book", "student", "due_date", "status"]),
    # Transport
    _doc("transport_pass", "Transport Pass", "student", "Transport Pass",
         ["admission_no", "first_name", "school_class", "uses_transport"]),
    _doc("bus_allocation", "Bus Allocation", "transport_route", "Bus Allocation",
         ["name", "vehicle_no", "driver_name", "capacity", "fee"]),
    _doc("route_card", "Route Card", "transport_route", "Route Card",
         ["name", "vehicle_no", "driver_name"]),
    # Hostel
    _doc("hostel_allocation", "Hostel Allocation", "hostel_room", "Hostel Allocation",
         ["hostel_name", "room_no", "capacity", "occupied", "warden"]),
    _doc("room_agreement", "Room Agreement", "hostel_room", "Hostel Room Agreement",
         ["hostel_name", "room_no", "warden"]),
    _doc("checkout_report", "Checkout Report", "hostel_room", "Hostel Checkout Report",
         ["hostel_name", "room_no", "occupied"]),
    # Staff
    _doc("teacher_appointment", "Teacher Appointment", "teacher", "Appointment Letter",
         ["employee_no", "name", "email", "qualification", "specialization", "join_date",
          "status"]),
    _doc("staff_id", "Staff ID", "teacher", "Staff ID Card",
         ["employee_no", "name", "specialization"]),
    _doc("assignment_letter", "Assignment Letter", "subject_assignment", "Assignment Letter",
         ["school_class", "subject", "teacher", "term", "hours_per_week"]),
]


# ── forms / views ────────────────────────────────────────────────────────────
def _form_for(slug):
    obj = SCHOOL_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = SCHOOL_OBJECTS[slug]
    field_slugs = {f["slug"] for f in obj["fields"]}
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if "status" in field_slugs:
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


# ── navigation ───────────────────────────────────────────────────────────────
def _nav_group(label, slugs):
    return {"label": label, "items": [
        {"label": SCHOOL_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
        for s in slugs]}


SCHOOL_NAV = [
    _nav_group("Admissions", ["inquiry", "admission_application", "guardian"]),
    _nav_group("Students", ["student", "enrollment", "attendance",
                            "student_status_history"]),
    _nav_group("Lifecycle", ["promotion", "transfer", "graduation_record", "withdrawal",
                             "alumni"]),
    _nav_group("Academics", ["campus", "academic_year", "term", "academic_calendar_event",
                             "grade_level", "school_class", "subject", "teacher",
                             "timetable_entry"]),
    _nav_group("Academic Planning", ["curriculum", "subject_assignment", "lesson_plan",
                                     "assignment", "promotion_rule"]),
    _nav_group("Examinations", ["exam", "exam_result"]),
    _nav_group("Finance", ["fee_structure", "fee_invoice", "fee_payment"]),
    _nav_group("Fee Management", ["fee_category", "fee_installment_plan", "fee_discount",
                                  "fee_scholarship", "fee_waiver", "fee_refund", "fee_writeoff"]),
    _nav_group("Library", ["library_book", "book_loan"]),
    _nav_group("Transport & Hostel", ["transport_route", "hostel_room"]),
    # Student Services (Phase 1.6)
    _nav_group("Attendance & Leave", ["leave_request", "attendance_correction"]),
    _nav_group("Behaviour", ["behaviour_category", "behaviour_incident", "disciplinary_action"]),
    _nav_group("Counselling", ["counselling_referral", "counselling_session",
                               "counselling_action_plan", "career_counselling"]),
    _nav_group("Medical", ["medical_profile", "medical_condition", "allergy", "medication",
                           "vaccination_record", "medical_visit", "medical_alert",
                           "health_screening", "emergency_medical_contact"]),
    _nav_group("Special Education", ["learning_support", "special_need", "accommodation_plan",
                                     "iep"]),
    _nav_group("Activities & Welfare", ["student_club", "club_membership", "sport",
                                        "sport_participation", "competition",
                                        "competition_participation", "achievement", "award",
                                        "student_activity", "volunteer_program",
                                        "volunteer_participation", "student_leadership", "house",
                                        "house_membership", "student_election"]),
    _nav_group("Career", ["internship", "placement_prep"]),
    _nav_group("Student Records", ["student_note", "student_alert", "student_risk_indicator",
                                   "parent_meeting", "id_card_request", "gate_pass", "meal_plan"]),
    _nav_group("Safety & Safeguarding", ["visitor_log", "incident_report", "lost_and_found",
                                         "safeguarding_record"]),
]


# ── portal grants (Phase 1.5) — configure the generic Portal Engine via metadata ONLY. Parent &
# student portal users link to a STUDENT record; per-student data is direct single-hop, class-level
# data (timetable/assignments/subjects) uses the Core indirect-scope (link_source="school_class").
# Teachers are staff → they use the INTERNAL app (teacher role), not the external portal realm. ──
_PORTAL_SCOPES = [
    ("student", "id", ""),                        # own profile
    ("attendance", "student", ""),
    ("exam_result", "student", ""),               # grades / report cards
    ("enrollment", "student", ""),
    ("fee_invoice", "student", ""),               # fee statement / outstanding
    ("fee_installment_plan", "student", ""),
    ("fee_scholarship", "student", ""),
    ("fee_discount", "student", ""),
    ("book_loan", "student", ""),                 # library
    ("promotion", "student", ""),
    ("transfer", "student", ""),
    ("graduation_record", "student", ""),
    ("timetable_entry", "school_class", "school_class"),   # indirect: student's class
    ("assignment", "school_class", "school_class"),        # indirect: homework / assignments
    ("subject_assignment", "school_class", "school_class"),  # indirect: subjects for the class
    # Student Services (Phase 1.6) — per-student records the family may view (NOT the confidential
    # counselling/medical-detail/safeguarding records).
    ("leave_request", "student", ""),
    ("behaviour_incident", "student", ""),
    ("award", "student", ""),
    ("achievement", "student", ""),
    ("student_activity", "student", ""),
    ("club_membership", "student", ""),
    ("sport_participation", "student", ""),
    ("student_leadership", "student", ""),
    ("medical_alert", "student", ""),
]
SCHOOL_PORTAL_GRANTS = [
    {"entity_slug": e, "portal_type": pt, "link_field": lf, "link_source": ls, "can_read": True}
    for pt in ("student", "parent")
    for (e, lf, ls) in _PORTAL_SCOPES
]


# ── the package block (Solution Package Platform metadata) ───────────────────
def _package_block() -> dict:
    return {
        "slug": "school", "name": "School Management", "version": "2.7.0",
        "author": "Sridhar ERP",
        "description": "K-12 School Management — full student lifecycle (inquiry → admission → "
                       "enrollment → promotion/transfer → graduation → alumni), academic "
                       "structure (campus, terms, calendar, curriculum, allocations, lesson "
                       "plans), attendance, examinations, fees with accounting, library, "
                       "transport and hostel.",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": ["accounting", "workflow"],
        "requires_capabilities": ["metadata", "dynamic_forms", "views", "workflows",
                                  "reports", "dashboards", "rbac", "notifications",
                                  "accounting", "numbering", "documents", "analytics_kpi"],
        "requires_packages": [],
        "optional_packages": [{"slug": "hr", "version": "*"}],   # teachers ↔ HR employees
        "conflicts_packages": [],
        "provides_capabilities": ["school", "student_information_system",
                                  "student_lifecycle"],
        # Declarative, additive-safe upgrade steps to bring a v1.x install up to v2.0 (Phase 1.1
        # student lifecycle). New entities/fields apply through the additive applier; this only
        # adds the new student fields (idempotent) + defaults the status for existing rows.
        "migrations": [
            {"version": "2.0.0",
             "description": "Student lifecycle: emergency contact + transport + nationality, "
                            "and default the student status.",
             "operations": [
                 {"op": "add_field", "entity": "student",
                  "field": {"slug": "emergency_contact", "name": "Emergency Contact",
                            "field_type": "phone", "is_promoted": True}},
                 {"op": "add_field", "entity": "student",
                  "field": {"slug": "uses_transport", "name": "Uses Transport",
                            "field_type": "boolean", "is_promoted": True}},
                 {"op": "add_field", "entity": "student",
                  "field": {"slug": "nationality", "name": "Nationality",
                            "field_type": "text", "is_promoted": True}},
                 {"op": "set_default", "entity": "student", "field": "status",
                  "value": "applicant"}]},
            {"version": "2.1.0",
             "description": "Academic structure: default new terms to planning.",
             "operations": [
                 {"op": "set_default", "entity": "term", "field": "status",
                  "value": "planning"}]},
            {"version": "2.2.0",
             "description": "Fee Management depth: installment plans, discounts, scholarships, "
                            "waivers, refunds and write-offs — new request entities consume the "
                            "Core Collections (F2) + Credits (F3) engines. New entities apply "
                            "additively on upgrade; this defaults the fee-invoice status.",
             "operations": [
                 {"op": "set_default", "entity": "fee_invoice", "field": "status",
                  "value": "draft"}]},
            {"version": "2.3.0",
             "description": "Documents: the full School document ecosystem (admissions, student, "
                            "academic, fee, library, transport, hostel, staff) as DocumentTemplate "
                            "metadata rendered by the Core document engine + auto-generation via "
                            "action_generate_document. No schema change (templates are metadata).",
             "operations": [
                 {"op": "set_default", "entity": "student", "field": "status",
                  "value": "applicant"}]},
            {"version": "2.4.0",
             "description": "Portal experience: parent + student portals configured on the generic "
                            "Portal Engine via portal_grants (per-student single-hop + indirect "
                            "class scoping); new Assignment entity applies additively.",
             "operations": [
                 {"op": "set_default", "entity": "assignment", "field": "status",
                  "value": "draft"}]},
            {"version": "2.5.0",
             "description": "Student Services: attendance depth (leave/corrections), behaviour, "
                            "counselling, medical, special education, activities/welfare, career, "
                            "notes/alerts/risk, and safety (visitor/incident/safeguarding) — all "
                            "new entities apply additively; reuse workflow/approval/notification/"
                            "document/portal Core. No schema change to existing entities.",
             "operations": [
                 {"op": "set_default", "entity": "leave_request", "field": "status",
                  "value": "requested"}]},
            {"version": "2.6.0",
             "description": "Reporting, Analytics & Executive Intelligence: cross-module reports, "
                            "an Analytics KPI registry (academic/financial/operations/risk) via "
                            "the Analytics Engine, and an executive dashboard. Reports/KPIs/"
                            "dashboards are metadata — no schema change.",
             "operations": [
                 {"op": "set_default", "entity": "student", "field": "status",
                  "value": "applicant"}]},
            {"version": "2.7.0",
             "description": "Enterprise hardening: data-integrity validation rules (block_save on "
                            "non-positive financial amounts / negative marks, reusing the Rules "
                            "engine) + SLA response-time policies for safeguarding/counselling/"
                            "incidents (reusing the SLA engine). Rules/SLA are metadata — no "
                            "schema change.",
             "operations": [
                 {"op": "set_default", "entity": "safeguarding_record", "field": "status",
                  "value": "open"}]},
        ],
    }


# ── manifest assembly + seed ─────────────────────────────────────────────────
def build_school_manifest() -> dict:
    return {
        "schema_version": 1,
        "package": _package_block(),
        "entities": list(SCHOOL_OBJECTS.values()),
        "forms": [_form_for(s) for s in SCHOOL_OBJECTS],
        "views": [v for s in SCHOOL_OBJECTS for v in _views_for(s)],
        "workflows": SCHOOL_WORKFLOWS,
        "reports": SCHOOL_REPORTS,
        "rules": SCHOOL_RULES,
        "sla_policies": SCHOOL_SLA_POLICIES,
        "notification_templates": SCHOOL_NOTIFICATIONS,
        "document_templates": SCHOOL_DOCUMENTS,
        "portal_grants": SCHOOL_PORTAL_GRANTS,
        "kpis": SCHOOL_KPIS,
        "roles": SCHOOL_ROLES,
        "dashboards": SCHOOL_DASHBOARDS,
        "navigations": [{"ref": "main", "name": "School Menu", "scope": "app",
                         "tree": SCHOOL_NAV}],
        "home_layouts": [{"ref": "home", "name": "School Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "School Management"}]},
                         *SCHOOL_ROLE_HOMES],
        "applications": [{
            "slug": "school", "name": "School Management", "icon": "GraduationCap",
            "color": "#0d9488", "included_entity_slugs": _MAIN,
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in SCHOOL_ROLES], "is_published": True,
        }],
    }


def seed_school_template():
    """Upsert the published, system School SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="school",
        defaults={
            "name": "School Management",
            "category": "Education",
            "description": "Complete K-12 School Management solution — full student lifecycle "
                           "(inquiry → admission → enrollment → promotion/transfer → graduation "
                           "→ alumni), academics, attendance, examinations, fees (with real "
                           "accounting), library, transport and hostel. Reuses the ERP Core; "
                           "ships zero native code.",
            "icon": "GraduationCap", "color": "#0d9488", "publisher": "Sridhar ERP",
            "version": "2.7.0", "manifest": build_school_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
