"""
University Management Solution blueprint — Phase U1 (Academic Core + multi-college hierarchy).

The THIRD education package (after the FROZEN School v2 + College v1). **Pure manifest: ships NO
native code** — it reuses every ERP Core engine exactly as School and College do (metadata/forms/
views, workflow, RBAC, reporting, dashboards, analytics KPI, notifications). University is the FINAL
reuse VALIDATOR before Academic/Campus-Ops/Research Base extraction: it materializes the SAME academic
spine School+College proved, adding University depth **as metadata only**, not new entities.

U1 optimization result (approved gate): **0 University-only master entities.** Everything University
adds is metadata/config on the shared academic spine:
  * Multi-college hierarchy (College/School above Faculty) → ``faculty.parent`` self-lookup +
    ``org_level`` select (NOT a new entity).
  * Double / joint / dual degrees, ECTS/credit system, certificate/diploma award levels →
    ``program`` metadata (``program_type``/``partner_program``/``partner_institution``/
    ``credit_system``; ``degree_type`` already spans certificate→doctorate).
  * Majors / minors → ``specialization.spec_type``.
  * Exchange / international students → ``student`` metadata (``student_type``/``visa_status``/
    ``home_institution``/``sponsor``).

Independent package: ``requires_packages=[]`` (Core only); ``optional_packages`` = hr. No dependency
on School/College/Projects/Research. Later phases (U2 Registration … U9 Hardening) add the rest as
pure-manifest consumers of the frozen platforms.
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


# ── business objects (U1 academic core — the materialized Academic-Base spine) ─────────────────────
UNIVERSITY_OBJECTS: dict[str, dict] = {
    # Academic-structure spine — SAME pattern as School/College (the extraction evidence).
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
        # University credit systems / calendars = term metadata (no new entity).
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

    # Organisation — the MULTI-COLLEGE hierarchy is metadata on faculty (parent + org_level),
    # NOT a new entity: College/School/Faculty are all `faculty` rows at different org_levels.
    "faculty": _entity("faculty", "Academic Unit", "Academic Units", [
        _f("name", "Name", "text", is_required=True),          # e.g. College of Engineering
        _f("code", "Code", "text", is_unique=True),
        _select("org_level", "Level", "college", "school", "faculty"),   # multi-college hierarchy
        _lookup("parent", "Parent Unit", "faculty"),           # self-referencing org tree
        _f("dean", "Dean / Head", "user"),
        _lookup("campus", "Campus", "campus"),
        _f("description", "Description", "textarea"),
    ]),
    "department": _entity("department", "Department", "Departments", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _lookup("faculty", "Academic Unit", "faculty"),
        _f("head", "Head of Department", "user"),
    ]),

    # Programs / degrees — double/joint/dual + ECTS + award levels are ALL program metadata.
    "program": _entity("program", "Program", "Programs", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("degree_type", "Degree Type", "certificate", "diploma", "bachelor",
                "master", "doctorate"),
        # Double / joint / dual degrees = metadata, not a new entity.
        _select("program_type", "Program Type", "single", "double", "joint", "dual"),
        _lookup("partner_program", "Partner Program", "program"),
        _f("partner_institution", "Partner Institution", "text"),
        # Credit system (ECTS/US/CATS) = metadata, not a new entity.
        _select("credit_system", "Credit System", "us_credit", "ects", "cats", "other"),
        _lookup("department", "Department", "department"),
        _f("duration_years", "Duration (Years)", "decimal"),
        _f("total_credits_required", "Total Credits Required", "integer"),
        _f("max_credits_per_term", "Max Credits / Term", "integer"),
        _status("draft", "active", "archived"),
    ]),
    "specialization": _entity("specialization", "Specialization", "Specializations", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("spec_type", "Type", "major", "minor", "concentration"),   # majors/minors metadata
        _lookup("program", "Program", "program"),
        _f("required_credits", "Required Credits", "integer"),
    ]),

    # Courses / sections / prerequisites.
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
        _auto("section_code", "Section Code", "USEC-"),
        _lookup("course", "Course", "course"),
        _lookup("term", "Term", "term"),
        _lookup("instructor", "Instructor", "instructor"),
        _f("capacity", "Capacity", "integer"),
        _f("enrolled_count", "Enrolled", "integer"),
        _f("room", "Room", "text"),
        _f("schedule", "Schedule", "text"),
        _status("open", "closed", "cancelled"),
    ]),

    # Curriculum (program → courses).
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

    # Student master + program enrollment — exchange/international = student metadata (no entity).
    "student": _entity("student", "Student", "Students", [
        _auto("student_no", "Student No", "USTU-"),
        _f("first_name", "First Name", "text", is_required=True),
        _f("last_name", "Last Name", "text"),
        _f("dob", "Date of Birth", "date"),
        _select("gender", "Gender", "female", "male", "other"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("nationality", "Nationality", "text"),
        # Exchange / international student handling = metadata, not a new entity.
        _select("student_type", "Student Type", "regular", "exchange", "international", "visiting"),
        _f("visa_status", "Visa Status", "text"),
        _f("home_institution", "Home Institution", "text"),
        _f("sponsor", "Sponsor", "text"),
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

    # ══ U2: Course Registration (mirrors College C2; consumes the Core Guard Framework) ══════════
    # 4 registration entities matching College C2 + ZERO University-only entities. All higher-ed
    # deltas (exchange/visiting/cross-campus/inter-college/cross-listing) are METADATA on
    # ``registration`` + the existing curriculum_course/course_section pattern — no parallel model.
    "registration_period": _entity(
        "registration_period", "Registration Period", "Registration Periods", [
            _f("name", "Name", "text", is_required=True),
            _lookup("term", "Term", "term"),
            _f("start_date", "Start Date", "date"),
            _f("end_date", "End Date", "date"),
            _status("planning", "open", "closed"),
        ]),
    "registration_hold": _entity("registration_hold", "Registration Hold", "Registration Holds", [
        _lookup("student", "Student", "student"),
        _select("hold_type", "Hold Type", "financial", "advising", "academic", "disciplinary"),
        _f("reason", "Reason", "textarea"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),
    # The registration record — the guard TRIGGER (created ``confirmed``; the eligibility guard
    # re-measures live cross-record state and the false branch reverts to ``waitlisted``). University
    # metadata: enrollment_type (exchange/visiting/audit), host_campus (cross-campus), is_inter_college,
    # and listed_as (cross-listed alternate code) — all fields on THIS entity, not new entities.
    "registration": _entity("registration", "Registration", "Registrations", [
        _auto("registration_no", "Registration No", "UREG-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _lookup("term", "Term", "term"),
        _f("credit_hours", "Credit Hours", "integer"),
        _select("enrollment_type", "Enrollment Type", "regular", "exchange", "visiting", "audit"),
        _lookup("host_campus", "Host Campus", "campus"),   # cross-campus registration (metadata)
        _f("is_inter_college", "Inter-College", "boolean"),
        _f("listed_as", "Listed As", "text"),              # cross-listed alternate code (metadata)
        _f("registered_date", "Registered Date", "date"),
        _status("confirmed", "waitlisted", "dropped", "completed"),
    ]),
    "waitlist_entry": _entity("waitlist_entry", "Waitlist Entry", "Waitlist Entries", [
        _lookup("student", "Student", "student"),
        _lookup("course_section", "Course Section", "course_section"),
        _f("position", "Position", "integer"),
        _f("requested_date", "Requested Date", "date"),
        _status("waiting", "promoted", "expired"),
    ]),

    # ══ U3: Grades / GPA / Transcript (mirrors College C3; consumes CG-2 unchanged; 0 new entities) ══
    # 10 grade-cluster entities matching College C3. University differences (graduate/doctoral/
    # pass-fail/comprehensive/honours/exchange/international-ECTS notation) are ALL metadata/data on
    # these — no additional entity passes the 6-point business-object test.
    "grade_scheme": _entity("grade_scheme", "Grade Scheme", "Grade Schemes", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        # University: multiple schemes as DATA (undergraduate/graduate/doctoral/pass-fail).
        _select("scheme_level", "Level", "undergraduate", "graduate", "doctoral", "pass_fail"),
        _f("description", "Description", "textarea"),
        _f("min_pass_gpa", "Minimum Pass GPA", "decimal"),
        _f("is_default", "Default Scheme", "boolean"),
        _status("draft", "active", "archived"),
    ]),
    "grade_scale": _entity("grade_scale", "Grade Scale", "Grade Scales", [
        _lookup("grade_scheme", "Grade Scheme", "grade_scheme"),
        _f("letter", "Letter Grade", "text", is_required=True),
        _f("grade_points", "Grade Points", "decimal"),
        _f("min_percent", "Min %", "decimal"),
        _f("max_percent", "Max %", "decimal"),
        _f("is_passing", "Passing", "boolean"),
    ]),
    "assessment": _entity("assessment", "Assessment", "Assessments", [
        _f("name", "Name", "text", is_required=True),
        _lookup("course_section", "Course Section", "course_section"),
        # University: comprehensive / qualifying exams = assessment type (metadata).
        _select("assessment_type", "Type", "quiz", "assignment", "midterm", "final",
                "project", "participation", "lab", "comprehensive", "qualifying"),
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
        _f("weight", "Weight (%)", "decimal"),
        _f("weighted_score", "Weighted Score", "formula", is_promoted=False,
           config={"expression": "score * weight"}),
        _status("draft", "published"),
    ]),
    "course_result": _entity("course_result", "Course Result", "Course Results", [
        _auto("result_no", "Result No", "UCR-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("term", "Term", "term"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("score", "Score (%)", "decimal"),
        _f("letter_grade", "Letter Grade", "text"),
        _f("grade_points", "Grade Points", "decimal"),
        # CG-2 canonical credit-weighted quality points (non-promoted formula → JSONB-safe on PG).
        _f("quality_points", "Quality Points", "formula", is_promoted=False,
           config={"expression": "grade_points * credit_hours"}),
        # University: pass/fail research credits = grade_mode metadata (GPA aggregate filters
        # grade_mode="graded"; pass_fail still counts toward earned credits / degree progress).
        _select("grade_mode", "Grade Mode", "graded", "pass_fail", "audit"),
        _f("attempt", "Attempt", "integer"),
        _status("draft", "submitted", "approved", "published", "superseded"),
    ]),
    "semester_result": _entity("semester_result", "Semester Result", "Semester Results", [
        _auto("semester_result_no", "Semester Result No", "USR-"),
        _lookup("student", "Student", "student"),
        _lookup("term", "Term", "term"),
        _lookup("program", "Program", "program"),
        _f("term_credits", "Term Credits", "decimal"),
        _f("term_quality_points", "Term Quality Points", "decimal"),
        _f("term_gpa", "Term GPA", "decimal"),
        _status("draft", "finalized", "published"),
    ]),
    "student_academic_record": _entity(
        "student_academic_record", "Student Academic Record", "Student Academic Records", [
            _auto("academic_record_no", "Academic Record No", "USAR-"),
            _lookup("student", "Student", "student"),
            _lookup("program", "Program", "program"),
            _f("cgpa", "CGPA", "decimal"),
            _f("credits_earned", "Credits Earned", "decimal"),
            _f("credits_attempted", "Credits Attempted", "decimal"),
            _select("academic_standing", "Academic Standing", "new", "good_standing",
                    "deans_list", "probation", "suspension", "dismissed"),
            # University: honours classification (UK/Commonwealth + US) as metadata values.
            _select("honours", "Honours", "none", "first_class", "second_class_upper",
                    "second_class_lower", "cum_laude", "magna_cum_laude", "summa_cum_laude"),
            _f("as_of_date", "As Of", "date"),
            _status("active", "archived"),
        ]),
    "degree_progress": _entity("degree_progress", "Degree Progress", "Degree Progress", [
        _auto("progress_no", "Progress No", "UDP-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _f("credits_completed", "Credits Completed", "decimal"),
        _f("credits_required", "Credits Required", "decimal"),
        _f("progress_percent", "Progress %", "decimal"),
        _f("as_of_date", "As Of", "date"),
        _status("in_progress", "completed"),
    ]),
    "transfer_credit": _entity("transfer_credit", "Transfer Credit", "Transfer Credits", [
        _lookup("student", "Student", "student"),
        _lookup("course", "Equivalent Course", "course"),
        _f("external_course", "External Course", "text"),
        _f("source_institution", "Source Institution", "text"),
        # University: exchange / international transfer sources = metadata.
        _select("source_type", "Source Type", "regular", "exchange", "international"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("grade", "Grade", "text"),
        _status("pending", "approved", "rejected"),
    ]),
    "graduation_application": _entity(
        "graduation_application", "Graduation Application", "Graduation Applications", [
            _auto("application_no", "Application No", "UGRAD-"),
            _lookup("student", "Student", "student"),
            _lookup("program", "Program", "program"),
            _f("expected_grad_date", "Expected Graduation", "date"),
            _status("applied", "under_review", "approved", "conferred", "denied"),
        ]),

    # ══ U4: Faculty · Advising · Graduate Supervision ═══════════════════════════
    # 9 faculty/advising entities matching College C4 (faculty = the U1 `instructor`, reused) + the
    # generic graduate-supervision pair (`graduate_committee` + `graduate_review`). Supervisor/
    # co-supervisor/external-examiner/committee-membership = `advisor_assignment` metadata.
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
    "faculty_workload": _entity("faculty_workload", "Faculty Workload", "Faculty Workloads", [
        _lookup("instructor", "Instructor", "instructor"),
        _lookup("term", "Term", "term"),
        _f("total_load_hours", "Total Load Hours", "decimal"),
        _f("section_count", "Sections", "integer"),
        _f("as_of_date", "As Of", "date"),
        _status("draft", "published"),
    ]),
    # Supervisor / co-supervisor / external-examiner / committee membership = advisor_assignment
    # metadata (advisor_role + committee lookup) — NOT new entities.
    "advisor_assignment": _entity("advisor_assignment", "Advisor Assignment", "Advisor Assignments", [
        _auto("assignment_no", "Assignment No", "UADVA-"),
        _lookup("advisor", "Advisor", "instructor"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _select("advisor_role", "Role", "academic_advisor", "supervisor", "co_supervisor",
                "committee_chair", "committee_member", "external_examiner"),
        _lookup("committee", "Graduate Committee", "graduate_committee"),
        _f("is_external", "External", "boolean"),
        _f("assigned_date", "Assigned Date", "date"),
        _status("active", "ended"),
    ]),
    "advisor_caseload": _entity("advisor_caseload", "Advisor Caseload", "Advisor Caseloads", [
        _lookup("advisor", "Advisor", "instructor"),
        _f("active_advisees", "Active Advisees", "integer"),
        _f("as_of_date", "As Of", "date"),
        _status("active", "archived"),
    ]),
    "advising_session": _entity("advising_session", "Advising Session", "Advising Sessions", [
        _auto("session_no", "Session No", "UADV-"),
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
    "academic_hold": _entity("academic_hold", "Academic Hold", "Academic Holds", [
        _auto("hold_no", "Hold No", "UHOLD-"),
        _lookup("student", "Student", "student"),
        _select("hold_type", "Hold Type", "advising", "academic", "disciplinary", "health", "other"),
        _f("reason", "Reason", "textarea"),
        _f("placed_by", "Placed By", "user"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),
    "override_request": _entity("override_request", "Override Request", "Override Requests", [
        _auto("request_no", "Request No", "UOVR-"),
        _lookup("student", "Student", "student"),
        _lookup("course", "Course", "course"),
        _lookup("course_section", "Course Section", "course_section"),
        _select("request_type", "Type", "prerequisite", "capacity", "credit_overload",
                "time_conflict", "other"),
        _f("reason", "Reason", "textarea"),
        _status("pending", "approved", "denied"),
    ]),

    # Graduate supervision — the ONLY two committee/review entities (6-point rule; specialised
    # committees/defenses = ``committee_type``/``review_type`` metadata, never separate entities).
    "graduate_committee": _entity("graduate_committee", "Graduate Committee", "Graduate Committees", [
        _auto("committee_no", "Committee No", "GCOM-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _select("committee_type", "Type", "thesis", "dissertation", "comprehensive", "proposal"),
        _lookup("chair", "Chair", "instructor"),
        _f("formed_date", "Formed Date", "date"),
        _status("proposed", "approved", "active", "dissolved"),
    ]),
    "graduate_review": _entity("graduate_review", "Graduate Review", "Graduate Reviews", [
        _auto("review_no", "Review No", "GREV-"),
        _lookup("student", "Student", "student"),
        _lookup("graduate_committee", "Committee", "graduate_committee"),
        _select("review_type", "Type", "comprehensive", "proposal_defense", "final_defense",
                "viva", "progress"),
        _f("review_date", "Review Date", "date"),
        _f("external_examiner", "External Examiner", "text"),
        _select("outcome", "Outcome", "pending", "pass", "pass_with_revisions", "fail_resubmit",
                "fail"),
        _status("scheduled", "held", "completed", "cancelled"),
    ]),

    # ══ U5: Finance & Financial Aid (mirrors College C5; consumes the Core Financial Platform) ══════
    # ALL money movement reuses GL/Credits/Collections/Documents via workflow steps — University
    # defines METADATA ONLY. University differences (assistantship/fellowship/loan/fee/installment
    # types, funding sources) = metadata on these entities; 0 new University-only finance entities.
    "tuition_category": _entity("tuition_category", "Tuition Category", "Tuition Categories", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("fee_type", "Fee Type", "tuition", "registration", "laboratory", "library",
                "technology", "activity", "exam", "thesis", "other"),
        _select("frequency", "Frequency", "per_term", "per_year", "per_credit_hour", "one_time"),
        _f("description", "Description", "textarea"),
    ]),
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
    "tuition_charge": _entity("tuition_charge", "Tuition Charge", "Tuition Charges", [
        _auto("charge_no", "Charge No", "UTUI-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _lookup("term", "Term", "term"),
        _lookup("tuition_structure", "Tuition Structure", "tuition_structure"),
        _f("credit_hours", "Credit Hours", "integer"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _status("draft", "issued", "paid", "partial", "overdue", "cancelled"),
    ]),
    "tuition_adjustment": _entity("tuition_adjustment", "Tuition Adjustment", "Tuition Adjustments", [
        _auto("adjustment_no", "Adjustment No", "UTADJ-"),
        _lookup("student", "Student", "student"),
        _lookup("tuition_charge", "Tuition Charge", "tuition_charge"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "applied", "rejected"),
    ]),
    "student_account": _entity("student_account", "Student Account", "Student Accounts", [
        _auto("account_no", "Account No", "UACCT-"),
        _lookup("student", "Student", "student"),
        _lookup("program", "Program", "program"),
        _status("active", "closed"),
    ]),
    "student_payment": _entity("student_payment", "Student Payment", "Student Payments", [
        _auto("receipt_no", "Receipt No", "USRCPT-"),
        _lookup("student", "Student", "student"),
        _lookup("tuition_charge", "Tuition Charge", "tuition_charge"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("payment_date", "Payment Date", "date"),
        _select("method", "Method", "cash", "bank", "card", "online", "cheque", "sponsor"),
        _f("reference", "Reference", "text"),
    ]),
    "aid_program": _entity("aid_program", "Financial Aid Program", "Financial Aid Programs", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        # University: assistantships + fellowships as aid types (metadata).
        _select("aid_type", "Aid Type", "grant", "bursary", "scholarship", "work_study",
                "teaching_assistantship", "research_assistantship", "fellowship", "sponsorship",
                "loan"),
        _f("funding_source", "Funding Source", "text"),
        _f("description", "Description", "textarea"),
        _status("draft", "active", "closed"),
    ]),
    "aid_award": _entity("aid_award", "Aid Award", "Aid Awards", [
        _auto("award_no", "Award No", "UAID-"),
        _lookup("student", "Student", "student"),
        _lookup("aid_program", "Aid Program", "aid_program"),
        _select("aid_type", "Aid Type", "grant", "bursary", "scholarship", "work_study",
                "teaching_assistantship", "research_assistantship", "fellowship"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("stipend_amount", "Stipend Amount", "currency"),   # assistantship/fellowship stipend
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("reason", "Reason", "text"),
        _status("requested", "approved", "awarded", "rejected"),
    ]),
    "aid_renewal": _entity("aid_renewal", "Aid Renewal", "Aid Renewals", [
        _auto("renewal_no", "Renewal No", "UAIDR-"),
        _lookup("aid_award", "Aid Award", "aid_award"),
        _lookup("student", "Student", "student"),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("amount", "Amount", "currency", is_required=True),
        _status("requested", "approved", "renewed", "denied"),
    ]),
    "sponsorship": _entity("sponsorship", "Sponsorship", "Sponsorships", [
        _auto("sponsorship_no", "Sponsorship No", "USPON-"),
        _lookup("student", "Student", "student"),
        _f("sponsor_name", "Sponsor", "text", is_required=True),
        _select("sponsorship_type", "Type", "government", "corporate", "foundation", "embassy",
                "individual"),
        _f("amount", "Amount", "currency", is_required=True),
        _lookup("academic_year", "Academic Year", "academic_year"),
        _f("agreement_ref", "Agreement Ref", "text"),
        _status("requested", "approved", "active", "ended", "rejected"),
    ]),
    "student_loan": _entity("student_loan", "Student Loan", "Student Loans", [
        _auto("loan_no", "Loan No", "ULOAN-"),
        _lookup("student", "Student", "student"),
        _lookup("aid_program", "Aid Program", "aid_program"),
        _select("loan_type", "Loan Type", "federal", "private", "institutional"),
        _f("principal_amount", "Principal", "currency", is_required=True),
        _f("interest_rate", "Interest Rate (%)", "decimal"),
        _f("num_installments", "Installments", "integer"),
        _select("frequency", "Frequency", "monthly", "quarterly", "yearly"),
        _f("start_date", "Repayment Start", "date"),
        _f("disbursement_date", "Disbursement Date", "date"),
        _status("applied", "approved", "disbursed", "repaying", "closed", "rejected"),
    ]),
    "payment_plan": _entity("payment_plan", "Payment Plan", "Payment Plans", [
        _auto("plan_ref", "Plan Ref", "UPPLAN-"),
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
        _auto("agreement_no", "Agreement No", "UPAGR-"),
        _lookup("student", "Student", "student"),
        _lookup("payment_plan", "Payment Plan", "payment_plan"),
        _f("terms", "Terms", "textarea"),
        _f("signed_date", "Signed Date", "date"),
        _status("draft", "active", "breached", "completed"),
    ]),
    "financial_hold": _entity("financial_hold", "Financial Hold", "Financial Holds", [
        _auto("hold_no", "Hold No", "UFHOLD-"),
        _lookup("student", "Student", "student"),
        _f("reason", "Reason", "textarea"),
        _f("amount_outstanding", "Amount Outstanding", "currency"),
        _f("placed_date", "Placed Date", "date"),
        _status("active", "cleared"),
    ]),

    # ══ U6: Campus Operations (mirrors College C6; charges reuse the Financial Platform) ═══════════
    # 33 campus-ops entities matching College C6 + 1 genuinely new object (parking_permit). University
    # differences (residence/medical/counselling/club/transport types) = metadata. Charge-bearing
    # services (library fine, residence/meal/transport/parking fees) → campus_charge → Core GL.
    "campus_charge": _entity("campus_charge", "Campus Charge", "Campus Charges", [
        _auto("charge_no", "Charge No", "UCMP-"),
        _lookup("student", "Student", "student"),
        _select("service_type", "Service", "library_fine", "residence_fee", "meal_plan",
                "transport", "parking", "id_card", "other"),
        _f("amount", "Amount", "currency", is_required=True),
        _f("charge_date", "Charge Date", "date"),
        _f("due_date", "Due Date", "date"),
        _status("draft", "issued", "paid", "cancelled"),
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
        _auto("loan_ref", "Loan Ref", "ULN-"),
        _lookup("library_book", "Book", "library_book"),
        _lookup("student", "Student", "student"),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("return_date", "Return Date", "date"),
        _status("issued", "returned", "overdue", "lost"),
    ]),
    "residence_room": _entity("residence_room", "Residence Room", "Residence Rooms", [
        _f("residence_hall", "Residence Hall", "text", is_required=True),
        _f("room_no", "Room No", "text"),
        # University: residence type = metadata (undergraduate/graduate/married/exchange/international).
        _select("residence_type", "Type", "undergraduate", "graduate", "married",
                "exchange", "international"),
        _f("capacity", "Capacity", "integer"),
        _f("occupied", "Occupied", "integer"),
        _f("resident_advisor", "Resident Advisor", "user"),
    ]),
    "room_allocation": _entity("room_allocation", "Room Allocation", "Room Allocations", [
        _auto("allocation_no", "Allocation No", "URES-"),
        _lookup("student", "Student", "student"),
        _lookup("residence_room", "Room", "residence_room"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("active", "ended"),
    ]),
    "transport_route": _entity("transport_route", "Transport Route", "Transport Routes", [
        _f("name", "Name", "text", is_required=True),
        _f("vehicle_no", "Vehicle No", "text"),
        _f("driver_name", "Driver Name", "text"),
        _select("transport_zone", "Zone", "zone_a", "zone_b", "zone_c", "intercampus"),
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
    # Access/facility permit — ONE GENERIC permit entity (permit_type metadata) covering parking,
    # lab, residence, equipment, etc. — the graduate_committee/graduate_review generalization applied
    # to facility access; prevents future per-facility permit entities. 6-point justified (durable
    # authorization with its own lifecycle; NOT the one-time gate_pass, NOT the campus_charge fee).
    "access_permit": _entity("access_permit", "Access Permit", "Access Permits", [
        _auto("permit_no", "Permit No", "UPERM-"),
        _lookup("student", "Holder", "student"),
        _select("permit_type", "Permit Type", "parking", "lab_access", "residence_access",
                "library_after_hours", "equipment", "gym"),
        _f("resource_ref", "Resource / Zone", "text"),   # parking zone, lab, room, equipment
        _f("reference_detail", "Reference", "text"),      # vehicle reg (parking), asset tag, etc.
        _f("valid_from", "Valid From", "date"),
        _f("valid_to", "Valid To", "date"),
        _status("issued", "active", "expired", "revoked"),
    ]),
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
        _auto("visit_no", "Visit No", "UMV-"),
        _lookup("student", "Student", "student"),
        _select("case_type", "Case Type", "general", "emergency", "chronic", "mental_health",
                "injury", "screening"),
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
    "counselling_referral": _entity(
        "counselling_referral", "Counselling Referral", "Counselling Referrals", [
            _lookup("student", "Student", "student"),
            _f("referred_by", "Referred By", "user"),
            _select("counselling_type", "Type", "academic", "career", "personal",
                    "mental_health", "financial", "crisis"),
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
    "student_club": _entity("student_club", "Club", "Clubs", [
        _f("name", "Name", "text", is_required=True),
        _select("club_category", "Category", "academic", "cultural", "sports", "professional",
                "social", "religious", "political", "service"),
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
    "student_activity": _entity("student_activity", "Student Activity / Event", "Student Activities", [
        _lookup("student", "Student", "student"),
        _f("activity_name", "Activity / Event", "text", is_required=True),
        _f("activity_date", "Date", "date"),
        _f("hours", "Hours", "decimal"),
        _f("activity_type", "Type", "text"),
    ]),
    "visitor_log": _entity("visitor_log", "Visitor Log", "Visitor Log", [
        _auto("visitor_no", "Visitor No", "UVIS-"),
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
        _auto("pass_no", "Pass No", "UGP-"),
        _lookup("student", "Student", "student"),
        _select("pass_type", "Type", "check_in", "check_out", "gate_pass"),
        _f("pass_time", "Time", "datetime"),
        _f("reason", "Reason", "text"),
        _f("authorized_by", "Authorized By", "user"),
        _status("pending", "approved", "used"),
    ]),
    "incident_report": _entity("incident_report", "Incident Report", "Incident Reports", [
        _auto("incident_ref", "Incident Ref", "UINC-"),
        _select("incident_type", "Type", "safety", "security", "property", "medical", "other"),
        _f("incident_date", "Date", "datetime"),
        _f("location", "Location", "text"),
        _f("description", "Description", "textarea"),
        _f("reported_by", "Reported By", "user"),
        _select("severity", "Severity", "low", "medium", "high", "critical"),
        _status("open", "investigating", "closed"),
    ]),
    "welfare_case": _entity("welfare_case", "Student Welfare Case", "Student Welfare Cases", [
        _auto("case_no", "Case No", "UWEL-"),
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
        _auto("request_no", "Request No", "UIDC-"),
        _lookup("student", "Student", "student"),
        _select("reason", "Reason", "new", "replacement", "renewal"),
        _f("request_date", "Request Date", "date"),
        _status("requested", "approved", "issued"),
    ]),

    # ══ U7: Research Administration — an OVERLAY on the frozen Projects platform ═════════════════════
    # Research owns ONLY scholarly administration. It NEVER duplicates academic (student/instructor/
    # committee/review/supervision — those are U1/U4), Projects (project/task/milestone/budget/gantt/
    # timesheet/resource/dependency/risk — the Projects platform), or Financial (GL/Credits/Collections
    # — the Core Financial Platform). Thesis/dissertation supervision + defenses/vivas are ALREADY
    # U4 (graduate_committee + graduate_review); the deposited thesis is a ``publication``. A research
    # student is ``student`` + ``advisor_assignment`` + ``research_team_member`` — no duplicate model.
    "research_center": _entity("research_center", "Research Center", "Research Centers", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("director", "Director", "user"),
        _lookup("faculty", "Academic Unit", "faculty"),
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
    # The research-project OVERLAY — REFERENCES an existing Projects ``project`` (the single PM source
    # of truth). Scholarly fields only; NO tasks/schedule/budget/milestones here — those live on the
    # Projects project. Requires the optional Projects package.
    "research_project": _entity("research_project", "Research Project", "Research Projects", [
        _auto("research_no", "Research No", "URSP-"),
        _lookup("project", "Projects Project", "project"),   # ← the frozen Projects platform project
        _f("title", "Title", "text", is_required=True),
        _lookup("research_center", "Center", "research_center"),
        _lookup("research_group", "Group", "research_group"),
        _f("principal_investigator", "Principal Investigator", "user"),
        _select("research_type", "Type", "basic", "applied", "experimental", "clinical",
                "translational"),
        _status("proposed", "active", "completed", "suspended", "terminated"),
    ]),
    # The SINGLE research-membership entity. A graduate research student = member_type
    # ``graduate_research_student`` (no separate research_student entity; the person is ``student`` +
    # ``advisor_assignment(supervisor)``).
    "research_team_member": _entity(
        "research_team_member", "Research Team Member", "Research Team Members", [
            _lookup("research_project", "Research Project", "research_project"),
            _f("member", "Member", "user"),
            _select("member_type", "Role", "principal_investigator", "co_principal_investigator",
                    "research_staff", "supervisor", "graduate_research_student",
                    "research_assistant", "collaborator"),
            _f("allocation_percent", "Allocation %", "decimal"),
            _status("active", "inactive"),
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
        _auto("proposal_no", "Proposal No", "UPROP-"),
        _f("title", "Title", "text", is_required=True),
        _f("submitted_by", "Submitted By", "user"),
        _lookup("research_center", "Center", "research_center"),
        _lookup("funding_agency", "Funding Agency", "funding_agency"),
        _f("requested_funding", "Requested Funding", "currency"),
        _f("abstract", "Abstract", "textarea"),
        _status("draft", "submitted", "under_review", "approved", "rejected"),
    ]),
    "ethics_approval": _entity("ethics_approval", "Ethics / IRB Approval", "Ethics Approvals", [
        _auto("protocol_no", "Protocol No", "UIRB-"),
        _lookup("research_project", "Research Project", "research_project"),
        # Human/animal/biosafety = committee_type metadata, NOT separate entities.
        _select("committee_type", "Committee", "irb", "iacuc", "ethics_board", "biosafety"),
        _f("submission_date", "Submission Date", "date"),
        _f("decision_date", "Decision Date", "date"),
        _f("expiry_date", "Expiry Date", "date"),
        _status("submitted", "under_review", "approved", "rejected", "expired"),
    ]),
    "grant": _entity("grant", "Grant", "Grants", [
        _auto("grant_no", "Grant No", "UGRT-"),
        _f("title", "Title", "text", is_required=True),
        _lookup("funding_agency", "Funding Agency", "funding_agency"),
        _lookup("research_project", "Research Project", "research_project"),
        _f("award_amount", "Award Amount", "currency", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("applied", "awarded", "active", "closed", "rejected"),
    ]),
    "grant_application": _entity("grant_application", "Grant Application", "Grant Applications", [
        _auto("application_no", "Application No", "UGAPP-"),
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
    # publication_type ``thesis``/``dissertation`` carries the deposited graduate work — no thesis
    # entity (supervision/examination = U4 graduate_committee + graduate_review).
    "publication": _entity("publication", "Publication", "Publications", [
        _auto("publication_no", "Publication No", "UPUB-"),
        _f("title", "Title", "text", is_required=True),
        _select("publication_type", "Type", "journal_article", "conference_paper", "book",
                "book_chapter", "preprint", "technical_report", "thesis", "dissertation"),
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
        _auto("patent_ref", "Patent Ref", "UPAT-"),
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
            _auto("ip_no", "IP No", "UIP-"),
            _f("title", "Title", "text", is_required=True),
            _select("ip_type", "Type", "patent", "copyright", "trademark", "trade_secret",
                    "software", "design"),
            _lookup("research_project", "Research Project", "research_project"),
            _f("owner", "Owner", "text"),
            _f("disclosure_date", "Disclosure Date", "date"),
            _status("disclosed", "protected", "licensed", "expired"),
        ]),
    "research_contract": _entity("research_contract", "Research Contract", "Research Contracts", [
        _auto("contract_no", "Contract No", "URCT-"),
        _f("title", "Title", "text", is_required=True),
        _lookup("research_project", "Research Project", "research_project"),
        _lookup("funding_agency", "Counterparty", "funding_agency"),
        _f("contract_value", "Contract Value", "currency"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _status("draft", "under_negotiation", "signed", "active", "completed", "terminated"),
    ]),

    # ══ U8: Executive Analytics · Accreditation · Compliance · Portals (mirrors College C8) ══════════
    # The ONLY new data objects are accreditation + compliance (genuine institutional records with their
    # own lifecycle/workflows/documents/reports). Everything else in U8 — executive scorecards,
    # institutional KPIs, portals, executive/regulatory/audit-readiness reporting — is CONFIG over the
    # frozen Dashboard/Analytics/Reporting/Portal/Audit platforms (no new entity). Institutional vs
    # programmatic vs international accreditation = ``body_type``/``scope`` metadata; federal/state/
    # accreditor/data-privacy compliance = ``category`` metadata — NOT separate entities.
    "accreditation_body": _entity("accreditation_body", "Accreditation Body", "Accreditation Bodies", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("body_type", "Type", "regional", "national", "programmatic", "international"),
        _f("country", "Country", "text"),
        _f("website", "Website", "url"),
    ]),
    "accreditation": _entity("accreditation", "Accreditation", "Accreditations", [
        _auto("accreditation_no", "Accreditation No", "UACR-"),
        _lookup("accreditation_body", "Body", "accreditation_body"),
        _lookup("program", "Program", "program"),
        _f("scope", "Scope", "text"),                      # institutional vs programmatic = metadata
        _f("award_date", "Award Date", "date"),
        _f("expiry_date", "Expiry Date", "date"),
        _f("cycle_years", "Cycle (Years)", "integer"),
        _status("applied", "self_study", "site_visit", "accredited", "probation", "denied",
                "expired"),
    ]),
    "compliance_requirement": _entity(
        "compliance_requirement", "Compliance Requirement", "Compliance Requirements", [
            _auto("requirement_no", "Requirement No", "UCMP-"),
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

_MAIN = list(UNIVERSITY_OBJECTS.keys())


# ── workflows (reuse the workflow engine — mirror College C1 lifecycles) ──────────────────────────
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created", trigger_config=None):
    return {"slug": slug, "name": name, "trigger_type": trigger_type,
            "trigger_config": trigger_config or {}, "entity_slug": entity_slug,
            "steps": steps, "edges": edges}


def _gq(entity, **eq):
    """NQL AST query for a guard rule (single entity + equality conditions). Values may be
    ``{{record.*}}`` templates — the Core ``action_guard`` executor resolves them (reusing
    ``resolve_value``) before calling GuardService. Identical pattern to College C2."""
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    return {"entity": entity, "filter": {"op": "and", "conditions": conds}}


def _agg_measure(name, entity, aggregate, field=None, **eq):
    """One ``action_aggregate`` measure (single entity + equality filter). Identical pattern to
    College C3 — ALL GPA/CGPA/credit calculation is the Core Aggregation Framework (CG-2, unchanged);
    University writes zero calculation logic. Pass/fail exclusion = an added ``grade_mode`` filter."""
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    m = {"name": name, "query": {"entity": entity, "filter": {"op": "and", "conditions": conds}},
         "aggregate": aggregate}
    if field:
        m["field"] = field
    return m


# U2 eligibility guards (config only — ALL enforcement is the reusable Core Guard Framework, CG-1).
# Registration is created ``confirmed``, so each guard measures live cross-record state WITH the new
# record included (hence ``lte``); the false branch reverts an ineligible record to ``waitlisted``.
# Capacity + credit-limit thresholds are DYNAMIC (read from course_section.capacity /
# program.max_credits_per_term — U1 fields). Cross-campus/inter-college/exchange are recorded as
# metadata and do NOT change the eligibility rules.
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


UNIVERSITY_WORKFLOWS = [
    # Program enrollment created → mark the student enrolled + notify.
    _wf("program_enrollment_activated", "Program Enrollment Activated", "program_enrollment", [
        {"slug": "enroll", "step_type": "action_update_record", "name": "Mark Student Enrolled",
         "is_entry": True, "config": {"entity_slug": "student",
             "record_id": "{{record.student}}", "data": {"status": "enrolled"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "enrollment_confirmed"}},
    ], [{"source": "enroll", "target": "notify"}]),

    # Program activated → notify the department.
    _wf("program_activated", "Program Activated", "program", [
        {"slug": "check", "step_type": "condition", "name": "Active?", "is_entry": True,
         "config": {"condition_nql": 'status = "active"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "program_activated"}},
    ], [{"source": "check", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ U2 — Registration eligibility (consumer of the Core Guard Framework, unchanged from C2) ══
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

    # U2 — Drop notifies (a dropped registration frees its seat; the capacity guard re-measures live).
    _wf("registration_dropped", "Registration Dropped", "registration", [
        {"slug": "dropped", "step_type": "condition", "name": "Dropped?", "is_entry": True,
         "config": {"condition_nql": 'status = "dropped"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "registration_dropped"}},
    ], [{"source": "dropped", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # U2 — Hold cleared → notify the student they may register.
    _wf("registration_hold_cleared", "Registration Hold Cleared", "registration_hold", [
        {"slug": "cleared", "step_type": "condition", "name": "Cleared?", "is_entry": True,
         "config": {"condition_nql": 'status = "cleared"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "registration_hold_cleared"}},
    ], [{"source": "cleared", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ U3 — Grades / GPA (pure-manifest consumers of the Aggregation Framework, CG-2 unchanged) ══
    # Grade book: course_result.score = Σ(score×weight)/Σ(weight) over published assessment results.
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

    # Grade entry: resolve grade_points from the grade_scale (fires when letter_grade is set).
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

    # Grade lifecycle notifications.
    _wf("grade_published", "Grade Published", "course_result", [
        {"slug": "c", "step_type": "condition", "name": "Published?", "is_entry": True,
         "config": {"condition_nql": 'status = "published"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "grade_published"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Term GPA = Σ(quality_points)/Σ(credit_hours) over PUBLISHED, GRADED results (pass/fail excluded
    # via the added grade_mode filter) — CG-2 unchanged, University handles pass/fail by config.
    _wf("compute_term_gpa", "Compute Term GPA", "semester_result", [
        {"slug": "gpa", "step_type": "action_aggregate", "name": "Aggregate Term GPA",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("qp", "course_result", "sum", "quality_points",
                             student="{{record.student}}", term="{{record.term}}",
                             status="published", grade_mode="graded"),
                _agg_measure("cr", "course_result", "sum", "credit_hours",
                             student="{{record.student}}", term="{{record.term}}",
                             status="published", grade_mode="graded"),
            ],
            "computes": [{"name": "term_gpa", "expression": "qp / cr if cr > 0 else 0"}],
            "target": {"entity_slug": "semester_result", "record_id": "{{record.id}}",
                       "data": {"term_gpa": "{{agg.term_gpa}}", "term_credits": "{{agg.cr}}",
                                "term_quality_points": "{{agg.qp}}"}}}},
    ], []),

    # CGPA over all PUBLISHED, GRADED results → student_academic_record; fires the standing + honours
    # ladders via field_changed(cgpa).
    _wf("compute_cgpa", "Compute CGPA", "student_academic_record", [
        {"slug": "cgpa", "step_type": "action_aggregate", "name": "Aggregate CGPA",
         "is_entry": True, "config": {
            "measures": [
                _agg_measure("tqp", "course_result", "sum", "quality_points",
                             student="{{record.student}}", status="published", grade_mode="graded"),
                _agg_measure("tcr", "course_result", "sum", "credit_hours",
                             student="{{record.student}}", status="published", grade_mode="graded"),
            ],
            "computes": [{"name": "cgpa", "expression": "tqp / tcr if tcr > 0 else 0"}],
            "target": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                       "data": {"cgpa": "{{agg.cgpa}}", "credits_earned": "{{agg.tcr}}"}}}},
    ], []),

    # Academic standing ladder (reuse College C3 pattern; field_changed(cgpa), loop-free).
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

    # University: HONOURS classification ladder (UK/Commonwealth degree class from CGPA) — same
    # field_changed(cgpa) condition-ladder pattern as standing; watches cgpa so writing honours never
    # re-fires it. Genuine University addition expressed entirely as workflow config (no new entity).
    _wf("university_honours_classification", "Honours Classification", "student_academic_record", [
        {"slug": "c_first", "step_type": "condition", "name": "First Class?", "is_entry": True,
         "config": {"condition_nql": "cgpa >= 3.7"}},
        {"slug": "set_first", "step_type": "action_update_record", "name": "Set First Class",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"honours": "first_class"}}},
        {"slug": "c_upper", "step_type": "condition", "name": "Second Upper?",
         "config": {"condition_nql": "cgpa >= 3.3"}},
        {"slug": "set_upper", "step_type": "action_update_record", "name": "Set Second Upper",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"honours": "second_class_upper"}}},
        {"slug": "c_lower", "step_type": "condition", "name": "Second Lower?",
         "config": {"condition_nql": "cgpa >= 3.0"}},
        {"slug": "set_lower", "step_type": "action_update_record", "name": "Set Second Lower",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"honours": "second_class_lower"}}},
        {"slug": "set_none", "step_type": "action_update_record", "name": "Set No Honours",
         "config": {"entity_slug": "student_academic_record", "record_id": "{{record.id}}",
                    "data": {"honours": "none"}}},
    ], [
        {"source": "c_first", "target": "set_first", "condition_label": "true"},
        {"source": "c_first", "target": "c_upper", "condition_label": "false"},
        {"source": "c_upper", "target": "set_upper", "condition_label": "true"},
        {"source": "c_upper", "target": "c_lower", "condition_label": "false"},
        {"source": "c_lower", "target": "set_lower", "condition_label": "true"},
        {"source": "c_lower", "target": "set_none", "condition_label": "false"},
    ], trigger_type="field_changed", trigger_config={"fields": ["cgpa"]}),

    # Degree audit: Σ published credits (incl. passed pass/fail) vs the program requirement.
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

    # Graduation conferred → transcript + notify.
    _wf("graduation_conferred", "Graduation Conferred", "graduation_application", [
        {"slug": "c", "step_type": "condition", "name": "Conferred?", "is_entry": True,
         "config": {"condition_nql": 'status = "conferred"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Official Transcript",
         "config": {"template_slug": "official_transcript"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "graduation_conferred"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # ══ U4 — Faculty / Advising / Graduate Supervision (CG-2 aggregates + lifecycles) ══
    # Faculty teaching load = Σ(load_hours)+count(sections) over active teaching assignments (CG-2).
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

    # Advisor caseload = count(active advisor assignments) for the advisor (CG-2).
    _wf("compute_advisor_caseload", "Compute Advisor Caseload", "advisor_caseload", [
        {"slug": "count", "step_type": "action_aggregate", "name": "Aggregate Caseload",
         "is_entry": True, "config": {
            "measures": [_agg_measure("n", "advisor_assignment", "count",
                                      advisor="{{record.advisor}}", status="active")],
            "target": {"entity_slug": "advisor_caseload", "record_id": "{{record.id}}",
                       "data": {"active_advisees": "{{agg.n}}"}}}},
    ], []),

    # Advisor assigned / advising session scheduled → notify.
    _wf("advisor_assigned", "Advisor Assigned", "advisor_assignment", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "advisor_assigned"}},
    ], []),
    _wf("advising_session_scheduled", "Advising Session Scheduled", "advising_session", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "advising_scheduled"}},
    ], []),

    # Academic hold placed / cleared → notify.
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

    # Override submitted → notify approver; approved/denied → notify student.
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

    # Graduate committee approved → appointment letter + notify.
    _wf("graduate_committee_approved", "Graduate Committee Approved", "graduate_committee", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Committee Appointment",
         "config": {"template_slug": "committee_appointment"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "committee_approved"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # Graduate review completed (comprehensive/defense/viva/progress) → result letter + notify.
    _wf("graduate_review_completed", "Graduate Review Completed", "graduate_review", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Review Result",
         "config": {"template_slug": "review_result"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "review_completed"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),

    # ══ U5 — Finance (ALL money movement delegates to the Core Financial Platform) ══
    # Tuition charge issued → GL (Dr A/R 1100, Cr Revenue 4100) → notify → invoice.
    _wf("tuition_charge_posting", "Tuition Charge Posting", "tuition_charge", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receivable",
         "is_entry": True, "config": {
             "source_module": "university", "source_ref": "{{record.charge_no}}",
             "memo": "Tuition charge {{record.charge_no}}",
             "account_debit": "1100", "account_credit": "4100", "amount": "{{record.amount}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "payment_due"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Tuition Invoice",
         "config": {"template_slug": "tuition_invoice"}},
    ], [{"source": "post", "target": "notify"}, {"source": "notify", "target": "doc"}]),

    # Student payment received → GL (Dr Cash 1000, Cr A/R 1100) → receipt.
    _wf("student_payment_posting", "Student Payment Posting", "student_payment", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receipt",
         "is_entry": True, "config": {
             "source_module": "university", "source_ref": "{{record.receipt_no}}",
             "memo": "Student receipt {{record.receipt_no}}",
             "account_debit": "1000", "account_credit": "1100", "amount": "{{record.amount}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Receipt",
         "config": {"template_slug": "receipt"}},
    ], [{"source": "post", "target": "doc"}]),

    # Tuition adjustment approved → credit (Credits engine).
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

    # Aid award approved (grants/scholarships/assistantships/fellowships) → scholarship credit → letter.
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

    # Aid renewal approved → scholarship credit.
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

    # Sponsorship approved → sponsorship credit → letter.
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

    # Student loan disbursed → GL (Dr A/R 1100, Cr Cash 1000) + repayment schedule (Collections).
    _wf("student_loan_disburse", "Disburse Student Loan", "student_loan", [
        {"slug": "check", "step_type": "condition", "name": "Disbursed?", "is_entry": True,
         "config": {"condition_nql": 'status = "disbursed"'}},
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Disbursement",
         "config": {"source_module": "university", "source_ref": "{{record.loan_no}}",
                    "memo": "Loan disbursement {{record.loan_no}}",
                    "account_debit": "1100", "account_credit": "1000",
                    "amount": "{{record.principal_amount}}"}},
        {"slug": "plan", "step_type": "action_create_installment_plan", "name": "Repayment Schedule",
         "config": {"total_amount": "{{record.principal_amount}}",
                    "num_installments": "{{record.num_installments}}",
                    "frequency": "{{record.frequency}}", "start_date": "{{record.start_date}}",
                    "subject_ref": "{{record.student}}",
                    "source_document_ref": "{{record.loan_no}}", "external_ref": "{{record.loan_no}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Loan Letter",
         "config": {"template_slug": "loan_letter"}},
    ], [{"source": "check", "target": "post", "condition_label": "true"},
        {"source": "post", "target": "plan"}, {"source": "plan", "target": "doc"}],
        trigger_type="record_updated"),

    # Payment plan approved → due schedule (Collections) → activate → notify.
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
                    "source_document_ref": "{{record.plan_ref}}", "external_ref": "{{record.plan_ref}}"}},
        {"slug": "mark", "step_type": "action_set_field", "name": "Activate",
         "config": {"field": "status", "value": "active"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "installment_reminder"}},
    ], [{"source": "check", "target": "plan", "condition_label": "true"},
        {"source": "plan", "target": "mark"}, {"source": "mark", "target": "notify"}],
        trigger_type="record_updated"),

    # Financial hold placed → REUSE the frozen U2 registration_hold (hold_type=financial) so the U2
    # eligibility guard blocks registration → notify. Zero new blocking logic.
    _wf("financial_hold_placed", "Financial Hold Placed", "financial_hold", [
        {"slug": "active", "step_type": "condition", "name": "Active?", "is_entry": True,
         "config": {"condition_nql": 'status = "active"'}},
        {"slug": "reg_hold", "step_type": "action_create_record", "name": "Create Registration Hold",
         "config": {"entity_slug": "registration_hold",
                    "data": {"student": "{{record.student}}", "hold_type": "financial",
                             "reason": "{{record.reason}}", "status": "active"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "hold_applied"}},
    ], [{"source": "active", "target": "reg_hold", "condition_label": "true"},
        {"source": "reg_hold", "target": "notify"}]),

    # Financial hold cleared → notify.
    _wf("financial_hold_cleared", "Financial Hold Cleared", "financial_hold", [
        {"slug": "c", "step_type": "condition", "name": "Cleared?", "is_entry": True,
         "config": {"condition_nql": 'status = "cleared"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "hold_released"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Graduation finance check — a guard on graduation approval: an active financial hold reverts it
    # to review (reuses the Core Guard Framework).
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

    # ══ U6 — Campus Operations (mirror College C6; charges reuse the Financial Platform) ══
    _wf("campus_charge_posting", "Campus Charge Posting", "campus_charge", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Charge",
         "is_entry": True, "config": {
             "source_module": "university", "source_ref": "{{record.charge_no}}",
             "memo": "Campus charge {{record.charge_no}}",
             "account_debit": "1100", "account_credit": "4100", "amount": "{{record.amount}}"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Receipt",
         "config": {"template_slug": "campus_charge_receipt"}},
    ], [{"source": "post", "target": "doc"}]),
    _wf("book_overdue_notice", "Book Overdue Notice", "book_loan", [
        {"slug": "c", "step_type": "condition", "name": "Overdue?", "is_entry": True,
         "config": {"condition_nql": 'status = "overdue"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "book_overdue"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("room_allocated", "Room Allocated", "room_allocation", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "room_allocated"}},
    ], []),
    _wf("access_permit_issued", "Access Permit Issued", "access_permit", [
        {"slug": "c", "step_type": "condition", "name": "Active?", "is_entry": True,
         "config": {"condition_nql": 'status = "active"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "permit_issued"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("medical_alert_raised", "Medical Alert Raised", "medical_alert", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "medical_alert"}},
    ], []),
    _wf("counselling_referral_created", "Counselling Referral", "counselling_referral", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Counsellor",
         "is_entry": True, "config": {"template_slug": "counselling_referral"}},
    ], []),
    _wf("award_granted", "Award Granted", "award", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "is_entry": True, "config": {"template_slug": "award_received"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Award Certificate",
         "config": {"template_slug": "award_certificate"}},
    ], [{"source": "notify", "target": "doc"}]),
    _wf("incident_logged", "Incident Logged", "incident_report", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Security",
         "is_entry": True, "config": {"template_slug": "incident_logged"}},
    ], []),
    _wf("welfare_case_opened", "Welfare Case Opened", "welfare_case", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Welfare Lead",
         "is_entry": True, "config": {"template_slug": "welfare_alert"}},
    ], []),
    _wf("visitor_checked_in", "Visitor Checked In", "visitor_log", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Host",
         "is_entry": True, "config": {"template_slug": "visitor_checkin"}},
    ], []),
    _wf("gate_pass_approved", "Gate Pass Approved", "gate_pass", [
        {"slug": "c", "step_type": "condition", "name": "Approved?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "gate_pass_approved"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("id_card_issued", "ID Card Issued", "id_card_request", [
        {"slug": "c", "step_type": "condition", "name": "Issued?", "is_entry": True,
         "config": {"condition_nql": 'status = "issued"'}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "ID Card",
         "config": {"template_slug": "id_card"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Student",
         "config": {"template_slug": "id_card_issued"}},
    ], [{"source": "c", "target": "doc", "condition_label": "true"},
        {"source": "doc", "target": "notify"}], trigger_type="record_updated"),
    _wf("lost_item_claimed", "Lost Item Claimed", "lost_and_found", [
        {"slug": "c", "step_type": "condition", "name": "Claimed?", "is_entry": True,
         "config": {"condition_nql": 'status = "claimed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "lost_item_claimed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ U7 — Research Administration (overlay; Documents/Notifications + the Core Financial Platform;
    # grant BUDGET/EXPENSES stay on the Projects project — never a research budget) ══
    # Research proposal approved → approval document + notify (the PI then creates a Projects project
    # and a thin research_project overlay against it).
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

    # Grant awarded → POST funding to GL (Dr A/R 1100 from agency, Cr Revenue 4100) via the Core
    # Financial Platform → award letter → notify. Grant BUDGET/EXPENSES live on the Projects project.
    _wf("grant_awarded", "Grant Awarded", "grant", [
        {"slug": "c", "step_type": "condition", "name": "Awarded?", "is_entry": True,
         "config": {"condition_nql": 'status = "awarded"'}},
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Grant Funding",
         "config": {"source_module": "university", "source_ref": "{{record.grant_no}}",
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

    # Research contract signed → notify.
    _wf("research_contract_signed", "Research Contract Signed", "research_contract", [
        {"slug": "c", "step_type": "condition", "name": "Signed?", "is_entry": True,
         "config": {"condition_nql": 'status = "signed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "contract_signed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ U8 — Accreditation & Compliance lifecycles (reuse Workflow / Documents / Notifications) ══
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
UNIVERSITY_ROLES = [
    _role("university_administrator", "University Administrator",
          "Full access to the university solution.", [(None, _FULL + ["admin"])]),
    _role("registrar", "Registrar", "Students, program enrollment, sections, and registration.",
          [("student", _FULL), ("program_enrollment", _FULL), ("course_section", _FULL),
           ("program", ["read"]), ("course", ["read"]), ("curriculum", ["read"]),
           ("term", ["read", "update"]), ("academic_calendar_event", _FULL),
           # U2 registration.
           ("registration", _FULL), ("registration_period", _FULL),
           ("registration_hold", _FULL), ("waitlist_entry", _FULL),
           # U3 grades / records.
           ("course_result", _FULL), ("semester_result", _FULL),
           ("student_academic_record", _FULL), ("degree_progress", _FULL),
           ("transfer_credit", _FULL), ("graduation_application", _FULL),
           ("grade_scheme", ["read"]), ("grade_scale", ["read"]),
           # U4 faculty admin.
           ("teaching_assignment", ["read"]), ("advisor_assignment", ["read"]),
           ("academic_hold", ["read", "update"]), ("override_request", _FULL)]),
    _role("academic_advisor", "Academic Advisor",
          "Advises students; places holds; supervises and reviews graduate students.",
          [("student", ["read"]), ("registration", ["read"]), ("waitlist_entry", ["read"]),
           ("registration_hold", _FULL), ("program_enrollment", ["read"]),
           # U4 advising + graduate supervision.
           ("advisor_assignment", _FULL), ("advisor_caseload", ["read"]),
           ("advising_session", _FULL), ("advising_note", _FULL), ("academic_hold", _FULL),
           ("override_request", ["read", "update"]), ("graduate_committee", ["read", "update"]),
           ("graduate_review", _FULL)]),
    _role("graduate_school_officer", "Graduate School Officer",
          "Manages graduate committees, supervision and review/defense milestones.",
          [("graduate_committee", _FULL), ("graduate_review", _FULL),
           ("advisor_assignment", _FULL), ("student", ["read"]), ("program", ["read"]),
           ("instructor", ["read"])]),
    # U5 finance roles.
    _role("bursar", "Bursar / Finance Officer",
          "Owns tuition, charges, payments, plans, finance holds and finance reporting.",
          [("tuition_category", _FULL), ("tuition_structure", _FULL), ("tuition_charge", _FULL),
           ("tuition_adjustment", _FULL), ("student_account", _FULL), ("student_payment", _FULL),
           ("payment_plan", _FULL), ("payment_agreement", _FULL), ("financial_hold", _FULL),
           ("aid_award", ["read"]), ("sponsorship", ["read"]),
           ("student_loan", ["read", "update"]), ("student", ["read"]),
           ("program", ["read"]), ("term", ["read"])]),
    _role("financial_aid_officer", "Financial Aid Officer",
          "Owns aid programs, awards, renewals, assistantships, sponsorships and student loans.",
          [("aid_program", _FULL), ("aid_award", _FULL), ("aid_renewal", _FULL),
           ("sponsorship", _FULL), ("student_loan", _FULL), ("student", ["read"]),
           ("tuition_charge", ["read"]), ("student_account", ["read"]),
           ("financial_hold", ["read"])]),
    _role("dean", "Dean", "Academic-unit oversight across programs and departments.",
          [(None, ["read", "export"]), ("faculty", ["read", "update"]),
           ("department", ["read", "update"])]),
    _role("department_head", "Head of Department",
          "Department courses, sections, instructors, curriculum, grade schemes and grade approval.",
          [("course", _FULL), ("prerequisite", _FULL), ("course_section", _FULL),
           ("instructor", _FULL), ("curriculum", _FULL), ("curriculum_course", _FULL),
           ("program", ["read", "update"]), ("specialization", _FULL),
           ("department", ["read"]), ("student", ["read"]),
           # U3 — owns the grading policy + approves submitted grades.
           ("grade_scheme", _FULL), ("grade_scale", _FULL),
           ("assessment", ["read"]), ("assessment_result", ["read"]),
           ("course_result", ["read", "update", "export"]),
           # U4 — manages teaching assignments/workload + approves overrides.
           ("teaching_assignment", _FULL), ("office_hour", ["read"]),
           ("faculty_workload", ["read"]), ("override_request", _FULL),
           ("advisor_assignment", ["read"])]),
    _role("instructor", "Instructor", "Assigned sections, grade book and grade entry.",
          [("course_section", ["read"]), ("course", ["read"]), ("student", ["read"]),
           ("program_enrollment", ["read"]),
           # U3 — instructors build the grade book and enter grades.
           ("assessment", _FULL), ("assessment_result", _FULL),
           ("course_result", ["create", "read", "update"]),
           ("grade_scheme", ["read"]), ("grade_scale", ["read"]),
           # U4 — faculty see assignments/workload, keep office hours, advise & supervise.
           ("teaching_assignment", ["read"]), ("office_hour", _FULL),
           ("faculty_workload", ["read"]), ("advising_session", ["create", "read", "update"]),
           ("advising_note", ["create", "read", "update"]),
           ("graduate_committee", ["read"]), ("graduate_review", ["read", "update"])]),
    # U6 campus-operations roles.
    _role("campus_services_officer", "Campus Services Officer",
          "Library, residence, transport, access permits, meals, ID cards, lost & found, charges.",
          [("library_book", _FULL), ("book_loan", _FULL), ("residence_room", _FULL),
           ("room_allocation", _FULL), ("transport_route", _FULL),
           ("transport_subscription", _FULL), ("access_permit", _FULL), ("meal_plan", _FULL),
           ("id_card_request", _FULL), ("lost_and_found", _FULL), ("campus_charge", _FULL),
           ("student", ["read"])]),
    _role("campus_health_officer", "Campus Health & Counselling Officer",
          "Campus health center + counselling (confidential records).",
          [("medical_profile", _FULL), ("medical_condition", _FULL), ("allergy", _FULL),
           ("medication", _FULL), ("vaccination_record", _FULL), ("medical_visit", _FULL),
           ("medical_alert", _FULL), ("health_screening", _FULL),
           ("counselling_referral", _FULL), ("counselling_session", _FULL),
           ("counselling_action_plan", _FULL), ("student", ["read"])]),
    _role("activities_coordinator", "Activities Coordinator",
          "Clubs, sports, competitions, events, awards and student activities.",
          [("student_club", _FULL), ("club_membership", _FULL), ("sport", _FULL),
           ("sport_participation", _FULL), ("competition", _FULL), ("competition_entry", _FULL),
           ("award", _FULL), ("student_activity", _FULL), ("student", ["read"])]),
    _role("security_officer", "Campus Security Officer",
          "Visitor management, gate passes, access permits, incidents, welfare and lost & found.",
          [("visitor_log", _FULL), ("gate_pass", _FULL), ("access_permit", ["read", "update"]),
           ("incident_report", _FULL), ("welfare_case", _FULL), ("lost_and_found", _FULL),
           ("student", ["read"])]),
    # U7 research-administration roles.
    _role("research_director", "Research Director",
          "Owns research centers/groups/projects, proposals, ethics, grants, outputs and IP.",
          [("research_center", _FULL), ("research_group", _FULL), ("research_project", _FULL),
           ("research_team_member", _FULL), ("funding_agency", _FULL), ("research_proposal", _FULL),
           ("ethics_approval", _FULL), ("grant", _FULL), ("grant_application", _FULL),
           ("journal", _FULL), ("conference", _FULL), ("publication", _FULL), ("patent", _FULL),
           ("intellectual_property", _FULL), ("research_contract", _FULL),
           ("project", ["read"]), ("student", ["read"]), ("instructor", ["read"])]),
    _role("principal_investigator", "Principal Investigator",
          "Leads a research project overlay: team, proposals, outputs and IP for their project.",
          [("research_project", ["read", "update"]), ("research_team_member", _FULL),
           ("research_proposal", _FULL), ("grant_application", ["read", "create", "update"]),
           ("ethics_approval", ["read", "create", "update"]), ("publication", _FULL),
           ("patent", _FULL), ("intellectual_property", _FULL), ("grant", ["read"]),
           ("research_contract", ["read"]), ("journal", ["read"]), ("conference", ["read"]),
           ("project", ["read"]), ("student", ["read"])]),
    _role("research_officer", "Research Officer",
          "Research-office administration: agencies, grants, ethics and contracts records.",
          [("funding_agency", _FULL), ("grant", _FULL), ("grant_application", _FULL),
           ("ethics_approval", _FULL), ("research_contract", _FULL), ("research_proposal", ["read"]),
           ("research_project", ["read"]), ("publication", ["read"]), ("patent", ["read"]),
           ("intellectual_property", ["read"])]),
    # U8 — executive + compliance roles (read-across for institutional analytics; accreditation/
    # compliance owners).
    _role("president", "President / Vice-Chancellor",
          "Institution-wide executive read access + accreditation oversight.",
          [(None, ["read", "export"]), ("accreditation", ["read", "update"]),
           ("accreditation_body", ["read"])]),
    _role("compliance_officer", "Compliance Officer",
          "Accreditation and institutional compliance management.",
          [("accreditation_body", _FULL), ("accreditation", _FULL),
           ("compliance_requirement", _FULL), ("compliance_record", _FULL)]),
]


# ── reports + dashboards + KPIs (reuse reporting + analytics) ─────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


UNIVERSITY_REPORTS = [
    _report("academic_units_report", "Academic Units", "faculty", "pivot"),
    _report("programs_report", "Programs", "program", "pivot"),
    _report("courses_report", "Courses", "course", "pivot"),
    _report("sections_report", "Course Sections", "course_section", "pivot"),
    _report("enrollment_report", "Program Enrollment", "program_enrollment", "pivot"),
    _report("instructors_report", "Instructors", "instructor", "pivot"),
    _report("curriculum_report", "Curriculum", "curriculum_course", "pivot"),
    _report("student_roster_report", "Student Roster", "student"),
    # U2 registration reports.
    _report("registrations_report", "Registrations", "registration", "pivot"),
    _report("holds_report", "Registration Holds", "registration_hold", "pivot"),
    _report("waitlist_report", "Waitlist", "waitlist_entry"),
    # U3 academic reports.
    _report("course_results_report", "Course Results", "course_result", "pivot"),
    _report("semester_results_report", "Semester Results", "semester_result", "pivot"),
    _report("gpa_distribution_report", "GPA Distribution", "student_academic_record", "pivot"),
    _report("academic_standing_report", "Academic Standing", "student_academic_record", "pivot"),
    _report("honours_report", "Honours Classification", "student_academic_record", "pivot"),
    _report("degree_progress_report", "Degree Progress", "degree_progress", "pivot"),
    _report("transfer_credits_report", "Transfer Credits", "transfer_credit", "pivot"),
    _report("transcript_report", "Student Transcript", "course_result"),
    # U4 faculty / advising / graduate-supervision reports.
    _report("teaching_assignments_report", "Teaching Assignments", "teaching_assignment", "pivot"),
    _report("faculty_workload_report", "Faculty Workload", "faculty_workload", "pivot"),
    _report("advisor_assignments_report", "Advisor Assignments", "advisor_assignment", "pivot"),
    _report("advising_sessions_report", "Advising Sessions", "advising_session", "pivot"),
    _report("academic_holds_report", "Academic Holds", "academic_hold", "pivot"),
    _report("override_requests_report", "Override Requests", "override_request", "pivot"),
    _report("graduate_committees_report", "Graduate Committees", "graduate_committee", "pivot"),
    _report("graduate_reviews_report", "Graduate Reviews", "graduate_review", "pivot"),
    # U5 finance reports.
    _report("tuition_collection_report", "Tuition Collection", "student_payment", "pivot"),
    _report("outstanding_balance_report", "Outstanding Balance", "tuition_charge", "pivot"),
    _report("financial_aid_report", "Financial Aid", "aid_award", "pivot"),
    _report("assistantships_report", "Assistantships & Fellowships", "aid_award", "pivot"),
    _report("sponsorship_report", "Sponsorships", "sponsorship", "pivot"),
    _report("student_loans_report", "Student Loans", "student_loan", "pivot"),
    _report("aging_report", "Aging", "tuition_charge", "pivot"),
    _report("financial_holds_report", "Financial Holds", "financial_hold", "pivot"),
    # U6 campus-operations reports.
    _report("book_loans_report", "Book Loans", "book_loan", "pivot"),
    _report("residence_occupancy_report", "Residence Occupancy", "room_allocation", "pivot"),
    _report("access_permits_report", "Access Permits", "access_permit", "pivot"),
    _report("medical_visits_report", "Medical Visits", "medical_visit", "pivot"),
    _report("counselling_report", "Counselling Referrals", "counselling_referral", "pivot"),
    _report("activities_report", "Student Activities & Events", "student_activity", "pivot"),
    _report("incidents_report", "Incident Reports", "incident_report", "pivot"),
    _report("meal_plans_report", "Meal Plans", "meal_plan", "pivot"),
    _report("campus_charges_report", "Campus Charges", "campus_charge", "pivot"),
    # U7 research reports.
    _report("research_projects_report", "Research Projects", "research_project", "pivot"),
    _report("research_proposals_report", "Research Proposals", "research_proposal", "pivot"),
    _report("grants_report", "Grants", "grant", "pivot"),
    _report("publications_report", "Publications", "publication", "pivot"),
    _report("patents_report", "Patents & IP", "patent", "pivot"),
    _report("ethics_approvals_report", "Ethics Approvals", "ethics_approval", "pivot"),
    _report("research_contracts_report", "Research Contracts", "research_contract", "pivot"),
    # U8 executive / accreditation / compliance reports (Reporting engine — pivot/CSV/XLSX/PDF).
    _report("accreditation_report", "Accreditation Status", "accreditation", "pivot"),
    _report("compliance_report", "Compliance Requirements", "compliance_requirement", "pivot"),
    _report("compliance_records_report", "Compliance Records", "compliance_record", "pivot"),
]


def _kpi(code, name, category, nql_source, *, aggregate="count", value_field="",
         direction="higher_better", unit=""):
    return {"code": code, "name": name, "category": category, "source_type": "nql",
            "nql_source": nql_source, "aggregate": aggregate, "value_field": value_field,
            "direction": direction, "unit": unit}


UNIVERSITY_KPIS = [
    _kpi("active_programs", "Active Programs", "academic", 'FROM program WHERE status = "active"'),
    _kpi("total_courses", "Total Courses", "academic", "FROM course"),
    _kpi("enrolled_students", "Enrolled Students", "academic",
         'FROM student WHERE status = "enrolled"'),
    _kpi("international_students", "International Students", "academic",
         'FROM student WHERE student_type = "international"'),
    _kpi("open_sections", "Open Sections", "operations", 'FROM course_section WHERE status = "open"'),
    _kpi("active_instructors", "Active Instructors", "operations",
         'FROM instructor WHERE status = "active"'),
    # U2 registration KPIs.
    _kpi("confirmed_registrations", "Confirmed Registrations", "academic",
         'FROM registration WHERE status = "confirmed"'),
    _kpi("waitlisted_registrations", "Waitlisted Registrations", "operations",
         'FROM registration WHERE status = "waitlisted"', direction="lower_better"),
    _kpi("active_holds", "Active Registration Holds", "operations",
         'FROM registration_hold WHERE status = "active"', direction="lower_better"),
    _kpi("exchange_registrations", "Exchange Registrations", "academic",
         'FROM registration WHERE enrollment_type = "exchange"'),
    # U3 academic-performance KPIs (avg CGPA reuses the analytics avg aggregate).
    _kpi("average_cgpa", "Average CGPA", "academic", "FROM student_academic_record",
         aggregate="avg", value_field="cgpa", direction="higher_better", unit="GPA"),
    _kpi("deans_list_students", "Dean's List Students", "academic",
         'FROM student_academic_record WHERE academic_standing = "deans_list"'),
    _kpi("first_class_honours", "First-Class Honours", "academic",
         'FROM student_academic_record WHERE honours = "first_class"'),
    _kpi("probation_students", "Students on Probation", "academic",
         'FROM student_academic_record WHERE academic_standing = "probation"',
         direction="lower_better"),
    _kpi("published_results", "Published Course Results", "operations",
         'FROM course_result WHERE status = "published"'),
    _kpi("pending_grade_approvals", "Grades Awaiting Approval", "operations",
         'FROM course_result WHERE status = "submitted"', direction="lower_better"),
    # U4 faculty / advising / graduate-supervision KPIs.
    _kpi("active_teaching_assignments", "Active Teaching Assignments", "operations",
         'FROM teaching_assignment WHERE status = "active"'),
    _kpi("average_teaching_load", "Average Teaching Load", "operations",
         "FROM faculty_workload", aggregate="avg", value_field="total_load_hours", unit="hrs"),
    _kpi("average_advisor_caseload", "Average Advisor Caseload", "operations",
         "FROM advisor_caseload", aggregate="avg", value_field="active_advisees"),
    _kpi("active_academic_holds", "Active Academic Holds", "operations",
         'FROM academic_hold WHERE status = "active"', direction="lower_better"),
    _kpi("active_graduate_committees", "Active Graduate Committees", "academic",
         'FROM graduate_committee WHERE status = "active"'),
    _kpi("scheduled_graduate_reviews", "Scheduled Graduate Reviews", "academic",
         'FROM graduate_review WHERE status = "scheduled"'),
    # U5 finance KPIs (single-aggregate; ratio/grouped metrics = reports).
    _kpi("tuition_revenue", "Tuition Revenue", "finance", "FROM tuition_charge",
         aggregate="sum", value_field="amount", unit="currency"),
    _kpi("total_collected", "Total Collected", "finance", "FROM student_payment",
         aggregate="sum", value_field="amount", unit="currency"),
    _kpi("aid_distribution", "Financial Aid Distributed", "finance",
         'FROM aid_award WHERE status = "awarded"', aggregate="sum", value_field="amount",
         unit="currency"),
    _kpi("assistantship_awards", "Assistantship Awards", "finance",
         'FROM aid_award WHERE aid_type = "research_assistantship"'),
    _kpi("loan_exposure", "Loan Exposure", "finance",
         'FROM student_loan WHERE status = "disbursed"', aggregate="sum",
         value_field="principal_amount", direction="lower_better", unit="currency"),
    _kpi("active_financial_holds", "Active Financial Holds", "finance",
         'FROM financial_hold WHERE status = "active"', direction="lower_better"),
    # U6 campus-operations KPIs.
    _kpi("books_on_loan", "Books on Loan", "operations",
         'FROM book_loan WHERE status = "issued"'),
    _kpi("active_room_allocations", "Active Room Allocations", "operations",
         'FROM room_allocation WHERE status = "active"'),
    _kpi("active_access_permits", "Active Access Permits", "operations",
         'FROM access_permit WHERE status = "active"'),
    _kpi("active_medical_alerts", "Active Medical Alerts", "operations",
         'FROM medical_alert WHERE severity = "critical"', direction="lower_better"),
    _kpi("open_counselling_referrals", "Open Counselling Referrals", "operations",
         'FROM counselling_referral WHERE status = "open"'),
    _kpi("open_incidents", "Open Incidents", "operations",
         'FROM incident_report WHERE status = "open"', direction="lower_better"),
    _kpi("active_meal_plans", "Active Meal Plans", "operations",
         'FROM meal_plan WHERE status = "active"'),
    # U7 research KPIs.
    _kpi("active_research_projects", "Active Research Projects", "research",
         'FROM research_project WHERE status = "active"'),
    _kpi("research_income", "Research Income", "research",
         'FROM grant WHERE status = "awarded"', aggregate="sum", value_field="award_amount",
         unit="currency"),
    _kpi("active_grants", "Active Grants", "research", 'FROM grant WHERE status = "active"'),
    _kpi("publications_count", "Publications", "research",
         'FROM publication WHERE status = "published"'),
    _kpi("patents_granted", "Patents Granted", "research",
         'FROM patent WHERE status = "granted"'),
    _kpi("pending_ethics_reviews", "Pending Ethics Reviews", "operations",
         'FROM ethics_approval WHERE status = "under_review"', direction="lower_better"),
    # U8 executive / institutional KPIs (Analytics engine; scorecards group existing + these).
    _kpi("active_accreditations", "Active Accreditations", "executive",
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


UNIVERSITY_DASHBOARDS = [
    {"slug": "executive_dashboard", "name": "Executive Dashboard", "is_default": True, "widgets": [
        _w("metric_card", "Active Programs", 0, 0, 3, 2),
        _w("metric_card", "Enrolled Students", 3, 0, 3, 2),
        _w("metric_card", "International Students", 6, 0, 3, 2),
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
        _w("report", "Academic Units", 0, 0, 4, 4, report_slug="academic_units_report"),
        _w("report", "Programs", 4, 0, 4, 4, report_slug="programs_report"),
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
        _w("metric_card", "First-Class Honours", 6, 0, 3, 2),
        _w("metric_card", "Students on Probation", 9, 0, 3, 2),
        _w("report", "GPA Distribution", 0, 2, 6, 4, report_slug="gpa_distribution_report"),
        _w("report", "Honours Classification", 6, 2, 6, 4, report_slug="honours_report"),
        _w("report", "Degree Progress", 0, 6, 12, 4, report_slug="degree_progress_report"),
    ]},
    {"slug": "faculty_dashboard", "name": "Faculty Dashboard", "widgets": [
        _w("metric_card", "Active Teaching Assignments", 0, 0, 4, 2),
        _w("metric_card", "Average Teaching Load", 4, 0, 4, 2),
        _w("metric_card", "Average Advisor Caseload", 8, 0, 4, 2),
        _w("report", "Teaching Assignments", 0, 2, 6, 4, report_slug="teaching_assignments_report"),
        _w("report", "Advisor Assignments", 6, 2, 6, 4, report_slug="advisor_assignments_report"),
    ]},
    {"slug": "graduate_school_dashboard", "name": "Graduate School", "widgets": [
        _w("metric_card", "Active Graduate Committees", 0, 0, 4, 2),
        _w("metric_card", "Scheduled Graduate Reviews", 4, 0, 4, 2),
        _w("report", "Graduate Committees", 0, 2, 6, 4, report_slug="graduate_committees_report"),
        _w("report", "Graduate Reviews", 6, 2, 6, 4, report_slug="graduate_reviews_report"),
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
    {"slug": "financial_aid_dashboard", "name": "Financial Aid", "widgets": [
        _w("metric_card", "Aid Distributed", 0, 0, 4, 2),
        _w("metric_card", "Assistantship Awards", 4, 0, 4, 2),
        _w("metric_card", "Loan Exposure", 8, 0, 4, 2),
        _w("report", "Financial Aid", 0, 2, 6, 4, report_slug="financial_aid_report"),
        _w("report", "Assistantships & Fellowships", 6, 2, 6, 4, report_slug="assistantships_report"),
    ]},
    {"slug": "campus_services_dashboard", "name": "Campus Services", "widgets": [
        _w("metric_card", "Books on Loan", 0, 0, 3, 2),
        _w("metric_card", "Active Room Allocations", 3, 0, 3, 2),
        _w("metric_card", "Active Access Permits", 6, 0, 3, 2),
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
        _w("report", "Access Permits", 6, 2, 6, 4, report_slug="access_permits_report"),
    ]},
    {"slug": "research_dashboard", "name": "Research Dashboard", "widgets": [
        _w("metric_card", "Active Research Projects", 0, 0, 3, 2),
        _w("metric_card", "Research Income", 3, 0, 3, 2),
        _w("metric_card", "Publications", 6, 0, 3, 2),
        _w("metric_card", "Patents Granted", 9, 0, 3, 2),
        _w("report", "Research Projects", 0, 2, 6, 4, report_slug="research_projects_report"),
        _w("report", "Grants", 6, 2, 6, 4, report_slug="grants_report"),
        _w("report", "Publications", 0, 6, 12, 4, report_slug="publications_report"),
    ]},
    # U8 — executive scorecard (Dashboard runtime; metric cards over existing + new KPIs) + risk board.
    {"slug": "executive_scorecard", "name": "Executive Scorecard", "widgets": [
        _w("metric_card", "Enrolled Students", 0, 0, 3, 2),
        _w("metric_card", "Active Programs", 3, 0, 3, 2),
        _w("metric_card", "Average CGPA", 6, 0, 3, 2),
        _w("metric_card", "Tuition Revenue", 9, 0, 3, 2),
        _w("metric_card", "Research Income", 0, 2, 3, 2),
        _w("metric_card", "Active Accreditations", 3, 2, 3, 2),
        _w("metric_card", "Overdue Compliance Items", 6, 2, 3, 2),
        _w("metric_card", "Active Financial Holds", 9, 2, 3, 2),
        _w("report", "Program Enrollment", 0, 4, 6, 4, report_slug="enrollment_report"),
        _w("report", "Accreditation Status", 6, 4, 6, 4, report_slug="accreditation_report"),
    ]},
    {"slug": "risk_dashboard", "name": "Institutional Risk & Compliance", "widgets": [
        _w("metric_card", "Open Compliance Items", 0, 0, 4, 2),
        _w("metric_card", "Overdue Compliance Items", 4, 0, 4, 2),
        _w("metric_card", "Active Accreditations", 8, 0, 4, 2),
        _w("report", "Compliance Requirements", 0, 2, 6, 4, report_slug="compliance_report"),
        _w("report", "Accreditation Status", 6, 2, 6, 4, report_slug="accreditation_report"),
    ]},
]

_ROLE_HOME = [
    ("university_administrator", "executive_dashboard"),
    ("registrar", "registrar_dashboard"),
    ("dean", "academic_dashboard"),
    ("department_head", "academic_dashboard"),
    ("instructor", "academic_dashboard"),
    ("academic_advisor", "registration_dashboard"),
    ("research_director", "research_dashboard"),
    ("president", "executive_scorecard"),
    ("compliance_officer", "risk_dashboard"),
]

_DASH_NAMES = {d["slug"]: d["name"] for d in UNIVERSITY_DASHBOARDS}
UNIVERSITY_ROLE_HOMES = [
    {"ref": f"home_{rs}", "name": _DASH_NAMES.get(ds, "Home"), "role_slug": rs,
     "widgets": [{"type": "dashboard", "title": _DASH_NAMES.get(ds, "Home"),
                  "config": {"dashboard_slug": ds}}]}
    for rs, ds in _ROLE_HOME
]


UNIVERSITY_NOTIFICATIONS = [
    {"slug": "enrollment_confirmed", "name": "Enrollment Confirmed", "channels": ["in_app"],
     "subject_template": "Enrollment confirmed",
     "body_template": "You are enrolled in your program."},
    {"slug": "program_activated", "name": "Program Activated", "channels": ["in_app"],
     "subject_template": "Program activated", "body_template": "A program is now active."},
    # U2 registration notifications.
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
    # U3 grade + graduation notifications.
    {"slug": "grade_published", "name": "Grade Published", "channels": ["in_app"],
     "subject_template": "Your grade is published",
     "body_template": "A course grade has been published to your record."},
    {"slug": "graduation_conferred", "name": "Graduation Conferred", "channels": ["in_app"],
     "subject_template": "Congratulations — degree conferred",
     "body_template": "Your degree has been conferred. Congratulations, graduate!"},
    # U4 faculty / advising / graduate-supervision notifications.
    {"slug": "advisor_assigned", "name": "Advisor Assigned", "channels": ["in_app"],
     "subject_template": "You have a new academic advisor",
     "body_template": "An academic advisor/supervisor has been assigned to you."},
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
    {"slug": "committee_approved", "name": "Committee Approved", "channels": ["in_app"],
     "subject_template": "Graduate committee approved",
     "body_template": "Your graduate committee has been approved."},
    {"slug": "review_completed", "name": "Graduate Review Completed", "channels": ["in_app"],
     "subject_template": "Graduate review completed",
     "body_template": "A graduate review/defense has been completed."},
    # U5 finance notifications.
    {"slug": "payment_due", "name": "Payment Due", "channels": ["in_app"],
     "subject_template": "Tuition payment due",
     "body_template": "A tuition charge has been issued to your account."},
    {"slug": "installment_reminder", "name": "Installment Reminder", "channels": ["in_app"],
     "subject_template": "Installment reminder",
     "body_template": "You have an upcoming installment on your payment plan."},
    {"slug": "aid_approved", "name": "Financial Aid Approved", "channels": ["in_app"],
     "subject_template": "Your financial aid was approved",
     "body_template": "Your financial aid award has been approved and applied to your account."},
    {"slug": "hold_applied", "name": "Financial Hold Applied", "channels": ["in_app"],
     "subject_template": "A financial hold was placed on your account",
     "body_template": "A financial hold has been placed; please settle your balance."},
    {"slug": "hold_released", "name": "Financial Hold Released", "channels": ["in_app"],
     "subject_template": "Your financial hold was released",
     "body_template": "A financial hold on your account has been released."},
    # U6 campus-operations notifications.
    {"slug": "book_overdue", "name": "Book Overdue", "channels": ["in_app"],
     "subject_template": "Library book overdue",
     "body_template": "A library book on loan to you is overdue; please return it."},
    {"slug": "room_allocated", "name": "Room Allocated", "channels": ["in_app"],
     "subject_template": "Residence room allocated",
     "body_template": "You have been allocated a residence room."},
    {"slug": "permit_issued", "name": "Access Permit Issued", "channels": ["in_app"],
     "subject_template": "Access permit issued",
     "body_template": "An access permit has been issued to you."},
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
    # U7 research notifications.
    {"slug": "proposal_approved", "name": "Research Proposal Approved", "channels": ["in_app"],
     "subject_template": "Your research proposal was approved",
     "body_template": "A research proposal has been approved; you may set up the project."},
    {"slug": "ethics_approved", "name": "Ethics Approved", "channels": ["in_app"],
     "subject_template": "Ethics / IRB approval granted",
     "body_template": "An ethics/IRB protocol has been approved."},
    {"slug": "grant_awarded", "name": "Grant Awarded", "channels": ["in_app"],
     "subject_template": "Grant awarded",
     "body_template": "A research grant has been awarded and the funding posted."},
    {"slug": "publication_published", "name": "Publication Published", "channels": ["in_app"],
     "subject_template": "Publication published",
     "body_template": "A research publication has been marked as published."},
    {"slug": "patent_granted", "name": "Patent Granted", "channels": ["in_app"],
     "subject_template": "Patent granted",
     "body_template": "A patent has been granted."},
    {"slug": "contract_signed", "name": "Research Contract Signed", "channels": ["in_app"],
     "subject_template": "Research contract signed",
     "body_template": "A research contract has been signed."},
    # U8 accreditation & compliance notifications.
    {"slug": "accreditation_granted", "name": "Accreditation Granted", "channels": ["in_app"],
     "subject_template": "Accreditation granted",
     "body_template": "An accreditation has been granted."},
    {"slug": "compliance_overdue", "name": "Compliance Overdue", "channels": ["in_app"],
     "subject_template": "Compliance requirement overdue",
     "body_template": "A compliance requirement is overdue and needs attention."},
    {"slug": "compliance_met", "name": "Compliance Met", "channels": ["in_app"],
     "subject_template": "Compliance requirement met",
     "body_template": "A compliance requirement has been met."},
]


# ── U3 documents + grade approval (reuse the Core Document + Approvals engines) ──
UNIVERSITY_DOCUMENT_TEMPLATES = [
    {"slug": "official_transcript", "name": "Official Transcript", "entity_slug": "student",
     "page_config": {"title": "Official Academic Transcript",
                     "subtitle": "Higher-education transcript (credit / GPA; ECTS notation where "
                                 "the program's credit system is ECTS)"},
     "blocks": [
         {"type": "field", "label": "Student No", "field": "student_no"},
         {"type": "field", "label": "First Name", "field": "first_name"},
         {"type": "field", "label": "Last Name", "field": "last_name"},
         {"type": "field", "label": "Program", "field": "program"},
     ],
     "line_items": {"entity_slug": "course_result", "relation_field": "student",
                    "columns": ["result_no", "course", "term", "credit_hours",
                                "letter_grade", "grade_points"]}},
]

UNIVERSITY_APPROVALS = [
    {"slug": "grade_approval", "name": "Grade Approval", "entity_slug": "course_result",
     "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "department_head"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "draft"}]},
]


# ── U4 documents + approvals (reuse the Core Document + Approvals engines) ──
UNIVERSITY_DOCUMENT_TEMPLATES += [
    {"slug": "committee_appointment", "name": "Committee Appointment",
     "entity_slug": "graduate_committee",
     "page_config": {"title": "Graduate Committee Appointment", "subtitle": "{{record.committee_no}}"},
     "blocks": [
         {"type": "field", "label": "Committee No", "field": "committee_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Type", "field": "committee_type"},
         {"type": "field", "label": "Chair", "field": "chair"},
     ], "line_items": {}},
    {"slug": "review_result", "name": "Graduate Review Result", "entity_slug": "graduate_review",
     "page_config": {"title": "Graduate Review Result", "subtitle": "{{record.review_no}}"},
     "blocks": [
         {"type": "field", "label": "Review No", "field": "review_no"},
         {"type": "field", "label": "Student", "field": "student"},
         {"type": "field", "label": "Type", "field": "review_type"},
         {"type": "field", "label": "Outcome", "field": "outcome"},
     ], "line_items": {}},
]

UNIVERSITY_APPROVALS += [
    {"slug": "override_approval", "name": "Override Request Approval",
     "entity_slug": "override_request", "trigger_condition_nql": 'status = "pending"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "department_head"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "denied"}]},
    {"slug": "graduate_committee_approval", "name": "Graduate Committee Approval",
     "entity_slug": "graduate_committee", "trigger_condition_nql": 'status = "proposed"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "graduate_school_officer"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "dissolved"}]},
]


# ── U5 finance documents + approvals (reuse the Core Document + Approvals engines) ──
def _fdoc(slug, name, entity, subtitle_field, fields):
    return {"slug": slug, "name": name, "entity_slug": entity,
            "page_config": {"title": name, "subtitle": "{{record." + subtitle_field + "}}"},
            "blocks": [{"type": "field", "label": lbl, "field": f} for lbl, f in fields],
            "line_items": {}}


UNIVERSITY_DOCUMENT_TEMPLATES += [
    {"slug": "fee_statement", "name": "Fee Statement", "entity_slug": "student",
     "page_config": {"title": "Student Fee Statement", "subtitle": "Account statement"},
     "blocks": [{"type": "field", "label": "Student No", "field": "student_no"},
                {"type": "field", "label": "First Name", "field": "first_name"},
                {"type": "field", "label": "Last Name", "field": "last_name"}],
     "line_items": {"entity_slug": "tuition_charge", "relation_field": "student",
                    "columns": ["charge_no", "term", "amount", "due_date", "status"]}},
    _fdoc("tuition_invoice", "Tuition Invoice", "tuition_charge", "charge_no",
          [("Charge No", "charge_no"), ("Student", "student"), ("Amount", "amount"),
           ("Due Date", "due_date")]),
    _fdoc("financial_aid_letter", "Financial Aid Letter", "aid_award", "award_no",
          [("Award No", "award_no"), ("Student", "student"), ("Aid Type", "aid_type"),
           ("Amount", "amount")]),
    _fdoc("sponsorship_letter", "Sponsorship Letter", "sponsorship", "sponsorship_no",
          [("Sponsorship No", "sponsorship_no"), ("Sponsor", "sponsor_name"),
           ("Student", "student"), ("Amount", "amount")]),
    _fdoc("loan_letter", "Loan Letter", "student_loan", "loan_no",
          [("Loan No", "loan_no"), ("Student", "student"), ("Principal", "principal_amount"),
           ("Type", "loan_type")]),
    _fdoc("receipt", "Payment Receipt", "student_payment", "receipt_no",
          [("Receipt No", "receipt_no"), ("Student", "student"), ("Amount", "amount"),
           ("Method", "method")]),
]

UNIVERSITY_APPROVALS += [
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
]


# ── U6 campus documents + approvals (reuse the Core Document + Approvals engines) ──
UNIVERSITY_DOCUMENT_TEMPLATES += [
    _fdoc("id_card", "Student ID Card", "id_card_request", "request_no",
          [("Request No", "request_no"), ("Student", "student"), ("Reason", "reason")]),
    _fdoc("award_certificate", "Award Certificate", "award", "award_name",
          [("Student", "student"), ("Award", "award_name"), ("Date", "award_date")]),
    _fdoc("campus_charge_receipt", "Campus Charge Receipt", "campus_charge", "charge_no",
          [("Charge No", "charge_no"), ("Student", "student"), ("Service", "service_type"),
           ("Amount", "amount")]),
]

UNIVERSITY_APPROVALS += [
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
]


# ── U7 research documents + approvals (reuse the Core Document + Approvals engines) ──
UNIVERSITY_DOCUMENT_TEMPLATES += [
    _fdoc("research_proposal_document", "Research Proposal Approval", "research_proposal",
          "proposal_no", [("Proposal No", "proposal_no"), ("Title", "title"),
                          ("Submitted By", "submitted_by"), ("Requested", "requested_funding")]),
    _fdoc("ethics_certificate", "Ethics / IRB Certificate", "ethics_approval", "protocol_no",
          [("Protocol No", "protocol_no"), ("Committee", "committee_type"),
           ("Decision Date", "decision_date"), ("Expiry", "expiry_date")]),
    _fdoc("grant_award_letter", "Grant Award Letter", "grant", "grant_no",
          [("Grant No", "grant_no"), ("Title", "title"), ("Amount", "award_amount"),
           ("Start", "start_date")]),
    _fdoc("patent_certificate", "Patent Certificate", "patent", "patent_ref",
          [("Patent Ref", "patent_ref"), ("Title", "title"), ("Grant Date", "grant_date"),
           ("Jurisdiction", "jurisdiction")]),
    _fdoc("research_contract_document", "Research Contract", "research_contract", "contract_no",
          [("Contract No", "contract_no"), ("Title", "title"), ("Value", "contract_value"),
           ("Start", "start_date")]),
]

# ── U8 accreditation documents (reuse the Core Document engine) ──
UNIVERSITY_DOCUMENT_TEMPLATES += [
    _fdoc("accreditation_certificate", "Accreditation Certificate", "accreditation",
          "accreditation_no", [("Accreditation No", "accreditation_no"), ("Scope", "scope"),
                               ("Award Date", "award_date"), ("Expiry", "expiry_date")]),
]

UNIVERSITY_APPROVALS += [
    {"slug": "research_proposal_approval", "name": "Research Proposal Approval",
     "entity_slug": "research_proposal", "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "research_director"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
    {"slug": "ethics_approval_process", "name": "Ethics / IRB Approval",
     "entity_slug": "ethics_approval", "trigger_condition_nql": 'status = "submitted"',
     "levels": [{"level": 1, "quorum": "any",
                 "approvers": [{"type": "role", "value": "research_director"}]}],
     "on_approve_actions": [{"type": "update_field", "field": "status", "value": "approved"}],
     "on_reject_actions": [{"type": "update_field", "field": "status", "value": "rejected"}]},
]


# ── forms / views ────────────────────────────────────────────────────────────
def _form_for(slug):
    obj = UNIVERSITY_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = UNIVERSITY_OBJECTS[slug]
    field_slugs = {f["slug"] for f in obj["fields"]}
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if "status" in field_slugs:
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


# ── U8 portal grants (reuse the FROZEN Core Portal engine — NO portal entities are created) ──
# The Portal Platform owns portals. U8 only configures ``portal_grants``: every portal query
# server-side AND-injects ``{link_field} = portal_user.linked_record_id`` (unspoofable row isolation).
# Student & parent portals link on ``student``; the faculty portal links on the instructor record
# (``instructor``/``advisor`` lookups). NOTE: the frozen U7 research entities carry USER-typed
# principal_investigator/member fields (not instructor/student record lookups), so a research_project
# portal grant cannot isolate correctly without modifying frozen U7 — which governance forbids;
# research visibility for faculty is therefore delivered through the faculty portal's advising/teaching
# records, not a research_project grant. This is a frozen-U7 data-model characteristic, not a
# Platform Gap (the Portal Platform is complete).
def _grant(entity_slug, *, create=False, portal_type="student", link_field="student"):
    return {"entity_slug": entity_slug, "portal_type": portal_type, "link_field": link_field,
            "can_read": True, "can_create": create, "can_update": False}


UNIVERSITY_PORTAL_GRANTS = [
    # Student self-service — grades/records, finance, and campus services (link_field=student).
    _grant("course_result"), _grant("semester_result"), _grant("student_academic_record"),
    _grant("degree_progress"), _grant("tuition_charge"), _grant("student_payment"),
    _grant("aid_award"), _grant("book_loan"), _grant("room_allocation"),
    _grant("access_permit"), _grant("meal_plan"), _grant("campus_charge"),
    _grant("gate_pass", create=True), _grant("id_card_request", create=True),
    # Parent / proxy portal — grades + bills (portal_type=parent, still link_field=student).
    _grant("course_result", portal_type="parent"),
    _grant("semester_result", portal_type="parent"),
    _grant("tuition_charge", portal_type="parent"),
    _grant("student_payment", portal_type="parent"),
    # Faculty portal — the instructor sees their own teaching, workload, office hours and advising
    # (portal_type=faculty; linked to the instructor record via instructor/advisor lookups).
    _grant("teaching_assignment", portal_type="faculty", link_field="instructor"),
    _grant("faculty_workload", portal_type="faculty", link_field="instructor"),
    _grant("office_hour", portal_type="faculty", link_field="instructor"),
    _grant("advising_session", portal_type="faculty", link_field="advisor"),
]


# ── navigation ───────────────────────────────────────────────────────────────
def _nav_group(label, slugs):
    return {"label": label, "items": [
        {"label": UNIVERSITY_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
        for s in slugs]}


UNIVERSITY_NAV = [
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
    _nav_group("Faculty & Advising", ["teaching_assignment", "office_hour", "faculty_workload",
                                      "advisor_assignment", "advisor_caseload", "advising_session",
                                      "advising_note", "academic_hold", "override_request"]),
    _nav_group("Graduate Supervision", ["graduate_committee", "graduate_review"]),
    _nav_group("Tuition & Billing", ["tuition_category", "tuition_structure", "tuition_charge",
                                     "tuition_adjustment", "student_account", "student_payment"]),
    _nav_group("Financial Aid", ["aid_program", "aid_award", "aid_renewal", "sponsorship",
                                 "student_loan"]),
    _nav_group("Payments & Holds", ["payment_plan", "payment_agreement", "financial_hold"]),
    # U6 campus operations.
    _nav_group("Library & Residence", ["library_book", "book_loan", "residence_room",
                                       "room_allocation"]),
    _nav_group("Transport, Parking & Meals", ["transport_route", "transport_subscription",
                                              "access_permit", "meal_plan", "campus_charge"]),
    _nav_group("Health & Counselling", ["medical_profile", "medical_condition", "allergy",
                                        "medication", "vaccination_record", "medical_visit",
                                        "medical_alert", "health_screening",
                                        "counselling_referral", "counselling_session",
                                        "counselling_action_plan"]),
    _nav_group("Activities & Events", ["student_club", "club_membership", "sport",
                                       "sport_participation", "competition", "competition_entry",
                                       "award", "student_activity"]),
    _nav_group("Safety & Security", ["visitor_log", "gate_pass", "incident_report",
                                     "welfare_case", "lost_and_found", "id_card_request"]),
    # U7 research administration.
    _nav_group("Research Organization", ["research_center", "research_group", "research_project",
                                         "research_team_member"]),
    _nav_group("Proposals, Grants & Ethics", ["research_proposal", "grant_application", "grant",
                                              "ethics_approval", "funding_agency"]),
    _nav_group("Outputs & IP", ["publication", "journal", "conference", "patent",
                                "intellectual_property", "research_contract"]),
    # U8 accreditation & compliance.
    _nav_group("Accreditation & Compliance", ["accreditation_body", "accreditation",
                                              "compliance_requirement", "compliance_record"]),
]


# ══ U9: Enterprise hardening — data-integrity validation + SLA response (Rules/SLA engines) ═════════
# ADDITIVE guard rails ONLY (new manifest sections; U1–U8 entity/workflow/role/report definitions are
# NOT touched). Mirrors the certified School Phase 1.8 / College C9 pattern. block_save protects the
# reused GL/Credits/Collections posting paths from zero/negative amounts and guards academic
# calculations from out-of-range values; SLA policies add welfare/safety/turnaround governance.
def _block_rule(entity, field, op, val, msg, trigger):
    return {"slug": f"validate_{entity}_{field}_{trigger}",
            "name": f"Validate {entity}.{field}", "entity_slug": entity, "trigger_on": trigger,
            "condition_nql": f"{field} {op} {val}",
            "actions": [{"type": "block_save", "message": msg}], "priority": 10}


# Money fields that post to the financial platform (must be > 0 — protects the GL/Credits/Collections
# postings the U5–U8 workflows fire).
_MONEY_FIELDS = [
    ("tuition_charge", "amount"), ("student_payment", "amount"), ("tuition_adjustment", "amount"),
    ("aid_award", "amount"), ("aid_renewal", "amount"), ("sponsorship", "amount"),
    ("student_loan", "principal_amount"), ("payment_plan", "total_amount"),
    ("campus_charge", "amount"), ("grant", "award_amount"), ("research_contract", "contract_value"),
]

UNIVERSITY_RULES = [
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


UNIVERSITY_SLA_POLICIES = [
    _sla("welfare_case_response", "Welfare Case Response", "welfare_case", 1440),        # 24h
    _sla("incident_response", "Incident Response", "incident_report", 2880),             # 48h
    _sla("medical_alert_response", "Medical Alert Response", "medical_alert", 720),      # 12h
    _sla("ethics_review_turnaround", "Ethics Review Turnaround", "ethics_approval", 20160, 90),  # 14d
    _sla("compliance_turnaround", "Compliance Turnaround", "compliance_requirement", 20160, 90),  # 14d
    _sla("accreditation_review", "Accreditation Review", "accreditation", 43200, 90),    # 30d
]


# ── package block ─────────────────────────────────────────────────────────────
def _package_block() -> dict:
    return {
        "slug": "university", "name": "University Management", "version": "1.0.0",
        "author": "Sridhar ERP",
        "description": "Higher-education University Management — academic core with a multi-college "
                       "hierarchy (colleges/schools/faculties/departments as a self-referencing "
                       "academic-unit tree), programs (UG/Masters/PhD, double/joint/dual degrees, "
                       "majors/minors, ECTS/credit systems), courses/sections/curriculum, and a "
                       "student master with exchange/international handling — ALL as metadata on the "
                       "shared academic spine. The THIRD education package; reuses the ERP Core, "
                       "ships zero native code, installs independently.",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": ["workflow"],
        "requires_capabilities": ["metadata", "dynamic_forms", "views", "workflows",
                                  "reports", "dashboards", "rbac", "notifications",
                                  "numbering", "analytics_kpi",
                                  # U2 — registration eligibility = the Core Guard Framework (CG-1).
                                  "cross_record_validation",
                                  # U3 — GPA/CGPA/standing/honours/degree-progress = the Core
                                  # Aggregation Framework (CG-2); University writes zero calculation.
                                  "cross_record_aggregation", "documents",
                                  # U5 — all money movement reuses the Core financial platform.
                                  "accounting"],
        "requires_packages": [],
        # instructors ↔ HR employees; U7 research_project OVERLAYS the frozen Projects ``project``.
        "optional_packages": [{"slug": "hr", "version": "*"},
                              {"slug": "projects", "version": "*"}],
        "conflicts_packages": [],
        "provides_capabilities": ["university", "higher_education", "student_information_system",
                                  "multi_college", "course_registration", "grade_management",
                                  "academic_records", "transcripts", "faculty_management",
                                  "academic_advising", "graduate_supervision", "student_finance",
                                  "financial_aid", "tuition_management", "campus_operations",
                                  "library_management", "residence_life", "student_wellbeing",
                                  "research_management", "research_administration",
                                  # U8 — executive layer + institutional governance (config over the
                                  # frozen Dashboard/Analytics/Reporting/Portal platforms).
                                  "institutional_accreditation", "institutional_compliance",
                                  "executive_analytics", "executive_reporting"],
        "migrations": [],
    }


# ── manifest assembly + seed ─────────────────────────────────────────────────
def build_university_manifest() -> dict:
    return {
        "schema_version": 1,
        "package": _package_block(),
        "entities": list(UNIVERSITY_OBJECTS.values()),
        "forms": [_form_for(s) for s in UNIVERSITY_OBJECTS],
        "views": [v for s in UNIVERSITY_OBJECTS for v in _views_for(s)],
        "workflows": UNIVERSITY_WORKFLOWS,
        "reports": UNIVERSITY_REPORTS,
        "kpis": UNIVERSITY_KPIS,
        "portal_grants": UNIVERSITY_PORTAL_GRANTS,
        "rules": UNIVERSITY_RULES,                  # U9 — data-integrity validation (Rules engine)
        "sla_policies": UNIVERSITY_SLA_POLICIES,    # U9 — response-time SLA (SLA engine)
        "notification_templates": UNIVERSITY_NOTIFICATIONS,
        "document_templates": UNIVERSITY_DOCUMENT_TEMPLATES,
        "approval_processes": UNIVERSITY_APPROVALS,
        "roles": UNIVERSITY_ROLES,
        "dashboards": UNIVERSITY_DASHBOARDS,
        "navigations": [{"ref": "main", "name": "University Menu", "scope": "app",
                         "tree": UNIVERSITY_NAV}],
        "home_layouts": [{"ref": "home", "name": "University Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "University Management"}]},
                         *UNIVERSITY_ROLE_HOMES],
        "applications": [{
            "slug": "university", "name": "University Management", "icon": "GraduationCap",
            "color": "#4338ca", "included_entity_slugs": _MAIN,
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in UNIVERSITY_ROLES], "is_published": True,
        }],
    }


def seed_university_template():
    """Upsert the published, system University SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="university",
        defaults={
            "name": "University Management",
            "category": "Education",
            "description": "Higher-education University Management — academic core with a "
                           "multi-college hierarchy, programs (double/joint degrees, ECTS), "
                           "courses/curriculum, and exchange/international students. The third "
                           "education package; ships zero native code, installs independently.",
            "icon": "GraduationCap", "color": "#4338ca", "publisher": "Sridhar ERP",
            "version": "1.0.0", "manifest": build_university_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
