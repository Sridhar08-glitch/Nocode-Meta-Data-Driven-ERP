"""
College Management Solution blueprint (College package — Phases C1 Academic Core + C2 Registration).

The SECOND education package. **Pure manifest: ships NO native code** — it reuses every ERP Core
engine exactly as School does (metadata/forms/views, workflow, RBAC, reporting, dashboards,
analytics KPI, notifications). College is the reuse VALIDATOR: it mirrors School's proven manifest
patterns for the shared academic spine and adds only the credit/program-centric capabilities that
higher-ed requires. It does NOT fork logic, duplicate engines, or extract Academic Base.

C1 scope = the academic core (per COLLEGE_ARCHITECTURE_ANALYSIS.md §9, the binding contract):
faculties/colleges + departments, programs/specializations, courses + sections + prerequisites,
curriculum, instructors, plus the inherited academic-structure spine (year/term/calendar/campus)
and a minimal student + program-enrollment anchor.

C2 scope = Course Registration — registration period, self-service registration, holds, waitlist,
and eligibility enforcement (section capacity + per-term credit limit + registration holds). C2 is
the FIRST manifest consumer of the certified Core Guard Framework (Platform Gap A,
`PLATFORM_GAP_guard_framework.md`): the ``registration_eligibility`` workflow uses the reusable
``action_guard`` step (query → aggregate → compare → threshold) to enforce cross-record constraints
declaratively — a section's live confirmed count vs its ``capacity`` (dynamic threshold), the
student's term credit sum vs the program's ``max_credits_per_term`` (dynamic threshold), and the
absence of an active registration hold. NO native code: College writes zero eligibility logic; it
only composes guard-rule config in the manifest. (Grades/GPA C3, faculty depth C4 follow later.)

Documented C2 limitation — **multi-hop prerequisite chains**: a single ``action_guard`` expresses a
single-hop query. A course with a *chain* of prerequisites (course → its prerequisites → the
student's completion of each) needs the deferred multi-hop guard extension (see the Guard Framework
roadmap). C2 therefore enforces the tractable, high-value constraints (capacity, credit limit,
holds) declaratively today and flags prerequisite-chain automation as a documented follow-up rather
than forking bespoke logic into the package.
"""
from __future__ import annotations


# ── field/entity helpers (same manifest DSL every solution package uses) ─────
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


# ── business objects (C1 academic core) ──────────────────────────────────────
COLLEGE_OBJECTS: dict[str, dict] = {
    # Academic-structure spine — INHERITED pattern from School (identical mechanics).
    "campus": _entity("campus", "Campus", "Campuses", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("address", "Address", "textarea"),
        _f("is_main", "Main Campus", "boolean"),
    ]),
    "academic_year": _entity("academic_year", "Academic Year", "Academic Years", [
        _f("name", "Name", "text", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("is_current", "Current", "boolean"),
        _status("planning", "active", "closed"),
    ]),
    "term": _entity("term", "Term", "Terms", [
        _f("name", "Name", "text", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _select("term_type", "Term Type", "semester", "trimester", "quarter"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("sequence", "Sequence", "integer"),
        _status("planning", "active", "closed"),
    ]),
    "academic_calendar_event": _entity(
        "academic_calendar_event", "Calendar Event", "Calendar Events", [
            _f("title", "Title", "text", is_required=True),
            _lookup("academic_year", "Academic Year", "academic_year"),
            _select("event_type", "Event Type", "holiday", "exam", "registration",
                    "orientation", "break", "meeting"),
            _f("start_date", "Start Date", "date"),
            _f("end_date", "End Date", "date"),
            _f("description", "Description", "textarea"),
        ]),

    # Organisation — NEW for College (School had only campus + teacher).
    "faculty": _entity("faculty", "Faculty / College", "Faculties", [
        _f("name", "Name", "text", is_required=True),   # e.g. Faculty of Engineering
        _f("code", "Code", "text", is_unique=True),
        _f("dean", "Dean", "user"),
        _lookup("campus", "Campus", "campus"),
        _f("description", "Description", "textarea"),
    ]),
    "department": _entity("department", "Department", "Departments", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _lookup("faculty", "Faculty", "faculty"),
        _f("head", "Head of Department", "user"),
    ]),

    # Programs / degrees / specializations — NEW, College-defining.
    "program": _entity("program", "Program", "Programs", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("degree_type", "Degree Type", "certificate", "diploma", "bachelor",
                "master", "doctorate"),
        _lookup("department", "Department", "department"),
        _f("duration_years", "Duration (Years)", "decimal"),
        _f("total_credits_required", "Total Credits Required", "integer"),
        # C2: per-term credit ceiling — the DYNAMIC threshold the credit-limit guard reads.
        _f("max_credits_per_term", "Max Credits / Term", "integer"),
        _status("draft", "active", "archived"),
    ]),
    "specialization": _entity("specialization", "Specialization", "Specializations", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("spec_type", "Type", "major", "minor", "concentration"),
        _lookup("program", "Program", "program"),
        _f("required_credits", "Required Credits", "integer"),
    ]),

    # Courses / sections / prerequisites — EXTENDED (course from School subject) + NEW (sections).
    "course": _entity("course", "Course", "Courses", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _lookup("department", "Department", "department"),
        _f("credit_hours", "Credit Hours", "integer"),
        _select("level", "Level", "undergraduate", "graduate", "postgraduate"),
        _f("description", "Description", "textarea"),
        _status("active", "inactive"),
    ]),
    "prerequisite": _entity("prerequisite", "Prerequisite", "Prerequisites", [
        _lookup("course", "Course", "course"),
        _lookup("prerequisite_course", "Prerequisite Course", "course"),
        _select("requirement_type", "Type", "required", "recommended", "corequisite"),
        _f("min_grade", "Minimum Grade", "text"),
    ]),
    "instructor": _entity("instructor", "Instructor", "Instructors", [
        _f("employee_no", "Employee No", "text", is_unique=True),
        _f("name", "Name", "text", is_required=True),
        _f("email", "Email", "email"),
        _lookup("department", "Department", "department"),
        _select("rank", "Rank", "lecturer", "assistant_professor", "associate_professor",
                "professor"),
        _status("active", "on_leave", "left"),
    ]),
    "course_section": _entity("course_section", "Course Section", "Course Sections", [
        _auto("section_code", "Section Code", "SEC-"),
        _lookup("course", "Course", "course"),
        _lookup("term", "Term", "term"),
        _lookup("instructor", "Instructor", "instructor"),
        _f("capacity", "Capacity", "integer"),
        _f("enrolled_count", "Enrolled", "integer"),
        _f("room", "Room", "text"),
        _f("schedule", "Schedule", "text"),
        _status("open", "closed", "cancelled"),
    ]),

    # Curriculum (program → courses) — EXTENDED from School curriculum.
    "curriculum": _entity("curriculum", "Curriculum", "Curricula", [
        _f("name", "Name", "text", is_required=True),
        _lookup("program", "Program", "program"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("description", "Description", "textarea"),
        _status("draft", "active", "archived"),
    ]),
    "curriculum_course": _entity("curriculum_course", "Curriculum Course", "Curriculum Courses", [
        _lookup("curriculum", "Curriculum", "curriculum"),
        _lookup("course", "Course", "course"),
        _select("requirement", "Requirement", "required", "elective"),
        _f("semester_sequence", "Semester", "integer"),
    ]),

    # Student anchor + program enrollment — EXTENDED (student) / NEW (program enrollment).
    "student": _entity("student", "Student", "Students", [
        _auto("student_no", "Student No", "STU-"),
        _f("first_name", "First Name", "text", is_required=True),
        _f("last_name", "Last Name", "text"),
        _f("dob", "Date of Birth", "date"),
        _select("gender", "Gender", "female", "male", "other"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("nationality", "Nationality", "text"),
        _lookup("program", "Program", "program"),
        _f("admission_year", "Admission Year", "text"),
        _status("applicant", "enrolled", "graduated", "withdrawn", "suspended"),
    ]),
    "program_enrollment": _entity("program_enrollment", "Program Enrollment", "Program Enrollments", [
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("enrollment_date", "Enrollment Date", "date"),
        _f("expected_graduation", "Expected Graduation", "date"),
        _status("active", "completed", "withdrawn"),
    ]),

    # ── C2: Course Registration ───────────────────────────────────────────────
    # Registration window — a guard checks an OPEN period exists for the term (exists guard).
    "registration_period": _entity(
        "registration_period", "Registration Period", "Registration Periods", [
            _f("name", "Name", "text", is_required=True),
            _lookup("term", "Term", "term"),
            _f("start_date", "Start Date", "date"),
            _f("end_date", "End Date", "date"),
            _status("planning", "open", "closed"),
        ]),
    # Registration holds — an active hold BLOCKS registration (not_exists guard).
    "registration_hold": _entity("registration_hold", "Registration Hold", "Registration Holds", [
        _lookup("student", "Student", "student"),
        _select("hold_type", "Hold Type", "financial", "advising", "academic", "disciplinary"),
        _f("reason", "Reason", "textarea"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),
    # The registration record — the guard TRIGGER. Created ``confirmed``; the eligibility guard
    # re-measures the live cross-record state (self included) and the false branch reverts it to
    # ``waitlisted`` when a constraint is breached. credit_hours/program/term are denormalised so a
    # single-entity guard query can sum credits and read the program's per-term ceiling.
    "registration": _entity("registration", "Registration", "Registrations", [
        _auto("registration_no", "Registration No", "REG-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _lookup("term", "Term", "term"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("registered_date", "Registered Date", "date"),
        _status("confirmed", "waitlisted", "dropped", "completed"),
    ]),
    # Waitlist queue for a full section (ordered by position).
    "waitlist_entry": _entity("waitlist_entry", "Waitlist Entry", "Waitlist Entries", [
        _lookup("student", "Student", "student"),
        _lookup("course_section", "Course Section", "course_section"),
        _f("position", "Position", "integer"),
        _f("requested_date", "Requested Date", "date"),
        _status("waiting", "promoted", "expired"),
    ]),

    # ══ C3: Assessment, Grades, GPA, Standing, Degree Progress, Transcript ═══════
    # Grade scheme + scale — the grading policy. ``grade_scale`` maps a letter to grade_points; the
    # grade-points-lookup workflow reads it via ``action_aggregate`` (no native mapping code).
    "grade_scheme": _entity("grade_scheme", "Grade Scheme", "Grade Schemes", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("description", "Description", "textarea"),
        _f("min_pass_gpa", "Minimum Pass GPA", "decimal"),
        _f("is_default", "Default Scheme", "boolean"),
        _status("draft", "active", "archived"),
    ]),
    "grade_scale": _entity("grade_scale", "Grade Scale", "Grade Scales", [
        _lookup("grade_scheme", "Grade Scheme", "grade_scheme"),
        _f("letter", "Letter Grade", "text", is_required=True),   # A, A-, B+, …
        _f("grade_points", "Grade Points", "decimal"),            # 4.0, 3.7, …
        _f("min_percent", "Min %", "decimal"),
        _f("max_percent", "Max %", "decimal"),
        _f("is_passing", "Passing", "boolean"),
    ]),

    # Grade book — assessments per section + per-student results (continuous assessment).
    "assessment": _entity("assessment", "Assessment", "Assessments", [
        _f("name", "Name", "text", is_required=True),
        _lookup("course_section", "Course Section", "course_section"),
        _select("assessment_type", "Type", "quiz", "assignment", "midterm", "final",
                "project", "participation", "lab"),
        _f("weight", "Weight (%)", "decimal"),
        _f("max_score", "Max Score", "decimal"),
        _f("due_date", "Due Date", "date"),
        _status("draft", "published", "graded", "closed"),
    ]),
    "assessment_result": _entity("assessment_result", "Assessment Result", "Assessment Results", [
        _lookup("student", "Student", "student"),
        _lookup("assessment", "Assessment", "assessment"),
        _lookup("course_section", "Course Section", "course_section"),
        _f("score", "Score", "decimal"),
        _f("weight", "Weight (%)", "decimal"),     # denormalised so a single-entity agg can weight
        # NON-PROMOTED formula (JSONB-safe on PG; NQL casts custom_data ::numeric so it is
        # SQL-summable) — the per-child weight the course-score aggregate sums (CG-2 usage note).
        _f("weighted_score", "Weighted Score", "formula", is_promoted=False,
           config={"expression": "score * weight"}),
        _status("draft", "published"),
    ]),

    # Course result — the graded course outcome + the credit-weighted quality-points building block.
    "course_result": _entity("course_result", "Course Result", "Course Results", [
        _auto("result_no", "Result No", "CR-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("term", "Term", "term"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _f("credit_hours", "Credit Hours", "integer"),   # denormalised from the course
        _f("score", "Score (%)", "decimal"),
        _f("letter_grade", "Letter Grade", "text"),
        _f("grade_points", "Grade Points", "decimal"),
        # NON-PROMOTED formula = the CANONICAL credit-weighted quality points (CG-2 §11). Σ of this
        # over a term / all terms, divided by Σ credit_hours, IS the GPA/CGPA — computed declaratively
        # by ``action_aggregate``, never by College code.
        _f("quality_points", "Quality Points", "formula", is_promoted=False,
           config={"expression": "grade_points * credit_hours"}),
        _f("attempt", "Attempt", "integer"),
        # Repeat-course policy: a superseded earlier attempt is set ``superseded`` so only the latest
        # ``published`` attempt is summed into GPA (status-based, no boolean-in-NQL needed).
        _status("draft", "submitted", "approved", "published", "superseded"),
    ]),

    # Semester result — the per-student-per-term GPA record (target of the term-GPA aggregate).
    "semester_result": _entity("semester_result", "Semester Result", "Semester Results", [
        _auto("semester_result_no", "Semester Result No", "SR-"),
        _lookup("student", "Student", "student"),
        _lookup("term", "Term", "term"),
        _lookup("program", "Program", "program"),
        _f("term_credits", "Term Credits", "decimal"),
        _f("term_quality_points", "Term Quality Points", "decimal"),
        _f("term_gpa", "Term GPA", "decimal"),
        _status("draft", "finalized", "published"),
    ]),

    # Student academic record — the CUMULATIVE per-student record (target of the CGPA aggregate +
    # standing). A NEW C3 entity (the frozen C1 ``student`` master is never modified).
    "student_academic_record": _entity(
        "student_academic_record", "Student Academic Record", "Student Academic Records", [
            _auto("academic_record_no", "Academic Record No", "SAR-"),
            _lookup("student", "Student", "student"),
            _lookup("program", "Program", "program"),
            _f("cgpa", "CGPA", "decimal"),
            _f("credits_earned", "Credits Earned", "decimal"),
            _f("credits_attempted", "Credits Attempted", "decimal"),
            _select("academic_standing", "Academic Standing", "new", "good_standing",
                    "deans_list", "probation", "suspension", "dismissed"),
            _select("honours", "Honours", "none", "cum_laude", "magna_cum_laude", "summa_cum_laude"),
            _f("as_of_date", "As Of", "date"),
            _status("active", "archived"),
        ]),

    # Degree progress — credits completed vs the program requirement (degree audit).
    "degree_progress": _entity("degree_progress", "Degree Progress", "Degree Progress", [
        _auto("progress_no", "Progress No", "DP-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _f("credits_completed", "Credits Completed", "decimal"),
        _f("credits_required", "Credits Required", "decimal"),
        _f("progress_percent", "Progress %", "decimal"),
        _f("as_of_date", "As Of", "date"),
        _status("in_progress", "completed"),
    ]),

    # Transfer credits — external credits recognised toward the program (metadata; credit-only).
    "transfer_credit": _entity("transfer_credit", "Transfer Credit", "Transfer Credits", [
        _lookup("student", "Student", "student"),
        _lookup("course", "Equivalent Course", "course"),
        _f("external_course", "External Course", "text"),
        _f("source_institution", "Source Institution", "text"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("grade", "Grade", "text"),
        _status("pending", "approved", "rejected"),
    ]),

    # Graduation application — metadata lifecycle only (no eligibility engine per the C3 mandate).
    "graduation_application": _entity(
        "graduation_application", "Graduation Application", "Graduation Applications", [
            _auto("application_no", "Application No", "GRAD-"),
            _lookup("student", "Student", "student"),
            _lookup("program", "Program", "program"),
            _f("expected_grad_date", "Expected Graduation", "date"),
            _status("applied", "under_review", "approved", "conferred", "denied"),
        ]),

    # ══ C4: Faculty & Academic Advising ═════════════════════════════════════════
    # Faculty PROFILE / rank / employment-status = the FROZEN C1 ``instructor`` (reused, NEVER
    # modified; instructors ↔ HR employees via the optional HR package). C4 adds only the academic
    # overlay — teaching assignments, workload, advising, holds, overrides — as NEW entities that
    # LOOK UP the frozen instructor/student/course_section/term. No duplicate employee management.
    "teaching_assignment": _entity(
        "teaching_assignment", "Teaching Assignment", "Teaching Assignments", [
            _lookup("instructor", "Instructor", "instructor"),
            _lookup("course_section", "Course Section", "course_section"),
            _lookup("term", "Term", "term"),
            _select("role", "Role", "primary", "co_instructor", "teaching_assistant", "grader"),
            _f("load_hours", "Load Hours", "decimal"),
            _status("planned", "active", "completed", "cancelled"),
        ]),
    "office_hour": _entity("office_hour", "Office Hour", "Office Hours", [
        _lookup("instructor", "Instructor", "instructor"),
        _lookup("term", "Term", "term"),
        _select("day_of_week", "Day", "monday", "tuesday", "wednesday", "thursday", "friday",
                "saturday", "sunday"),
        _f("start_time", "Start Time", "time"),
        _f("end_time", "End Time", "time"),
        _f("location", "Location", "text"),
    ]),
    # Teaching load = Σ(teaching_assignment.load_hours) per instructor+term — a CG-2 aggregate target.
    "faculty_workload": _entity("faculty_workload", "Faculty Workload", "Faculty Workloads", [
        _lookup("instructor", "Instructor", "instructor"),
        _lookup("term", "Term", "term"),
        _f("total_load_hours", "Total Load Hours", "decimal"),
        _f("section_count", "Sections", "integer"),
        _f("as_of_date", "As Of", "date"),
        _status("draft", "published"),
    ]),
    "advisor_assignment": _entity("advisor_assignment", "Advisor Assignment", "Advisor Assignments", [
        _auto("assignment_no", "Assignment No", "ADVA-"),
        _lookup("advisor", "Advisor", "instructor"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _f("assigned_date", "Assigned Date", "date"),
        _status("active", "ended"),
    ]),
    # Advisor caseload = count(active advisor_assignment) per advisor — a CG-2 aggregate target.
    "advisor_caseload": _entity("advisor_caseload", "Advisor Caseload", "Advisor Caseloads", [
        _lookup("advisor", "Advisor", "instructor"),
        _f("active_advisees", "Active Advisees", "integer"),
        _f("as_of_date", "As Of", "date"),
        _status("active", "archived"),
    ]),
    "advising_session": _entity("advising_session", "Advising Session", "Advising Sessions", [
        _auto("session_no", "Session No", "ADV-"),
        _lookup("student", "Student", "student"),
        _lookup("advisor", "Advisor", "instructor"),
        _f("session_date", "Session Date", "date"),
        _select("mode", "Mode", "in_person", "virtual", "phone"),
        _f("topic", "Topic", "text"),
        _f("summary", "Summary", "textarea"),
        _status("scheduled", "completed", "cancelled", "no_show"),
    ]),
    "advising_note": _entity("advising_note", "Advising Note", "Advising Notes", [
        _lookup("student", "Student", "student"),
        _lookup("advisor", "Advisor", "instructor"),
        _lookup("advising_session", "Session", "advising_session"),
        _select("category", "Category", "academic", "career", "personal", "administrative"),
        _f("note", "Note", "textarea"),
        _f("is_private", "Private", "boolean"),
    ]),
    # Academic / advising holds (broader than the C2 registration_hold; not a duplicate of it).
    "academic_hold": _entity("academic_hold", "Academic Hold", "Academic Holds", [
        _auto("hold_no", "Hold No", "HOLD-"),
        _lookup("student", "Student", "student"),
        _select("hold_type", "Hold Type", "advising", "academic", "disciplinary", "health", "other"),
        _f("reason", "Reason", "textarea"),
        _f("placed_by", "Placed By", "user"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),
    # Override requests (prereq / capacity / credit-overload waivers) — approved via the Core
    # Approvals engine (``override_approval`` process).
    "override_request": _entity("override_request", "Override Request", "Override Requests", [
        _auto("request_no", "Request No", "OVR-"),
        _lookup("student", "Student", "student"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _select("request_type", "Type", "prerequisite", "capacity", "credit_overload",
                "time_conflict", "other"),
        _f("reason", "Reason", "textarea"),
        _status("pending", "approved", "denied"),
    ]),

    # ══ C5: Finance & Financial Aid ═════════════════════════════════════════════
    # ALL money movement reuses the Core financial platform (GL / Credits / Collections / Documents)
    # via workflow steps — College defines METADATA ONLY, mirroring the certified School fee pattern.
    # NO accounting/collections/credit calculation lives in this package. ──────────────────────────
    # ── Academic finance (tuition definitions) ──
    "tuition_category": _entity("tuition_category", "Tuition Category", "Tuition Categories", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("fee_type", "Fee Type", "tuition", "registration", "laboratory", "library",
                "technology", "activity", "exam", "other"),
        _select("frequency", "Frequency", "per_term", "per_year", "per_credit_hour", "one_time"),
        _f("description", "Description", "textarea"),
    ]),
    # Tuition by program / semester / credit-hour = the basis + program/term/rate fields (metadata).
    "tuition_structure": _entity("tuition_structure", "Tuition Structure", "Tuition Structures", [
        _f("name", "Name", "text", is_required=True),
        _lookup("program", "Program", "program"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _lookup("tuition_category", "Category", "tuition_category"),
        _select("basis", "Basis", "flat", "per_credit_hour", "per_semester"),
        _f("amount", "Flat Amount", "currency"),
        _f("rate_per_credit", "Rate / Credit Hour", "currency"),
        _status("draft", "active", "archived"),
    ]),
    # The tuition charge (invoice) — posts Dr A/R, Cr Revenue via action_post_journal (GL).
    "tuition_charge": _entity("tuition_charge", "Tuition Charge", "Tuition Charges", [
        _auto("charge_no", "Charge No", "TUI-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("term", "Term", "term"),
        _lookup("tuition_structure", "Tuition Structure", "tuition_structure"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("amount", "Amount", "currency", is_required=True),   # billable amount that posts to GL
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _status("draft", "issued", "paid", "partial", "overdue", "cancelled"),
    ]),
    # Tuition adjustment → posts a credit (Dr contra / Cr A/R) via action_apply_credit (Credits).
    "tuition_adjustment": _entity("tuition_adjustment", "Tuition Adjustment", "Tuition Adjustments", [
        _auto("adjustment_no", "Adjustment No", "TADJ-"),
        _lookup("student", "Student", "student"),
        _lookup("tuition_charge", "Tuition Charge", "tuition_charge"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "applied", "rejected"),
    ]),

    # ── Student finance (account + receipts; balance/statements are GL/report/document derived) ──
    "student_account": _entity("student_account", "Student Account", "Student Accounts", [
        _auto("account_no", "Account No", "ACCT-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _status("active", "closed"),
    ]),
    "student_payment": _entity("student_payment", "Student Payment", "Student Payments", [
        _auto("receipt_no", "Receipt No", "SRCPT-"),
        _lookup("student", "Student", "student"),
        _lookup("tuition_charge", "Tuition Charge", "tuition_charge"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("payment_date", "Payment Date", "date"),
        _select("method", "Method", "cash", "bank", "card", "online", "cheque", "sponsor"),
        _f("reference", "Reference", "text"),
    ]),

    # ── Financial aid (grants/bursaries/scholarships/work-study; awards → Credits) ──
    "aid_program": _entity("aid_program", "Financial Aid Program", "Financial Aid Programs", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("aid_type", "Aid Type", "grant", "bursary", "scholarship", "work_study",
                "sponsorship", "loan"),
        _f("funding_source", "Funding Source", "text"),
        _f("description", "Description", "textarea"),
        _status("draft", "active", "closed"),
    ]),
    "aid_award": _entity("aid_award", "Aid Award", "Aid Awards", [
        _auto("award_no", "Award No", "AID-"),
        _lookup("student", "Student", "student"),
        _lookup("aid_program", "Aid Program", "aid_program"),
        _select("aid_type", "Aid Type", "grant", "bursary", "scholarship", "work_study"),
        _f("amount", "Amount", "currency", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "awarded", "rejected"),
    ]),
    "aid_renewal": _entity("aid_renewal", "Aid Renewal", "Aid Renewals", [
        _auto("renewal_no", "Renewal No", "AIDR-"),
        _lookup("aid_award", "Aid Award", "aid_award"),
        _lookup("student", "Student", "student"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("amount", "Amount", "currency", is_required=True),
        _status("requested", "approved", "renewed", "denied"),
    ]),
    # Third-party sponsorship (a sponsor pays on the student's behalf → Credits).
    "sponsorship": _entity("sponsorship", "Sponsorship", "Sponsorships", [
        _auto("sponsorship_no", "Sponsorship No", "SPON-"),
        _lookup("student", "Student", "student"),
        _f("sponsor_name", "Sponsor", "text", is_required=True),
        _f("amount", "Amount", "currency", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("agreement_ref", "Agreement Ref", "text"),
        _status("requested", "approved", "active", "ended", "rejected"),
    ]),
    # Student loan — disbursement posts to GL; repayment schedule via the Collections Engine.
    "student_loan": _entity("student_loan", "Student Loan", "Student Loans", [
        _auto("loan_no", "Loan No", "LOAN-"),
        _lookup("student", "Student", "student"),
        _lookup("aid_program", "Aid Program", "aid_program"),
        _f("principal_amount", "Principal", "currency", is_required=True),
        _f("interest_rate", "Interest Rate (%)", "decimal"),
        _f("term_months", "Term (Months)", "integer"),
        _f("num_installments", "Installments", "integer"),
        _select("frequency", "Frequency", "monthly", "quarterly", "yearly"),
        _f("start_date", "Repayment Start", "date"),
        _f("disbursement_date", "Disbursement Date", "date"),
        _status("applied", "approved", "disbursed", "repaying", "closed", "rejected"),
    ]),

    # ── Payment (plans / agreements → Collections) ──
    "payment_plan": _entity("payment_plan", "Payment Plan", "Payment Plans", [
        _auto("plan_ref", "Plan Ref", "PPLAN-"),
        _lookup("student", "Student", "student"),
        _lookup("tuition_charge", "Tuition Charge", "tuition_charge"),
        _f("total_amount", "Total Amount", "currency", is_required=True),
        _f("num_installments", "Installments", "integer", is_required=True),
        _select("frequency", "Frequency", "monthly", "quarterly", "yearly"),
        _f("start_date", "Start Date", "date"),
        _f("grace_days", "Grace Days", "integer"),
        _select("late_fee_type", "Late Fee Type", "none", "flat", "percent"),
        _f("late_fee_value", "Late Fee Value", "currency"),
        _status("draft", "approved", "active", "cancelled"),
    ]),
    "payment_agreement": _entity("payment_agreement", "Payment Agreement", "Payment Agreements", [
        _auto("agreement_no", "Agreement No", "PAGR-"),
        _lookup("student", "Student", "student"),
        _lookup("payment_plan", "Payment Plan", "payment_plan"),
        _f("terms", "Terms", "textarea"),
        _f("signed_date", "Signed Date", "date"),
        _status("draft", "active", "breached", "completed"),
    ]),

    # ── Finance holds (block registration by REUSING the frozen C2 registration_hold + guard) ──
    "financial_hold": _entity("financial_hold", "Financial Hold", "Financial Holds", [
        _auto("hold_no", "Hold No", "FHOLD-"),
        _lookup("student", "Student", "student"),
        _f("reason", "Reason", "textarea"),
        _f("amount_outstanding", "Amount Outstanding", "currency"),
        _f("blocks_registration", "Blocks Registration", "boolean"),
        _f("blocks_graduation", "Blocks Graduation", "boolean"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),

    # ══ C6: Campus Operations ═══════════════════════════════════════════════════
    # REUSES the FROZEN School campus-ops architecture verbatim (same entity/workflow/report/portal/
    # document/notification shapes), adapted ONLY in vocabulary for higher-ed (Residence↔Hostel, Campus
    # Health Center↔Clinic, Welfare Case↔Safeguarding). Charge-bearing services (library fines,
    # residence/meal/transport fees) reuse the C5 financial platform via one ``campus_charge`` +
    # ``action_post_journal`` — ZERO package accounting. ──────────────────────────────────────────
    # Charge-bearing campus services → post Dr A/R 1100, Cr Revenue 4100 via GL (reuse C5 platform).
    "campus_charge": _entity("campus_charge", "Campus Charge", "Campus Charges", [
        _auto("charge_no", "Charge No", "CMP-"),
        _lookup("student", "Student", "student"),
        _select("service_type", "Service", "library_fine", "residence_fee", "meal_plan",
                "transport", "id_card", "other"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("charge_date", "Charge Date", "date"),
        _f("due_date", "Due Date", "date"),
        _status("draft", "issued", "paid", "cancelled"),
    ]),

    # Library.
    "library_book": _entity("library_book", "Library Book", "Library Books", [
        _f("title", "Title", "text", is_required=True),
        _f("author", "Author", "text"),
        _f("isbn", "ISBN", "text"),
        _f("category", "Category", "text"),
        _f("total_copies", "Total Copies", "integer"),
        _f("available_copies", "Available Copies", "integer"),
    ]),
    "book_loan": _entity("book_loan", "Book Loan", "Book Loans", [
        _auto("loan_ref", "Loan Ref", "LN-"),
        _lookup("library_book", "Book", "library_book"),
        _lookup("student", "Student", "student"),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("return_date", "Return Date", "date"),
        _status("issued", "returned", "overdue", "lost"),
    ]),

    # Residence (higher-ed vocabulary for Hostel).
    "residence_room": _entity("residence_room", "Residence Room", "Residence Rooms", [
        _f("residence_hall", "Residence Hall", "text", is_required=True),
        _f("room_no", "Room No", "text"),
        _f("capacity", "Capacity", "integer"),
        _f("occupied", "Occupied", "integer"),
        _f("resident_advisor", "Resident Advisor", "user"),
    ]),
    "room_allocation": _entity("room_allocation", "Room Allocation", "Room Allocations", [
        _auto("allocation_no", "Allocation No", "RES-"),
        _lookup("student", "Student", "student"),
        _lookup("residence_room", "Room", "residence_room"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("active", "ended"),
    ]),

    # Transport.
    "transport_route": _entity("transport_route", "Transport Route", "Transport Routes", [
        _f("name", "Name", "text", is_required=True),
        _f("vehicle_no", "Vehicle No", "text"),
        _f("driver_name", "Driver Name", "text"),
        _f("capacity", "Capacity", "integer"),
        _f("fee", "Fee", "currency"),
    ]),
    "transport_subscription": _entity(
        "transport_subscription", "Transport Subscription", "Transport Subscriptions", [
            _lookup("student", "Student", "student"),
            _lookup("transport_route", "Route", "transport_route"),
            _f("start_date", "Start Date", "date"),
            _status("active", "suspended", "ended"),
        ]),

    # Campus Health Center (higher-ed vocabulary for the School Clinic).
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
    ]),
    "medication": _entity("medication", "Medication", "Medications", [
        _lookup("student", "Student", "student"),
        _f("medication_name", "Medication", "text", is_required=True),
        _f("dosage", "Dosage", "text"),
        _f("frequency", "Frequency", "text"),
        _f("prescriber", "Prescriber", "text"),
    ]),
    "vaccination_record": _entity(
        "vaccination_record", "Vaccination Record", "Vaccination Records", [
            _lookup("student", "Student", "student"),
            _f("vaccine_name", "Vaccine", "text", is_required=True),
            _f("dose", "Dose", "text"),
            _f("administered_date", "Administered", "date"),
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
        _status("waiting", "in_progress", "completed"),
    ]),
    "medical_alert": _entity("medical_alert", "Medical Alert", "Medical Alerts", [
        _lookup("student", "Student", "student"),
        _f("alert_type", "Alert Type", "text"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _f("description", "Description", "textarea"),
        _f("is_active", "Active", "boolean"),
    ]),
    "health_screening": _entity("health_screening", "Health Screening", "Health Screenings", [
        _lookup("student", "Student", "student"),
        _select("screening_type", "Type", "vision", "dental", "hearing", "bmi", "general"),
        _f("screening_date", "Date", "date"),
        _f("result", "Result", "text"),
        _f("follow_up_required", "Follow-up Required", "boolean"),
    ]),

    # Counselling.
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
            _lookup("counselling_session", "Session", "counselling_session"),
            _f("goals", "Goals", "textarea"),
            _f("actions", "Actions", "textarea"),
            _f("review_date", "Review Date", "date"),
            _status("active", "completed"),
        ]),

    # Activities.
    "student_club": _entity("student_club", "Club", "Clubs", [
        _f("name", "Name", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("coordinator", "Coordinator", "user"),
        _f("description", "Description", "textarea"),
        _f("capacity", "Capacity", "integer"),
    ]),
    "club_membership": _entity("club_membership", "Club Membership", "Club Memberships", [
        _lookup("student", "Student", "student"),
        _lookup("student_club", "Club", "student_club"),
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
        _select("level", "Level", "campus", "regional", "national", "international"),
        _f("organizer", "Organizer", "text"),
    ]),
    "competition_entry": _entity(
        "competition_entry", "Competition Entry", "Competition Entries", [
            _lookup("student", "Student", "student"),
            _lookup("competition", "Competition", "competition"),
            _f("result", "Result", "text"),
            _f("rank", "Rank", "integer"),
            _status("registered", "participated", "withdrawn"),
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

    # Visitor management, gate pass, incident, welfare, lost & found, meals, ID cards.
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
    "gate_pass": _entity("gate_pass", "Gate Pass", "Gate Passes", [
        _auto("pass_no", "Pass No", "GP-"),
        _lookup("student", "Student", "student"),
        _select("pass_type", "Type", "check_in", "check_out", "gate_pass"),
        _f("pass_time", "Time", "datetime"),
        _f("reason", "Reason", "text"),
        _f("authorized_by", "Authorized By", "user"),
        _status("pending", "approved", "used"),
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
    "welfare_case": _entity("welfare_case", "Student Welfare Case", "Student Welfare Cases", [
        _auto("case_no", "Case No", "WEL-"),
        _lookup("student", "Student", "student"),
        _f("concern_type", "Concern Type", "text"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _f("reported_by", "Reported By", "user"),
        _f("report_date", "Report Date", "date"),
        _f("notes", "Notes", "textarea", config={"is_pii": True}),
        _status("open", "investigating", "referred", "closed"),
    ]),
    "lost_and_found": _entity("lost_and_found", "Lost & Found", "Lost & Found", [
        _f("item_name", "Item", "text", is_required=True),
        _f("category", "Category", "text"),
        _f("found_date", "Found Date", "date"),
        _f("location", "Location", "text"),
        _f("claimed_by", "Claimed By", "text"),
        _status("found", "claimed", "disposed"),
    ]),
    "meal_plan": _entity("meal_plan", "Meal Plan", "Meal Plans", [
        _lookup("student", "Student", "student"),
        _f("plan_type", "Plan Type", "text"),
        _f("start_date", "Start Date", "date"),
        _status("active", "suspended", "ended"),
    ]),
    "id_card_request": _entity("id_card_request", "ID Card Request", "ID Card Requests", [
        _auto("request_no", "Request No", "IDC-"),
        _lookup("student", "Student", "student"),
        _select("reason", "Reason", "new", "replacement", "renewal"),
        _f("request_date", "Request Date", "date"),
        _status("requested", "approved", "issued"),
    ]),

    # ══ C7: Research — OVERLAY on the frozen Projects platform (NEVER duplicates PM) ═════════════
    # The Projects package (P2.10) is the SINGLE OWNER of project/task/milestone/deliverable/
    # dependency/schedule/gantt/calendar/resource/timesheet/expense/budget/EVM/risk/issue/change/
    # quality. C7 adds ONLY scholarly metadata; every research object references a Projects
    # ``project`` (+ frozen ``instructor``/``student``/``faculty``) via lookup. Grant funding → C5
    # financial platform (GL); grant budget/expenses → the linked Projects project. ZERO PM here.
    "research_center": _entity("research_center", "Research Center", "Research Centers", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("director", "Director", "user"),
        _lookup("faculty", "Faculty", "faculty"),
        _f("focus_area", "Focus Area", "text"),
        _f("description", "Description", "textarea"),
        _status("active", "inactive"),
    ]),
    "research_group": _entity("research_group", "Research Group", "Research Groups", [
        _f("name", "Name", "text", is_required=True),
        _lookup("research_center", "Center", "research_center"),
        _f("lead", "Group Lead", "user"),
        _f("focus_area", "Focus Area", "text"),
        _status("active", "inactive"),
    ]),
    # The research-project OVERLAY — REFERENCES an existing Projects ``project`` (single PM source of
    # truth). Scholarly fields only; NO tasks/schedule/budget/milestones here (those live on the
    # Projects project).
    "research_project": _entity("research_project", "Research Project", "Research Projects", [
        _auto("research_no", "Research No", "RSP-"),
        _lookup("project", "Projects Project", "project"),   # ← the Projects package project
        _f("title", "Title", "text", is_required=True),
        _lookup("research_center", "Center", "research_center"),
        _lookup("research_group", "Group", "research_group"),
        _f("principal_investigator", "Principal Investigator", "user"),
        _select("research_type", "Type", "basic", "applied", "experimental", "clinical",
                "translational"),
        _status("proposed", "active", "completed", "suspended", "terminated"),
    ]),
    "research_team_member": _entity(
        "research_team_member", "Research Team Member", "Research Team Members", [
            _lookup("research_project", "Research Project", "research_project"),
            _f("member", "Member", "user"),
            _select("member_type", "Role", "principal_investigator", "co_principal_investigator",
                    "research_staff", "supervisor", "collaborator"),
            _f("allocation_percent", "Allocation %", "decimal"),
            _status("active", "inactive"),
        ]),
    "research_student": _entity("research_student", "Research Student", "Research Students", [
        _lookup("student", "Student", "student"),
        _lookup("research_project", "Research Project", "research_project"),
        _f("supervisor", "Supervisor", "user"),
        _select("degree_level", "Degree Level", "masters", "mphil", "phd", "postdoc"),
        _status("active", "graduated", "withdrawn"),
    ]),
    "funding_agency": _entity("funding_agency", "Funding Agency", "Funding Agencies", [
        _f("name", "Name", "text", is_required=True),
        _select("agency_type", "Type", "government", "foundation", "industry", "international",
                "internal"),
        _f("country", "Country", "text"),
        _f("contact_email", "Contact Email", "email"),
        _status("active", "inactive"),
    ]),
    "research_proposal": _entity("research_proposal", "Research Proposal", "Research Proposals", [
        _auto("proposal_no", "Proposal No", "PROP-"),
        _f("title", "Title", "text", is_required=True),
        _f("submitted_by", "Submitted By", "user"),
        _lookup("research_center", "Center", "research_center"),
        _lookup("funding_agency", "Funding Agency", "funding_agency"),
        _f("requested_funding", "Requested Funding", "currency"),
        _f("abstract", "Abstract", "textarea"),
        _status("draft", "submitted", "under_review", "approved", "rejected"),
    ]),
    "ethics_approval": _entity("ethics_approval", "Ethics / IRB Approval", "Ethics Approvals", [
        _auto("protocol_no", "Protocol No", "IRB-"),
        _lookup("research_project", "Research Project", "research_project"),
        _select("committee_type", "Committee", "irb", "iacuc", "ethics_board", "biosafety"),
        _f("submission_date", "Submission Date", "date"),
        _f("decision_date", "Decision Date", "date"),
        _f("expiry_date", "Expiry Date", "date"),
        _status("submitted", "under_review", "approved", "rejected", "expired"),
    ]),
    "grant": _entity("grant", "Grant", "Grants", [
        _auto("grant_no", "Grant No", "GRT-"),
        _f("title", "Title", "text", is_required=True),
        _lookup("funding_agency", "Funding Agency", "funding_agency"),
        _lookup("research_project", "Research Project", "research_project"),
        _f("award_amount", "Award Amount", "currency", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("applied", "awarded", "active", "closed", "rejected"),
    ]),
    "grant_application": _entity("grant_application", "Grant Application", "Grant Applications", [
        _auto("application_no", "Application No", "GAPP-"),
        _lookup("research_proposal", "Proposal", "research_proposal"),
        _lookup("funding_agency", "Funding Agency", "funding_agency"),
        _f("requested_amount", "Requested Amount", "currency"),
        _f("submission_date", "Submission Date", "date"),
        _status("draft", "submitted", "under_review", "awarded", "declined"),
    ]),
    "journal": _entity("journal", "Journal", "Journals", [
        _f("name", "Name", "text", is_required=True),
        _f("publisher", "Publisher", "text"),
        _f("issn", "ISSN", "text"),
        _f("impact_factor", "Impact Factor", "decimal"),
        _select("quartile", "Quartile", "q1", "q2", "q3", "q4"),
    ]),
    "conference": _entity("conference", "Conference", "Conferences", [
        _f("name", "Name", "text", is_required=True),
        _f("location", "Location", "text"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("ranking", "Ranking", "text"),
    ]),
    "publication": _entity("publication", "Publication", "Publications", [
        _auto("publication_no", "Publication No", "PUB-"),
        _f("title", "Title", "text", is_required=True),
        _select("publication_type", "Type", "journal_article", "conference_paper", "book",
                "book_chapter", "preprint", "technical_report"),
        _lookup("research_project", "Research Project", "research_project"),
        _lookup("journal", "Journal", "journal"),
        _lookup("conference", "Conference", "conference"),
        _f("authors", "Authors", "textarea"),
        _f("publication_date", "Publication Date", "date"),
        _f("doi", "DOI", "text"),
        _f("citation_count", "Citations", "integer"),
        _status("draft", "submitted", "under_review", "accepted", "published"),
    ]),
    "patent": _entity("patent", "Patent", "Patents", [
        _auto("patent_ref", "Patent Ref", "PAT-"),
        _f("title", "Title", "text", is_required=True),
        _lookup("research_project", "Research Project", "research_project"),
        _f("inventors", "Inventors", "textarea"),
        _f("application_number", "Application Number", "text"),
        _f("filing_date", "Filing Date", "date"),
        _f("grant_date", "Grant Date", "date"),
        _f("jurisdiction", "Jurisdiction", "text"),
        _status("disclosed", "filed", "pending", "granted", "rejected", "expired"),
    ]),
    "intellectual_property": _entity(
        "intellectual_property", "Intellectual Property", "Intellectual Property", [
            _auto("ip_no", "IP No", "IP-"),
            _f("title", "Title", "text", is_required=True),
            _select("ip_type", "Type", "patent", "copyright", "trademark", "trade_secret",
                    "software", "design"),
            _lookup("research_project", "Research Project", "research_project"),
            _f("owner", "Owner", "text"),
            _f("disclosure_date", "Disclosure Date", "date"),
            _status("disclosed", "protected", "licensed", "expired"),
        ]),
    "thesis": _entity("thesis", "Thesis / Dissertation", "Theses", [
        _auto("thesis_no", "Thesis No", "THS-"),
        _lookup("research_student", "Research Student", "research_student"),
        _f("supervisor", "Supervisor", "user"),
        _f("title", "Title", "text", is_required=True),
        _select("work_type", "Type", "masters_thesis", "mphil_thesis", "phd_dissertation"),
        _f("submission_date", "Submission Date", "date"),
        _f("defense_date", "Defense Date", "date"),
        _status("proposal", "in_progress", "submitted", "under_examination", "defended",
                "awarded", "rejected"),
    ]),
    "research_contract": _entity("research_contract", "Research Contract", "Research Contracts", [
        _auto("contract_no", "Contract No", "RCT-"),
        _f("title", "Title", "text", is_required=True),
        _lookup("research_project", "Research Project", "research_project"),
        _lookup("funding_agency", "Counterparty", "funding_agency"),
        _f("contract_value", "Contract Value", "currency"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("draft", "under_review", "signed", "active", "expired", "terminated"),
    ]),

    # ══ C8: Executive Analytics, Accreditation & Compliance ══════════════════════
    # C8 is presentation/config over the FROZEN Reporting/Analytics/Dashboard/Portal platforms
    # (executive dashboards, scorecards, KPIs, reports, portal enhancements) — no new engine. The
    # ONLY new data objects are accreditation + compliance (genuine institutional records).
    "accreditation_body": _entity("accreditation_body", "Accreditation Body", "Accreditation Bodies", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("body_type", "Type", "regional", "national", "programmatic", "international"),
        _f("country", "Country", "text"),
        _f("website", "Website", "url"),
    ]),
    "accreditation": _entity("accreditation", "Accreditation", "Accreditations", [
        _auto("accreditation_no", "Accreditation No", "ACR-"),
        _lookup("accreditation_body", "Body", "accreditation_body"),
        _lookup("program", "Program", "program"),
        _f("scope", "Scope", "text"),
        _f("award_date", "Award Date", "date"),
        _f("expiry_date", "Expiry Date", "date"),
        _f("cycle_years", "Cycle (Years)", "integer"),
        _status("applied", "self_study", "site_visit", "accredited", "probation", "denied",
                "expired"),
    ]),
    "compliance_requirement": _entity(
        "compliance_requirement", "Compliance Requirement", "Compliance Requirements", [
            _auto("requirement_no", "Requirement No", "CMP-"),
            _f("name", "Name", "text", is_required=True),
            _select("category", "Category", "federal", "state", "accreditor", "internal",
                    "safety", "financial", "data_privacy"),
            _f("description", "Description", "textarea"),
            _f("owner", "Owner", "user"),
            _f("due_date", "Due Date", "date"),
            _status("pending", "in_progress", "met", "overdue", "waived"),
        ]),
    "compliance_record": _entity("compliance_record", "Compliance Record", "Compliance Records", [
        _lookup("compliance_requirement", "Requirement", "compliance_requirement"),
        _f("period", "Period", "text"),
        _f("evidence", "Evidence", "textarea"),
        _f("submitted_by", "Submitted By", "user"),
        _f("review_date", "Review Date", "date"),
        _status("submitted", "reviewed", "accepted", "rejected"),
    ]),
}

_MAIN = list(COLLEGE_OBJECTS.keys())


# ── workflows (reuse the workflow engine) ─────────────────────────────────────
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created", trigger_config=None):
    return {"slug": slug, "name": name, "trigger_type": trigger_type,
            "trigger_config": trigger_config or {}, "entity_slug": entity_slug,
            "steps": steps, "edges": edges}


def _agg_measure(name, entity, aggregate, field=None, **eq):
    """Build one ``action_aggregate`` measure (single entity + equality filter). Values may be
    ``{{record.*}}`` templates — the Core ``action_aggregate`` executor resolves them against the
    trigger record (reusing ``resolve_value``) before calling the domain-agnostic AggregationService.
    ALL cross-record aggregation is the Core Aggregation Framework (CG-2); College writes zero
    calculation logic — it only composes measure/compute config in the manifest."""
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    m = {"name": name, "query": {"entity": entity, "filter": {"op": "and", "conditions": conds}},
         "aggregate": aggregate}
    if field:
        m["field"] = field
    return m


def _gq(entity, **eq):
    """Build an NQL AST query for a guard rule (single entity + equality conditions).

    Values may be ``{{record.*}}`` templates — the ``action_guard`` executor resolves them against
    the trigger record (reusing the Core ``resolve_value``) before calling the GuardService."""
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    return {"entity": entity, "filter": {"op": "and", "conditions": conds}}


# C2 eligibility guards (config only — ALL enforcement is the reusable Core Guard Framework).
# The registration is created ``confirmed``, so each guard measures the live cross-record state with
# the new record INCLUDED (hence ``lte``); the false branch reverts an ineligible record to
# ``waitlisted``. Capacity + credit-limit thresholds are DYNAMIC (read from course_section/program).
_REGISTRATION_GUARDS = [
    {"name": "capacity",
     "query": _gq("registration", course_section="{{record.course_section}}", status="confirmed"),
     "aggregate": "count", "operator": "lte",
     "threshold": {"query": _gq("course_section", id="{{record.course_section}}"),
                   "aggregate": "value", "field": "capacity"},
     "severity": "block", "message": "Section is full."},
    {"name": "credit_limit",
     "query": _gq("registration", student="{{record.student}}", term="{{record.term}}",
                  status="confirmed"),
     "aggregate": "sum", "field": "credit_hours", "operator": "lte",
     "threshold": {"query": _gq("program", id="{{record.program}}"),
                   "aggregate": "value", "field": "max_credits_per_term"},
     "severity": "block", "message": "Exceeds the program's per-term credit limit."},
    {"name": "no_active_hold",
     "query": _gq("registration_hold", student="{{record.student}}", status="active"),
     "operator": "not_exists",
     "severity": "block", "message": "Student has an active registration hold."},
]


COLLEGE_WORKFLOWS = [
    # Program enrollment created → mark the student enrolled (related-record target) + notify.
    _wf("program_enrollment_activated", "Program Enrollment Activated", "program_enrollment", [
        {"slug": "enroll", "step_type": "action_update_record", "name": "Mark Student Enrolled",
         "is_entry": True, "config": {"entity_slug": "student",
             "record_id": "{{record.student}}", "data": {"status": "enrolled"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "enrollment_confirmed"}},
    ], [{"source": "enroll", "target": "notify"}]),

    # Program activated → notify the department (lightweight lifecycle demo).
    _wf("program_activated", "Program Activated", "program", [
        {"slug": "check", "step_type": "condition", "name": "Active?", "is_entry": True,
         "config": {"condition_nql": 'status = "active"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "program_activated"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # C2 — Registration eligibility (FIRST consumer of the Core Guard Framework, Gap A).
    # Guard branches true → confirm+notify; false (capacity/credit/hold breached) → waitlist.
    _wf("registration_eligibility", "Registration Eligibility", "registration", [
        {"slug": "guard", "step_type": "action_guard", "name": "Check Eligibility",
         "is_entry": True, "config": {"guards": _REGISTRATION_GUARDS}},
        {"slug": "confirm_notify", "step_type": "action_send_notification",
         "name": "Notify Confirmed", "config": {"template_slug": "registration_confirmed"}},
        {"slug": "to_waitlist", "step_type": "action_update_record", "name": "Move to Waitlist",
         "config": {"entity_slug": "registration", "record_id": "{{record.id}}",
                    "data": {"status": "waitlisted"}}},
        {"slug": "waitlist_notify", "step_type": "action_send_notification",
         "name": "Notify Waitlisted", "config": {"template_slug": "registration_waitlisted"}},
    ], [
        {"source": "guard", "target": "confirm_notify", "condition_label": "true"},
        {"source": "guard", "target": "to_waitlist", "condition_label": "false"},
        {"source": "to_waitlist", "target": "waitlist_notify"},
    ]),

    # C2 — Drop notifies (a dropped registration frees its seat; the capacity guard re-measures live).
    _wf("registration_dropped", "Registration Dropped", "registration", [
        {"slug": "dropped", "step_type": "condition", "name": "Dropped?", "is_entry": True,
         "config": {"condition_nql": 'status = "dropped"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "registration_dropped"}},
    ], [{"source": "dropped", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # C2 — Hold cleared → notify the student they may register.
    _wf("registration_hold_cleared", "Registration Hold Cleared", "registration_hold", [
        {"slug": "cleared", "step_type": "condition", "name": "Cleared?", "is_entry": True,
         "config": {"condition_nql": 'status = "cleared"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "registration_hold_cleared"}},
    ], [{"source": "cleared", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ C3 — Grades / GPA / Standing (pure manifest consumers of the Core Aggregation Framework) ══
    # Grade book: derive a course_result's % score = Σ(score×weight)/Σ(weight) over the section's
    # published assessment results — the reusable weighted-average pattern (action_aggregate #1).
    _wf("compute_course_score", "Compute Course Score", "course_result", [
        {"slug": "score", "step_type": "action_aggregate", "name": "Aggregate Assessment Score",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("ws", "assessment_result", "sum", "weighted_score",
                             student="{{record.student}}",
                             course_section="{{record.course_section}}", status="published"),
                _agg_measure("tw", "assessment_result", "sum", "weight",
                             student="{{record.student}}",
                             course_section="{{record.course_section}}", status="published"),
            ],
            "computes": [{"name": "pct", "expression": "ws / tw if tw > 0 else 0"}],
            "target": {"entity_slug": "course_result", "record_id": "{{record.id}}",
                       "data": {"score": "{{agg.pct}}"}}}},
    ], []),

    # Grade entry: resolve grade_points for the entered letter grade from the grade_scale
    # (action_aggregate #2, a single-row value lookup). Fires when letter_grade is set (field_changed
    # watches ONLY letter_grade, so writing grade_points can never re-trigger it). quality_points
    # (grade_points × credit_hours) then recomputes automatically as a formula field.
    _wf("grade_points_lookup", "Grade Points Lookup", "course_result", [
        {"slug": "has_letter", "step_type": "condition", "name": "Letter Grade Set?",
         "is_entry": True, "config": {"condition_nql": "letter_grade is not null"}},
        {"slug": "lookup", "step_type": "action_aggregate", "name": "Resolve Grade Points",
         "config": {
            "measures": [_agg_measure("gp", "grade_scale", "max", "grade_points",
                                      letter="{{record.letter_grade}}")],
            "target": {"entity_slug": "course_result", "record_id": "{{record.id}}",
                       "data": {"grade_points": "{{agg.gp}}"}}}},
    ], [{"source": "has_letter", "target": "lookup", "condition_label": "true"}],
        trigger_type="field_changed", trigger_config={"fields": ["letter_grade"]}),

    # Grade lifecycle notifications (submitted → approver; approved → instructor; published → student).
    _wf("grade_submitted", "Grade Submitted", "course_result", [
        {"slug": "c", "step_type": "condition", "name": "Submitted?", "is_entry": True,
         "config": {"condition_nql": 'status = "submitted"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Approver",
         "config": {"template_slug": "grade_submitted"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("grade_published", "Grade Published", "course_result", [
        {"slug": "c", "step_type": "condition", "name": "Published?", "is_entry": True,
         "config": {"condition_nql": 'status = "published"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "grade_published"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Term GPA = Σ(quality_points)/Σ(credit_hours) over the student's PUBLISHED results for the term,
    # persisted to the semester_result (action_aggregate #3 — the canonical credit-weighted GPA).
    _wf("compute_term_gpa", "Compute Term GPA", "semester_result", [
        {"slug": "gpa", "step_type": "action_aggregate", "name": "Aggregate Term GPA",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("qp", "course_result", "sum", "quality_points",
                             student="{{record.student}}", term="{{record.term}}",
                             status="published"),
                _agg_measure("cr", "course_result", "sum", "credit_hours",
                             student="{{record.student}}", term="{{record.term}}",
                             status="published"),
            ],
            "computes": [{"name": "term_gpa", "expression": "qp / cr if cr > 0 else 0"}],
            "target": {"entity_slug": "semester_result", "record_id": "{{record.id}}",
                       "data": {"term_gpa": "{{agg.term_gpa}}", "term_credits": "{{agg.cr}}",
                                "term_quality_points": "{{agg.qp}}"}}}},
    ], []),

    # CGPA = the same over ALL the student's PUBLISHED results, persisted to the student_academic_record
    # (action_aggregate #4). Writing cgpa fires field_changed(cgpa) → the standing workflow below.
    _wf("compute_cgpa", "Compute CGPA", "student_academic_record", [
        {"slug": "cgpa", "step_type": "action_aggregate", "name": "Aggregate CGPA",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("tqp", "course_result", "sum", "quality_points",
                             student="{{record.student}}", status="published"),
                _agg_measure("tcr", "course_result", "sum", "credit_hours",
                             student="{{record.student}}", status="published"),
            ],
            "computes": [{"name": "cgpa", "expression": "tqp / tcr if tcr > 0 else 0"}],
            "target": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                       "data": {"cgpa": "{{agg.cgpa}}", "credits_earned": "{{agg.tcr}}"}}}},
    ], []),

    # Academic standing = a CGPA-threshold ladder (elif chain via condition branches). Triggered by
    # field_changed(cgpa) so setting academic_standing (a different field) NEVER re-fires it — a clean,
    # loop-free consumer of the platform's field_changed trigger. Zero native standing code.
    _wf("student_academic_standing", "Academic Standing", "student_academic_record", [
        {"slug": "c_deans", "step_type": "condition", "name": "Dean's List?", "is_entry": True,
         "config": {"condition_nql": "cgpa >= 3.5"}},
        {"slug": "set_deans", "step_type": "action_update_record", "name": "Set Dean's List",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"academic_standing": "deans_list"}}},
        {"slug": "c_good", "step_type": "condition", "name": "Good Standing?",
         "config": {"condition_nql": "cgpa >= 2.0"}},
        {"slug": "set_good", "step_type": "action_update_record", "name": "Set Good Standing",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"academic_standing": "good_standing"}}},
        {"slug": "c_prob", "step_type": "condition", "name": "Probation?",
         "config": {"condition_nql": "cgpa >= 1.0"}},
        {"slug": "set_prob", "step_type": "action_update_record", "name": "Set Probation",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"academic_standing": "probation"}}},
        {"slug": "set_susp", "step_type": "action_update_record", "name": "Set Suspension",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"academic_standing": "suspension"}}},
    ], [
        {"source": "c_deans", "target": "set_deans", "condition_label": "true"},
        {"source": "c_deans", "target": "c_good", "condition_label": "false"},
        {"source": "c_good", "target": "set_good", "condition_label": "true"},
        {"source": "c_good", "target": "c_prob", "condition_label": "false"},
        {"source": "c_prob", "target": "set_prob", "condition_label": "true"},
        {"source": "c_prob", "target": "set_susp", "condition_label": "false"},
    ], trigger_type="field_changed", trigger_config={"fields": ["cgpa"]}),

    # Degree audit: credits completed vs the program's requirement (read as a single-row measure —
    # same dynamic-threshold pattern the C2 guard uses), persisted to degree_progress
    # (action_aggregate #5).
    _wf("compute_degree_progress", "Compute Degree Progress", "degree_progress", [
        {"slug": "prog", "step_type": "action_aggregate", "name": "Aggregate Degree Progress",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("earned", "course_result", "sum", "credit_hours",
                             student="{{record.student}}", status="published"),
                _agg_measure("required", "program", "max", "total_credits_required",
                             id="{{record.program}}"),
            ],
            "computes": [{"name": "pct",
                          "expression": "earned / required * 100 if required > 0 else 0"}],
            "target": {"entity_slug": "degree_progress", "record_id": "{{record.id}}",
                       "data": {"credits_completed": "{{agg.earned}}",
                                "credits_required": "{{agg.required}}",
                                "progress_percent": "{{agg.pct}}"}}}},
    ], []),

    # Graduation conferred → notify the student (metadata lifecycle; no eligibility engine).
    _wf("graduation_conferred", "Graduation Conferred", "graduation_application", [
        {"slug": "c", "step_type": "condition", "name": "Conferred?", "is_entry": True,
         "config": {"condition_nql": 'status = "conferred"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "graduation_conferred"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ C4 — Faculty & Advising (2 more pure-manifest Aggregation-Framework consumers) ══
    # Faculty teaching load = Σ(load_hours) + count(sections) over active teaching assignments for the
    # instructor+term, persisted to the faculty_workload record (action_aggregate).
    _wf("compute_faculty_workload", "Compute Faculty Workload", "faculty_workload", [
        {"slug": "load", "step_type": "action_aggregate", "name": "Aggregate Teaching Load",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("hrs", "teaching_assignment", "sum", "load_hours",
                             instructor="{{record.instructor}}", term="{{record.term}}",
                             status="active"),
                _agg_measure("secs", "teaching_assignment", "count",
                             instructor="{{record.instructor}}", term="{{record.term}}",
                             status="active"),
            ],
            "target": {"entity_slug": "faculty_workload", "record_id": "{{record.id}}",
                       "data": {"total_load_hours": "{{agg.hrs}}",
                                "section_count": "{{agg.secs}}"}}}},
    ], []),

    # Advisor caseload = count(active advisor assignments) for the advisor, persisted to the
    # advisor_caseload record (action_aggregate).
    _wf("compute_advisor_caseload", "Compute Advisor Caseload", "advisor_caseload", [
        {"slug": "count", "step_type": "action_aggregate", "name": "Aggregate Caseload",
         "is_entry": True, "config": {
            "measures": [_agg_measure("n", "advisor_assignment", "count",
                                      advisor="{{record.advisor}}", status="active")],
            "target": {"entity_slug": "advisor_caseload", "record_id": "{{record.id}}",
                       "data": {"active_advisees": "{{agg.n}}"}}}},
    ], []),

    # Advisor assigned → notify (single-step notification, like the C3 aggregate workflows).
    _wf("advisor_assigned", "Advisor Assigned", "advisor_assignment", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "advisor_assigned"}},
    ], []),

    # Advising session scheduled → notify the student.
    _wf("advising_session_scheduled", "Advising Session Scheduled", "advising_session", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "advising_scheduled"}},
    ], []),

    # Academic hold placed / cleared → notify the student.
    _wf("academic_hold_placed", "Academic Hold Placed", "academic_hold", [
        {"slug": "c", "step_type": "condition", "name": "Active?", "is_entry": True,
         "config": {"condition_nql": 'status = "active"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "academic_hold_placed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}]),
    _wf("academic_hold_cleared", "Academic Hold Cleared", "academic_hold", [
        {"slug": "c", "step_type": "condition", "name": "Cleared?", "is_entry": True,
         "config": {"condition_nql": 'status = "cleared"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "academic_hold_cleared"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Override request submitted → notify approver; approved / denied → notify the student.
    _wf("override_submitted", "Override Request Submitted", "override_request", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Approver",
         "is_entry": True, "config": {"template_slug": "override_submitted"}},
    ], []),
    _wf("override_approved", "Override Approved", "override_request", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "override_approved"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("override_denied", "Override Denied", "override_request", [
        {"slug": "c", "step_type": "condition", "name": "Denied?", "is_entry": True,
         "config": {"condition_nql": 'status = "denied"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "override_denied"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ C5 — Finance (ALL money movement delegates to Core engines; zero College accounting) ══
    # Tuition charge issued → POST TO GL (Dr A/R 1100, Cr Revenue 4100) → notify → invoice PDF.
    _wf("tuition_charge_posting", "Tuition Charge Posting", "tuition_charge", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receivable",
         "is_entry": True, "config": {
             "source_module": "college", "source_ref": "{{record.charge_no}}",
             "memo": "Tuition charge {{record.charge_no}}",
             "account_debit": "1100", "account_credit": "4100",
             "amount": "{{record.amount}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "payment_due"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Tuition Invoice",
         "config": {"template_slug": "tuition_invoice"}},
    ], [{"source": "post", "target": "notify"}, {"source": "notify", "target": "doc"}]),

    # Student payment received → POST TO GL (Dr Cash 1000, Cr A/R 1100) → notify → receipt PDF.
    _wf("student_payment_posting", "Student Payment Posting", "student_payment", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receipt",
         "is_entry": True, "config": {
             "source_module": "college", "source_ref": "{{record.receipt_no}}",
             "memo": "Student receipt {{record.receipt_no}}",
             "account_debit": "1000", "account_credit": "1100",
             "amount": "{{record.amount}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Receipt",
         "config": {"template_slug": "receipt"}},
    ], [{"source": "post", "target": "doc"}]),

    # Tuition adjustment approved → post a credit (Dr contra / Cr A/R) via the Credit Engine.
    _wf("tuition_adjustment_apply", "Apply Tuition Adjustment", "tuition_adjustment", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "discount", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}",
                    "applies_to_ref": "{{record.tuition_charge}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.adjustment_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Applied",
         "config": {"field": "status", "value": "applied"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}], trigger_type="record_updated"),

    # Aid award approved → post a scholarship credit (Dr Scholarships / Cr A/R) → letter → notify.
    _wf("aid_award_apply", "Award Financial Aid", "aid_award", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "scholarship", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}", "reason": "{{record.reason}}",
                    "external_ref": "{{record.award_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Awarded",
         "config": {"field": "status", "value": "awarded"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Aid Letter",
         "config": {"template_slug": "financial_aid_letter"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "aid_approved"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}, {"source": "mark", "target": "doc"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Aid rejected → notify the student.
    _wf("aid_award_rejected", "Aid Rejected", "aid_award", [
        {"slug": "check", "step_type": "condition", "name": "Rejected?", "is_entry": True,
         "config": {"condition_nql": 'status = "rejected"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "aid_rejected"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Aid renewal approved → post a scholarship credit for the renewal via the Credit Engine.
    _wf("aid_renewal_apply", "Renew Financial Aid", "aid_renewal", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "scholarship", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}", "reason": "Aid renewal",
                    "external_ref": "{{record.renewal_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Renewed",
         "config": {"field": "status", "value": "renewed"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}], trigger_type="record_updated"),

    # Sponsorship approved → post a sponsorship credit (Dr Scholarships / Cr A/R) → letter.
    _wf("sponsorship_apply", "Apply Sponsorship", "sponsorship", [
        {"slug": "check", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "credit", "step_type": "action_apply_credit", "name": "Apply Credit",
         "config": {"kind": "scholarship", "amount": "{{record.amount}}",
                    "subject_ref": "{{record.student}}", "reason": "Sponsorship",
                    "external_ref": "{{record.sponsorship_no}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Mark Active",
         "config": {"field": "status", "value": "active"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Sponsorship Letter",
         "config": {"template_slug": "sponsorship_letter"}},
    ], [{"source": "check", "target": "credit", "condition_label": "true"},
        {"source": "credit", "target": "mark"}, {"source": "mark", "target": "doc"}],
        trigger_type="record_updated"),

    # Student loan disbursed → post the disbursement (Dr A/R 1100, Cr Cash 1000) + build the
    # repayment schedule via the Collections Engine → loan letter.
    _wf("student_loan_disburse", "Disburse Student Loan", "student_loan", [
        {"slug": "check", "step_type": "condition", "name": "Disbursed?", "is_entry": True,
         "config": {"condition_nql": 'status = "disbursed"'}},
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Disbursement",
         "config": {"source_module": "college", "source_ref": "{{record.loan_no}}",
                    "memo": "Loan disbursement {{record.loan_no}}",
                    "account_debit": "1100", "account_credit": "1000",
                    "amount": "{{record.principal_amount}}"}},
        {"slug": "plan", "step_type": "action_create_installment_plan", "name": "Repayment Schedule",
         "config": {"total_amount": "{{record.principal_amount}}",
                    "num_installments": "{{record.num_installments}}",
                    "frequency": "{{record.frequency}}", "start_date": "{{record.start_date}}",
                    "subject_ref": "{{record.student}}",
                    "source_document_ref": "{{record.loan_no}}",
                    "external_ref": "{{record.loan_no}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Loan Letter",
         "config": {"template_slug": "loan_letter"}},
    ], [{"source": "check", "target": "post", "condition_label": "true"},
        {"source": "post", "target": "plan"}, {"source": "plan", "target": "doc"}],
        trigger_type="record_updated"),

    # Payment plan approved → build the due schedule via the Collections Engine → activate → notify.
    _wf("payment_plan_create", "Create Payment Plan", "payment_plan", [
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
         "config": {"template_slug": "installment_reminder"}},
    ], [{"source": "check", "target": "plan", "condition_label": "true"},
        {"source": "plan", "target": "mark"}, {"source": "mark", "target": "notify"}],
        trigger_type="record_updated"),

    # Financial hold placed → REUSE the FROZEN C2 registration_hold (hold_type=financial) so the C2
    # eligibility guard blocks registration — zero new blocking logic — → notify the student.
    _wf("financial_hold_placed", "Financial Hold Placed", "financial_hold", [
        {"slug": "active", "step_type": "condition", "name": "Active?",
         "is_entry": True, "config": {"condition_nql": 'status = "active"'}},
        {"slug": "reg_hold", "step_type": "action_create_record", "name": "Create Registration Hold",
         "config": {"entity_slug": "registration_hold",
                    "data": {"student": "{{record.student}}", "hold_type": "financial",
                             "reason": "{{record.reason}}", "status": "active"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "hold_applied"}},
    ], [{"source": "active", "target": "reg_hold", "condition_label": "true"},
        {"source": "reg_hold", "target": "notify"}]),

    # Financial hold cleared → notify (the registrar clears the linked registration_hold).
    _wf("financial_hold_cleared", "Financial Hold Cleared", "financial_hold", [
        {"slug": "c", "step_type": "condition", "name": "Cleared?", "is_entry": True,
         "config": {"condition_nql": 'status = "cleared"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "hold_released"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Graduation blocking — a NEW C5 guard on graduation approval: if the student has an active
    # financial hold, revert to review (reuses the Core Guard Framework; does not modify C3).
    _wf("graduation_finance_check", "Graduation Finance Check", "graduation_application", [
        {"slug": "approved", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "guard", "step_type": "action_guard", "name": "No Financial Hold?",
         "config": {"guards": [
             {"name": "no_financial_hold",
              "query": {"entity": "financial_hold", "filter": {"op": "and", "conditions": [
                  {"field": "student", "op": "=", "value": "{{record.student}}"},
                  {"field": "status", "op": "=", "value": "active"}]}},
              "operator": "not_exists", "severity": "block",
              "message": "Student has an active financial hold."}]}},
        {"slug": "block", "step_type": "action_update_record", "name": "Hold Graduation",
         "config": {"entity_slug": "graduation_application", "record_id": "{{record.id}}",
                    "data": {"status": "under_review"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Finance Hold",
         "config": {"template_slug": "hold_applied"}},
    ], [{"source": "approved", "target": "guard", "condition_label": "true"},
        {"source": "guard", "target": "block", "condition_label": "false"},
        {"source": "block", "target": "notify"}], trigger_type="record_updated"),

    # ══ C6 — Campus Operations (mirror the frozen School campus-ops workflows; charges reuse C5) ══
    # Charge-bearing campus service issued → POST TO GL (Dr A/R 1100, Cr Revenue 4100) → receipt.
    _wf("campus_charge_posting", "Campus Charge Posting", "campus_charge", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Charge",
         "is_entry": True, "config": {
             "source_module": "college", "source_ref": "{{record.charge_no}}",
             "memo": "Campus charge {{record.charge_no}}",
             "account_debit": "1100", "account_credit": "4100",
             "amount": "{{record.amount}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Receipt",
         "config": {"template_slug": "campus_charge_receipt"}},
    ], [{"source": "post", "target": "doc"}]),

    # Book loan overdue → notify the student.
    _wf("book_overdue_notice", "Book Overdue Notice", "book_loan", [
        {"slug": "c", "step_type": "condition", "name": "Overdue?", "is_entry": True,
         "config": {"condition_nql": 'status = "overdue"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "book_overdue"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Room allocated → notify the student.
    _wf("room_allocated", "Room Allocated", "room_allocation", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "room_allocated"}},
    ], []),

    # Medical alert raised → notify (mirrors School medical_alert_raised).
    _wf("medical_alert_raised", "Medical Alert Raised", "medical_alert", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "medical_alert"}},
    ], []),

    # Counselling referral created → notify the counselling team (mirrors School).
    _wf("counselling_referral_created", "Counselling Referral", "counselling_referral", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Counsellor",
         "is_entry": True, "config": {"template_slug": "counselling_referral"}},
    ], []),

    # Award granted → congratulate the student + certificate (mirrors School award_granted).
    _wf("award_granted", "Award Granted", "award", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "award_received"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Award Certificate",
         "config": {"template_slug": "award_certificate"}},
    ], [{"source": "notify", "target": "doc"}]),

    # Incident report logged → notify the security office.
    _wf("incident_logged", "Incident Logged", "incident_report", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Security",
         "is_entry": True, "config": {"template_slug": "incident_logged"}},
    ], []),

    # Welfare case opened → confidential alert to the welfare lead (mirrors School safeguarding).
    _wf("welfare_case_opened", "Welfare Case Opened", "welfare_case", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Welfare Lead",
         "is_entry": True, "config": {"template_slug": "welfare_alert"}},
    ], []),

    # Visitor checked in → notify the host.
    _wf("visitor_checked_in", "Visitor Checked In", "visitor_log", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Host",
         "is_entry": True, "config": {"template_slug": "visitor_checkin"}},
    ], []),

    # Gate pass approved → notify the student.
    _wf("gate_pass_approved", "Gate Pass Approved", "gate_pass", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "gate_pass_approved"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ID card issued → generate the card document + notify.
    _wf("id_card_issued", "ID Card Issued", "id_card_request", [
        {"slug": "c", "step_type": "condition", "name": "Issued?", "is_entry": True,
         "config": {"condition_nql": 'status = "issued"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "ID Card",
         "config": {"template_slug": "id_card"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "id_card_issued"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Lost item claimed → notify.
    _wf("lost_item_claimed", "Lost Item Claimed", "lost_and_found", [
        {"slug": "c", "step_type": "condition", "name": "Claimed?", "is_entry": True,
         "config": {"condition_nql": 'status = "claimed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "lost_item_claimed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ C7 — Research (scholarly lifecycles; grant funding reuses C5 GL; NO PM, NO research budget) ══
    # Research proposal approved → notify (PI then creates a Projects project + research_project overlay).
    _wf("research_proposal_approved", "Research Proposal Approved", "research_proposal", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Proposal Approval",
         "config": {"template_slug": "research_proposal_document"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify PI",
         "config": {"template_slug": "proposal_approved"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Ethics / IRB approved → certificate + notify.
    _wf("ethics_approved", "Ethics Approved", "ethics_approval", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Ethics Certificate",
         "config": {"template_slug": "ethics_certificate"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "ethics_approved"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Grant awarded → POST funding to GL (Dr A/R 1100 from agency, Cr Grant Revenue 4100) via the C5
    # financial platform → award letter → notify. Grant BUDGET/EXPENSES stay on the Projects project.
    _wf("grant_awarded", "Grant Awarded", "grant", [
        {"slug": "c", "step_type": "condition", "name": "Awarded?", "is_entry": True,
         "config": {"condition_nql": 'status = "awarded"'}},
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Grant Funding",
         "config": {"source_module": "college", "source_ref": "{{record.grant_no}}",
                    "memo": "Grant funding {{record.grant_no}}",
                    "account_debit": "1100", "account_credit": "4100",
                    "amount": "{{record.award_amount}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Grant Award Letter",
         "config": {"template_slug": "grant_award_letter"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify PI",
         "config": {"template_slug": "grant_awarded"}},
    ], [{"source": "c", "target": "post", "condition_label": "true"},
        {"source": "post", "target": "doc"}, {"source": "doc", "target": "notify"}],
        trigger_type="record_updated"),

    # Publication published → notify.
    _wf("publication_published", "Publication Published", "publication", [
        {"slug": "c", "step_type": "condition", "name": "Published?", "is_entry": True,
         "config": {"condition_nql": 'status = "published"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "publication_published"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Patent granted → certificate + notify.
    _wf("patent_granted", "Patent Granted", "patent", [
        {"slug": "c", "step_type": "condition", "name": "Granted?", "is_entry": True,
         "config": {"condition_nql": 'status = "granted"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Patent Certificate",
         "config": {"template_slug": "patent_certificate"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "patent_granted"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Thesis defended → certificate + notify.
    _wf("thesis_defended", "Thesis Defended", "thesis", [
        {"slug": "c", "step_type": "condition", "name": "Defended?", "is_entry": True,
         "config": {"condition_nql": 'status = "defended"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Thesis Certificate",
         "config": {"template_slug": "thesis_certificate"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "thesis_defended"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Research contract signed → notify.
    _wf("research_contract_signed", "Research Contract Signed", "research_contract", [
        {"slug": "c", "step_type": "condition", "name": "Signed?", "is_entry": True,
         "config": {"condition_nql": 'status = "signed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "contract_signed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ C8 — Accreditation & Compliance lifecycles (reuse Workflow/Documents/Notifications) ══
    _wf("accreditation_granted", "Accreditation Granted", "accreditation", [
        {"slug": "c", "step_type": "condition", "name": "Accredited?", "is_entry": True,
         "config": {"condition_nql": 'status = "accredited"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Accreditation Certificate",
         "config": {"template_slug": "accreditation_certificate"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "accreditation_granted"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),
    _wf("compliance_overdue", "Compliance Overdue", "compliance_requirement", [
        {"slug": "c", "step_type": "condition", "name": "Overdue?", "is_entry": True,
         "config": {"condition_nql": 'status = "overdue"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Owner",
         "config": {"template_slug": "compliance_overdue"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("compliance_met", "Compliance Met", "compliance_requirement", [
        {"slug": "c", "step_type": "condition", "name": "Met?", "is_entry": True,
         "config": {"condition_nql": 'status = "met"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "compliance_met"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
]


# ── roles (reuse RBAC) ────────────────────────────────────────────────────────
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
COLLEGE_ROLES = [
    _role("college_administrator", "College Administrator", "Full access to the college solution.",
          [(None, _FULL + ["admin"])]),
    _role("registrar", "Registrar", "Students, program enrollment, sections, and registration.",
          [("student", _FULL), ("program_enrollment", _FULL), ("course_section", _FULL),
           ("program", ["read"]), ("course", ["read"]), ("curriculum", ["read"]),
           ("term", ["read", "update"]), ("academic_calendar_event", _FULL),
           ("registration", _FULL), ("registration_period", _FULL),
           ("registration_hold", _FULL), ("waitlist_entry", _FULL),
           # C3 — registrar owns results, records, degree audit, transfers and graduation.
           ("course_result", _FULL), ("semester_result", _FULL),
           ("student_academic_record", _FULL), ("degree_progress", _FULL),
           ("transfer_credit", _FULL), ("graduation_application", _FULL),
           ("grade_scheme", ["read"]), ("grade_scale", ["read"]),
           # C4 — registrar processes overrides and sees holds/assignments.
           ("override_request", _FULL), ("academic_hold", ["read", "update"]),
           ("teaching_assignment", ["read"]), ("advisor_assignment", ["read"])]),
    _role("academic_advisor", "Academic Advisor",
          "Advises students; places and clears registration holds; reviews academic standing.",
          [("student", ["read"]), ("registration", ["read"]), ("waitlist_entry", ["read"]),
           ("registration_hold", _FULL), ("program_enrollment", ["read"]),
           # C3 — advisors read academic records / progress / results.
           ("student_academic_record", ["read"]), ("degree_progress", ["read"]),
           ("semester_result", ["read"]), ("course_result", ["read"]),
           ("graduation_application", ["read", "update"]),
           # C4 — advising is the advisor's core surface.
           ("advisor_assignment", _FULL), ("advisor_caseload", ["read"]),
           ("advising_session", _FULL), ("advising_note", _FULL),
           ("academic_hold", _FULL), ("override_request", ["read", "update"])]),
    _role("dean", "Dean", "Faculty oversight across programs and departments.",
          [(None, ["read", "export"]), ("faculty", ["read", "update"]),
           ("department", ["read", "update"])]),
    _role("department_head", "Head of Department",
          "Department courses, sections, instructors, curriculum, grade schemes and grade approval.",
          [("course", _FULL), ("prerequisite", _FULL), ("course_section", _FULL),
           ("instructor", _FULL), ("curriculum", _FULL), ("curriculum_course", _FULL),
           ("program", ["read", "update"]), ("specialization", _FULL),
           ("department", ["read"]), ("student", ["read"]),
           # C3 — owns the grading policy + approves submitted grades.
           ("grade_scheme", _FULL), ("grade_scale", _FULL),
           ("assessment", ["read"]), ("assessment_result", ["read"]),
           ("course_result", ["read", "update", "export"]),
           # C4 — manages teaching assignments/workload + approves overrides.
           ("teaching_assignment", _FULL), ("office_hour", ["read"]),
           ("faculty_workload", ["read"]), ("override_request", _FULL),
           ("advisor_assignment", ["read"])]),
    _role("instructor", "Instructor",
          "Assigned sections, grade book, grade entry, office hours and advising.",
          [("course_section", ["read"]), ("course", ["read"]), ("student", ["read"]),
           ("program_enrollment", ["read"]),
           # C3 — instructors build the grade book and enter grades.
           ("assessment", _FULL), ("assessment_result", _FULL),
           ("course_result", ["create", "read", "update"]),
           ("grade_scheme", ["read"]), ("grade_scale", ["read"]),
           # C4 — faculty see their assignments/workload, keep office hours, may advise.
           ("teaching_assignment", ["read"]), ("office_hour", _FULL),
           ("faculty_workload", ["read"]), ("advising_session", ["create", "read", "update"]),
           ("advising_note", ["create", "read", "update"]),
           ("academic_hold", ["read"]), ("override_request", ["read"])]),
    # C5 — finance roles.
    _role("bursar", "Bursar / Finance Officer",
          "Owns tuition, charges, payments, plans, finance holds and finance reporting.",
          [("tuition_category", _FULL), ("tuition_structure", _FULL), ("tuition_charge", _FULL),
           ("tuition_adjustment", _FULL), ("student_account", _FULL), ("student_payment", _FULL),
           ("payment_plan", _FULL), ("payment_agreement", _FULL), ("financial_hold", _FULL),
           ("aid_award", ["read"]), ("sponsorship", ["read"]),
           ("student_loan", ["read", "update"]), ("student", ["read"]),
           ("program", ["read"]), ("term", ["read"])]),
    _role("financial_aid_officer", "Financial Aid Officer",
          "Owns aid programs, awards, renewals, sponsorships and student loans.",
          [("aid_program", _FULL), ("aid_award", _FULL), ("aid_renewal", _FULL),
           ("sponsorship", _FULL), ("student_loan", _FULL), ("student", ["read"]),
           ("tuition_charge", ["read"]), ("student_account", ["read"]),
           ("financial_hold", ["read"])]),
    # C6 — campus-operations roles.
    _role("campus_services_officer", "Campus Services Officer",
          "Library, residence, transport, meals, ID cards, lost & found and campus charges.",
          [("library_book", _FULL), ("book_loan", _FULL), ("residence_room", _FULL),
           ("room_allocation", _FULL), ("transport_route", _FULL),
           ("transport_subscription", _FULL), ("meal_plan", _FULL), ("id_card_request", _FULL),
           ("lost_and_found", _FULL), ("campus_charge", _FULL), ("student", ["read"])]),
    _role("campus_health_officer", "Campus Health & Counselling Officer",
          "Campus health center + counselling (confidential records).",
          [("medical_profile", _FULL), ("medical_condition", _FULL), ("allergy", _FULL),
           ("medication", _FULL), ("vaccination_record", _FULL), ("medical_visit", _FULL),
           ("medical_alert", _FULL), ("health_screening", _FULL),
           ("counselling_referral", _FULL), ("counselling_session", _FULL),
           ("counselling_action_plan", _FULL), ("student", ["read"])]),
    _role("activities_coordinator", "Activities Coordinator",
          "Clubs, sports, competitions, awards and student activities.",
          [("student_club", _FULL), ("club_membership", _FULL), ("sport", _FULL),
           ("sport_participation", _FULL), ("competition", _FULL), ("competition_entry", _FULL),
           ("award", _FULL), ("student_activity", _FULL), ("student", ["read"])]),
    _role("security_officer", "Campus Security Officer",
          "Visitor management, gate passes, incidents, welfare and lost & found.",
          [("visitor_log", _FULL), ("gate_pass", _FULL), ("incident_report", _FULL),
           ("welfare_case", _FULL), ("lost_and_found", _FULL), ("student", ["read"])]),
    # C7 — research roles.
    _role("research_director", "Research Director",
          "Oversees research centers, proposals, ethics, publications, IP and contracts.",
          [("research_center", _FULL), ("research_group", _FULL), ("research_project", _FULL),
           ("research_team_member", _FULL), ("research_proposal", _FULL),
           ("ethics_approval", _FULL), ("publication", _FULL), ("patent", _FULL),
           ("intellectual_property", _FULL), ("research_contract", _FULL),
           ("thesis", ["read"]), ("grant", ["read"]), ("funding_agency", ["read"])]),
    _role("principal_investigator", "Principal Investigator",
          "Leads research projects, proposals, publications and supervises research students.",
          [("research_project", ["read", "update"]), ("research_team_member", _FULL),
           ("research_student", _FULL), ("research_proposal", _FULL), ("publication", _FULL),
           ("patent", _FULL), ("intellectual_property", _FULL), ("thesis", _FULL),
           ("ethics_approval", ["create", "read", "update"]), ("grant", ["read"]),
           ("student", ["read"])]),
    _role("grants_officer", "Grants Officer",
          "Manages grants, grant applications, funding agencies and research contracts.",
          [("grant", _FULL), ("grant_application", _FULL), ("funding_agency", _FULL),
           ("research_contract", _FULL), ("research_proposal", ["read"]),
           ("research_project", ["read"])]),
    _role("research_officer", "Research Officer",
          "Administers research records, publications, conferences and journals.",
          [("publication", _FULL), ("journal", _FULL), ("conference", _FULL),
           ("research_project", ["read"]), ("research_student", ["read"]),
           ("ethics_approval", ["read"])]),
    # C8 — executive + compliance roles (read-across for analytics; accreditation/compliance owners).
    _role("president", "President / Executive",
          "Institution-wide executive read access + accreditation oversight.",
          [(None, ["read", "export"]), ("accreditation", ["read", "update"]),
           ("accreditation_body", ["read"])]),
    _role("provost", "Provost / Academic Executive",
          "Academic executive read access across programs, faculty and research.",
          [(None, ["read", "export"])]),
    _role("compliance_officer", "Compliance Officer",
          "Accreditation and institutional compliance management.",
          [("accreditation_body", _FULL), ("accreditation", _FULL),
           ("compliance_requirement", _FULL), ("compliance_record", _FULL),
           ("program", ["read"])]),
]


# ── reports + dashboards + KPIs (reuse reporting + analytics) ─────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


COLLEGE_REPORTS = [
    _report("programs_report", "Programs", "program", "pivot"),
    _report("courses_report", "Courses", "course", "pivot"),
    _report("sections_report", "Course Sections", "course_section", "pivot"),
    _report("enrollment_report", "Program Enrollment", "program_enrollment", "pivot"),
    _report("instructors_report", "Instructors", "instructor", "pivot"),
    _report("curriculum_report", "Curriculum", "curriculum_course", "pivot"),
    _report("student_roster_report", "Student Roster", "student"),
    # C2 registration reports.
    _report("registrations_report", "Registrations", "registration", "pivot"),
    _report("holds_report", "Registration Holds", "registration_hold", "pivot"),
    _report("waitlist_report", "Waitlist", "waitlist_entry"),
    # C3 academic reports.
    _report("course_results_report", "Course Results", "course_result", "pivot"),
    _report("semester_results_report", "Semester Results", "semester_result", "pivot"),
    _report("gpa_distribution_report", "GPA Distribution", "student_academic_record", "pivot"),
    _report("academic_standing_report", "Academic Standing", "student_academic_record", "pivot"),
    _report("degree_progress_report", "Degree Progress", "degree_progress", "pivot"),
    _report("transfer_credits_report", "Transfer Credits", "transfer_credit", "pivot"),
    _report("graduation_report", "Graduation Applications", "graduation_application", "pivot"),
    _report("transcript_report", "Student Transcript", "course_result"),
    # C4 faculty & advising reports.
    _report("teaching_assignments_report", "Teaching Assignments", "teaching_assignment", "pivot"),
    _report("faculty_workload_report", "Faculty Workload", "faculty_workload", "pivot"),
    _report("office_hours_report", "Office Hours", "office_hour"),
    _report("advisor_assignments_report", "Advisor Assignments", "advisor_assignment", "pivot"),
    _report("advising_sessions_report", "Advising Sessions", "advising_session", "pivot"),
    _report("academic_holds_report", "Academic Holds", "academic_hold", "pivot"),
    _report("override_requests_report", "Override Requests", "override_request", "pivot"),
    # C5 finance reports (Reporting engine — includes the ratio/grouped metrics the KPI engine can't
    # express as a single aggregate: collection rate, outstanding balance, revenue by program/faculty).
    _report("student_balance_report", "Student Balance", "student_account", "pivot"),
    _report("tuition_collection_report", "Tuition Collection", "student_payment", "pivot"),
    _report("outstanding_balance_report", "Outstanding Balance", "tuition_charge", "pivot"),
    _report("financial_aid_report", "Financial Aid", "aid_award", "pivot"),
    _report("sponsorship_report", "Sponsorships", "sponsorship", "pivot"),
    _report("scholarship_report", "Scholarships", "aid_award", "pivot"),
    _report("revenue_by_program_report", "Revenue by Program", "tuition_charge", "pivot"),
    _report("aging_report", "Aging", "tuition_charge", "pivot"),
    _report("installment_status_report", "Installment Status", "payment_plan", "pivot"),
    # C6 campus-operations reports.
    _report("book_loans_report", "Book Loans", "book_loan", "pivot"),
    _report("residence_occupancy_report", "Residence Occupancy", "room_allocation", "pivot"),
    _report("transport_report", "Transport Subscriptions", "transport_subscription", "pivot"),
    _report("medical_visits_report", "Medical Visits", "medical_visit", "pivot"),
    _report("counselling_report", "Counselling Referrals", "counselling_referral", "pivot"),
    _report("activities_report", "Student Activities", "student_activity", "pivot"),
    _report("awards_report", "Awards", "award", "pivot"),
    _report("incidents_report", "Incident Reports", "incident_report", "pivot"),
    _report("gate_pass_report", "Gate Passes", "gate_pass", "pivot"),
    _report("meal_plans_report", "Meal Plans", "meal_plan", "pivot"),
    _report("campus_charges_report", "Campus Charges", "campus_charge", "pivot"),
    # C7 research reports.
    _report("research_projects_report", "Research Projects", "research_project", "pivot"),
    _report("grants_report", "Grants", "grant", "pivot"),
    _report("funding_by_agency_report", "Funding by Agency", "grant", "pivot"),
    _report("publications_report", "Publications", "publication", "pivot"),
    _report("patents_report", "Patents", "patent", "pivot"),
    _report("theses_report", "Theses & Dissertations", "thesis", "pivot"),
    _report("ethics_report", "Ethics Approvals", "ethics_approval", "pivot"),
    _report("research_contracts_report", "Research Contracts", "research_contract", "pivot"),
    # C8 executive / accreditation / compliance reports (Reporting engine — pivot/CSV/XLSX/PDF).
    _report("accreditation_report", "Accreditation Status", "accreditation", "pivot"),
    _report("compliance_report", "Compliance Requirements", "compliance_requirement", "pivot"),
    _report("student_success_report", "Student Success", "student_academic_record", "pivot"),
    _report("enrollment_analytics_report", "Enrollment Analytics", "program_enrollment", "pivot"),
    _report("faculty_analytics_report", "Faculty Analytics", "faculty_workload", "pivot"),
]


def _kpi(code, name, category, nql_source, *, aggregate="count", value_field="",
         direction="higher_better", unit=""):
    return {"code": code, "name": name, "category": category, "source_type": "nql",
            "nql_source": nql_source, "aggregate": aggregate, "value_field": value_field,
            "direction": direction, "unit": unit}


COLLEGE_KPIS = [
    _kpi("active_programs", "Active Programs", "academic", 'FROM program WHERE status = "active"'),
    _kpi("total_courses", "Total Courses", "academic", "FROM course"),
    _kpi("enrolled_students", "Enrolled Students", "academic",
         'FROM student WHERE status = "enrolled"'),
    _kpi("open_sections", "Open Sections", "operations", 'FROM course_section WHERE status = "open"'),
    _kpi("active_instructors", "Active Instructors", "operations",
         'FROM instructor WHERE status = "active"'),
    # C2 registration KPIs.
    _kpi("confirmed_registrations", "Confirmed Registrations", "academic",
         'FROM registration WHERE status = "confirmed"'),
    _kpi("waitlisted_registrations", "Waitlisted Registrations", "operations",
         'FROM registration WHERE status = "waitlisted"', direction="lower_better"),
    _kpi("active_holds", "Active Registration Holds", "operations",
         'FROM registration_hold WHERE status = "active"', direction="lower_better"),
    # C3 academic-performance KPIs (avg CGPA reuses the analytics avg aggregate over the record).
    _kpi("average_cgpa", "Average CGPA", "academic", "FROM student_academic_record",
         aggregate="avg", value_field="cgpa", direction="higher_better", unit="GPA"),
    _kpi("deans_list_students", "Dean's List Students", "academic",
         'FROM student_academic_record WHERE academic_standing = "deans_list"'),
    _kpi("probation_students", "Students on Probation", "academic",
         'FROM student_academic_record WHERE academic_standing = "probation"',
         direction="lower_better"),
    _kpi("published_results", "Published Course Results", "operations",
         'FROM course_result WHERE status = "published"'),
    _kpi("pending_grade_approvals", "Grades Awaiting Approval", "operations",
         'FROM course_result WHERE status = "submitted"', direction="lower_better"),
    # C4 faculty & advising KPIs.
    _kpi("active_teaching_assignments", "Active Teaching Assignments", "operations",
         'FROM teaching_assignment WHERE status = "active"'),
    _kpi("average_teaching_load", "Average Teaching Load", "operations",
         "FROM faculty_workload", aggregate="avg", value_field="total_load_hours", unit="hrs"),
    _kpi("average_advisor_caseload", "Average Advisor Caseload", "operations",
         "FROM advisor_caseload", aggregate="avg", value_field="active_advisees"),
    _kpi("scheduled_advising_sessions", "Scheduled Advising Sessions", "academic",
         'FROM advising_session WHERE status = "scheduled"'),
    _kpi("active_academic_holds", "Active Academic Holds", "operations",
         'FROM academic_hold WHERE status = "active"', direction="lower_better"),
    _kpi("pending_overrides", "Pending Override Requests", "operations",
         'FROM override_request WHERE status = "pending"', direction="lower_better"),
    # C5 finance KPIs (single-aggregate only — ratio/grouped metrics like collection rate & revenue
    # by faculty are Reporting-engine reports above, not faked as single-aggregate KPIs).
    _kpi("tuition_revenue", "Tuition Revenue", "finance", "FROM tuition_charge",
         aggregate="sum", value_field="amount", unit="currency"),
    _kpi("total_collected", "Total Collected", "finance", "FROM student_payment",
         aggregate="sum", value_field="amount", unit="currency"),
    _kpi("average_tuition", "Average Tuition Charge", "finance", "FROM tuition_charge",
         aggregate="avg", value_field="amount", unit="currency"),
    _kpi("aid_distribution", "Financial Aid Distributed", "finance",
         'FROM aid_award WHERE status = "awarded"', aggregate="sum", value_field="amount",
         unit="currency"),
    _kpi("scholarship_amount", "Scholarship Amount", "finance",
         'FROM aid_award WHERE aid_type = "scholarship"', aggregate="sum", value_field="amount",
         unit="currency"),
    _kpi("loan_exposure", "Loan Exposure", "finance",
         'FROM student_loan WHERE status = "disbursed"', aggregate="sum",
         value_field="principal_amount", direction="lower_better", unit="currency"),
    _kpi("active_financial_holds", "Active Financial Holds", "finance",
         'FROM financial_hold WHERE status = "active"', direction="lower_better"),
    # C6 campus-operations KPIs.
    _kpi("books_on_loan", "Books on Loan", "operations",
         'FROM book_loan WHERE status = "issued"'),
    _kpi("overdue_books", "Overdue Books", "operations",
         'FROM book_loan WHERE status = "overdue"', direction="lower_better"),
    _kpi("active_room_allocations", "Active Room Allocations", "operations",
         'FROM room_allocation WHERE status = "active"'),
    _kpi("active_medical_alerts", "Active Medical Alerts", "operations",
         'FROM medical_alert WHERE severity = "critical"', direction="lower_better"),
    _kpi("open_counselling_referrals", "Open Counselling Referrals", "operations",
         'FROM counselling_referral WHERE status = "open"'),
    _kpi("open_incidents", "Open Incidents", "operations",
         'FROM incident_report WHERE status = "open"', direction="lower_better"),
    _kpi("active_meal_plans", "Active Meal Plans", "operations",
         'FROM meal_plan WHERE status = "active"'),
    _kpi("campus_charge_revenue", "Campus Charge Revenue", "finance", "FROM campus_charge",
         aggregate="sum", value_field="amount", unit="currency"),
    # C7 research KPIs.
    _kpi("active_research_projects", "Active Research Projects", "research",
         'FROM research_project WHERE status = "active"'),
    _kpi("total_grant_funding", "Total Grant Funding", "research",
         'FROM grant WHERE status = "awarded"', aggregate="sum", value_field="award_amount",
         unit="currency"),
    _kpi("active_grants", "Active Grants", "research", 'FROM grant WHERE status = "active"'),
    _kpi("total_publications", "Publications", "research",
         'FROM publication WHERE status = "published"'),
    _kpi("patents_granted", "Patents Granted", "research",
         'FROM patent WHERE status = "granted"'),
    _kpi("research_students", "Research Students", "research",
         'FROM research_student WHERE status = "active"'),
    _kpi("pending_ethics_approvals", "Pending Ethics Approvals", "research",
         'FROM ethics_approval WHERE status = "under_review"', direction="lower_better"),
    # C8 executive / institutional KPIs (Analytics engine; scorecards group existing + these).
    _kpi("total_students", "Total Students", "executive", "FROM student"),
    _kpi("total_faculty", "Total Faculty", "executive", "FROM instructor"),
    _kpi("accredited_programs", "Accredited Programs", "executive",
         'FROM accreditation WHERE status = "accredited"'),
    _kpi("open_compliance_items", "Open Compliance Items", "executive",
         'FROM compliance_requirement WHERE status = "pending"', direction="lower_better"),
    _kpi("overdue_compliance_items", "Overdue Compliance Items", "executive",
         'FROM compliance_requirement WHERE status = "overdue"', direction="lower_better"),
]


def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


COLLEGE_DASHBOARDS = [
    {"slug": "executive_dashboard", "name": "Executive Dashboard", "is_default": True, "widgets": [
        _w("metric_card", "Active Programs", 0, 0, 3, 2),
        _w("metric_card", "Enrolled Students", 3, 0, 3, 2),
        _w("metric_card", "Open Sections", 6, 0, 3, 2),
        _w("metric_card", "Instructors", 9, 0, 3, 2),
        _w("report", "Program Enrollment", 0, 2, 6, 4, report_slug="enrollment_report"),
        _w("report", "Programs", 6, 2, 6, 4, report_slug="programs_report"),
    ]},
    {"slug": "registrar_dashboard", "name": "Registrar Dashboard", "widgets": [
        _w("report", "Program Enrollment", 0, 0, 6, 4, report_slug="enrollment_report"),
        _w("report", "Course Sections", 6, 0, 6, 4, report_slug="sections_report"),
        _w("report", "Student Roster", 0, 4, 12, 4, report_slug="student_roster_report"),
    ]},
    {"slug": "academic_dashboard", "name": "Academic Dashboard", "widgets": [
        _w("report", "Programs", 0, 0, 4, 4, report_slug="programs_report"),
        _w("report", "Courses", 4, 0, 4, 4, report_slug="courses_report"),
        _w("report", "Curriculum", 8, 0, 4, 4, report_slug="curriculum_report"),
    ]},
    {"slug": "registration_dashboard", "name": "Registration Dashboard", "widgets": [
        _w("metric_card", "Confirmed Registrations", 0, 0, 4, 2),
        _w("metric_card", "Waitlisted", 4, 0, 4, 2),
        _w("metric_card", "Active Holds", 8, 0, 4, 2),
        _w("report", "Registrations", 0, 2, 6, 4, report_slug="registrations_report"),
        _w("report", "Waitlist", 6, 2, 6, 4, report_slug="waitlist_report"),
    ]},
    {"slug": "academic_performance_dashboard", "name": "Academic Performance", "widgets": [
        _w("metric_card", "Average CGPA", 0, 0, 3, 2),
        _w("metric_card", "Dean's List Students", 3, 0, 3, 2),
        _w("metric_card", "Students on Probation", 6, 0, 3, 2),
        _w("metric_card", "Grades Awaiting Approval", 9, 0, 3, 2),
        _w("report", "GPA Distribution", 0, 2, 6, 4, report_slug="gpa_distribution_report"),
        _w("report", "Academic Standing", 6, 2, 6, 4, report_slug="academic_standing_report"),
        _w("report", "Degree Progress", 0, 6, 12, 4, report_slug="degree_progress_report"),
    ]},
    {"slug": "faculty_dashboard", "name": "Faculty Dashboard", "widgets": [
        _w("metric_card", "Active Teaching Assignments", 0, 0, 4, 2),
        _w("metric_card", "Average Teaching Load", 4, 0, 4, 2),
        _w("metric_card", "Pending Override Requests", 8, 0, 4, 2),
        _w("report", "Teaching Assignments", 0, 2, 6, 4, report_slug="teaching_assignments_report"),
        _w("report", "Faculty Workload", 6, 2, 6, 4, report_slug="faculty_workload_report"),
    ]},
    {"slug": "advisor_dashboard", "name": "Advisor Dashboard", "widgets": [
        _w("metric_card", "Average Advisor Caseload", 0, 0, 4, 2),
        _w("metric_card", "Scheduled Advising Sessions", 4, 0, 4, 2),
        _w("metric_card", "Active Academic Holds", 8, 0, 4, 2),
        _w("report", "Advisor Assignments", 0, 2, 6, 4, report_slug="advisor_assignments_report"),
        _w("report", "Advising Sessions", 6, 2, 6, 4, report_slug="advising_sessions_report"),
        _w("report", "Academic Holds", 0, 6, 12, 4, report_slug="academic_holds_report"),
    ]},
    {"slug": "finance_dashboard", "name": "Finance Dashboard", "widgets": [
        _w("metric_card", "Tuition Revenue", 0, 0, 3, 2),
        _w("metric_card", "Total Collected", 3, 0, 3, 2),
        _w("metric_card", "Loan Exposure", 6, 0, 3, 2),
        _w("metric_card", "Active Financial Holds", 9, 0, 3, 2),
        _w("report", "Tuition Collection", 0, 2, 6, 4, report_slug="tuition_collection_report"),
        _w("report", "Outstanding Balance", 6, 2, 6, 4, report_slug="outstanding_balance_report"),
        _w("report", "Aging", 0, 6, 12, 4, report_slug="aging_report"),
    ]},
    {"slug": "financial_aid_dashboard", "name": "Financial Aid Dashboard", "widgets": [
        _w("metric_card", "Aid Distributed", 0, 0, 4, 2),
        _w("metric_card", "Scholarship Amount", 4, 0, 4, 2),
        _w("metric_card", "Loan Exposure", 8, 0, 4, 2),
        _w("report", "Financial Aid", 0, 2, 6, 4, report_slug="financial_aid_report"),
        _w("report", "Sponsorships", 6, 2, 6, 4, report_slug="sponsorship_report"),
    ]},
    {"slug": "campus_services_dashboard", "name": "Campus Services", "widgets": [
        _w("metric_card", "Books on Loan", 0, 0, 3, 2),
        _w("metric_card", "Overdue Books", 3, 0, 3, 2),
        _w("metric_card", "Active Room Allocations", 6, 0, 3, 2),
        _w("metric_card", "Active Meal Plans", 9, 0, 3, 2),
        _w("report", "Book Loans", 0, 2, 6, 4, report_slug="book_loans_report"),
        _w("report", "Residence Occupancy", 6, 2, 6, 4, report_slug="residence_occupancy_report"),
    ]},
    {"slug": "health_wellbeing_dashboard", "name": "Health & Wellbeing", "widgets": [
        _w("metric_card", "Active Medical Alerts", 0, 0, 4, 2),
        _w("metric_card", "Open Counselling Referrals", 4, 0, 4, 2),
        _w("report", "Medical Visits", 0, 2, 6, 4, report_slug="medical_visits_report"),
        _w("report", "Counselling Referrals", 6, 2, 6, 4, report_slug="counselling_report"),
    ]},
    {"slug": "campus_security_dashboard", "name": "Campus Security", "widgets": [
        _w("metric_card", "Open Incidents", 0, 0, 4, 2),
        _w("report", "Incident Reports", 0, 2, 6, 4, report_slug="incidents_report"),
        _w("report", "Gate Passes", 6, 2, 6, 4, report_slug="gate_pass_report"),
    ]},
    {"slug": "research_dashboard", "name": "Research Dashboard", "widgets": [
        _w("metric_card", "Active Research Projects", 0, 0, 3, 2),
        _w("metric_card", "Total Grant Funding", 3, 0, 3, 2),
        _w("metric_card", "Publications", 6, 0, 3, 2),
        _w("metric_card", "Patents Granted", 9, 0, 3, 2),
        _w("report", "Research Projects", 0, 2, 6, 4, report_slug="research_projects_report"),
        _w("report", "Publications", 6, 2, 6, 4, report_slug="publications_report"),
    ]},
    {"slug": "grants_dashboard", "name": "Grants & Funding", "widgets": [
        _w("metric_card", "Total Grant Funding", 0, 0, 4, 2),
        _w("metric_card", "Active Grants", 4, 0, 4, 2),
        _w("report", "Grants", 0, 2, 6, 4, report_slug="grants_report"),
        _w("report", "Funding by Agency", 6, 2, 6, 4, report_slug="funding_by_agency_report"),
    ]},
    # C8 — executive scorecards (Dashboard runtime; metric cards over existing + new KPIs).
    {"slug": "executive_scorecard", "name": "Executive Scorecard", "widgets": [
        _w("metric_card", "Total Students", 0, 0, 3, 2),
        _w("metric_card", "Total Faculty", 3, 0, 3, 2),
        _w("metric_card", "Tuition Revenue", 6, 0, 3, 2),
        _w("metric_card", "Total Grant Funding", 9, 0, 3, 2),
        _w("metric_card", "Average CGPA", 0, 2, 3, 2),
        _w("metric_card", "Accredited Programs", 3, 2, 3, 2),
        _w("metric_card", "Active Research Projects", 6, 2, 3, 2),
        _w("metric_card", "Overdue Compliance Items", 9, 2, 3, 2),
        _w("report", "Enrollment Analytics", 0, 4, 6, 4, report_slug="enrollment_analytics_report"),
        _w("report", "Student Success", 6, 4, 6, 4, report_slug="student_success_report"),
    ]},
    {"slug": "provost_dashboard", "name": "Provost Dashboard", "widgets": [
        _w("metric_card", "Enrolled Students", 0, 0, 3, 2),
        _w("metric_card", "Average CGPA", 3, 0, 3, 2),
        _w("metric_card", "Total Faculty", 6, 0, 3, 2),
        _w("metric_card", "Publications", 9, 0, 3, 2),
        _w("report", "Faculty Analytics", 0, 2, 6, 4, report_slug="faculty_analytics_report"),
        _w("report", "GPA Distribution", 6, 2, 6, 4, report_slug="gpa_distribution_report"),
    ]},
    {"slug": "cfo_dashboard", "name": "Finance Executive", "widgets": [
        _w("metric_card", "Tuition Revenue", 0, 0, 3, 2),
        _w("metric_card", "Total Collected", 3, 0, 3, 2),
        _w("metric_card", "Aid Distributed", 6, 0, 3, 2),
        _w("metric_card", "Active Financial Holds", 9, 0, 3, 2),
        _w("report", "Tuition Collection", 0, 2, 6, 4, report_slug="tuition_collection_report"),
        _w("report", "Outstanding Balance", 6, 2, 6, 4, report_slug="outstanding_balance_report"),
    ]},
    {"slug": "risk_dashboard", "name": "Institutional Risk", "widgets": [
        _w("metric_card", "Students on Probation", 0, 0, 3, 2),
        _w("metric_card", "Active Financial Holds", 3, 0, 3, 2),
        _w("metric_card", "Overdue Compliance Items", 6, 0, 3, 2),
        _w("metric_card", "Open Incidents", 9, 0, 3, 2),
        _w("report", "Compliance Requirements", 0, 2, 6, 4, report_slug="compliance_report"),
        _w("report", "Accreditation Status", 6, 2, 6, 4, report_slug="accreditation_report"),
    ]},
]

_ROLE_HOME = [
    ("college_administrator", "executive_dashboard"),
    ("registrar", "registrar_dashboard"),
    ("dean", "academic_dashboard"),
    ("department_head", "academic_dashboard"),
    ("instructor", "academic_dashboard"),
    ("academic_advisor", "registration_dashboard"),
    # C8 — executive role homes (DG-5 role-home runtime; no dashboard-platform change).
    ("president", "executive_scorecard"),
    ("provost", "provost_dashboard"),
    ("bursar", "cfo_dashboard"),
    ("compliance_officer", "risk_dashboard"),
]

_DASH_NAMES = {d["slug"]: d["name"] for d in COLLEGE_DASHBOARDS}
COLLEGE_ROLE_HOMES = [
    {"ref": f"home_{rs}", "name": _DASH_NAMES.get(ds, "Home"), "role_slug": rs,
     "widgets": [{"type": "dashboard", "title": _DASH_NAMES.get(ds, "Home"),
                  "config": {"dashboard_slug": ds}}]}
    for rs, ds in _ROLE_HOME
]


COLLEGE_NOTIFICATIONS = [
    {"slug": "enrollment_confirmed", "name": "Enrollment Confirmed", "channels": ["in_app"],
     "subject_template": "Enrollment confirmed",
     "body_template": "You are enrolled in your program."},
    {"slug": "program_activated", "name": "Program Activated", "channels": ["in_app"],
     "subject_template": "Program activated", "body_template": "A program is now active."},
    # C2 registration notifications.
    {"slug": "registration_confirmed", "name": "Registration Confirmed", "channels": ["in_app"],
     "subject_template": "Registration confirmed",
     "body_template": "Your course registration is confirmed."},
    {"slug": "registration_waitlisted", "name": "Registration Waitlisted", "channels": ["in_app"],
     "subject_template": "Placed on the waitlist",
     "body_template": "The section is full or a limit was reached; you are waitlisted."},
    {"slug": "registration_dropped", "name": "Registration Dropped", "channels": ["in_app"],
     "subject_template": "Registration dropped",
     "body_template": "Your course registration has been dropped."},
    {"slug": "registration_hold_cleared", "name": "Hold Cleared", "channels": ["in_app"],
     "subject_template": "Registration hold cleared",
     "body_template": "Your registration hold is cleared; you may register."},
    # C3 grade + graduation notifications.
    {"slug": "grade_submitted", "name": "Grade Submitted", "channels": ["in_app"],
     "subject_template": "Grade submitted for approval",
     "body_template": "A course grade has been submitted and awaits approval."},
    {"slug": "grade_published", "name": "Grade Published", "channels": ["in_app"],
     "subject_template": "Your grade is published",
     "body_template": "A course grade has been published to your record."},
    {"slug": "graduation_conferred", "name": "Graduation Conferred", "channels": ["in_app"],
     "subject_template": "Congratulations — degree conferred",
     "body_template": "Your degree has been conferred. Congratulations, graduate!"},
    # C4 faculty & advising notifications.
    {"slug": "advisor_assigned", "name": "Advisor Assigned", "channels": ["in_app"],
     "subject_template": "You have a new academic advisor",
     "body_template": "An academic advisor has been assigned to you."},
    {"slug": "advising_scheduled", "name": "Advising Session Scheduled", "channels": ["in_app"],
     "subject_template": "Advising session scheduled",
     "body_template": "An advising session has been scheduled."},
    {"slug": "academic_hold_placed", "name": "Academic Hold Placed", "channels": ["in_app"],
     "subject_template": "An academic hold was placed on your account",
     "body_template": "An academic hold has been placed; please contact your advisor."},
    {"slug": "academic_hold_cleared", "name": "Academic Hold Cleared", "channels": ["in_app"],
     "subject_template": "Your academic hold was cleared",
     "body_template": "An academic hold on your account has been cleared."},
    {"slug": "override_submitted", "name": "Override Request Submitted", "channels": ["in_app"],
     "subject_template": "Override request awaiting approval",
     "body_template": "An override request has been submitted and awaits approval."},
    {"slug": "override_approved", "name": "Override Approved", "channels": ["in_app"],
     "subject_template": "Your override request was approved",
     "body_template": "Your override request has been approved."},
    {"slug": "override_denied", "name": "Override Denied", "channels": ["in_app"],
     "subject_template": "Your override request was denied",
     "body_template": "Your override request has been denied."},
    # C5 finance notifications.
    {"slug": "payment_due", "name": "Payment Due", "channels": ["in_app"],
     "subject_template": "Tuition payment due",
     "body_template": "A tuition charge has been issued to your account."},
    {"slug": "installment_reminder", "name": "Installment Reminder", "channels": ["in_app"],
     "subject_template": "Installment reminder",
     "body_template": "You have an upcoming installment on your payment plan."},
    {"slug": "aid_approved", "name": "Financial Aid Approved", "channels": ["in_app"],
     "subject_template": "Your financial aid was approved",
     "body_template": "Your financial aid award has been approved and applied to your account."},
    {"slug": "aid_rejected", "name": "Financial Aid Rejected", "channels": ["in_app"],
     "subject_template": "Financial aid decision",
     "body_template": "Your financial aid application was not approved."},
    {"slug": "hold_applied", "name": "Financial Hold Applied", "channels": ["in_app"],
     "subject_template": "A financial hold was placed on your account",
     "body_template": "A financial hold has been placed; please settle your balance."},
    {"slug": "hold_released", "name": "Financial Hold Released", "channels": ["in_app"],
     "subject_template": "Your financial hold was released",
     "body_template": "A financial hold on your account has been released."},
    # C6 campus-operations notifications.
    {"slug": "book_overdue", "name": "Book Overdue", "channels": ["in_app"],
     "subject_template": "Library book overdue",
     "body_template": "A library book on loan to you is overdue; please return it."},
    {"slug": "room_allocated", "name": "Room Allocated", "channels": ["in_app"],
     "subject_template": "Residence room allocated",
     "body_template": "You have been allocated a residence room."},
    {"slug": "medical_alert", "name": "Medical Alert", "channels": ["in_app"],
     "subject_template": "Medical alert", "body_template": "A medical alert has been raised."},
    {"slug": "counselling_referral", "name": "Counselling Referral", "channels": ["in_app"],
     "subject_template": "Counselling referral",
     "body_template": "A counselling referral has been created."},
    {"slug": "award_received", "name": "Award Received", "channels": ["in_app"],
     "subject_template": "Congratulations on your award",
     "body_template": "You have received an award. Congratulations!"},
    {"slug": "incident_logged", "name": "Incident Logged", "channels": ["in_app"],
     "subject_template": "Incident reported",
     "body_template": "A campus incident has been reported."},
    {"slug": "welfare_alert", "name": "Welfare Alert", "channels": ["in_app"],
     "subject_template": "Welfare case", "body_template": "A student welfare case has been opened."},
    {"slug": "visitor_checkin", "name": "Visitor Check-in", "channels": ["in_app"],
     "subject_template": "Visitor arrived", "body_template": "Your visitor has checked in."},
    {"slug": "gate_pass_approved", "name": "Gate Pass Approved", "channels": ["in_app"],
     "subject_template": "Gate pass approved", "body_template": "Your gate pass has been approved."},
    {"slug": "id_card_issued", "name": "ID Card Issued", "channels": ["in_app"],
     "subject_template": "ID card issued", "body_template": "Your ID card has been issued."},
    {"slug": "lost_item_claimed", "name": "Lost Item Claimed", "channels": ["in_app"],
     "subject_template": "Lost item claimed", "body_template": "A lost item has been claimed."},
    {"slug": "campus_charge_receipt", "name": "Campus Charge Receipt", "channels": ["in_app"],
     "subject_template": "Campus charge receipt",
     "body_template": "A receipt for your campus charge is available."},
    # C7 research notifications.
    {"slug": "proposal_approved", "name": "Proposal Approved", "channels": ["in_app"],
     "subject_template": "Research proposal approved",
     "body_template": "Your research proposal has been approved."},
    {"slug": "ethics_approved", "name": "Ethics Approved", "channels": ["in_app"],
     "subject_template": "Ethics / IRB approval granted",
     "body_template": "Ethics approval has been granted for your research."},
    {"slug": "grant_awarded", "name": "Grant Awarded", "channels": ["in_app"],
     "subject_template": "Grant awarded",
     "body_template": "A research grant has been awarded and funding posted."},
    {"slug": "publication_published", "name": "Publication Published", "channels": ["in_app"],
     "subject_template": "Publication published",
     "body_template": "A research publication has been published."},
    {"slug": "patent_granted", "name": "Patent Granted", "channels": ["in_app"],
     "subject_template": "Patent granted", "body_template": "A patent has been granted."},
    {"slug": "thesis_defended", "name": "Thesis Defended", "channels": ["in_app"],
     "subject_template": "Thesis defended",
     "body_template": "Congratulations — your thesis has been successfully defended."},
    {"slug": "contract_signed", "name": "Research Contract Signed", "channels": ["in_app"],
     "subject_template": "Research contract signed",
     "body_template": "A research contract has been signed."},
    # C8 accreditation & compliance notifications.
    {"slug": "accreditation_granted", "name": "Accreditation Granted", "channels": ["in_app"],
     "subject_template": "Accreditation granted",
     "body_template": "A program has been accredited."},
    {"slug": "compliance_overdue", "name": "Compliance Overdue", "channels": ["in_app"],
     "subject_template": "Compliance requirement overdue",
     "body_template": "A compliance requirement is overdue and needs attention."},
    {"slug": "compliance_met", "name": "Compliance Met", "channels": ["in_app"],
     "subject_template": "Compliance requirement met",
     "body_template": "A compliance requirement has been satisfied."},
]


# ── forms / views ────────────────────────────────────────────────────────────
def _form_for(slug):
    obj = COLLEGE_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = COLLEGE_OBJECTS[slug]
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
        {"label": COLLEGE_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
        for s in slugs]}


COLLEGE_NAV = [
    _nav_group("Academics", ["campus", "academic_year", "term", "academic_calendar_event",
                             "faculty", "department"]),
    _nav_group("Programs & Curriculum", ["program", "specialization", "curriculum",
                                         "curriculum_course"]),
    _nav_group("Courses", ["course", "prerequisite", "course_section", "instructor"]),
    _nav_group("Students", ["student", "program_enrollment"]),
    _nav_group("Registration", ["registration_period", "registration", "registration_hold",
                                "waitlist_entry"]),
    _nav_group("Grades & Assessment", ["grade_scheme", "grade_scale", "assessment",
                                       "assessment_result", "course_result"]),
    _nav_group("Academic Records", ["semester_result", "student_academic_record",
                                    "degree_progress", "transfer_credit",
                                    "graduation_application"]),
    _nav_group("Faculty & Teaching", ["teaching_assignment", "office_hour", "faculty_workload"]),
    _nav_group("Advising", ["advisor_assignment", "advisor_caseload", "advising_session",
                            "advising_note", "academic_hold", "override_request"]),
    _nav_group("Tuition & Billing", ["tuition_category", "tuition_structure", "tuition_charge",
                                     "tuition_adjustment", "student_account", "student_payment"]),
    _nav_group("Financial Aid", ["aid_program", "aid_award", "aid_renewal", "sponsorship",
                                 "student_loan"]),
    _nav_group("Payments & Holds", ["payment_plan", "payment_agreement", "financial_hold"]),
    # C6 campus operations.
    _nav_group("Library & Residence", ["library_book", "book_loan", "residence_room",
                                       "room_allocation"]),
    _nav_group("Transport & Meals", ["transport_route", "transport_subscription", "meal_plan",
                                     "campus_charge"]),
    _nav_group("Health & Counselling", ["medical_profile", "medical_condition", "allergy",
                                        "medication", "vaccination_record", "medical_visit",
                                        "medical_alert", "health_screening",
                                        "counselling_referral", "counselling_session",
                                        "counselling_action_plan"]),
    _nav_group("Activities & Awards", ["student_club", "club_membership", "sport",
                                       "sport_participation", "competition", "competition_entry",
                                       "award", "student_activity"]),
    _nav_group("Safety & Security", ["visitor_log", "gate_pass", "incident_report",
                                     "welfare_case", "lost_and_found", "id_card_request"]),
    # C7 research (scholarly overlay — project execution lives in the Projects app).
    _nav_group("Research Centers & Groups", ["research_center", "research_group",
                                             "research_project", "research_team_member",
                                             "research_student"]),
    _nav_group("Proposals, Grants & Ethics", ["research_proposal", "grant_application", "grant",
                                              "funding_agency", "ethics_approval"]),
    _nav_group("Publications & IP", ["publication", "journal", "conference", "patent",
                                     "intellectual_property"]),
    _nav_group("Theses & Contracts", ["thesis", "research_contract"]),
    # C8 — accreditation & compliance (executive analytics = dashboards via role home, not nav).
    _nav_group("Accreditation & Compliance", ["accreditation_body", "accreditation",
                                              "compliance_requirement", "compliance_record"]),
]


# ── C6 portal grants (reuse the Core Portal engine — student-facing campus services) ──
def _grant(entity_slug, *, create=False, portal_type="student"):
    return {"entity_slug": entity_slug, "portal_type": portal_type, "link_field": "student",
            "can_read": True, "can_create": create, "can_update": False}


COLLEGE_PORTAL_GRANTS = [
    _grant("book_loan"), _grant("room_allocation"), _grant("transport_subscription"),
    _grant("meal_plan"), _grant("campus_charge"), _grant("gate_pass", create=True),
    _grant("id_card_request", create=True), _grant("aid_award"), _grant("tuition_charge"),
    _grant("student_payment"),
    _grant("research_student"),   # C7 — a research student sees their own research record
    # C8 — student self-service (grades/results) + parent/proxy portal (grades + bills), all via the
    # FROZEN Portal engine (portal_grants + portal_type); every query AND-injects link_field=student.
    _grant("course_result"), _grant("semester_result"), _grant("student_academic_record"),
    _grant("tuition_charge", portal_type="parent"),
    _grant("course_result", portal_type="parent"),
    _grant("semester_result", portal_type="parent"),
    _grant("student_payment", portal_type="parent"),
]


# ── C3 documents + grade approval (reuse the Core Document + Approvals engines) ──
# Official transcript = the Core document engine bound to the student, with course results as line
# items (reused; no College PDF/rendering code).
COLLEGE_DOCUMENT_TEMPLATES = [
    {"slug": "official_transcript", "name": "Official Transcript", "entity_slug": "student",
     "page_config": {"title": "Official Academic Transcript", "subtitle": "Student academic record"},
     "blocks": [
         {"type": "field", "label": "Student No", "field": "student_no"},
         {"type": "field", "label": "First Name", "field": "first_name"},
         {"type": "field", "label": "Last Name", "field": "last_name"},
         {"type": "field", "label": "Program", "field": "program"},
     ],
     "line_items": {"entity_slug": "course_result", "relation_field": "student",
                    "columns": ["result_no", "course", "term", "credit_hours",
                                "letter_grade", "grade_points"]}},
    # C4 — faculty profile (reuses the frozen instructor + teaching assignments) + advising summary.
    {"slug": "faculty_profile", "name": "Faculty Profile", "entity_slug": "instructor",
     "page_config": {"title": "Faculty Profile", "subtitle": "Academic staff record"},
     "blocks": [
         {"type": "field", "label": "Employee No", "field": "employee_no"},
         {"type": "field", "label": "Name", "field": "name"},
         {"type": "field", "label": "Rank", "field": "rank"},
         {"type": "field", "label": "Department", "field": "department"},
     ],
     "line_items": {"entity_slug": "teaching_assignment", "relation_field": "instructor",
                    "columns": ["course_section", "term", "role", "load_hours", "status"]}},
    {"slug": "advising_summary", "name": "Advising Summary", "entity_slug": "student",
     "page_config": {"title": "Academic Advising Summary", "subtitle": "Student advising record"},
     "blocks": [
         {"type": "field", "label": "Student No", "field": "student_no"},
         {"type": "field", "label": "First Name", "field": "first_name"},
         {"type": "field", "label": "Last Name", "field": "last_name"},
     ],
     "line_items": {"entity_slug": "advising_session", "relation_field": "student",
                    "columns": ["session_no", "session_date", "mode", "topic", "status"]}},
    # C5 — finance documents (Core Document engine; NO College rendering code).
    {"slug": "fee_statement", "name": "Fee Statement", "entity_slug": "student",
     "page_config": {"title": "Student Fee Statement", "subtitle": "Account statement"},
     "blocks": [
         {"type": "field", "label": "Student No", "field": "student_no"},
         {"type": "field", "label": "First Name", "field": "first_name"},
         {"type": "field", "label": "Last Name", "field": "last_name"},
     ],
     "line_items": {"entity_slug": "tuition_charge", "relation_field": "student",
                    "columns": ["charge_no", "term", "amount", "due_date", "status"]}},
    {"slug": "tuition_invoice", "name": "Tuition Invoice", "entity_slug": "tuition_charge",
     "page_config": {"title": "Tuition Invoice", "subtitle": "{{record.charge_no}}"},
     "blocks": [
         {"type": "field", "label": "Charge No", "field": "charge_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Amount", "field": "amount"},
         {"type": "field", "label": "Due Date", "field": "due_date"},
     ], "line_items": {}},
    {"slug": "financial_aid_letter", "name": "Financial Aid Letter", "entity_slug": "aid_award",
     "page_config": {"title": "Financial Aid Award Letter", "subtitle": "{{record.award_no}}"},
     "blocks": [
         {"type": "field", "label": "Award No", "field": "award_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Aid Type", "field": "aid_type"},
         {"type": "field", "label": "Amount", "field": "amount"},
     ], "line_items": {}},
    {"slug": "sponsorship_letter", "name": "Sponsorship Letter", "entity_slug": "sponsorship",
     "page_config": {"title": "Sponsorship Confirmation", "subtitle": "{{record.sponsorship_no}}"},
     "blocks": [
         {"type": "field", "label": "Sponsorship No", "field": "sponsorship_no"},
         {"type": "field", "label": "Sponsor", "field": "sponsor_name"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Amount", "field": "amount"},
     ], "line_items": {}},
    {"slug": "loan_letter", "name": "Loan Letter", "entity_slug": "student_loan",
     "page_config": {"title": "Student Loan Agreement", "subtitle": "{{record.loan_no}}"},
     "blocks": [
         {"type": "field", "label": "Loan No", "field": "loan_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Principal", "field": "principal_amount"},
         {"type": "field", "label": "Interest Rate", "field": "interest_rate"},
     ], "line_items": {}},
    {"slug": "receipt", "name": "Payment Receipt", "entity_slug": "student_payment",
     "page_config": {"title": "Payment Receipt", "subtitle": "{{record.receipt_no}}"},
     "blocks": [
         {"type": "field", "label": "Receipt No", "field": "receipt_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Amount", "field": "amount"},
         {"type": "field", "label": "Method", "field": "method"},
     ], "line_items": {}},
    # C6 — campus documents (Core Document engine; ID card, award certificate, campus receipt).
    {"slug": "id_card", "name": "Student ID Card", "entity_slug": "id_card_request",
     "page_config": {"title": "Student ID Card", "subtitle": "{{record.request_no}}"},
     "blocks": [
         {"type": "field", "label": "Request No", "field": "request_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Reason", "field": "reason"},
     ], "line_items": {}},
    {"slug": "award_certificate", "name": "Award Certificate", "entity_slug": "award",
     "page_config": {"title": "Certificate of Award", "subtitle": "{{record.award_name}}"},
     "blocks": [
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Award", "field": "award_name"},
         {"type": "field", "label": "Date", "field": "award_date"},
     ], "line_items": {}},
    {"slug": "campus_charge_receipt", "name": "Campus Charge Receipt", "entity_slug": "campus_charge",
     "page_config": {"title": "Campus Charge Receipt", "subtitle": "{{record.charge_no}}"},
     "blocks": [
         {"type": "field", "label": "Charge No", "field": "charge_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Service", "field": "service_type"},
         {"type": "field", "label": "Amount", "field": "amount"},
     ], "line_items": {}},
    # C7 — research documents (Core Document engine).
    {"slug": "research_proposal_document", "name": "Research Proposal",
     "entity_slug": "research_proposal",
     "page_config": {"title": "Research Proposal", "subtitle": "{{record.proposal_no}}"},
     "blocks": [
         {"type": "field", "label": "Proposal No", "field": "proposal_no"},
         {"type": "field", "label": "Title", "field": "title"},
         {"type": "field", "label": "Requested Funding", "field": "requested_funding"},
     ], "line_items": {}},
    {"slug": "ethics_certificate", "name": "Ethics Certificate", "entity_slug": "ethics_approval",
     "page_config": {"title": "Ethics / IRB Approval Certificate", "subtitle": "{{record.protocol_no}}"},
     "blocks": [
         {"type": "field", "label": "Protocol No", "field": "protocol_no"},
         {"type": "field", "label": "Committee", "field": "committee_type"},
         {"type": "field", "label": "Expiry", "field": "expiry_date"},
     ], "line_items": {}},
    {"slug": "grant_award_letter", "name": "Grant Award Letter", "entity_slug": "grant",
     "page_config": {"title": "Grant Award Letter", "subtitle": "{{record.grant_no}}"},
     "blocks": [
         {"type": "field", "label": "Grant No", "field": "grant_no"},
         {"type": "field", "label": "Title", "field": "title"},
         {"type": "field", "label": "Award Amount", "field": "award_amount"},
     ], "line_items": {}},
    {"slug": "patent_certificate", "name": "Patent Certificate", "entity_slug": "patent",
     "page_config": {"title": "Patent Certificate", "subtitle": "{{record.patent_ref}}"},
     "blocks": [
         {"type": "field", "label": "Patent Ref", "field": "patent_ref"},
         {"type": "field", "label": "Title", "field": "title"},
         {"type": "field", "label": "Jurisdiction", "field": "jurisdiction"},
     ], "line_items": {}},
    {"slug": "thesis_certificate", "name": "Thesis Certificate", "entity_slug": "thesis",
     "page_config": {"title": "Thesis / Dissertation Certificate", "subtitle": "{{record.thesis_no}}"},
     "blocks": [
         {"type": "field", "label": "Thesis No", "field": "thesis_no"},
         {"type": "field", "label": "Title", "field": "title"},
         {"type": "field", "label": "Type", "field": "work_type"},
     ], "line_items": {}},
    # C8 — accreditation certificate (Core Document engine).
    {"slug": "accreditation_certificate", "name": "Accreditation Certificate",
     "entity_slug": "accreditation",
     "page_config": {"title": "Certificate of Accreditation", "subtitle": "{{record.accreditation_no}}"},
     "blocks": [
         {"type": "field", "label": "Accreditation No", "field": "accreditation_no"},
         {"type": "field", "label": "Program", "field": "program"},
         {"type": "field", "label": "Award Date", "field": "award_date"},
         {"type": "field", "label": "Expiry Date", "field": "expiry_date"},
     ], "line_items": {}},
]

# Grade approval = the Core Approvals engine (multi-level, quorum) — a submitted grade is approved by
# the Head of Department; on approve it advances to ``approved``, on reject back to ``draft``.
COLLEGE_APPROVALS = [
    {"slug": "grade_approval", "name": "Grade Approval", "entity_slug": "course_result",
     "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "department_head"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "draft"}]},
    # C4 — override-request approval (Head of Department): approve → approved, reject → denied.
    {"slug": "override_approval", "name": "Override Request Approval", "entity_slug": "override_request",
     "trigger_condition_nql": 'status = "pending"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "department_head"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "denied"}]},
    # C5 — finance approvals (Core Approvals engine). Aid/loan/adjustment gate BEFORE the Credit/GL
    # posting workflow fires (the posting workflows key off status="approved").
    {"slug": "aid_approval", "name": "Financial Aid Approval", "entity_slug": "aid_award",
     "trigger_condition_nql": 'status = "requested"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "financial_aid_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    {"slug": "loan_approval", "name": "Student Loan Approval", "entity_slug": "student_loan",
     "trigger_condition_nql": 'status = "applied"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "financial_aid_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    {"slug": "tuition_adjustment_approval", "name": "Tuition Adjustment Approval",
     "entity_slug": "tuition_adjustment", "trigger_condition_nql": 'status = "requested"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "bursar"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    # C6 — gate pass + ID card approvals (Core Approvals engine).
    {"slug": "gate_pass_approval", "name": "Gate Pass Approval", "entity_slug": "gate_pass",
     "trigger_condition_nql": 'status = "pending"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "security_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": []},
    {"slug": "id_card_approval", "name": "ID Card Approval", "entity_slug": "id_card_request",
     "trigger_condition_nql": 'status = "requested"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "campus_services_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": []},
    # C7 — research approvals (Core Approvals engine). Proposal/ethics/grant/contract gate BEFORE
    # posting/lifecycle workflows fire.
    {"slug": "proposal_approval", "name": "Research Proposal Approval",
     "entity_slug": "research_proposal", "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "research_director"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    {"slug": "ethics_review", "name": "Ethics / IRB Review", "entity_slug": "ethics_approval",
     "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "all",
                 "approvers": [{"type": "role", "value": "research_director"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    {"slug": "grant_approval", "name": "Grant Approval", "entity_slug": "grant",
     "trigger_condition_nql": 'status = "applied"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "grants_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "awarded"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    # C8 — compliance record review (Core Approvals engine).
    {"slug": "compliance_review", "name": "Compliance Record Review",
     "entity_slug": "compliance_record", "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "compliance_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "accepted"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
]


# ══ C9: Enterprise hardening — data-integrity validation + SLA response (Rules/SLA engines) ══════
# ADDITIVE guard rails ONLY (new manifest sections; C1–C8 entity/workflow/role/report definitions are
# NOT touched). Mirrors the certified School Phase 1.8 pattern. block_save protects the reused
# GL/Credits/Collections posting paths from zero/negative amounts and guards academic calculations
# from out-of-range values; SLA policies add welfare/safety/turnaround responsiveness governance.
def _block_rule(entity, field, op, val, msg, trigger):
    return {"slug": f"validate_{entity}_{field}_{trigger}",
            "name": f"Validate {entity}.{field}", "entity_slug": entity, "trigger_on": trigger,
            "condition_nql": f"{field} {op} {val}",
            "actions": [{"type": "block_save", "message": msg}], "priority": 10}


# Money fields that post to the financial platform (must be > 0 — protects the GL/Credits/Collections
# postings the C5–C8 workflows fire).
_MONEY_FIELDS = [
    ("tuition_charge", "amount"), ("student_payment", "amount"), ("tuition_adjustment", "amount"),
    ("aid_award", "amount"), ("aid_renewal", "amount"), ("sponsorship", "amount"),
    ("student_loan", "principal_amount"), ("payment_plan", "total_amount"),
    ("campus_charge", "amount"), ("grant", "award_amount"), ("research_contract", "contract_value"),
]

COLLEGE_RULES = [
    _block_rule(e, f, "<=", "0", f"{f.replace('_', ' ').title()} must be greater than zero.", trig)
    for e, f in _MONEY_FIELDS for trig in ("before_create", "before_update")
] + [
    # Academic data integrity — protect GPA/credit calculations from out-of-range values.
    _block_rule("course_result", "grade_points", ">", "4.0", "Grade points cannot exceed 4.0.",
                "before_create"),
    _block_rule("course_result", "grade_points", ">", "4.0", "Grade points cannot exceed 4.0.",
                "before_update"),
    _block_rule("course_result", "credit_hours", "<=", "0",
                "Credit hours must be greater than zero.", "before_create"),
    _block_rule("registration", "credit_hours", "<=", "0",
                "Credit hours must be greater than zero.", "before_create"),
    _block_rule("course_result", "score", ">", "100", "Score cannot exceed 100%.", "before_create"),
    _block_rule("course_result", "score", ">", "100", "Score cannot exceed 100%.", "before_update"),
]


# SLA response-time policies (SLA engine; auto-attached on record.created; wall-clock).
def _sla(slug, name, entity, minutes, warn=80):
    return {"slug": slug, "name": name, "entity_slug": entity, "applies_when_nql": "",
            "targets": [{"metric": "resolution", "target_minutes": minutes,
                         "warning_at_percent": warn, "business_hours_only": False}]}


COLLEGE_SLA_POLICIES = [
    _sla("welfare_case_response", "Welfare Case Response", "welfare_case", 1440),        # 24h
    _sla("incident_response", "Incident Response", "incident_report", 2880),             # 48h
    _sla("medical_alert_response", "Medical Alert Response", "medical_alert", 720),      # 12h
    _sla("ethics_review_turnaround", "Ethics Review Turnaround", "ethics_approval", 20160, 90),  # 14d
    _sla("compliance_turnaround", "Compliance Turnaround", "compliance_requirement", 20160, 90),  # 14d
]


# ── package block ─────────────────────────────────────────────────────────────
def _package_block() -> dict:
    return {
        "slug": "college", "name": "College Management", "version": "1.0.0",
        "author": "Sridhar ERP",
        "description": "Higher-education College Management — academic core (faculties/departments, "
                       "programs/specializations, courses/sections/prerequisites, curriculum, "
                       "instructors) plus Course Registration (periods, holds, waitlist, and "
                       "capacity/credit-limit eligibility enforced declaratively via the Core Guard "
                       "Framework). The second education package; reuses the ERP Core, ships zero "
                       "native code.",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": ["workflow"],
        "requires_capabilities": ["metadata", "dynamic_forms", "views", "workflows",
                                  "reports", "dashboards", "rbac", "notifications",
                                  "numbering", "analytics_kpi", "cross_record_validation",
                                  # C3 — GPA/CGPA/standing/degree-progress = the Core Aggregation
                                  # Framework (CG-2); College writes zero calculation code.
                                  "cross_record_aggregation",
                                  # C5 — all money movement reuses the Core financial platform
                                  # (GL posting + documents); zero package accounting.
                                  "accounting", "documents"],
        "requires_packages": [],
        # instructors ↔ HR employees; research reuses the Projects platform for ALL project
        # execution (tasks/milestones/deliverables/budget/EVM/gantt/resources/timesheets) — a
        # research project references a Projects ``project``; College never duplicates PM.
        "optional_packages": [{"slug": "hr", "version": "*"}, {"slug": "projects", "version": "*"}],
        "conflicts_packages": [],
        "provides_capabilities": ["college", "higher_education", "student_information_system",
                                  "course_registration", "grade_management",
                                  "academic_records", "transcripts", "faculty_management",
                                  "academic_advising", "student_finance", "financial_aid",
                                  "tuition_management", "campus_operations",
                                  "library_management", "residence_life", "student_wellbeing",
                                  "research_management", "research_administration",
                                  "grants_and_publications", "executive_analytics",
                                  "accreditation_management", "compliance_management",
                                  "parent_portal"],
        "migrations": [],
    }


# ── manifest assembly + seed ─────────────────────────────────────────────────
def build_college_manifest() -> dict:
    return {
        "schema_version": 1,
        "package": _package_block(),
        "entities": list(COLLEGE_OBJECTS.values()),
        "forms": [_form_for(s) for s in COLLEGE_OBJECTS],
        "views": [v for s in COLLEGE_OBJECTS for v in _views_for(s)],
        "workflows": COLLEGE_WORKFLOWS,
        "rules": COLLEGE_RULES,                 # C9 — data-integrity validation (Rules engine)
        "sla_policies": COLLEGE_SLA_POLICIES,   # C9 — response-time SLA (SLA engine)
        "reports": COLLEGE_REPORTS,
        "kpis": COLLEGE_KPIS,
        "notification_templates": COLLEGE_NOTIFICATIONS,
        "document_templates": COLLEGE_DOCUMENT_TEMPLATES,
        "approval_processes": COLLEGE_APPROVALS,
        "portal_grants": COLLEGE_PORTAL_GRANTS,
        "roles": COLLEGE_ROLES,
        "dashboards": COLLEGE_DASHBOARDS,
        "navigations": [{"ref": "main", "name": "College Menu", "scope": "app",
                         "tree": COLLEGE_NAV}],
        "home_layouts": [{"ref": "home", "name": "College Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "College Management"}]},
                         *COLLEGE_ROLE_HOMES],
        "applications": [{
            "slug": "college", "name": "College Management", "icon": "GraduationCap",
            "color": "#1d4ed8", "included_entity_slugs": _MAIN,
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in COLLEGE_ROLES], "is_published": True,
        }],
    }


def seed_college_template():
    """Upsert the published, system College SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="college",
        defaults={
            "name": "College Management",
            "category": "Education",
            "description": "Higher-education College Management — academic core (programs, "
                           "departments, courses/sections, curriculum, instructors) on the ERP "
                           "Core. The second education package; ships zero native code.",
            "icon": "GraduationCap", "color": "#1d4ed8", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_college_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
