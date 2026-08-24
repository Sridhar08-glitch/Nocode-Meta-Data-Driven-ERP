"""
Hospital Management — the enterprise Health Information System package (H0 architecture approved).

The 1st clinical package. Pure manifest: every assertion is manifest provisioning + reuse of the frozen
ERP Core engines (metadata/workflow/RBAC/reporting/analytics/dashboards/numbering) — ZERO native code,
zero models, zero services, zero executors, zero migrations beyond the seed.

Independent package: ``requires_packages=[]`` (Core only); ``optional_packages`` = inventory + assets
(consumed later: pharmacy/stores → Inventory; biomedical/ambulance → Assets). No dependency on
School/College/University.

**H1 — Master Data & Facility (THIS PHASE):** the facility/provider/reference-data spine that every
later clinical phase (H2 patients … H14 hardening) builds on. Generalization-first: provider/ward/bed/
payer/service/medical-code carry ``*_type`` metadata — no per-variant entities (the certified
University discipline). Later phases add the rest as pure-manifest consumers of the frozen platforms.
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


# ── H1 business objects (Master Data & Facility spine) ─────────────────────────────────────────────
# Generalization-first: provider/ward/bed/payer/service use ``*_type`` metadata — NO per-variant
# entities (doctor/surgeon, icu/er/maternity, government/private payer are all metadata, not tables).
# ``diagnosis_code`` and ``procedure_code`` are kept as SEPARATE terminology reference masters
# (user-ratified 2026-07-03: no generic ``medical_code`` at H1 — keeps the model simpler, avoids an
# over-generalized terminology entity, and leaves room for a future Clinical/Terminology Base
# extraction if multiple healthcare packages demonstrate the reuse). ``drug_formulary`` is a richer
# drug master (not a bare code).
HOSPITAL_OBJECTS: dict[str, dict] = {
    "facility": _entity("facility", "Facility", "Facilities", [
        _auto("facility_no", "Facility No", "HFAC-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("facility_type", "Type", "hospital", "clinic", "diagnostic_center",
                "day_care", "specialty_center"),
        _f("address", "Address", "textarea"),
        _f("phone", "Phone", "text"),
        _f("bed_capacity", "Licensed Beds", "integer"),
        _f("is_main", "Main Facility", "boolean"),
        _status("active", "inactive"),
    ]),
    "clinical_department": _entity(
        "clinical_department", "Clinical Department", "Clinical Departments", [
            _auto("department_no", "Department No", "HDEP-"),
            _f("name", "Name", "text", is_required=True),
            _f("code", "Code", "text", is_unique=True),
            # clinical vs diagnostic vs support = metadata, not separate entities.
            _select("department_type", "Type", "clinical", "diagnostic", "surgical",
                    "critical_care", "support", "administrative"),
            _lookup("facility", "Facility", "facility"),
            _lookup("specialty", "Primary Specialty", "specialty"),
            _f("head", "Department Head", "user"),
            _status("active", "inactive"),
        ]),
    # Wards — general/icu/er/maternity/pediatric/surgical are ward_type METADATA, not entities.
    "ward": _entity("ward", "Ward", "Wards", [
        _auto("ward_no", "Ward No", "HWRD-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("ward_type", "Type", "general", "icu", "hdu", "emergency", "maternity",
                "pediatric", "surgical", "isolation", "psychiatric"),
        _lookup("facility", "Facility", "facility"),
        _lookup("clinical_department", "Department", "clinical_department"),
        _f("bed_count", "Bed Count", "integer"),
        _select("gender_policy", "Gender Policy", "any", "male", "female"),
        _status("active", "closed"),
    ]),
    # Beds — icu_bed/ward_bed are bed_type METADATA; the bed has its OWN status lifecycle.
    "bed": _entity("bed", "Bed", "Beds", [
        _auto("bed_no", "Bed No", "HBED-"),
        _f("label", "Bed Label", "text", is_required=True),
        _select("bed_type", "Type", "general", "icu", "hdu", "isolation", "maternity",
                "pediatric", "recovery", "day_care"),
        _lookup("ward", "Ward", "ward"),
        _f("is_chargeable", "Chargeable", "boolean"),
        _status("available", "occupied", "reserved", "cleaning", "blocked", "out_of_service"),
    ]),
    # Providers — doctor/surgeon/consultant/resident are provider_type METADATA, not entities.
    "provider": _entity("provider", "Provider", "Providers", [
        _auto("provider_no", "Provider No", "HPRO-"),
        _f("name", "Name", "text", is_required=True),
        _select("provider_type", "Type", "physician", "surgeon", "consultant", "resident",
                "nurse", "midwife", "technician", "therapist", "pharmacist"),
        _lookup("specialty", "Specialty", "specialty"),
        _lookup("clinical_department", "Department", "clinical_department"),
        _f("license_no", "License No", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "text"),
        _f("user_account", "User Account", "user"),
        _status("active", "on_leave", "inactive"),
    ]),
    # Specialty — the single generic reference master (reused by department/provider/service);
    # provider_specialty junction rejected (single primary specialty = a lookup).
    "specialty": _entity("specialty", "Specialty", "Specialties", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("category", "Category", "medical", "surgical", "diagnostic", "allied_health"),
        _f("description", "Description", "textarea"),
        _status("active", "inactive"),
    ]),
    # Service catalog — the billable/clinical service master (consumed by H9 billing later).
    "service_catalog": _entity("service_catalog", "Service", "Services", [
        _auto("service_no", "Service No", "HSVC-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("service_type", "Type", "consultation", "procedure", "diagnostic", "surgery",
                "nursing", "room_charge", "package", "other"),
        _lookup("specialty", "Specialty", "specialty"),
        _lookup("clinical_department", "Department", "clinical_department"),
        _f("standard_price", "Standard Price", "currency"),
        _f("is_taxable", "Taxable", "boolean"),
        _status("active", "inactive"),
    ]),
    # Payers — government/private-insurance/self-pay/corporate are payer_type METADATA, not entities.
    "payer": _entity("payer", "Payer", "Payers", [
        _auto("payer_no", "Payer No", "HPAY-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("payer_type", "Type", "self_pay", "government", "private_insurance",
                "corporate", "ngo", "international"),
        _f("contact_person", "Contact Person", "text"),
        _f("contact_email", "Contact Email", "email"),
        _f("phone", "Phone", "text"),
        _status("active", "inactive"),
    ]),
    # Diagnosis codes — the diagnosis terminology reference master (ICD-10/ICD-11/SNOMED = code_system
    # metadata). Kept separate from procedure codes (user-ratified — no generic medical_code at H1).
    "diagnosis_code": _entity("diagnosis_code", "Diagnosis Code", "Diagnosis Codes", [
        _f("code", "Code", "text", is_required=True, is_unique=True),
        _f("description", "Description", "text", is_required=True),
        _select("code_system", "Coding System", "icd10", "icd11", "snomed", "local"),
        _f("category", "Category", "text"),
        _status("active", "inactive"),
    ]),
    # Procedure codes — the procedure terminology reference master (CPT/ICD-PCS = code_system
    # metadata). Kept separate from diagnosis codes.
    "procedure_code": _entity("procedure_code", "Procedure Code", "Procedure Codes", [
        _f("code", "Code", "text", is_required=True, is_unique=True),
        _f("description", "Description", "text", is_required=True),
        _select("code_system", "Coding System", "cpt", "icd_pcs", "snomed", "local"),
        _f("category", "Category", "text"),
        _f("is_billable", "Billable", "boolean"),
        _status("active", "inactive"),
    ]),
    # Drug formulary — the drug reference master (consumed by H6 pharmacy; richer than a bare code).
    "drug_formulary": _entity("drug_formulary", "Formulary Drug", "Formulary Drugs", [
        _f("code", "Code", "text", is_required=True, is_unique=True),
        _f("name", "Brand Name", "text", is_required=True),
        _f("generic_name", "Generic Name", "text"),
        _select("form", "Form", "tablet", "capsule", "syrup", "injection", "infusion",
                "topical", "drops", "inhaler", "suppository"),
        _f("strength", "Strength", "text"),
        _f("atc_class", "ATC Class", "text"),
        _select("schedule", "Schedule", "otc", "prescription", "controlled", "narcotic"),
        _select("formulary_status", "Formulary Status", "formulary", "non_formulary",
                "restricted"),
        _status("active", "inactive"),
    ]),

    # ══ H2: Patient Administration & Registration ══════════════════════════════════════════════════
    # The FOUNDATIONAL patient identity every later phase (H3 appointments … H14) references. H2 owns
    # patient IDENTITY, not visits — a per-visit registration is an H4 ``encounter``, so no visit entity
    # here. OP/IP is encounter-level (not a patient attribute) → ``patient_category`` metadata only.
    # Generic objects: patient_contact(contact_type), insurance_policy(coverage_type) — no
    # next_of_kin/guarantor sub-entities.
    #
    # ARCHITECTURAL CORRECTION (user review 2026-07-03): ``allergy`` was moved to H4 (it is a
    # clinician-maintained CLINICAL record that drives medication safety/prescription/care — a
    # registration phase must not own a clinical entity), and ``patient_alert`` was REJECTED entirely
    # (it is a derived PRESENTATION layer aggregating allergy[H4]/fall-risk[H7]/isolation[H11]/VIP
    # [patient_category]/financial-hold[H9]/etc. from their OWNING modules — not an independent object).
    # H2 = patient + patient_contact + insurance_policy(coverage only) — exactly 3 entities.
    "patient": _entity("patient", "Patient", "Patients", [
        _auto("mrn", "MRN", "MRN-"),                       # medical record number
        _f("first_name", "First Name", "text", is_required=True),
        _f("last_name", "Last Name", "text", is_required=True),
        _f("date_of_birth", "Date of Birth", "date"),
        _select("gender", "Gender", "male", "female", "other", "unknown"),
        _select("blood_group", "Blood Group", "a_pos", "a_neg", "b_pos", "b_neg", "o_pos",
                "o_neg", "ab_pos", "ab_neg", "unknown"),
        _f("national_id", "National ID", "text"),
        _f("phone", "Phone", "text"),
        _f("email", "Email", "email"),
        _f("address", "Address", "textarea"),
        _select("marital_status", "Marital Status", "single", "married", "divorced", "widowed",
                "unknown"),
        # OP/IP is NOT a patient attribute (it is per-encounter) — category is a generic classifier.
        _select("patient_category", "Category", "regular", "newborn", "medico_legal", "vip",
                "unknown"),
        _f("registration_date", "Registration Date", "date"),
        _lookup("primary_facility", "Primary Facility", "facility"),
        _status("registered", "active", "inactive", "deceased"),
    ]),
    "patient_contact": _entity("patient_contact", "Patient Contact", "Patient Contacts", [
        _lookup("patient", "Patient", "patient"),
        _select("contact_type", "Type", "next_of_kin", "emergency", "guarantor", "referring"),
        _f("name", "Name", "text", is_required=True),
        _f("relationship", "Relationship", "text"),
        _f("phone", "Phone", "text"),
        _f("email", "Email", "email"),
        _f("is_primary", "Primary", "boolean"),
    ]),
    # Insurance COVERAGE (registration data). H9 owns the claim/preauthorization that REFERENCE this;
    # H2 never posts money — that is the Financial Platform via H9.
    "insurance_policy": _entity("insurance_policy", "Insurance Policy", "Insurance Policies", [
        _auto("policy_ref", "Policy Ref", "HINS-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("payer", "Payer", "payer"),
        _f("policy_no", "Policy No", "text"),
        _f("member_no", "Member No", "text"),
        _select("coverage_type", "Coverage", "outpatient", "inpatient", "comprehensive",
                "maternity", "dental", "optical"),
        _f("valid_from", "Valid From", "date"),
        _f("valid_to", "Valid To", "date"),
        _f("coverage_limit", "Coverage Limit", "currency"),
        _f("is_primary", "Primary", "boolean"),
        _status("active", "expired", "suspended"),
    ]),

    # ══ H3: Scheduling & Appointments ══════════════════════════════════════════════════════════════
    # H3 ends BEFORE the clinical encounter (H4) begins — it owns booking, availability and check-in,
    # not the consultation. Generic objects: appointment(appointment_type incl telemedicine),
    # provider_schedule(session_type + recurrence). REJECTED (derived / elsewhere): appointment_slot
    # (availability = provider_schedule − booked appts via the Guard capacity check, no slot rows),
    # queue (a derived view over checked-in appts; token = appointment field), check_in (an appointment
    # status), referral (clinical decision → H4), telemedicine_session (→ appointment_type).
    "provider_schedule": _entity("provider_schedule", "Provider Schedule", "Provider Schedules", [
        _auto("schedule_no", "Schedule No", "HSCH-"),
        _lookup("provider", "Provider", "provider"),
        _lookup("facility", "Facility", "facility"),
        _lookup("clinical_department", "Department", "clinical_department"),
        _select("session_type", "Session Type", "opd", "clinic", "emergency", "telemedicine",
                "procedure"),
        _select("recurrence", "Recurrence", "none", "daily", "weekly"),
        _select("day_of_week", "Day of Week", "mon", "tue", "wed", "thu", "fri", "sat", "sun"),
        _f("session_date", "Session Date", "date"),
        _f("start_time", "Start Time", "time"),
        _f("end_time", "End Time", "time"),
        _f("slot_duration_min", "Slot Duration (min)", "integer"),
        _f("capacity", "Capacity", "integer"),
        _status("active", "inactive"),
    ]),
    "appointment": _entity("appointment", "Appointment", "Appointments", [
        _auto("appointment_no", "Appointment No", "HAPT-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("provider", "Provider", "provider"),
        _lookup("provider_schedule", "Session", "provider_schedule"),
        _lookup("clinical_department", "Department", "clinical_department"),
        # video/phone/walk-in/follow-up = appointment_type metadata (no telemedicine_session entity).
        _select("appointment_type", "Type", "in_person", "telemedicine", "phone", "walk_in",
                "follow_up"),
        _f("appointment_date", "Date", "date"),
        _f("start_time", "Start Time", "time"),
        _f("reason", "Reason for Visit", "text"),
        _select("source", "Booking Source", "self", "referral", "walk_in", "online", "call_center"),
        # check-in = a status transition + these fields, NOT a separate entity; the OPD queue is a
        # derived view over checked-in appointments ordered by priority/time.
        _f("check_in_time", "Check-in Time", "datetime"),
        _f("queue_token", "Queue Token", "text"),
        _select("queue_priority", "Priority", "normal", "urgent", "emergency"),
        _status("requested", "booked", "confirmed", "checked_in", "in_progress", "completed",
                "cancelled", "no_show", "rescheduled", "waitlisted"),
    ]),
    "schedule_exception": _entity("schedule_exception", "Schedule Exception", "Schedule Exceptions", [
        _lookup("provider", "Provider", "provider"),
        _select("exception_type", "Type", "leave", "holiday", "blocked", "meeting", "training"),
        _f("exception_date", "Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("reason", "Reason", "text"),
        _status("active", "cancelled"),
    ]),
    "appointment_waitlist": _entity(
        "appointment_waitlist", "Appointment Waitlist", "Appointment Waitlist", [
            _auto("waitlist_no", "Waitlist No", "HWL-"),
            _lookup("patient", "Patient", "patient"),
            _lookup("provider", "Provider", "provider"),
            _lookup("clinical_department", "Department", "clinical_department"),
            _f("preferred_date", "Preferred Date", "date"),
            _f("reason", "Reason", "text"),
            _status("waiting", "offered", "booked", "expired", "cancelled"),
        ]),

    # ══ H4: Clinical Encounters (the EMR / clinical record) ═════════════════════════════════════════
    # H4 begins when the H3 appointment becomes in_progress and ends when the encounter is completed.
    # It owns the CLINICAL record ONLY — orders(H5)/prescriptions(H6)/admissions(H7)/billing(H9) are
    # elsewhere. Generic objects: clinical_note(note_type absorbs SOAP/progress/operative/physical_exam/
    # ros/assessment), diagnosis(diagnosis_type), allergy(allergy_type), vital_sign(vital_type — the
    # FHIR observation primitive), clinical_history(history_type absorbs past/family/social). chief
    # complaint + triage = encounter FIELDS, not entities.
    "encounter": _entity("encounter", "Clinical Encounter", "Clinical Encounters", [
        _auto("encounter_no", "Encounter No", "HENC-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("provider", "Provider", "provider"),
        _lookup("appointment", "Appointment", "appointment"),   # the H3 booking (may be walk-in/null)
        _lookup("clinical_department", "Department", "clinical_department"),
        _select("encounter_type", "Type", "outpatient", "emergency", "inpatient", "consult",
                "telemedicine"),
        _f("encounter_date", "Encounter Date", "datetime"),
        _f("chief_complaint", "Chief Complaint", "text"),       # not a separate entity
        _select("triage_level", "Triage Level (ESI)", "none", "1", "2", "3", "4", "5"),  # ER field
        _select("disposition", "Disposition", "pending", "discharged", "admitted", "referred",
                "transferred", "deceased", "lwbs"),             # outcome metadata (admission=H7)
        _status("planned", "in_progress", "completed", "cancelled"),
    ]),
    "clinical_note": _entity("clinical_note", "Clinical Note", "Clinical Notes", [
        _auto("note_no", "Note No", "HNOTE-"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("patient", "Patient", "patient"),
        _lookup("provider", "Author", "provider"),
        _select("note_type", "Type", "soap", "progress", "consultation", "operative", "nursing",
                "physical_exam", "review_of_systems", "assessment", "discharge"),
        _f("content", "Content", "textarea"),
        _f("note_datetime", "Note Date/Time", "datetime"),
        _status("draft", "signed", "amended", "locked"),
    ]),
    "diagnosis": _entity("diagnosis", "Diagnosis", "Diagnoses", [
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("patient", "Patient", "patient"),
        _lookup("diagnosis_code", "Diagnosis Code", "diagnosis_code"),   # H1 reference master
        _select("diagnosis_type", "Type", "primary", "secondary", "working", "provisional",
                "differential", "final"),
        _f("onset_date", "Onset Date", "date"),
        _f("notes", "Notes", "text"),
        _status("active", "resolved", "ruled_out"),
    ]),
    # Problem list — patient-level, longitudinal (spans encounters); genuinely distinct lifecycle from
    # the encounter-level ``diagnosis`` (kept separate, 7-point justified).
    "problem": _entity("problem", "Problem", "Problem List", [
        _lookup("patient", "Patient", "patient"),
        _lookup("diagnosis_code", "Coded As", "diagnosis_code"),
        _f("problem_name", "Problem", "text", is_required=True),
        _select("problem_type", "Type", "chronic", "acute", "recurring"),
        _f("onset_date", "Onset Date", "date"),
        _status("active", "resolved", "inactive"),
    ]),
    # Allergy — MOVED from H2 (clinician-maintained clinical record; feeds the H6 drug-safety Guard).
    "allergy": _entity("allergy", "Allergy", "Allergies", [
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Recorded At Encounter", "encounter"),
        _f("allergen", "Allergen", "text", is_required=True),
        _select("allergy_type", "Type", "drug", "food", "environmental", "other"),
        _f("reaction", "Reaction", "text"),
        _select("severity", "Severity", "mild", "moderate", "severe", "life_threatening"),
        _f("recorded_date", "Recorded Date", "date"),
        _status("active", "inactive", "resolved"),
    ]),
    # Vital sign — the generic observation primitive (vital_type absorbs BP/pulse/temp/etc.).
    "vital_sign": _entity("vital_sign", "Vital Sign", "Vital Signs", [
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("patient", "Patient", "patient"),
        _select("vital_type", "Vital", "blood_pressure_systolic", "blood_pressure_diastolic",
                "pulse", "temperature", "respiratory_rate", "spo2", "weight", "height", "bmi",
                "pain_score", "blood_glucose"),
        _f("value", "Value", "decimal"),
        _f("unit", "Unit", "text"),
        _f("recorded_at", "Recorded At", "datetime"),
    ]),
    "care_plan": _entity("care_plan", "Care Plan", "Care Plans", [
        _auto("care_plan_no", "Care Plan No", "HCP-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        # ``isolation`` (H13 IPC reuse) — an isolation precaution IS a typed care plan, NOT a new entity.
        _select("care_plan_type", "Type", "medical", "nursing", "discharge", "rehabilitation",
                "isolation"),
        _f("goals", "Goals", "textarea"),
        _f("interventions", "Interventions", "textarea"),
        _f("start_date", "Start Date", "date"),
        _status("draft", "active", "completed", "cancelled"),
    ]),
    # Clinical history — FOUR distinct entities (user-ratified architectural review 2026-07-03). Past-
    # medical / surgical / family / social history have genuinely different structure, lifecycle,
    # reporting and FHIR mapping (Condition / Procedure / FamilyMemberHistory / social-history
    # Observation) — a generic clinical_history would over-generalize distinct clinical concepts and
    # break structured reporting (smokers / family-history-of-cancer / previous-surgeries).
    "past_medical_history": _entity(
        "past_medical_history", "Past Medical History", "Past Medical History", [
            _lookup("patient", "Patient", "patient"),
            _lookup("encounter", "Recorded At Encounter", "encounter"),
            _f("condition", "Condition", "text", is_required=True),
            _lookup("diagnosis_code", "Coded As", "diagnosis_code"),
            _f("onset_date", "Onset Date", "date"),
            _f("notes", "Notes", "textarea"),
            _status("active", "resolved", "inactive"),
        ]),
    "surgical_history": _entity("surgical_history", "Surgical History", "Surgical History", [
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Recorded At Encounter", "encounter"),
        _f("procedure_name", "Procedure", "text", is_required=True),
        _lookup("procedure_code", "Coded As", "procedure_code"),
        _f("procedure_date", "Procedure Date", "date"),
        _f("facility_name", "Facility", "text"),             # external facility → text, not a lookup
        _f("surgeon_name", "Surgeon", "text"),               # external surgeon → text
        _f("notes", "Notes", "textarea"),
        _status("active", "inactive"),
    ]),
    "family_history": _entity("family_history", "Family History", "Family History", [
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Recorded At Encounter", "encounter"),
        _select("relationship", "Relationship", "father", "mother", "sibling", "grandparent",
                "child", "other"),
        _f("condition", "Condition", "text", is_required=True),
        _lookup("diagnosis_code", "Coded As", "diagnosis_code"),
        _f("age_of_onset", "Age of Onset", "integer"),
        _f("is_deceased", "Relative Deceased", "boolean"),
        _f("notes", "Notes", "textarea"),
        _status("active", "inactive"),
    ]),
    "social_history": _entity("social_history", "Social History", "Social History", [
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Recorded At Encounter", "encounter"),
        _select("category", "Category", "smoking", "alcohol", "substance_use", "occupation",
                "living_conditions", "diet", "exercise"),
        _select("usage_status", "Status", "current", "former", "never", "not_applicable"),
        _f("detail", "Detail", "text"),                      # occupation / substance / description
        _f("frequency", "Frequency / Quantity", "text"),
        _f("recorded_date", "Recorded Date", "date"),
        _status("active", "inactive"),
    ]),

    # ══ H5: Orders & Results (diagnostic ordering + result management) ══════════════════════════════
    # H5 begins when a clinician requests an investigation and ends when validated results reach the
    # clinical record. Lab/imaging/cardiology share ONE order + result lifecycle → order_type/
    # result_type metadata (FHIR ServiceRequest/DiagnosticReport). specimen is generic (specimen_type;
    # FHIR Specimen) and only lab/pathology orders create one. result_item is the discrete analyte
    # value (FHIR Observation). REJECTED: laboratory_order/imaging_order (→ order_type), lab/imaging
    # _result (→ result_type), order_panel/test_catalog (→ configuration + service_catalog H1),
    # result_attachment (→ the Documents platform).
    "diagnostic_order": _entity("diagnostic_order", "Diagnostic Order", "Diagnostic Orders", [
        _auto("order_no", "Order No", "HORD-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),          # the requesting H4 encounter
        _lookup("provider", "Ordering Provider", "provider"),
        _lookup("clinical_department", "Performing Department", "clinical_department"),
        _lookup("service", "Service / Test", "service_catalog"),  # the H1 catalogue entry (panel=config)
        _select("order_type", "Type", "laboratory", "imaging", "cardiology", "pathology",
                "procedure"),
        _f("test_name", "Test / Study", "text"),                 # free text when not catalogued
        _select("priority", "Priority", "routine", "urgent", "stat"),
        _f("clinical_notes", "Clinical Information", "text"),
        _f("ordered_datetime", "Ordered At", "datetime"),
        _status("requested", "collected", "in_progress", "completed", "verified", "cancelled"),
    ]),
    "specimen": _entity("specimen", "Specimen", "Specimens", [
        _auto("specimen_no", "Specimen No", "HSPC-"),
        _lookup("diagnostic_order", "Order", "diagnostic_order"),
        _lookup("patient", "Patient", "patient"),
        _select("specimen_type", "Type", "blood", "serum", "plasma", "urine", "tissue", "swab",
                "csf", "stool", "sputum", "other"),
        _f("collected_datetime", "Collected At", "datetime"),
        _f("collected_by", "Collected By", "user"),
        _f("container", "Container", "text"),
        _f("rejection_reason", "Rejection Reason", "text"),
        _status("ordered", "collected", "received", "rejected", "processed"),
    ]),
    "diagnostic_result": _entity("diagnostic_result", "Diagnostic Result", "Diagnostic Results", [
        _auto("result_no", "Result No", "HRES-"),
        _lookup("diagnostic_order", "Order", "diagnostic_order"),
        _lookup("patient", "Patient", "patient"),
        _select("result_type", "Type", "laboratory", "imaging", "cardiology", "pathology"),
        _f("report", "Report / Interpretation", "textarea"),     # imaging narrative; images via Documents
        _f("impression", "Impression", "text"),
        _f("performed_by", "Performed By", "user"),
        _f("verified_by", "Verified By", "user"),
        _f("result_datetime", "Result At", "datetime"),
        _status("draft", "verified", "released", "corrected"),
    ]),
    # result_item — the discrete analyte value (FHIR Observation); many per lab result, structured for
    # trending + abnormal flagging.
    "result_item": _entity("result_item", "Result Item", "Result Items", [
        _lookup("diagnostic_result", "Result", "diagnostic_result"),
        _f("analyte", "Analyte / Test", "text", is_required=True),
        _f("value", "Value", "text"),                            # text allows positive/negative/numeric
        _f("numeric_value", "Numeric Value", "decimal"),         # for trending
        _f("unit", "Unit", "text"),
        _f("reference_range", "Reference Range", "text"),
        _select("abnormal_flag", "Flag", "normal", "low", "high", "critical_low", "critical_high",
                "abnormal"),
        _status("preliminary", "final", "corrected"),
    ]),

    # ══ H6: Pharmacy & Medication (medication management) ═══════════════════════════════════════════
    # H6 begins when medication is PRESCRIBED and ends when it is ADMINISTERED or discontinued. It owns
    # the clinical medication workflow ONLY — the drug PRODUCT master is the H1 ``drug_formulary`` (FHIR
    # Medication; NO new ``medication`` entity — that would duplicate an existing master, 6-point rule),
    # and stock/batch/expiry/valuation/purchasing/warehouse are the INVENTORY platform (H6 references,
    # never recreates). FHIR: MedicationRequest → MedicationDispense → MedicationAdministration.
    # REJECTED: ``medication`` (→ H1 drug_formulary), ``medication_order`` (→ prescription; FHIR
    # MedicationRequest unifies inpatient order + outpatient prescription — one object, prescription_type
    # metadata), ``mar``/``medication_administration_record`` (the MAR is a DERIVED report/view over
    # medication_administration events, not an entity — the queue/patient_alert precedent),
    # inpatient/outpatient/discharge_prescription (→ prescription_type), oral/iv/im/topical_medication
    # (→ route metadata). Drug-safety CDS (allergy contraindication, duplicate therapy, interaction) is
    # the frozen Rules/Guard Platform (deterministic, no AI per §2) — NO parallel medication CDS engine.
    "prescription": _entity("prescription", "Prescription", "Prescriptions", [
        _auto("prescription_no", "Prescription No", "RX-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("provider", "Prescriber", "provider"),
        # FHIR MedicationRequest unifies the inpatient order + the outpatient/discharge prescription —
        # ONE entity, prescription_type metadata (no medication_order / *_prescription entities).
        _select("prescription_type", "Type", "outpatient", "inpatient", "discharge",
                "home_medication", "emergency"),
        _select("priority", "Priority", "routine", "urgent", "stat"),
        _f("prescribed_datetime", "Prescribed At", "datetime"),
        _f("notes", "Notes", "text"),
        _status("draft", "signed", "verified", "dispensed", "completed", "cancelled"),
    ]),
    # Prescription item — one drug line (FHIR dosageInstruction). ``drug`` references the H1 formulary
    # master (NOT a new medication entity). ``patient`` is denormalized (from the prescription) so the
    # duplicate-therapy Guard can query it directly — the specimen/result denormalization precedent.
    "prescription_item": _entity("prescription_item", "Prescription Item", "Prescription Items", [
        _lookup("prescription", "Prescription", "prescription"),
        _lookup("patient", "Patient", "patient"),
        _lookup("drug", "Drug", "drug_formulary"),               # FHIR Medication = H1 drug_formulary
        _f("dose", "Dose", "text"),
        _f("dose_unit", "Dose Unit", "text"),
        # oral/iv/im/topical are route METADATA — no per-route medication entities.
        _select("route", "Route", "oral", "iv", "im", "subcutaneous", "topical", "inhalation",
                "rectal", "ophthalmic", "nasal", "sublingual"),
        _f("frequency", "Frequency", "text"),                    # e.g. BD / TDS / q8h
        _f("duration", "Duration", "text"),                      # e.g. 5 days
        _f("quantity", "Quantity", "decimal"),
        _f("instructions", "Instructions", "text"),
        _f("is_prn", "PRN (as needed)", "boolean"),
        _status("active", "on_hold", "discontinued", "completed"),
    ]),
    # Dispense (FHIR MedicationDispense) — the pharmacy hand-out event. ``batch_no`` is a REFERENCE
    # string only; the batch/lot/expiry/stock master + valuation are the Inventory platform (H6 records
    # what was dispensed, it does NOT recreate stock control). A live stock decrement is a future
    # Inventory-integration executor seam (Platform Gap), never a private H6 stock engine.
    "medication_dispense": _entity("medication_dispense", "Dispense", "Dispenses", [
        _auto("dispense_no", "Dispense No", "DSP-"),
        _lookup("prescription", "Prescription", "prescription"),
        _lookup("prescription_item", "Item", "prescription_item"),
        _lookup("patient", "Patient", "patient"),
        _lookup("drug", "Drug", "drug_formulary"),
        _f("quantity_dispensed", "Quantity Dispensed", "decimal"),
        _f("batch_no", "Batch / Lot Ref", "text"),               # reference only — Inventory owns batches
        _f("dispensed_by", "Dispensed By", "user"),
        _f("dispense_datetime", "Dispensed At", "datetime"),
        _f("notes", "Notes", "text"),
        _status("pending", "prepared", "dispensed", "partially_dispensed", "returned", "cancelled"),
    ]),
    # Medication administration (FHIR MedicationAdministration) — the atomic "dose given" event. The MAR
    # (Medication Administration Record) is a DERIVED report/view over these events (grouped by patient/
    # time), NOT a separate entity — the derived-presentation precedent (H3 queue, H2 patient_alert).
    "medication_administration": _entity(
        "medication_administration", "Medication Administration", "Medication Administrations", [
            _auto("administration_no", "Administration No", "MAR-"),
            _lookup("prescription_item", "Prescribed Item", "prescription_item"),
            _lookup("patient", "Patient", "patient"),
            _lookup("drug", "Drug", "drug_formulary"),
            # short field slugs: entity slug (25) leaves ≤17 chars for the auto-index name (≤63 total).
            _f("scheduled_at", "Scheduled At", "datetime"),
            _f("administered_at", "Administered At", "datetime"),
            _f("dose_given", "Dose Given", "text"),
            _select("route", "Route", "oral", "iv", "im", "subcutaneous", "topical", "inhalation",
                    "rectal", "ophthalmic", "nasal", "sublingual"),
            _f("administered_by", "Administered By", "user"),     # the nurse
            _f("reason_not_given", "Reason (if not given)", "text"),
            _status("scheduled", "administered", "missed", "refused", "held", "completed"),
        ]),
    # Medication reconciliation (FHIR MedicationStatement-based) — the transition-of-care review event
    # (admission/transfer/discharge). The medications reconciled ARE the prescription_items (home meds =
    # prescription_type=home_medication); no reconciliation_item sub-entity (avoids entity explosion).
    "medication_reconciliation": _entity(
        "medication_reconciliation", "Medication Reconciliation", "Medication Reconciliations", [
            _auto("reconciliation_no", "Reconciliation No", "MREC-"),
            _lookup("patient", "Patient", "patient"),
            _lookup("encounter", "Encounter", "encounter"),
            _select("recon_type", "Type", "admission", "transfer", "discharge"),
            _f("performed_by", "Performed By", "user"),
            _f("reconciled_at", "Reconciled At", "datetime"),
            _f("outcome", "Outcome", "text"),
            _f("notes", "Notes", "textarea"),
            _status("pending", "in_progress", "completed", "cancelled"),
        ]),

    # ══ H7: Inpatient, Wards & Nursing (inpatient operations) ═══════════════════════════════════════
    # H7 begins at formal ADMISSION and ends at DISCHARGE. It owns the inpatient EPISODE + bed occupancy
    # + nursing operations ONLY. Boundaries: the clinical VISIT is the H4 ``encounter`` (an admission is
    # the multi-encounter episode it belongs to); the bed MASTER is H1 ``bed`` (H7 owns only the
    # assignment/occupancy lifecycle, never a bed/ward/room/facility); VITALS are H4 ``vital_sign``
    # (nursing_observation owns NON-vital assessments, it does not duplicate them); the NURSING CARE PLAN
    # is H4 ``care_plan(care_plan_type=nursing)`` and the DISCHARGE SUMMARY is H4 ``clinical_note
    # (note_type=discharge)`` — H7 REUSES both; MEDICATION ADMINISTRATION stays H6; billing is H9.
    # REJECTED: ``nursing_care_plan`` (→ H4 care_plan), ``discharge_summary`` (→ H4 clinical_note),
    # ``round_note`` (→ H4 clinical_note), ``bed_reservation``/``bed_hold`` (→ bed_assignment status
    # ``reserved`` + H1 bed), emergency/elective/daycare_admission (→ admission_type), icu/ward/room
    # _transfer (→ transfer_type), doctor/nurse/consultant_round (→ ward_round round_type), icu/ward/
    # isolation_bed_assignment (→ bed_assignment + H1 bed_type).
    "admission": _entity("admission", "Admission", "Admissions", [
        _auto("admission_no", "Admission No", "ADM-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Admitting Encounter", "encounter"),   # the H4 visit that admitted (≠ episode)
        _lookup("provider", "Attending Physician", "provider"),
        _lookup("ward", "Admitting Ward", "ward"),                  # H1 master (reference only)
        # emergency/elective/daycare/maternity/newborn = admission_type metadata (no per-variant entity).
        _select("admission_type", "Type", "emergency", "elective", "daycare", "maternity",
                "newborn", "transfer_in", "observation"),
        _select("admission_source", "Source", "emergency_dept", "opd", "referral", "transfer",
                "direct"),
        _f("admission_datetime", "Admitted At", "datetime"),
        _f("reason", "Reason for Admission", "text"),
        _lookup("admitting_diagnosis", "Admitting Diagnosis", "diagnosis_code"),  # H1 reference
        _f("expected_discharge", "Expected Discharge", "date"),
        _f("discharge_datetime", "Discharged At", "datetime"),
        _select("disposition", "Disposition", "pending", "home", "transferred", "referred",
                "lama", "absconded", "deceased"),                  # LAMA = left against medical advice
        _status("requested", "approved", "admitted", "discharged", "cancelled"),
    ]),
    # Bed assignment — owns the OCCUPANCY lifecycle; ``bed``/``ward`` are H1 masters (never recreated).
    # ``reserved`` absorbs bed_reservation/bed_hold (a hold = an assignment in the reserved state).
    "bed_assignment": _entity("bed_assignment", "Bed Assignment", "Bed Assignments", [
        _auto("assignment_no", "Assignment No", "BAS-"),
        _lookup("admission", "Admission", "admission"),
        _lookup("patient", "Patient", "patient"),
        _lookup("bed", "Bed", "bed"),                              # H1 master
        _lookup("ward", "Ward", "ward"),                           # H1 master (denormalized for reporting)
        _f("assigned_datetime", "Assigned At", "datetime"),
        _f("released_datetime", "Released At", "datetime"),
        _f("is_current", "Current", "boolean"),
        _status("assigned", "reserved", "occupied", "released", "cancelled"),
    ]),
    # Transfer — inter-bed/ward/department/facility move; icu/ward/room = transfer_type metadata.
    "transfer": _entity("transfer", "Transfer", "Transfers", [
        _auto("transfer_no", "Transfer No", "TRF-"),
        _lookup("admission", "Admission", "admission"),
        _lookup("patient", "Patient", "patient"),
        _select("transfer_type", "Type", "ward", "room", "bed", "icu", "department", "external"),
        _lookup("from_bed", "From Bed", "bed"),
        _lookup("to_bed", "To Bed", "bed"),
        _lookup("from_ward", "From Ward", "ward"),
        _lookup("to_ward", "To Ward", "ward"),
        _f("reason", "Reason", "text"),
        _f("transfer_datetime", "Transferred At", "datetime"),
        _f("requested_by", "Requested By", "user"),
        _status("requested", "approved", "completed", "cancelled"),
    ]),
    # Discharge — the discharge PROCESS + event (planning lifecycle). The discharge SUMMARY is an H4
    # clinical_note(note_type=discharge); discharge MEDICATIONS are H6 prescription(prescription_type=
    # discharge); billing clearance is H9 — H7 carries only a ``billing_cleared`` reference flag.
    "discharge": _entity("discharge", "Discharge", "Discharges", [
        _auto("discharge_no", "Discharge No", "DIS-"),
        _lookup("admission", "Admission", "admission"),
        _lookup("patient", "Patient", "patient"),
        _select("discharge_type", "Type", "routine", "against_advice", "transfer", "referral",
                "absconded", "deceased"),
        _f("planned_date", "Planned Date", "date"),
        _f("discharge_datetime", "Discharged At", "datetime"),
        _f("destination", "Destination", "text"),                  # home / facility name
        _f("follow_up", "Follow-up Instructions", "text"),
        _f("discharged_by", "Discharged By", "user"),
        _f("billing_cleared", "Billing Cleared", "boolean"),       # reference flag to the H9 clearance
        _status("planned", "approved", "discharged", "closed", "cancelled"),
    ]),
    # Nursing observation — NON-vital nursing assessments (intake/output, wound, mobility, neuro/GCS,
    # etc.). Vitals (BP/pulse/temp/spo2/…) are the H4 ``vital_sign`` primitive — REUSED, NOT duplicated
    # here (no BP/pulse/temp choices).
    "nursing_observation": _entity("nursing_observation", "Nursing Observation", "Nursing Observations",
        [
            _auto("observation_no", "Observation No", "NOB-"),
            _lookup("admission", "Admission", "admission"),
            _lookup("patient", "Patient", "patient"),
            _f("recorded_by", "Recorded By", "user"),
            _select("observation_type", "Type", "intake_output", "fluid_balance", "pain_assessment",
                    "wound_assessment", "skin_integrity", "mobility", "neuro_gcs", "bowel",
                    "nutrition", "fall_risk", "general"),
            _f("value", "Value", "text"),
            _f("detail", "Detail", "text"),
            _f("observed_at", "Observed At", "datetime"),
            _status("recorded", "reviewed"),
        ]),
    # Nursing task — the nursing worklist (care interventions assigned to a nurse).
    "nursing_task": _entity("nursing_task", "Nursing Task", "Nursing Tasks", [
        _auto("task_no", "Task No", "NTK-"),
        _lookup("admission", "Admission", "admission"),
        _lookup("patient", "Patient", "patient"),
        _select("task_type", "Type", "medication", "dressing", "mobilization", "observation",
                "hygiene", "feeding", "specimen_collection", "patient_education", "other"),
        _f("description", "Description", "text"),
        _f("assigned_to", "Assigned To", "user"),
        _f("due_datetime", "Due At", "datetime"),
        _select("priority", "Priority", "routine", "urgent", "stat"),
        _f("completed_at", "Completed At", "datetime"),
        _status("pending", "in_progress", "completed", "cancelled"),
    ]),
    # Nursing handover — the shift-change / transfer SBAR communication record.
    "nursing_handover": _entity("nursing_handover", "Nursing Handover", "Nursing Handovers", [
        _auto("handover_no", "Handover No", "NHO-"),
        _lookup("ward", "Ward", "ward"),
        _lookup("patient", "Patient", "patient"),
        _select("shift", "Shift", "morning", "evening", "night"),
        _select("handover_type", "Type", "shift", "transfer", "escalation"),
        _f("situation", "Situation", "text"),                      # SBAR
        _f("background", "Background", "text"),
        _f("assessment", "Assessment", "text"),
        _f("recommendation", "Recommendation", "text"),
        _f("handover_at", "Handover At", "datetime"),
        _f("from_nurse", "From Nurse", "user"),
        _f("to_nurse", "To Nurse", "user"),
        _status("draft", "completed"),
    ]),
    # Ward round — the round EVENT (doctor/nurse/consultant/MDT = round_type metadata). Per-patient
    # clinical findings are documented as H4 clinical_notes (round_note REJECTED).
    "ward_round": _entity("ward_round", "Ward Round", "Ward Rounds", [
        _auto("round_no", "Round No", "WRD-"),
        _lookup("ward", "Ward", "ward"),
        _lookup("provider", "Lead Clinician", "provider"),
        _select("round_type", "Type", "consultant", "doctor", "nurse", "multidisciplinary",
                "teaching", "grand"),
        _f("round_datetime", "Round At", "datetime"),
        _f("notes", "Round Notes", "text"),
        _status("scheduled", "in_progress", "completed", "cancelled"),
    ]),

    # ══ H8: Surgery / Operating Theatre & Critical Care (perioperative + intensive care) ═════════════
    # H8 begins at the decision for surgery and covers the perioperative + critical-care journey. It
    # REFERENCES the H4 encounter (the clinical visit) — surgery is the surgical CASE, NOT the visit;
    # it references H1 procedure_code/diagnosis_code and H7 admission; it recreates none of them.
    # GENERALIZATION DECISION (operating_theatre): kept SPECIFIC to H8 for now — the ONLY schedulable
    # clinical resource that exists yet is the OT. Radiology suites / endoscopy / dialysis chairs /
    # infusion bays are future domains with genuinely different session lifecycles; a generic
    # ``clinical_resource``/``resource_schedule`` would be speculative over-generalization (build the
    # generic only on real multi-consumer evidence — the Base rule). Recorded as a Clinical-Resource-Base
    # extraction CANDIDATE (see CLINICAL_BASE_CANDIDATES.md); revisit when a 2nd resource domain arrives.
    # REJECTED: ``surgical_team`` (the team = its members → surgical_team_member) / ``procedure_participant``
    # (= surgical_team_member); ``ventilator_setting``/``ventilator_event`` (→ icu_observation.observation_type
    # — one param per row, the vital_sign precedent); ``transfusion``/``blood_transfusion``/``blood_unit``
    # (→ H10 Blood Bank owns the crossmatch→issue→transfuse lifecycle; H8 is REFERENCED by it, never owns
    # it); major/minor/emergency/elective_surgery (→ procedure_type/urgency); general/regional/local/
    # sedation (→ anaesthesia_type); icu/nicu/picu/ccu (→ icu_type); prosthesis/mesh/stent/device
    # (→ implant_type).
    "operating_theatre": _entity("operating_theatre", "Operating Theatre", "Operating Theatres", [
        _auto("theatre_no", "Theatre No", "OT-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("theatre_type", "Type", "general", "cardiac", "orthopaedic", "neuro",
                "day_surgery", "hybrid", "obstetric"),
        _lookup("facility", "Facility", "facility"),               # H1 master
        _f("location", "Location", "text"),
        _status("available", "occupied", "cleaning", "blocked", "out_of_service"),
    ]),
    # OT session — the theatre AVAILABILITY window (the coexisting resource-schedule the H3 ratification
    # anticipated; provider_schedule is for clinicians, this is for the room). Surgeries book against it.
    "ot_schedule": _entity("ot_schedule", "Theatre Session", "Theatre Sessions", [
        _auto("schedule_no", "Session No", "OTS-"),
        _lookup("operating_theatre", "Theatre", "operating_theatre"),
        _lookup("surgeon", "Lead Surgeon", "provider"),
        _lookup("specialty", "Specialty", "specialty"),           # H1 master
        _f("session_date", "Session Date", "date"),
        _f("start_time", "Start Time", "time"),
        _f("end_time", "End Time", "time"),
        _select("session_type", "Session Type", "elective", "emergency", "day_case"),
        _f("capacity", "Capacity (cases)", "integer"),
        _status("active", "inactive"),
    ]),
    # Surgery — the surgical CASE (references the H4 encounter; procedure_type/urgency metadata).
    "surgery": _entity("surgery", "Surgery", "Surgeries", [
        _auto("surgery_no", "Surgery No", "SUR-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),           # references H4 (does NOT duplicate)
        _lookup("ot_schedule", "Theatre Session", "ot_schedule"),
        _lookup("operating_theatre", "Theatre", "operating_theatre"),
        _lookup("surgeon", "Lead Surgeon", "provider"),
        _select("procedure_type", "Type", "major", "intermediate", "minor", "day_case"),
        _select("urgency", "Urgency", "elective", "urgent", "emergency", "immediate"),
        _f("scheduled_start", "Scheduled Start", "datetime"),
        _f("actual_start", "Actual Start", "datetime"),
        _f("actual_end", "Actual End", "datetime"),
        _f("planned_procedure", "Planned Procedure", "text"),
        _lookup("primary_diagnosis", "Primary Diagnosis", "diagnosis_code"),  # H1 reference
        _status("booked", "prepared", "in_theatre", "in_progress", "completed", "recovery",
                "closed", "cancelled"),
    ]),
    # Surgical procedure — the coded procedure(s) performed within a surgery (FHIR Procedure); N per case.
    "surgical_procedure": _entity("surgical_procedure", "Surgical Procedure", "Surgical Procedures", [
        _auto("procedure_no", "Procedure No", "SP-"),
        _lookup("surgery", "Surgery", "surgery"),
        _lookup("patient", "Patient", "patient"),
        _lookup("procedure_code", "Procedure Code", "procedure_code"),  # H1 terminology master
        _f("name", "Procedure", "text", is_required=True),
        _f("sequence", "Sequence", "integer"),
        _select("laterality", "Laterality", "not_applicable", "left", "right", "bilateral"),
        _f("findings", "Findings", "text"),
        _status("planned", "performed", "abandoned"),
    ]),
    # Anaesthesia record — an independent business object (own clinician/lifecycle/documentation).
    "anaesthesia_record": _entity("anaesthesia_record", "Anaesthesia Record", "Anaesthesia Records", [
        _auto("anaesthesia_no", "Anaesthesia No", "AN-"),
        _lookup("surgery", "Surgery", "surgery"),
        _lookup("patient", "Patient", "patient"),
        _lookup("anaesthetist", "Anaesthetist", "provider"),
        _select("anaesthesia_type", "Type", "general", "regional", "local", "sedation",
                "spinal", "epidural", "combined"),
        _select("asa_grade", "ASA Grade", "1", "2", "3", "4", "5", "6"),
        _f("agents", "Agents", "text"),
        _f("technique", "Technique", "text"),
        _f("start_time", "Start Time", "datetime"),
        _f("end_time", "End Time", "datetime"),
        _f("complications", "Complications", "text"),
        _status("planned", "in_progress", "completed", "aborted"),
    ]),
    # Surgical team member — the surgery↔provider ASSIGNMENT as a first-class relationship entity (the
    # Global Relationship Review outcome): it carries a role, multiplicity (N per case) AND a status so a
    # member can be relieved/cover mid-case (FHIR CareTeam.participant / Procedure.performer). This is
    # the 1st materialization of a reusable Care-Team-Assignment pattern (see CLINICAL_BASE_CANDIDATES).
    "surgical_team_member": _entity(
        "surgical_team_member", "Surgical Team Member", "Surgical Team Members", [
            _lookup("surgery", "Surgery", "surgery"),
            _lookup("provider", "Provider", "provider"),
            _select("team_role", "Role", "lead_surgeon", "assistant", "anaesthetist",
                    "scrub_nurse", "circulating_nurse", "perfusionist", "technician", "observer"),
            _f("is_lead", "Lead", "boolean"),
            _f("responsibility", "Responsibility", "text"),
            _status("assigned", "present", "relieved", "absent"),   # temporal/relief-capable assignment
        ]),
    # Surgical safety checklist — the WHO 3-phase checklist (sign_in/time_out/sign_out); one per phase.
    "surgical_checklist": _entity("surgical_checklist", "Surgical Checklist", "Surgical Checklists", [
        _auto("checklist_no", "Checklist No", "SC-"),
        _lookup("surgery", "Surgery", "surgery"),
        _select("checklist_phase", "Phase", "sign_in", "time_out", "sign_out"),
        _f("completed_by", "Completed By", "user"),
        _f("completed_at", "Completed At", "datetime"),
        _f("all_confirmed", "All Items Confirmed", "boolean"),
        _f("notes", "Notes", "text"),
        _status("pending", "completed"),
    ]),
    # ICU episode — a critical-care stay (icu_type metadata; references the H7 admission). H7 owns the
    # admission/ward stay; H8 owns ONLY the intensive-care episode within it.
    "icu_episode": _entity("icu_episode", "ICU Episode", "ICU Episodes", [
        _auto("episode_no", "Episode No", "ICU-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("admission", "Admission", "admission"),           # references H7
        _lookup("ward", "ICU Ward", "ward"),                      # H1 master
        _select("icu_type", "Type", "icu", "nicu", "picu", "ccu", "hdu", "sicu", "micu"),
        _lookup("intensivist", "Intensivist", "provider"),
        _f("admitted_at", "Admitted At", "datetime"),
        _f("discharged_at", "Discharged At", "datetime"),
        _select("reason", "Reason", "post_operative", "respiratory", "cardiac", "neurological",
                "sepsis", "trauma", "other"),
        _f("apache_score", "APACHE II Score", "integer"),
        _status("active", "stepped_down", "discharged", "deceased"),
    ]),
    # ICU observation — ICU-SPECIFIC charting (ventilator/haemodynamic/neuro/renal). Standard vitals stay
    # the H4 vital_sign primitive (NOT duplicated); ventilator settings/events = observation_type rows.
    "icu_observation": _entity("icu_observation", "ICU Observation", "ICU Observations", [
        _auto("observation_no", "Observation No", "IOB-"),
        _lookup("icu_episode", "ICU Episode", "icu_episode"),
        _lookup("patient", "Patient", "patient"),
        _select("observation_type", "Type", "ventilator_mode", "ventilator_fio2", "ventilator_peep",
                "tidal_volume", "map", "cvp", "icp", "gcs", "rass", "urine_output", "fluid_balance",
                "vasopressor", "lactate"),
        _f("value", "Value", "text"),
        _f("unit", "Unit", "text"),
        _f("observed_at", "Observed At", "datetime"),
    ]),
    # Recovery episode (PACU) — the post-anaesthesia care period (Aldrete scoring + disposition).
    "recovery_episode": _entity("recovery_episode", "Recovery Episode", "Recovery Episodes", [
        _auto("recovery_no", "Recovery No", "PACU-"),
        _lookup("surgery", "Surgery", "surgery"),
        _lookup("patient", "Patient", "patient"),
        _f("admitted_at", "Admitted At", "datetime"),
        _f("discharged_at", "Discharged At", "datetime"),
        _f("aldrete_score", "Aldrete Score", "integer"),
        _select("disposition", "Disposition", "ward", "icu", "hdu", "home", "deceased"),
        _f("recovery_nurse", "Recovery Nurse", "user"),
        _status("in_recovery", "ready_for_discharge", "discharged", "transferred"),
    ]),
    # Implant — the implant/device catalog master (implant_type; regulatory traceability, like a drug
    # formulary for devices). Physical stock/batches are the Inventory platform.
    "implant": _entity("implant", "Implant", "Implants", [
        _auto("implant_no", "Implant No", "IMP-"),
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _select("implant_type", "Type", "prosthesis", "mesh", "stent", "plate", "screw",
                "pacemaker", "lens", "graft", "device"),
        _f("manufacturer", "Manufacturer", "text"),
        _f("model", "Model", "text"),
        _f("is_sterile", "Sterile", "boolean"),
        _status("active", "recalled", "inactive"),
    ]),
    # Implant usage — the per-surgery traceability record (serial/lot are references; Inventory owns stock).
    "implant_usage": _entity("implant_usage", "Implant Usage", "Implant Usage", [
        _auto("usage_no", "Usage No", "IU-"),
        _lookup("surgery", "Surgery", "surgery"),
        _lookup("patient", "Patient", "patient"),
        _lookup("implant", "Implant", "implant"),
        _f("serial_no", "Serial No", "text"),                     # regulatory traceability
        _f("lot_no", "Lot / Batch Ref", "text"),                  # reference — Inventory owns batches
        _f("site", "Anatomical Site", "text"),
        _f("implanted_at", "Implanted At", "datetime"),
        _status("implanted", "explanted"),
    ]),

    # ══ H9: Billing (thin — clinical charge capture + claim lifecycle; ALL money moves through the
    # frozen Finance Platform via workflow executors: action_post_journal (GL) / action_register_
    # settlement_document + action_auto_allocate/action_auto_reconcile (Settlement) / action_calculate_
    # tax (Tax) / action_apply_credit + action_issue_refund (Credit) / action_create_installment_plan
    # (Collections). Hospital owns ZERO ledger/tax/settlement/treasury logic. ``payer`` is the H1 master
    # (reused, not recreated); ``insurance_policy`` is the H2 coverage (referenced). Generalization:
    # charge_type/invoice_type/claim_type/payment_method are metadata — no per-variant entities. ══
    # Charge — a billable clinical event (FHIR ChargeItem). Captured during care; grouped into an invoice.
    "charge": _entity("charge", "Charge", "Charges", [
        _auto("charge_no", "Charge No", "CHG-"),
        _lookup("encounter", "Encounter", "encounter"),          # H4 — the clinical container
        _lookup("patient", "Patient", "patient"),                # H2
        _lookup("service", "Service", "service_catalog"),        # H1 billable service master
        _lookup("procedure_code", "Procedure Code", "procedure_code"),
        _select("charge_type", "Type", "consultation", "procedure", "lab", "imaging", "pharmacy",
                "room", "supply", "other"),
        _f("quantity", "Quantity", "decimal"),
        _f("unit_price", "Unit Price", "currency"),
        _f("amount", "Amount", "currency"),
        _f("is_taxable", "Taxable", "boolean"),
        _f("charge_date", "Charge Date", "datetime"),
        _lookup("invoice", "Invoice", "invoice"),                # set when billed
        _status("captured", "billed", "cancelled"),
    ]),
    # Invoice — the billable document that groups charges (FHIR Invoice + Account). Its finalization
    # posts to the GL + registers the AR settlement document (both via reused Finance executors).
    "invoice": _entity("invoice", "Invoice", "Invoices", [
        _auto("invoice_no", "Invoice No", "HINV-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("payer", "Payer", "payer"),                      # H1 payer master (may be self-pay)
        _select("invoice_type", "Type", "outpatient", "inpatient", "pharmacy", "emergency",
                "package"),
        _f("invoice_date", "Invoice Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("subtotal", "Subtotal", "currency"),
        _f("tax_amount", "Tax", "currency"),
        _f("total_amount", "Total", "currency"),
        _f("paid_amount", "Paid", "currency"),
        _f("balance", "Balance", "currency"),
        _status("draft", "finalized", "partially_paid", "paid", "cancelled"),
    ]),
    # Claim — an insurance claim submitted to a payer (FHIR Claim). References the invoice + the H2
    # coverage; the payer's adjudication comes back as a ``remittance``.
    "claim": _entity("claim", "Claim", "Claims", [
        _auto("claim_no", "Claim No", "CLM-"),
        _lookup("invoice", "Invoice", "invoice"),
        _lookup("payer", "Payer", "payer"),                      # H1
        _lookup("insurance_policy", "Coverage", "insurance_policy"),  # H2 coverage (referenced)
        _lookup("patient", "Patient", "patient"),
        _select("claim_type", "Type", "professional", "institutional", "pharmacy", "dental",
                "vision"),
        _f("claim_date", "Claim Date", "date"),
        _f("claimed_amount", "Claimed Amount", "currency"),
        _f("approved_amount", "Approved Amount", "currency"),
        _status("draft", "submitted", "in_review", "approved", "partially_approved", "denied",
                "paid"),
    ]),
    # Claim line — a per-service line of a claim (FHIR Claim.item). References the underlying charge;
    # carries the payer's per-line adjudication.
    "claim_line": _entity("claim_line", "Claim Line", "Claim Lines", [
        _auto("line_no", "Line No", "CLL-"),
        _lookup("claim", "Claim", "claim"),
        _lookup("charge", "Charge", "charge"),
        _lookup("service", "Service", "service_catalog"),
        _f("claimed_amount", "Claimed Amount", "currency"),
        _f("approved_amount", "Approved Amount", "currency"),
        _f("denial_reason", "Denial Reason", "text"),
        _status("submitted", "approved", "denied", "adjusted"),
    ]),
    # Pre-authorization — prior approval before service (FHIR Claim[use=preauth]). Distinct lifecycle
    # from a claim (occurs BEFORE care).
    "preauthorization": _entity("preauthorization", "Pre-Authorization", "Pre-Authorizations", [
        _auto("preauth_no", "Pre-Auth No", "PA-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("payer", "Payer", "payer"),
        _lookup("insurance_policy", "Coverage", "insurance_policy"),
        _lookup("procedure_code", "Procedure", "procedure_code"),
        _lookup("encounter", "Encounter", "encounter"),
        _f("requested_amount", "Requested Amount", "currency"),
        _f("approved_amount", "Approved Amount", "currency"),
        _f("valid_from", "Valid From", "date"),
        _f("valid_to", "Valid To", "date"),
        _f("authorization_ref", "Authorization Ref", "text"),
        _status("requested", "approved", "denied", "expired", "cancelled"),
    ]),
    # Remittance — the payer's adjudication result (FHIR ClaimResponse / PaymentReconciliation). Its
    # workflow auto-reconciles the payer's payment against the claim via the Settlement engine.
    "remittance": _entity("remittance", "Remittance", "Remittances", [
        _auto("remittance_no", "Remittance No", "RMT-"),
        _lookup("claim", "Claim", "claim"),
        _lookup("payer", "Payer", "payer"),
        _f("remittance_date", "Remittance Date", "date"),
        _f("approved_amount", "Approved Amount", "currency"),
        _f("paid_amount", "Paid Amount", "currency"),
        _f("denied_amount", "Denied Amount", "currency"),
        _f("adjustment_reason", "Adjustment Reason", "text"),
        _status("received", "posted", "reconciled", "disputed"),
    ]),
    # Payment — a cash receipt against an invoice (FHIR PaymentReconciliation). Any source (self-pay or
    # payer). Its workflow posts cash + ALLOCATES via the Settlement engine — Hospital owns no allocation.
    "payment": _entity("payment", "Payment", "Payments", [
        _auto("receipt_no", "Receipt No", "RCPT-"),
        _lookup("invoice", "Invoice", "invoice"),
        _lookup("patient", "Patient", "patient"),
        _lookup("payer", "Payer", "payer"),
        _select("payment_method", "Method", "cash", "card", "bank_transfer", "insurance",
                "cheque", "online"),
        _f("amount", "Amount", "currency"),
        _f("payment_date", "Payment Date", "date"),
        _f("reference", "Reference", "text"),
        _status("received", "allocated", "refunded", "reversed"),
    ]),

    # ══ H10: Blood Bank / Transfusion Medicine — the vein-to-vein clinical lifecycle (donor → donation
    # → serialized blood unit → qualification & compatibility testing → crossmatch → reserve → issue →
    # transfusion → haemovigilance). Generalization-first: component/donation/test/request/issue/reaction
    # variants are ``*_type`` metadata (no per-variant entities). A ``blood_unit`` is a SERIALIZED CLINICAL
    # object (the H8 implant precedent) — NOT Inventory stock; Inventory is reused only for fungible
    # reagents/kits, Assets for fridges/freezers (referenced via ``storage_asset``). Money never moves here
    # (transfusions are billed via the H9 ``charge``). REJECTED → metadata/status/derived: blood_component
    # (→ component_type), blood_inventory (→ derived over status + Inventory reagents), blood_screening/
    # infectious_disease_test/blood_grouping (→ test_type), compatibility (→ crossmatch.compatibility),
    # reservation (→ blood_unit reserved status), discard (→ discarded status + reason), traceability
    # (→ derived report/graph over the FK chain). ══
    # Donor — a blood donor (FHIR Patient/RelatedPerson). Own identity + eligibility/deferral; NOT a patient.
    "donor": _entity("donor", "Donor", "Donors", [
        _auto("donor_no", "Donor No", "HDNR-"),
        _f("name", "Name", "text", is_required=True),
        _select("donor_type", "Type", "voluntary", "replacement", "directed", "autologous"),
        _select("blood_group", "Blood Group", "a_pos", "a_neg", "b_pos", "b_neg", "o_pos", "o_neg",
                "ab_pos", "ab_neg", "unknown"),
        _f("date_of_birth", "Date of Birth", "date"),
        _select("gender", "Gender", "male", "female", "other"),
        _f("phone", "Phone", "text"),
        _f("email", "Email", "email"),
        _f("address", "Address", "textarea"),
        _f("last_donation_date", "Last Donation", "date"),
        _f("deferral_reason", "Deferral Reason", "text"),
        _f("deferred_until", "Deferred Until", "date"),
        _status("active", "deferred", "permanently_deferred", "inactive"),
    ]),
    # Donation — a collection event (FHIR BiologicallyDerivedProduct.collection). donation_no = the DIN.
    "donation": _entity("donation", "Donation", "Donations", [
        _auto("donation_no", "Donation No (DIN)", "DON-"),
        _lookup("donor", "Donor", "donor"),
        _select("donation_type", "Type", "whole_blood", "apheresis_platelet", "apheresis_plasma",
                "plasmapheresis", "autologous", "directed"),
        _lookup("facility", "Collection Facility", "facility"),
        _f("donation_date", "Donation Date", "datetime"),
        _f("volume_ml", "Volume (mL)", "integer"),
        _f("hemoglobin", "Hemoglobin (g/dL)", "decimal"),
        _f("collected_by", "Collected By", "user"),
        _status("collected", "tested", "processed", "quarantine", "released", "discarded"),
    ]),
    # Blood unit — the SERIALIZED product (FHIR BiologicallyDerivedProduct); one per component. Carries
    # ABO/Rh + expiry + its OWN status lifecycle (quarantine→available→reserved→issued→transfused/
    # discarded/recalled/expired). component_type is metadata (whole blood/PRBC/FFP/platelets/cryo).
    "blood_unit": _entity("blood_unit", "Blood Unit", "Blood Units", [
        _auto("unit_no", "Unit No", "BU-"),
        _lookup("donation", "Donation", "donation"),
        _select("component_type", "Component", "whole_blood", "prbc", "ffp", "platelets",
                "cryoprecipitate", "plasma"),
        _select("blood_group", "Blood Group", "a_pos", "a_neg", "b_pos", "b_neg", "o_pos", "o_neg",
                "ab_pos", "ab_neg"),
        _f("volume_ml", "Volume (mL)", "integer"),
        _f("collection_date", "Collection Date", "date"),
        _f("expiry_date", "Expiry Date", "date"),
        _lookup("storage_asset", "Storage Equipment", "asset"),     # Assets reference (fridge/freezer)
        _f("storage_location", "Storage Location", "text"),
        _lookup("reserved_for", "Reserved For", "patient"),          # reservation = state, not entity
        _f("reserved_until", "Reserved Until", "datetime"),
        _f("discard_reason", "Discard Reason", "text"),
        _f("recall_flag", "Recalled", "boolean"),
        _status("quarantine", "available", "reserved", "issued", "transfused", "discarded",
                "recalled", "expired"),
    ]),
    # Blood test — transfusion-medicine qualification + pre-transfusion testing (FHIR Observation/
    # DiagnosticReport). test_type unifies grouping/antibody-screen/infectious-disease/confirmatory; a
    # reactive result gates unit release. References the H5 ``specimen`` for the physical sample (reuse).
    "blood_test": _entity("blood_test", "Blood Test", "Blood Tests", [
        _auto("test_no", "Test No", "BT-"),
        _select("test_type", "Type", "abo_rh_grouping", "antibody_screen", "infectious_disease",
                "confirmatory"),
        _select("subject_type", "Subject", "donation", "unit", "recipient"),
        _lookup("donation", "Donation", "donation"),
        _lookup("blood_unit", "Blood Unit", "blood_unit"),
        _lookup("patient", "Recipient", "patient"),
        _lookup("specimen", "Specimen", "specimen"),                 # H5 physical sample (referenced)
        _select("result", "Result", "pending", "non_reactive", "reactive", "positive", "negative",
                "inconclusive"),
        _f("result_value", "Result Detail", "text"),
        _f("tested_by", "Tested By", "user"),
        _f("tested_at", "Tested At", "datetime"),
        _status("ordered", "in_progress", "resulted", "verified"),
    ]),
    # Blood request — a clinical transfusion order (FHIR ServiceRequest/SupplyRequest). request_type
    # carries urgency incl. emergency / massive-transfusion (metadata, not a per-variant entity).
    "blood_request": _entity("blood_request", "Blood Request", "Blood Requests", [
        _auto("request_no", "Request No", "BRQ-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("surgery", "Surgery", "surgery"),                    # H8 — for peri-operative transfusion
        _lookup("requesting_provider", "Requesting Provider", "provider"),
        _select("component_type", "Component", "whole_blood", "prbc", "ffp", "platelets",
                "cryoprecipitate", "plasma"),
        _select("blood_group", "Blood Group", "a_pos", "a_neg", "b_pos", "b_neg", "o_pos", "o_neg",
                "ab_pos", "ab_neg", "unknown"),
        _f("units_requested", "Units Requested", "integer"),
        _select("request_type", "Urgency", "routine", "urgent", "emergency", "massive_transfusion"),
        _f("required_by", "Required By", "datetime"),
        _f("indication", "Clinical Indication", "textarea"),
        _status("requested", "crossmatching", "ready", "issued", "fulfilled", "cancelled"),
    ]),
    # Crossmatch — the compatibility RELATIONSHIP (recipient request × blood unit → compatibility result;
    # FHIR Task + Observation). Gates reservation/issue; ``compatibility`` is a result field, not an entity.
    "crossmatch": _entity("crossmatch", "Crossmatch", "Crossmatches", [
        _auto("crossmatch_no", "Crossmatch No", "XM-"),
        _lookup("blood_request", "Blood Request", "blood_request"),
        _lookup("blood_unit", "Blood Unit", "blood_unit"),
        _lookup("patient", "Recipient", "patient"),
        _select("method", "Method", "serologic", "electronic", "immediate_spin"),
        _select("compatibility", "Compatibility", "compatible", "incompatible",
                "compatible_with_caution"),
        _f("crossmatched_by", "Crossmatched By", "user"),
        _f("crossmatched_at", "Crossmatched At", "datetime"),
        _status("pending", "complete", "invalidated"),
    ]),
    # Blood issue — the issue EVENT (FHIR SupplyDelivery); unit → ward/OR/patient. Emergency issue records
    # ``authorized_by`` + ``override_reason`` (the audited override); transitions the unit to ``issued``.
    "blood_issue": _entity("blood_issue", "Blood Issue", "Blood Issues", [
        _auto("issue_no", "Issue No", "BIS-"),
        _lookup("blood_request", "Blood Request", "blood_request"),
        _lookup("blood_unit", "Blood Unit", "blood_unit"),
        _lookup("crossmatch", "Crossmatch", "crossmatch"),
        _lookup("patient", "Patient", "patient"),
        _select("issue_type", "Type", "routine", "emergency", "return"),
        _f("is_emergency", "Emergency Release", "boolean"),
        _f("issued_to", "Issued To (Ward/OR)", "text"),
        _f("issued_by", "Issued By", "user"),
        _f("issued_at", "Issued At", "datetime"),
        _f("authorized_by", "Authorized By", "user"),                # emergency override authorizer
        _f("override_reason", "Override Reason", "textarea"),         # emergency override justification
        _status("issued", "returned", "transfused", "wasted", "rejected"),
    ]),
    # Transfusion — the administration EVENT (FHIR Procedure); the atomic give into the patient + monitoring.
    "transfusion": _entity("transfusion", "Transfusion", "Transfusions", [
        _auto("transfusion_no", "Transfusion No", "TXN-"),
        _lookup("blood_issue", "Blood Issue", "blood_issue"),
        _lookup("blood_unit", "Blood Unit", "blood_unit"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _f("administered_by", "Administered By", "user"),
        _f("started_at", "Started At", "datetime"),
        _f("completed_at", "Completed At", "datetime"),
        _f("volume_ml", "Volume Transfused (mL)", "integer"),
        _status("started", "completed", "stopped", "reaction"),
    ]),
    # Transfusion reaction — haemovigilance investigation (FHIR AdverseEvent). reaction_type is metadata.
    "transfusion_reaction": _entity("transfusion_reaction", "Transfusion Reaction",
                                    "Transfusion Reactions", [
        _auto("reaction_no", "Reaction No", "TRX-"),
        _lookup("transfusion", "Transfusion", "transfusion"),
        _lookup("blood_unit", "Blood Unit", "blood_unit"),
        _lookup("patient", "Patient", "patient"),
        _select("reaction_type", "Type", "febrile_non_hemolytic", "allergic", "anaphylactic",
                "acute_hemolytic", "delayed_hemolytic", "taco", "trali", "septic", "other"),
        _select("severity", "Severity", "mild", "moderate", "severe", "life_threatening"),
        _f("onset_at", "Onset At", "datetime"),
        _f("symptoms", "Symptoms", "textarea"),
        _f("action_taken", "Action Taken", "textarea"),
        _f("reported_by", "Reported By", "user"),
        _status("reported", "under_investigation", "investigated", "closed"),
    ]),
    # Blood recall / look-back — a regulated post-donation investigation spanning affected units/recipients.
    "blood_recall": _entity("blood_recall", "Blood Recall", "Blood Recalls", [
        _auto("recall_no", "Recall No", "BRC-"),
        _lookup("donation", "Source Donation", "donation"),
        _lookup("donor", "Donor", "donor"),
        _select("reason", "Reason", "donor_positive_test", "post_donation_illness", "quality_defect",
                "recipient_reaction", "regulatory"),
        _f("description", "Description", "textarea"),
        _f("units_affected", "Units Affected", "integer"),
        _f("initiated_by", "Initiated By", "user"),
        _f("initiated_at", "Initiated At", "datetime"),
        _f("disposition", "Disposition", "textarea"),
        _status("initiated", "tracing", "recipients_notified", "closed"),
    ]),
    # Storage excursion — a regulated cold-chain event owned by Blood Bank (NOT an IoT/monitoring engine;
    # real-time sensor ingestion belongs to the Integrations platform). References the Assets fridge/freezer
    # via ``storage_asset``; its workflow notifies staff and drives the quarantine → release/discard
    # disposition over the affected units' status lifecycle. Pure structured business event — no telemetry.
    "storage_excursion": _entity("storage_excursion", "Storage Excursion", "Storage Excursions", [
        _auto("excursion_no", "Excursion No", "EXC-"),
        _lookup("storage_asset", "Storage Equipment", "asset"),      # Assets reference (owned by Assets)
        _f("storage_location", "Affected Location", "text"),
        _f("excursion_start", "Excursion Start", "datetime"),
        _f("excursion_end", "Excursion End", "datetime"),
        _f("min_temperature", "Min Temp (°C)", "decimal"),
        _f("max_temperature", "Max Temp (°C)", "decimal"),
        _select("severity", "Severity", "minor", "major", "critical"),
        _f("investigation", "Investigation", "textarea"),
        _select("disposition", "Disposition", "pending", "units_released", "units_quarantined",
                "units_discarded"),
        _f("quarantine_wf_ref", "Quarantine Workflow Ref", "text"),
        _f("reported_by", "Reported By", "user"),
        _status("open", "investigating", "resolved", "closed"),
    ]),

    # ══ H11: Quality · Accreditation · Patient Safety — quality-governance business objects over the
    # FROZEN cross-cutting platforms (Analytics KPI / Reporting / Dashboards / Rules[block_save] / SLA /
    # Approvals / Workflow / Documents / Audit). Generalization-first: incident/audit/capa/standard/
    # complaint/risk variants are ``*_type`` metadata — NO per-variant entities. Quality *indicators* =
    # Analytics KPIs (not entities); policies/SOPs = Documents; RCA = the incident's investigation phase
    # (fields+status, not an entity). ``clinical_review`` (M&M/peer review) DEFERRED (needs a field-level
    # confidentiality model). No money/stock/legal-entity here (Finance/Inventory/Companies untouched). ══
    # Incident — a patient-safety event (FHIR AdverseEvent). incident_type + sentinel/near-miss flags are
    # metadata; the RCA is captured as investigation fields + status (no separate investigation entity).
    "incident": _entity("incident", "Incident", "Incidents", [
        _auto("incident_no", "Incident No", "INC-"),
        _select("incident_type", "Type", "fall", "medication_error", "hai", "wrong_site",
                "pressure_injury", "equipment", "security", "documentation", "delay_in_care", "other"),
        _select("severity", "Severity", "no_harm", "minor", "moderate", "major", "catastrophic"),
        _f("is_sentinel", "Sentinel Event", "boolean"),
        _f("is_near_miss", "Near Miss", "boolean"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("department", "Department", "clinical_department"),
        _lookup("asset", "Equipment", "asset"),                  # Assets reference (equipment incidents)
        _f("location", "Location", "text"),
        _f("reported_by", "Reported By", "user"),
        _f("occurred_at", "Occurred At", "datetime"),
        _f("description", "Description", "textarea"),
        _f("immediate_action", "Immediate Action", "textarea"),
        _f("root_cause", "Root Cause", "textarea"),              # RCA folded (investigation phase)
        _f("contributing_factors", "Contributing Factors", "textarea"),
        _f("investigation_summary", "Investigation Summary", "textarea"),
        _status("reported", "under_investigation", "rca_complete", "action_planned", "closed"),
    ]),
    # CAPA — a corrective/preventive action (FHIR Task). capa_type metadata; sourced from an incident /
    # audit_finding / complaint (lookups). SLA governs the due date (SLA engine, auto-attached on create).
    "capa": _entity("capa", "Corrective / Preventive Action", "CAPAs", [
        _auto("capa_no", "CAPA No", "CAPA-"),
        _select("capa_type", "Type", "corrective", "preventive"),
        _f("title", "Title", "text", is_required=True),
        _lookup("incident", "Incident", "incident"),
        _lookup("audit_finding", "Audit Finding", "audit_finding"),
        _lookup("complaint", "Complaint", "complaint"),
        _f("description", "Description", "textarea"),
        _f("owner", "Owner", "user"),
        _f("target_date", "Target Date", "date"),
        _f("completed_date", "Completed Date", "date"),
        _f("effectiveness_verified", "Effectiveness Verified", "boolean"),
        _f("effectiveness_notes", "Effectiveness Notes", "textarea"),
        _status("open", "in_progress", "implemented", "verified", "closed", "cancelled"),
    ]),
    # Accreditation — the hospital's accreditation cycle/status against a body. body_type metadata (JCI/
    # NABH/CBAHI/CAP/ISO/CMS) — accreditation_body is NOT a separate thin entity (leaner than the U8 split).
    "accreditation": _entity("accreditation", "Accreditation", "Accreditations", [
        _auto("accreditation_no", "Accreditation No", "ACR-"),
        _f("name", "Name", "text", is_required=True),
        _select("body_type", "Body", "jci", "nabh", "cbahi", "cap", "iso", "cms", "other"),
        _f("scope", "Scope", "text"),
        _f("valid_from", "Valid From", "date"),
        _f("valid_to", "Valid To", "date"),
        _f("surveyor_org", "Surveyor Organization", "text"),
        _status("draft", "self_assessment", "survey_scheduled", "surveyed", "accredited",
                "conditional", "denied", "expired"),
    ]),
    # Quality standard — a standard/requirement reference (accreditation chapter/ME, or a regulatory/
    # statutory/policy requirement). source_type + standard_type metadata GENERALIZE the U8 compliance_
    # requirement/record split into one reference (+ audit_finding = the compliance result).
    "quality_standard": _entity("quality_standard", "Quality Standard", "Quality Standards", [
        _f("standard_code", "Code", "text", is_required=True),
        _f("title", "Title", "text", is_required=True),
        _select("source_type", "Source", "accreditation", "regulatory", "statutory", "policy"),
        _select("standard_type", "Level", "chapter", "standard", "measurable_element"),
        _select("body_type", "Body", "jci", "nabh", "cbahi", "cap", "iso", "cms", "moh", "other"),
        _f("description", "Description", "textarea"),
        _status("active", "retired"),
    ]),
    # Quality audit — an audit / survey / rounds EVENT (FHIR Task). audit_type GENERALIZES survey/hand-
    # hygiene/EOC-rounds/clinical/medication/record/mock — no per-type entities.
    "quality_audit": _entity("quality_audit", "Quality Audit", "Quality Audits", [
        _auto("audit_no", "Audit No", "AUD-"),
        _f("name", "Name", "text", is_required=True),
        _select("audit_type", "Type", "accreditation_survey", "clinical", "hand_hygiene",
                "environment_of_care", "medication_use", "medical_record", "mock_survey", "other"),
        _lookup("accreditation", "Accreditation", "accreditation"),
        _lookup("department", "Department", "clinical_department"),
        _f("scheduled_date", "Scheduled Date", "date"),
        _f("conducted_by", "Conducted By", "user"),
        _f("score", "Score (%)", "decimal"),
        _f("summary", "Summary", "textarea"),
        _status("planned", "in_progress", "completed", "cancelled"),
    ]),
    # Audit finding — a finding/gap against a standard from an audit (= the compliance result). Child of
    # quality_audit; references the assessed quality_standard; its own severity + lifecycle.
    "audit_finding": _entity("audit_finding", "Audit Finding", "Audit Findings", [
        _auto("finding_no", "Finding No", "FND-"),
        _lookup("quality_audit", "Audit", "quality_audit"),
        _lookup("quality_standard", "Standard", "quality_standard"),
        _select("compliance", "Compliance", "compliant", "partial", "non_compliant",
                "not_applicable"),
        _select("severity", "Severity", "minor", "major", "critical"),
        _f("description", "Description", "textarea"),
        _f("recommendation", "Recommendation", "textarea"),
        _status("open", "capa_assigned", "resolved", "verified", "closed"),
    ]),
    # Complaint — a patient complaint / grievance (FHIR Communication). complaint_type + is_grievance
    # metadata (grievance/feedback are NOT separate entities).
    "complaint": _entity("complaint", "Complaint", "Complaints", [
        _auto("complaint_no", "Complaint No", "CMP-"),
        _select("complaint_type", "Type", "clinical", "service", "billing", "facility", "staff",
                "communication", "other"),
        _f("is_grievance", "Grievance", "boolean"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _f("complainant", "Complainant", "text"),
        _lookup("department", "Department", "clinical_department"),
        _select("severity", "Severity", "low", "medium", "high"),
        _f("received_at", "Received At", "datetime"),
        _f("description", "Description", "textarea"),
        _f("resolution_summary", "Resolution Summary", "textarea"),
        _status("received", "under_review", "resolved", "escalated", "closed"),
    ]),
    # Risk assessment — a proactive risk-register entry (FHIR RiskAssessment; JCI/NABH FMEA requirement).
    # method + category metadata; likelihood × impact → risk_score.
    "risk_assessment": _entity("risk_assessment", "Risk Assessment", "Risk Assessments", [
        _auto("risk_no", "Risk No", "RSK-"),
        _f("title", "Title", "text", is_required=True),
        _select("method", "Method", "fmea", "hazard", "general"),
        _select("category", "Category", "clinical", "operational", "environmental",
                "information_security", "financial", "strategic"),
        _lookup("department", "Department", "clinical_department"),
        _lookup("asset", "Asset", "asset"),
        _select("likelihood", "Likelihood", "rare", "unlikely", "possible", "likely",
                "almost_certain"),
        _select("impact", "Impact", "negligible", "minor", "moderate", "major", "severe"),
        _f("risk_score", "Risk Score", "integer"),
        _f("mitigation", "Mitigation Plan", "textarea"),
        _select("residual_risk", "Residual Risk", "low", "medium", "high", "extreme"),
        _f("owner", "Owner", "user"),
        _f("review_date", "Review Date", "date"),
        _status("identified", "assessed", "mitigating", "monitored", "closed"),
    ]),

    # ══ H13: FINAL functional phase — Consent · Referral · HIM/ROI · CSSD · Dietary · Transport ·
    # Mortuary. Genuine Hospital business objects over the FROZEN platforms; IPC isolation reuses H4
    # care_plan(care_plan_type=isolation) — NO isolation entity (Readiness Gate). Generalization-first:
    # every variant is ``*_type`` metadata. Signed forms/certs = Documents; disclosure trail = Audit;
    # instrument capital = Assets; kitchen/packs = Inventory; money = Finance — zero ownership leakage. ══
    # Consent — a clinical-legal consent record (FHIR Consent). consent_type metadata; the signed FORM is
    # a Document, e-signature is Portal, obtain/expire is Workflow/Rules — Hospital owns only the record.
    "consent": _entity("consent", "Consent", "Consents", [
        _auto("consent_no", "Consent No", "CNS-"),
        _select("consent_type", "Type", "treatment", "surgery", "anaesthesia", "transfusion",
                "procedure", "privacy", "research", "photography", "data_sharing", "dnr"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("surgery", "Surgery", "surgery"),
        _f("description", "Description", "textarea"),
        _f("obtained_by", "Obtained By", "user"),
        _f("witnessed_by", "Witnessed By", "user"),
        _f("valid_from", "Valid From", "date"),
        _f("valid_to", "Valid To", "date"),
        _f("document_ref", "Signed Document Ref", "text"),          # Documents platform reference
        _status("draft", "obtained", "active", "withdrawn", "expired", "declined"),
    ]),
    # Referral — a care-transfer request (FHIR ServiceRequest[referral]); DISTINCT from a diagnostic order.
    # referral_type metadata; completion feedback = a field (not an entity).
    "referral": _entity("referral", "Referral", "Referrals", [
        _auto("referral_no", "Referral No", "REF-"),
        _select("referral_type", "Type", "internal", "external", "inbound", "outbound"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("from_provider", "From Provider", "provider"),
        _lookup("from_department", "From Department", "clinical_department"),
        _lookup("to_provider", "To Provider", "provider"),
        _lookup("to_specialty", "To Specialty", "specialty"),
        _f("external_facility", "External Facility", "text"),        # external partner (not Companies)
        _f("reason", "Reason", "textarea"),
        _select("priority", "Priority", "routine", "urgent", "emergency"),
        _f("feedback", "Completion Feedback", "textarea"),
        _status("draft", "sent", "accepted", "scheduled", "completed", "declined", "cancelled"),
    ]),
    # Medical record request (HIM/ROI) — Hospital owns the REQUEST metadata; the released FILES = Documents,
    # the disclosure TRAIL = Audit (HIPAA accounting-of-disclosures), RETENTION = the Backups platform.
    "medical_record_request": _entity(
        "medical_record_request", "Medical Record Request", "Medical Record Requests", [
            _auto("request_no", "Request No", "ROI-"),
            _select("request_type", "Type", "roi", "copy", "amendment", "transfer",
                    "audit_disclosure"),
            _lookup("patient", "Patient", "patient"),
            _f("requester", "Requester", "text"),
            _select("requester_type", "Requester Type", "patient", "legal", "insurer", "provider",
                    "government", "other"),
            _f("purpose", "Purpose", "text"),
            _f("scope", "Scope", "textarea"),
            _f("legal_basis", "Legal Basis", "text"),
            _f("disclosed_to", "Disclosed To", "text"),
            _f("released_ref", "Released Document Ref", "text"),     # Documents platform reference
            _status("requested", "in_review", "approved", "released", "denied", "closed"),
        ]),
    # Instrument set (CSSD) — a reusable tray with its own STERILE lifecycle (Assets owns the capital
    # register; this owns sterile state). set_type metadata.
    "instrument_set": _entity("instrument_set", "Instrument Set", "Instrument Sets", [
        _auto("set_no", "Set No", "SET-"),
        _f("name", "Name", "text", is_required=True),
        _select("set_type", "Type", "general", "orthopedic", "laparoscopic", "cardiac", "ophthalmic",
                "dental", "ent", "custom"),
        _lookup("owning_department", "Owning Department", "clinical_department"),
        _lookup("asset_ref", "Asset Register", "asset"),            # Assets capital reference
        _f("contents", "Contents", "textarea"),
        _f("location", "Location", "text"),
        _f("sterile_until", "Sterile Until", "date"),
        _status("available", "issued", "in_use", "soiled", "in_cycle", "sterile", "expired",
                "retired"),
    ]),
    # Sterilization cycle (CSSD) — a sterilization batch (cycle_type metadata). References the Assets
    # sterilizer; a PASS sets the linked instrument_set sterile (OT traceability = set→cycle→surgery).
    "sterilization_cycle": _entity("sterilization_cycle", "Sterilization Cycle",
                                   "Sterilization Cycles", [
        _auto("cycle_no", "Cycle No", "STC-"),
        _select("cycle_type", "Type", "steam", "eto", "plasma", "dry_heat", "chemical"),
        _lookup("sterilizer_asset", "Sterilizer", "asset"),        # Assets equipment
        _lookup("instrument_set", "Instrument Set", "instrument_set"),
        _f("load_contents", "Load Contents", "textarea"),
        _f("load_ref", "Load Ref", "text"),
        _f("cycle_date", "Cycle Date", "datetime"),
        _select("bio_indicator", "Biological Indicator", "pending", "pass", "fail"),
        _f("operator", "Operator", "user"),
        _f("sterile_until", "Sterile Until", "date"),
        _status("loaded", "running", "passed", "failed", "released"),
    ]),
    # Diet order — a nutrition order (FHIR NutritionOrder). diet_type/texture metadata; allergy-aware via
    # the H4 allergy reference; meal production = Inventory/kitchen, nutrition assessment = H4 clinical_note.
    "diet_order": _entity("diet_order", "Diet Order", "Diet Orders", [
        _auto("order_no", "Order No", "DIET-"),
        _select("diet_type", "Type", "regular", "diabetic", "renal", "cardiac", "low_sodium", "npo",
                "clear_liquid", "full_liquid", "soft", "pureed", "enteral", "parenteral"),
        _select("texture", "Texture", "regular", "soft", "minced", "pureed", "liquid"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _lookup("allergy", "Allergy", "allergy"),                   # H4 allergy (allergy-aware)
        _f("calories", "Calories/day", "integer"),
        _f("special_instructions", "Special Instructions", "textarea"),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("ordered_by", "Ordered By", "user"),
        _status("draft", "active", "held", "completed", "cancelled"),
    ]),
    # Transport request — an internal patient-movement request. transport_type + purpose metadata; the
    # porter is the assigned user (not an entity).
    "transport_request": _entity("transport_request", "Transport Request", "Transport Requests", [
        _auto("request_no", "Request No", "TRP-"),
        _select("transport_type", "Type", "wheelchair", "stretcher", "bed", "ambulatory"),
        _select("purpose", "Purpose", "ot", "radiology", "discharge", "ward", "admission",
                "procedure", "other"),
        _lookup("patient", "Patient", "patient"),
        _f("from_location", "From", "text"),
        _f("to_location", "To", "text"),
        _select("priority", "Priority", "routine", "urgent", "stat"),
        _f("requested_at", "Requested At", "datetime"),
        _f("assigned_to", "Assigned Porter", "user"),
        _status("requested", "assigned", "in_transit", "completed", "cancelled"),
    ]),
    # Death record (mortuary) — a regulated death record + body custody (FHIR Patient.deceased). manner
    # metadata; custody/release/legal-hold/coroner = fields+status; the certificate is a Document.
    "death_record": _entity("death_record", "Death Record", "Death Records", [
        _auto("record_no", "Record No", "DTH-"),
        _lookup("patient", "Patient", "patient"),
        _lookup("encounter", "Encounter", "encounter"),
        _f("time_of_death", "Time of Death", "datetime"),
        _f("cause_of_death", "Cause of Death", "textarea"),
        _select("manner", "Manner", "natural", "accident", "suicide", "homicide", "undetermined"),
        _f("certified_by", "Certified By", "user"),
        _f("certificate_no", "Certificate No", "text"),
        _f("autopsy_required", "Autopsy Required", "boolean"),
        _f("coroner_referred", "Coroner Referred", "boolean"),
        _f("mortuary_location", "Mortuary Location", "text"),
        _f("legal_hold", "Legal Hold", "boolean"),
        _f("released_to", "Released To", "text"),
        _f("release_date", "Release Date", "date"),
        _status("recorded", "certified", "in_mortuary", "released", "legal_hold", "closed"),
    ]),
}

_MAIN = list(HOSPITAL_OBJECTS.keys())


# ── workflows (reuse the Workflow engine + the Guard Framework CG-1) ───────────────────────────────
def _wf(slug, name, entity_slug, steps, edges, trigger_type="record_created", trigger_config=None):
    return {"slug": slug, "name": name, "trigger_type": trigger_type,
            "trigger_config": trigger_config or {}, "entity_slug": entity_slug,
            "steps": steps, "edges": edges}


def _gq(entity, **eq):
    """NQL AST query for a guard rule (single entity + equality conditions). ``{{record.*}}`` templates
    are resolved by the frozen Core ``action_guard`` executor. Identical pattern to University U2."""
    conds = [{"field": k, "op": "=", "value": v} for k, v in eq.items()]
    return {"entity": entity, "filter": {"op": "and", "conditions": conds}}


# H3 appointment-booking guards (config only — ALL enforcement is the reusable Core Guard Framework,
# CG-1). An appointment is created ``confirmed``; each guard measures live cross-record state WITH the
# new record included (hence ``lte``), and the false branch waitlists an ineligible booking. Capacity
# is DYNAMIC (read from provider_schedule.capacity). Mirrors the certified University registration
# eligibility — zero appointment-specific enforcement logic.
_APPOINTMENT_GUARDS = [
    {"name": "capacity",
     "query": _gq("appointment", provider_schedule="{{record.provider_schedule}}",
                  status="confirmed"),
     "aggregate": "count", "operator": "lte",
     "threshold": {"query": _gq("provider_schedule", id="{{record.provider_schedule}}"),
                   "aggregate": "value", "field": "capacity"},
     "severity": "block", "message": "This session is fully booked."},
    {"name": "provider_available",
     "query": _gq("schedule_exception", provider="{{record.provider}}",
                  exception_date="{{record.appointment_date}}", status="active"),
     "operator": "not_exists",
     "severity": "block", "message": "The provider is unavailable on this date."},
]

# H6 drug-safety guard (config only — ALL enforcement is the reusable Core Guard Framework, CG-1; no
# medication-specific CDS engine, no AI per §2). Duplicate therapy: a new prescription_item is created
# ``active``; the guard counts active items for the SAME patient+drug (incl. the new one) and passes
# only when ≤ 1 — i.e. it fails when the patient already has another active order for the drug. The
# false branch holds the item for pharmacist review. Allergy-contraindication and drug-drug interaction
# use the SAME mechanism but need richer allergen↔drug matching / a licensed interaction knowledge base
# (a future Rules/reference-data addition or Platform Gap) — NEVER a private H6 engine.
_MEDICATION_SAFETY_GUARDS = [
    {"name": "duplicate_therapy",
     "query": _gq("prescription_item", patient="{{record.patient}}", drug="{{record.drug}}",
                  status="active"),
     "aggregate": "count", "operator": "lte", "threshold": 1,
     "severity": "block",
     "message": "An active order for this drug already exists for the patient (possible duplicate "
                "therapy) — held for pharmacist review."},
]

# H7 bed-availability guard (config only — the reusable Core Guard Framework, CG-1; H7 owns the
# occupancy lifecycle, H1 owns the bed). A new bed_assignment is created ``assigned``; the guard passes
# only when NO other assignment currently OCCUPIES the same bed — preventing a double-booking. Mirrors
# the H3 appointment provider-availability guard (not_exists). Zero bed-specific enforcement logic.
_BED_AVAILABILITY_GUARDS = [
    {"name": "bed_available",
     "query": _gq("bed_assignment", bed="{{record.bed}}", status="occupied"),
     "operator": "not_exists",
     "severity": "block", "message": "This bed is already occupied."},
]

# H8 theatre-session capacity guard (config only — the reusable Core Guard Framework, CG-1; a theatre
# is a resource with an availability session). A surgery is booked ``booked``; the guard counts booked
# cases against the same ot_schedule ≤ the session capacity. Mirrors the H3 appointment capacity guard
# exactly (dynamic threshold read from ot_schedule.capacity). Zero surgery-specific enforcement logic.
_SURGERY_BOOKING_GUARDS = [
    {"name": "theatre_capacity",
     "query": _gq("surgery", ot_schedule="{{record.ot_schedule}}", status="booked"),
     "aggregate": "count", "operator": "lte",
     "threshold": {"query": _gq("ot_schedule", id="{{record.ot_schedule}}"),
                   "aggregate": "value", "field": "capacity"},
     "severity": "block", "message": "This theatre session is fully booked."},
]

# H10 blood-safety guards (config only — the reusable Core Guard Framework, CG-1; NO private transfusion
# CDS engine, NO AI per §2). Two safety gates: (1) a unit may only be RELEASED (quarantine→available) when
# no reactive qualification test exists; (2) a unit may only be ISSUED to a patient when a COMPATIBLE
# crossmatch exists AND the unit is not already issued. Emergency issue reuses the SAME guards at ``warn``
# severity — documented + audited, never blocking (the certified block/warn primitive). The ABO/Rh
# determination is recorded by the technologist as the crossmatch ``compatibility`` result; the enforceable
# platform gate is "no issue without a compatible crossmatch" — an electronic ABO cross-check against a
# reference matrix is a future Rules/reference addition (Guard enhancement), NEVER a Hospital engine.
_UNIT_RELEASE_GUARDS = [
    # ``{{record_id}}`` is the trigger record's own id (the top-level run-context key the dispatcher
    # sets) — a guard query has no ``run.record_id`` fallback, so the self-reference must use it (not
    # ``{{record.id}}``, which only resolves inside record-action executors).
    {"name": "no_reactive_tests",
     "query": _gq("blood_test", blood_unit="{{record_id}}", result="reactive"),
     "operator": "not_exists",
     "severity": "block",
     "message": "A reactive qualification test exists for this unit — it cannot be released."},
]


def _issue_guards(severity):
    """The routine-issue safety guard: a unit may only be issued when a COMPATIBLE crossmatch exists for
    this request+unit. ``block`` for routine, ``warn`` for emergency uncrossmatched release (documented +
    audited, never blocking) — one definition, two severities. Double-issue is prevented by the unit's own
    status lifecycle (a compatible crossmatch reserves the unit; issuing consumes it), so the gate stays a
    single positive-existence check (no self-referential count of the just-created issue)."""
    return [
        {"name": "compatible_crossmatch",
         "query": _gq("crossmatch", blood_request="{{record.blood_request}}",
                      blood_unit="{{record.blood_unit}}", compatibility="compatible"),
         "aggregate": "exists", "operator": "exists", "severity": severity,
         "message": "No compatible crossmatch exists for this unit and request."},
    ]


HOSPITAL_WORKFLOWS = [
    # Appointment booking → the Core Guard Framework confirms or waitlists (capacity + availability).
    _wf("appointment_eligibility", "Appointment Eligibility", "appointment", [
        {"slug": "guard", "step_type": "action_guard", "name": "Check Availability & Capacity",
         "is_entry": True, "config": {"guards": _APPOINTMENT_GUARDS}},
        {"slug": "confirm_notify", "step_type": "action_send_notification",
         "name": "Notify Confirmed", "config": {"template_slug": "appointment_confirmed"}},
        {"slug": "to_waitlist", "step_type": "action_update_record", "name": "Move to Waitlist",
         "config": {"entity_slug": "appointment", "record_id": "{{record.id}}",
                    "data": {"status": "waitlisted"}}},
        {"slug": "waitlist_notify", "step_type": "action_send_notification",
         "name": "Notify Waitlisted", "config": {"template_slug": "appointment_waitlisted"}},
    ], [
        {"source": "guard", "target": "confirm_notify", "condition_label": "true"},
        {"source": "guard", "target": "to_waitlist", "condition_label": "false"},
        {"source": "to_waitlist", "target": "waitlist_notify"},
    ]),
    # Checked-in → notify the provider the patient has arrived (the OPD queue is a derived view).
    _wf("appointment_checked_in", "Appointment Checked In", "appointment", [
        {"slug": "c", "step_type": "condition", "name": "Checked in?", "is_entry": True,
         "config": {"condition_nql": 'status = "checked_in"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Provider",
         "config": {"template_slug": "appointment_checked_in"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Cancelled → notify the patient (the freed capacity is re-measured live by the next booking guard).
    _wf("appointment_cancelled", "Appointment Cancelled", "appointment", [
        {"slug": "c", "step_type": "condition", "name": "Cancelled?", "is_entry": True,
         "config": {"condition_nql": 'status = "cancelled"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Patient",
         "config": {"template_slug": "appointment_cancelled"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H4 — Clinical Encounter lifecycle (drives the H3 appointment status; H3 owns the entity/enum,
    # H4 drives the clinical transition — the ownership boundary confirmed at the H3 ratification) ══
    _wf("encounter_started", "Encounter Started", "encounter", [
        {"slug": "c", "step_type": "condition", "name": "In progress?", "is_entry": True,
         "config": {"condition_nql": 'status = "in_progress"'}},
        {"slug": "appt", "step_type": "action_update_record", "name": "Appointment In Progress",
         "config": {"entity_slug": "appointment", "record_id": "{{record.appointment}}",
                    "data": {"status": "in_progress"}}},
    ], [{"source": "c", "target": "appt", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("encounter_completed", "Encounter Completed", "encounter", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "appt", "step_type": "action_update_record", "name": "Appointment Completed",
         "config": {"entity_slug": "appointment", "record_id": "{{record.appointment}}",
                    "data": {"status": "completed"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Patient",
         "config": {"template_slug": "visit_completed"}},
    ], [{"source": "c", "target": "appt", "condition_label": "true"},
        {"source": "appt", "target": "notify"}], trigger_type="record_updated"),

    # ══ H5 — Orders & Results (reuse Workflow / Notifications; result release drives the order status
    # and hands validated results back to the ordering clinician — the H5→H4 boundary) ══
    _wf("diagnostic_order_placed", "Diagnostic Order Placed", "diagnostic_order", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Department",
         "is_entry": True, "config": {"template_slug": "order_received"}},
    ], []),
    _wf("result_released", "Diagnostic Result Released", "diagnostic_result", [
        {"slug": "c", "step_type": "condition", "name": "Released?", "is_entry": True,
         "config": {"condition_nql": 'status = "released"'}},
        {"slug": "order", "step_type": "action_update_record", "name": "Mark Order Verified",
         "config": {"entity_slug": "diagnostic_order", "record_id": "{{record.diagnostic_order}}",
                    "data": {"status": "verified"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Ordering Provider",
         "config": {"template_slug": "result_available"}},
    ], [{"source": "c", "target": "order", "condition_label": "true"},
        {"source": "order", "target": "notify"}], trigger_type="record_updated"),
    _wf("specimen_rejected", "Specimen Rejected", "specimen", [
        {"slug": "c", "step_type": "condition", "name": "Rejected?", "is_entry": True,
         "config": {"condition_nql": 'status = "rejected"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Recollection",
         "config": {"template_slug": "specimen_rejected"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H6 — Pharmacy & Medication (reuse Workflow / Guard / Notifications; drug-safety CDS is the
    # frozen Guard Framework, NOT a private medication engine — mirrors the H3 booking eligibility) ══
    # Drug-safety check on a new prescription item: duplicate-therapy is expressed as a Core Guard
    # (count active items for the same patient+drug ≤ 1). A flagged item is put on hold for pharmacist
    # review and the prescriber is notified — deterministic, no AI (§2), zero medication-specific logic.
    _wf("prescription_safety_check", "Prescription Safety Check", "prescription_item", [
        {"slug": "guard", "step_type": "action_guard", "name": "Drug Safety (Duplicate Therapy)",
         "is_entry": True, "config": {"guards": _MEDICATION_SAFETY_GUARDS}},
        {"slug": "hold", "step_type": "action_update_record", "name": "Hold for Pharmacist Review",
         "config": {"entity_slug": "prescription_item", "record_id": "{{record.id}}",
                    "data": {"status": "on_hold"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Prescriber",
         "config": {"template_slug": "medication_safety_alert"}},
    ], [
        {"source": "guard", "target": "hold", "condition_label": "false"},
        {"source": "hold", "target": "notify"},
    ]),
    # A verified prescription is queued to the pharmacy for dispensing.
    _wf("prescription_verified", "Prescription Verified", "prescription", [
        {"slug": "c", "step_type": "condition", "name": "Verified?", "is_entry": True,
         "config": {"condition_nql": 'status = "verified"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Pharmacy",
         "config": {"template_slug": "prescription_to_dispense"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Dispensing the medication marks its prescription dispensed and notifies the ward/patient.
    _wf("medication_dispensed", "Medication Dispensed", "medication_dispense", [
        {"slug": "c", "step_type": "condition", "name": "Dispensed?", "is_entry": True,
         "config": {"condition_nql": 'status = "dispensed"'}},
        {"slug": "rx", "step_type": "action_update_record", "name": "Mark Prescription Dispensed",
         "config": {"entity_slug": "prescription", "record_id": "{{record.prescription}}",
                    "data": {"status": "dispensed"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Ward",
         "config": {"template_slug": "medication_ready"}},
    ], [{"source": "c", "target": "rx", "condition_label": "true"},
        {"source": "rx", "target": "notify"}], trigger_type="record_updated"),
    # A missed dose is a safety event — notify the prescriber (the MAR report surfaces the pattern).
    _wf("medication_missed", "Medication Dose Missed", "medication_administration", [
        {"slug": "c", "step_type": "condition", "name": "Missed?", "is_entry": True,
         "config": {"condition_nql": 'status = "missed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Prescriber",
         "config": {"template_slug": "medication_missed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Completing a medication reconciliation notifies the care team.
    _wf("medication_reconciliation_completed", "Medication Reconciliation Completed",
        "medication_reconciliation", [
            {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
             "config": {"condition_nql": 'status = "completed"'}},
            {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Care Team",
             "config": {"template_slug": "reconciliation_completed"}},
        ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H7 — Inpatient, Wards & Nursing (reuse Workflow / Guard / Notifications; bed availability is the
    # frozen Guard Framework; the occupancy lifecycle drives the H1 bed status — H7→H1 handoff) ══
    # Assigning a bed runs the Core bed-availability Guard (double-booking prevention).
    _wf("bed_assignment_check", "Bed Assignment Check", "bed_assignment", [
        {"slug": "guard", "step_type": "action_guard", "name": "Check Bed Availability",
         "is_entry": True, "config": {"guards": _BED_AVAILABILITY_GUARDS}},
        {"slug": "ok", "step_type": "action_send_notification", "name": "Notify Ward",
         "config": {"template_slug": "bed_assigned"}},
        {"slug": "conflict", "step_type": "action_send_notification", "name": "Notify Bed Conflict",
         "config": {"template_slug": "bed_conflict"}},
    ], [
        {"source": "guard", "target": "ok", "condition_label": "true"},
        {"source": "guard", "target": "conflict", "condition_label": "false"},
    ]),
    # Occupancy lifecycle drives the H1 bed master status (H7 owns occupancy; H1 owns the bed).
    _wf("bed_occupied", "Bed Occupied", "bed_assignment", [
        {"slug": "c", "step_type": "condition", "name": "Occupied?", "is_entry": True,
         "config": {"condition_nql": 'status = "occupied"'}},
        {"slug": "bed", "step_type": "action_update_record", "name": "Mark Bed Occupied",
         "config": {"entity_slug": "bed", "record_id": "{{record.bed}}",
                    "data": {"status": "occupied"}}},
    ], [{"source": "c", "target": "bed", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("bed_released", "Bed Released", "bed_assignment", [
        {"slug": "c", "step_type": "condition", "name": "Released?", "is_entry": True,
         "config": {"condition_nql": 'status = "released"'}},
        {"slug": "bed", "step_type": "action_update_record", "name": "Mark Bed Available",
         "config": {"entity_slug": "bed", "record_id": "{{record.bed}}",
                    "data": {"status": "available"}}},
    ], [{"source": "c", "target": "bed", "condition_label": "true"}],
        trigger_type="record_updated"),
    # A patient formally admitted → notify the ward/attending.
    _wf("admission_admitted", "Patient Admitted", "admission", [
        {"slug": "c", "step_type": "condition", "name": "Admitted?", "is_entry": True,
         "config": {"condition_nql": 'status = "admitted"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Ward",
         "config": {"template_slug": "patient_admitted"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # A completed transfer → notify the receiving ward.
    _wf("transfer_completed", "Transfer Completed", "transfer", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Receiving Ward",
         "config": {"template_slug": "transfer_completed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Discharge completed → close the admission (H7 discharge → admission handoff) + notify.
    _wf("discharge_completed", "Discharge Completed", "discharge", [
        {"slug": "c", "step_type": "condition", "name": "Discharged?", "is_entry": True,
         "config": {"condition_nql": 'status = "discharged"'}},
        {"slug": "adm", "step_type": "action_update_record", "name": "Close Admission",
         "config": {"entity_slug": "admission", "record_id": "{{record.admission}}",
                    "data": {"status": "discharged"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Care Team",
         "config": {"template_slug": "patient_discharged"}},
    ], [{"source": "c", "target": "adm", "condition_label": "true"},
        {"source": "adm", "target": "notify"}], trigger_type="record_updated"),

    # ══ H8 — Surgery / OT & Critical Care (reuse Workflow / Guard / Notifications; theatre capacity is
    # the frozen Guard Framework; the surgery lifecycle drives the H8 theatre occupancy status) ══
    # Booking a surgery runs the Core theatre-session capacity Guard.
    _wf("surgery_booking_check", "Surgery Booking Check", "surgery", [
        {"slug": "guard", "step_type": "action_guard", "name": "Check Theatre Capacity",
         "is_entry": True, "config": {"guards": _SURGERY_BOOKING_GUARDS}},
        {"slug": "ok", "step_type": "action_send_notification", "name": "Notify Surgical Team",
         "config": {"template_slug": "surgery_booked"}},
        {"slug": "conflict", "step_type": "action_send_notification", "name": "Notify OT Coordinator",
         "config": {"template_slug": "surgery_conflict"}},
    ], [
        {"source": "guard", "target": "ok", "condition_label": "true"},
        {"source": "guard", "target": "conflict", "condition_label": "false"},
    ]),
    # The surgery lifecycle drives the theatre occupancy status (H8 owns both — case ↔ its OT room).
    _wf("theatre_occupied", "Theatre Occupied", "surgery", [
        {"slug": "c", "step_type": "condition", "name": "In theatre?", "is_entry": True,
         "config": {"condition_nql": 'status = "in_theatre"'}},
        {"slug": "ot", "step_type": "action_update_record", "name": "Mark Theatre Occupied",
         "config": {"entity_slug": "operating_theatre",
                    "record_id": "{{record.operating_theatre}}", "data": {"status": "occupied"}}},
    ], [{"source": "c", "target": "ot", "condition_label": "true"}],
        trigger_type="record_updated"),
    _wf("theatre_released", "Theatre Released", "surgery", [
        {"slug": "c", "step_type": "condition", "name": "Closed?", "is_entry": True,
         "config": {"condition_nql": 'status = "closed"'}},
        {"slug": "ot", "step_type": "action_update_record", "name": "Mark Theatre Available",
         "config": {"entity_slug": "operating_theatre",
                    "record_id": "{{record.operating_theatre}}", "data": {"status": "cleaning"}}},
    ], [{"source": "c", "target": "ot", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Surgery completed → move to recovery: notify PACU/ward.
    _wf("surgery_completed", "Surgery Completed", "surgery", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Recovery",
         "config": {"template_slug": "surgery_completed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # ICU episode stepped down / discharged → notify the receiving ward.
    _wf("icu_stepped_down", "ICU Step-Down", "icu_episode", [
        {"slug": "c", "step_type": "condition", "name": "Stepped down?", "is_entry": True,
         "config": {"condition_nql": 'status = "stepped_down"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Ward",
         "config": {"template_slug": "icu_stepped_down"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
    # Recovery ready for discharge → notify the ward to receive the patient.
    _wf("recovery_ready", "Recovery Ready", "recovery_episode", [
        {"slug": "c", "step_type": "condition", "name": "Ready?", "is_entry": True,
         "config": {"condition_nql": 'status = "ready_for_discharge"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Ward",
         "config": {"template_slug": "recovery_ready"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H9 — Billing (reuse the Finance Platform executors ONLY; Hospital posts NOTHING itself). Every
    # money movement is a frozen executor: action_post_journal (GLBus), action_register_settlement_
    # document + action_auto_allocate/action_auto_reconcile (Settlement). Mirrors the CERTIFIED School
    # fee_invoice_posting / fee_payment_posting pattern. ══
    # Invoice finalized → post A/R (Dr 1100 / Cr 4100 Service Revenue) → register the AR settlement
    # document (for aging + matching) → notify → generate the invoice PDF. Idempotent on invoice_no.
    _wf("invoice_finalized", "Invoice Finalized", "invoice", [
        {"slug": "c", "step_type": "condition", "name": "Finalized?", "is_entry": True,
         "config": {"condition_nql": 'status = "finalized"'}},
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receivable",
         "config": {"source_module": "hospital", "source_ref": "{{record.invoice_no}}",
                    "memo": "Hospital invoice {{record.invoice_no}}",
                    "account_debit": "1100", "account_credit": "4100",
                    "amount": "{{record.total_amount}}"}},
        {"slug": "settle", "step_type": "action_register_settlement_document",
         "name": "Register A/R Document",
         "config": {"partner_ref": "{{record.payer}}", "direction": "debit",
                    "amount": "{{record.total_amount}}", "doc_type": "invoice",
                    "document_ref": "{{record.invoice_no}}", "document_date": "{{record.invoice_date}}",
                    "due_date": "{{record.due_date}}", "account_code": "1100",
                    "source_module": "hospital", "external_ref": "{{record.invoice_no}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Patient",
         "config": {"template_slug": "invoice_finalized"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Generate Invoice PDF",
         "config": {"template_slug": "hospital_invoice"}},
    ], [{"source": "c", "target": "post", "condition_label": "true"},
        {"source": "post", "target": "settle"}, {"source": "settle", "target": "notify"},
        {"source": "notify", "target": "doc"}], trigger_type="record_updated"),

    # Payment received → post cash (Dr 1000 / Cr 1100 A/R) → register the credit settlement document →
    # auto-allocate the partner's open credits against their oldest open A/R (FIFO) → notify → receipt.
    _wf("payment_received", "Payment Received", "payment", [
        {"slug": "post", "step_type": "action_post_journal", "name": "Post Receipt", "is_entry": True,
         "config": {"source_module": "hospital", "source_ref": "{{record.receipt_no}}",
                    "memo": "Hospital receipt {{record.receipt_no}}",
                    "account_debit": "1000", "account_credit": "1100",
                    "amount": "{{record.amount}}"}},
        {"slug": "settle", "step_type": "action_register_settlement_document",
         "name": "Register Payment", "config": {
             "partner_ref": "{{record.payer}}", "direction": "credit", "amount": "{{record.amount}}",
             "doc_type": "payment", "document_ref": "{{record.receipt_no}}",
             "document_date": "{{record.payment_date}}", "account_code": "1100",
             "source_module": "hospital", "external_ref": "{{record.receipt_no}}"}},
        {"slug": "alloc", "step_type": "action_auto_allocate", "name": "Allocate to Invoices",
         "config": {"partner_ref": "{{record.payer}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "payment_received"}},
        {"slug": "doc", "step_type": "action_generate_document", "name": "Generate Receipt",
         "config": {"template_slug": "hospital_receipt"}},
    ], [{"source": "post", "target": "settle"}, {"source": "settle", "target": "alloc"},
        {"source": "alloc", "target": "notify"}, {"source": "notify", "target": "doc"}]),

    # Claim submitted → notify the claims desk.
    _wf("claim_submitted", "Claim Submitted", "claim", [
        {"slug": "c", "step_type": "condition", "name": "Submitted?", "is_entry": True,
         "config": {"condition_nql": 'status = "submitted"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Claims Desk",
         "config": {"template_slug": "claim_submitted"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Remittance received → auto-reconcile the payer's payments to their open claims/A/R (Settlement) →
    # notify billing.
    _wf("remittance_received", "Remittance Received", "remittance", [
        {"slug": "recon", "step_type": "action_auto_reconcile", "name": "Reconcile Payer",
         "is_entry": True, "config": {"partner_ref": "{{record.payer}}"}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Billing",
         "config": {"template_slug": "remittance_received"}},
    ], [{"source": "recon", "target": "notify"}]),

    # Pre-authorization decided → notify the requesting clinician.
    _wf("preauthorization_decided", "Pre-Authorization Decided", "preauthorization", [
        {"slug": "c", "step_type": "condition", "name": "Decided?", "is_entry": True,
         "config": {"condition_nql": 'status = "approved" OR status = "denied"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Clinician",
         "config": {"template_slug": "preauth_decided"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H10 — Blood Bank (reuse the Core Guard Framework + Workflow engine; frozen executors only —
    # action_guard / action_update_record / action_send_notification / condition). Blood safety = Guards;
    # every state transition is an append-only event + immutable audit row (vein-to-vein traceability). ══
    # Unit release — a unit set ``available`` is gated by the Guard (no reactive test); a failing gate
    # reverts it to ``quarantine`` (the certified optimistic-create/false-branch-correct pattern, H3).
    _wf("unit_release_check", "Unit Release Check", "blood_unit", [
        {"slug": "c", "step_type": "condition", "name": "Released?", "is_entry": True,
         "config": {"condition_nql": 'status = "available"'}},
        {"slug": "guard", "step_type": "action_guard", "name": "Qualification Test Check",
         "config": {"guards": _UNIT_RELEASE_GUARDS}},
        {"slug": "released_notify", "step_type": "action_send_notification", "name": "Notify Released",
         "config": {"template_slug": "unit_released"}},
        {"slug": "requarantine", "step_type": "action_update_record", "name": "Re-Quarantine",
         "config": {"entity_slug": "blood_unit", "record_id": "{{record.id}}",
                    "data": {"status": "quarantine"}}},
        {"slug": "quarantine_notify", "step_type": "action_send_notification", "name": "Notify Held",
         "config": {"template_slug": "unit_quarantined"}},
    ], [{"source": "c", "target": "guard", "condition_label": "true"},
        {"source": "guard", "target": "released_notify", "condition_label": "true"},
        {"source": "guard", "target": "requarantine", "condition_label": "false"},
        {"source": "requarantine", "target": "quarantine_notify"}],
        trigger_type="record_updated"),

    # Crossmatch complete → a COMPATIBLE result reserves the unit for the recipient (reservation = state,
    # not entity); an INCOMPATIBLE result notifies the bench.
    _wf("crossmatch_completed", "Crossmatch Completed", "crossmatch", [
        {"slug": "c", "step_type": "condition", "name": "Compatible?", "is_entry": True,
         "config": {"condition_nql": 'compatibility = "compatible"'}},
        {"slug": "reserve", "step_type": "action_update_record", "name": "Reserve Unit",
         "config": {"entity_slug": "blood_unit", "record_id": "{{record.blood_unit}}",
                    "data": {"status": "reserved", "reserved_for": "{{record.patient}}"}}},
        {"slug": "ready", "step_type": "action_send_notification", "name": "Notify Ready",
         "config": {"template_slug": "crossmatch_ready"}},
        {"slug": "incompat", "step_type": "action_send_notification", "name": "Notify Incompatible",
         "config": {"template_slug": "crossmatch_incompatible"}},
    ], [{"source": "c", "target": "reserve", "condition_label": "true"},
        {"source": "reserve", "target": "ready"},
        {"source": "c", "target": "incompat", "condition_label": "false"}],
        trigger_type="record_updated"),

    # Routine issue — the SAFETY GATE. A routine issue is blocked unless a compatible crossmatch exists
    # and the unit is not already issued; a passing gate marks the unit ``issued``, a failing gate rejects
    # the issue. (Optimistic-create + Guard false-branch correction, mirrors H3.)
    _wf("blood_issue_check", "Blood Issue Check", "blood_issue", [
        {"slug": "c", "step_type": "condition", "name": "Routine?", "is_entry": True,
         "config": {"condition_nql": 'issue_type = "routine"'}},
        {"slug": "guard", "step_type": "action_guard", "name": "Compatibility & Availability Check",
         "config": {"guards": _issue_guards("block")}},
        {"slug": "mark_issued", "step_type": "action_update_record", "name": "Mark Unit Issued",
         "config": {"entity_slug": "blood_unit", "record_id": "{{record.blood_unit}}",
                    "data": {"status": "issued"}}},
        {"slug": "issued_notify", "step_type": "action_send_notification", "name": "Notify Issued",
         "config": {"template_slug": "blood_issued"}},
        {"slug": "reject", "step_type": "action_update_record", "name": "Reject Issue",
         "config": {"entity_slug": "blood_issue", "record_id": "{{record.id}}",
                    "data": {"status": "rejected"}}},
        {"slug": "reject_notify", "step_type": "action_send_notification", "name": "Notify Rejected",
         "config": {"template_slug": "blood_issue_rejected"}},
    ], [{"source": "c", "target": "guard", "condition_label": "true"},
        {"source": "guard", "target": "mark_issued", "condition_label": "true"},
        {"source": "mark_issued", "target": "issued_notify"},
        {"source": "guard", "target": "reject", "condition_label": "false"},
        {"source": "reject", "target": "reject_notify"}]),

    # Emergency uncrossmatched release — the SAME safety guards at ``warn`` severity (documented, audited,
    # NEVER blocking); mandatory ``authorized_by`` + ``override_reason`` on the issue. The unit is issued
    # immediately; a retrospective crossmatch is documented later (append-only events keep the true order).
    _wf("emergency_issue", "Emergency Uncrossmatched Issue", "blood_issue", [
        {"slug": "c", "step_type": "condition", "name": "Emergency?", "is_entry": True,
         "config": {"condition_nql": 'issue_type = "emergency"'}},
        {"slug": "guard", "step_type": "action_guard", "name": "Advisory Compatibility Check",
         "config": {"guards": _issue_guards("warn")}},
        {"slug": "mark_issued", "step_type": "action_update_record", "name": "Mark Unit Issued",
         "config": {"entity_slug": "blood_unit", "record_id": "{{record.blood_unit}}",
                    "data": {"status": "issued"}}},
        {"slug": "emerg_notify", "step_type": "action_send_notification", "name": "Notify Emergency Issue",
         "config": {"template_slug": "emergency_blood_issued"}},
    ], [{"source": "c", "target": "guard", "condition_label": "true"},
        {"source": "guard", "target": "mark_issued", "condition_label": "true"},
        {"source": "mark_issued", "target": "emerg_notify"}]),

    # Transfusion complete → the unit is consumed (``transfused``) + notify.
    _wf("transfusion_completed", "Transfusion Completed", "transfusion", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "unit", "step_type": "action_update_record", "name": "Mark Unit Transfused",
         "config": {"entity_slug": "blood_unit", "record_id": "{{record.blood_unit}}",
                    "data": {"status": "transfused"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Completed",
         "config": {"template_slug": "transfusion_completed"}},
    ], [{"source": "c", "target": "unit", "condition_label": "true"},
        {"source": "unit", "target": "notify"}], trigger_type="record_updated"),

    # Transfusion reaction → flag the transfusion + alert haemovigilance (the investigation lifecycle
    # runs on the reaction record itself).
    _wf("transfusion_reaction_reported", "Transfusion Reaction Reported", "transfusion_reaction", [
        {"slug": "flag", "step_type": "action_update_record", "name": "Flag Transfusion",
         "is_entry": True,
         "config": {"entity_slug": "transfusion", "record_id": "{{record.transfusion}}",
                    "data": {"status": "reaction"}}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Haemovigilance",
         "config": {"template_slug": "transfusion_reaction_alert"}},
    ], [{"source": "flag", "target": "notify"}]),

    # Storage excursion reported → alert Blood Bank staff. Determining + quarantining the affected units,
    # then release/discard, are staff actions over the SAME blood_unit status lifecycle (Generic Runtime);
    # the excursion record + its disposition are the regulated audit trail. No telemetry/monitoring engine.
    _wf("storage_excursion_reported", "Storage Excursion Reported", "storage_excursion", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Blood Bank",
         "is_entry": True, "config": {"template_slug": "storage_excursion_alert"}},
    ], []),

    # Blood recall / look-back initiated → alert Blood Bank. Tracing affected units/recipients reuses the
    # derived traceability report over the FK chain; affected units are recalled via the status lifecycle.
    _wf("blood_recall_initiated", "Blood Recall Initiated", "blood_recall", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Alert Recall",
         "is_entry": True, "config": {"template_slug": "blood_recall_alert"}},
    ], []),

    # Donor deferred → notify (donor safety / eligibility).
    _wf("donor_deferred", "Donor Deferred", "donor", [
        {"slug": "c", "step_type": "condition", "name": "Deferred?", "is_entry": True,
         "config": {"condition_nql": 'status = "deferred" OR status = "permanently_deferred"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Deferral",
         "config": {"template_slug": "donor_deferred"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # ══ H11 — Quality · Accreditation · Patient Safety (reuse Workflow + Notifications; SLA auto-attaches
    # on create; Rules[block_save] enforce closure integrity). Frozen executors only. ══
    # Incident reported → notify quality; a high-severity/sentinel event escalates to leadership.
    _wf("incident_reported", "Incident Reported", "incident", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Quality",
         "is_entry": True, "config": {"template_slug": "incident_reported"}},
        {"slug": "sev", "step_type": "condition", "name": "Severe?",
         "config": {"condition_nql": 'severity = "catastrophic" OR severity = "major"'}},
        {"slug": "escalate", "step_type": "action_send_notification", "name": "Escalate to Leadership",
         "config": {"template_slug": "sentinel_alert"}},
    ], [{"source": "notify", "target": "sev"},
        {"source": "sev", "target": "escalate", "condition_label": "true"}]),

    # Incident RCA complete → notify.
    _wf("incident_investigated", "Incident Investigated", "incident", [
        {"slug": "c", "step_type": "condition", "name": "RCA Complete?", "is_entry": True,
         "config": {"condition_nql": 'status = "rca_complete"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "incident_investigated"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # CAPA assigned → notify the owner (SLA governs the due date).
    _wf("capa_assigned", "CAPA Assigned", "capa", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Owner",
         "is_entry": True, "config": {"template_slug": "capa_assigned"}},
    ], []),

    # CAPA verified/closed → notify.
    _wf("capa_verified", "CAPA Verified", "capa", [
        {"slug": "c", "step_type": "condition", "name": "Verified?", "is_entry": True,
         "config": {"condition_nql": 'status = "verified" OR status = "closed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "capa_verified"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Quality audit completed → notify.
    _wf("audit_completed", "Quality Audit Completed", "quality_audit", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "audit_completed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Audit finding raised → notify quality (a CAPA is created manually, referencing the finding).
    _wf("finding_raised", "Audit Finding Raised", "audit_finding", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Quality",
         "is_entry": True, "config": {"template_slug": "finding_raised"}},
    ], []),

    # Complaint logged → notify (SLA governs the response time).
    _wf("complaint_logged", "Complaint Logged", "complaint", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "is_entry": True, "config": {"template_slug": "complaint_logged"}},
    ], []),

    # Complaint resolved → notify.
    _wf("complaint_resolved", "Complaint Resolved", "complaint", [
        {"slug": "c", "step_type": "condition", "name": "Resolved?", "is_entry": True,
         "config": {"condition_nql": 'status = "resolved" OR status = "closed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "complaint_resolved"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Accreditation granted → notify (mirrors the certified University U8 accreditation lifecycle).
    _wf("accreditation_granted", "Accreditation Granted", "accreditation", [
        {"slug": "c", "step_type": "condition", "name": "Accredited?", "is_entry": True,
         "config": {"condition_nql": 'status = "accredited"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "accreditation_granted"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Risk assessment with a high residual risk → notify the risk manager.
    _wf("risk_escalated", "Risk Escalated", "risk_assessment", [
        {"slug": "c", "step_type": "condition", "name": "High Residual?", "is_entry": True,
         "config": {"condition_nql": 'residual_risk = "high" OR residual_risk = "extreme"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Risk Manager",
         "config": {"template_slug": "risk_escalated"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}]),

    # ══ H13 — Ancillary & Information-Governance lifecycles (frozen executors only; SLA auto-attaches on
    # create; Rules[block_save] enforce closure integrity). ══
    # Consent obtained/active → notify care team.
    _wf("consent_obtained", "Consent Obtained", "consent", [
        {"slug": "c", "step_type": "condition", "name": "Obtained?", "is_entry": True,
         "config": {"condition_nql": 'status = "obtained" OR status = "active"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "consent_obtained"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Referral sent → notify the receiving team.
    _wf("referral_sent", "Referral Sent", "referral", [
        {"slug": "c", "step_type": "condition", "name": "Sent?", "is_entry": True,
         "config": {"condition_nql": 'status = "sent"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Receiver",
         "config": {"template_slug": "referral_sent"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Referral completed → notify the referrer (feedback loop).
    _wf("referral_completed", "Referral Completed", "referral", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Referrer",
         "config": {"template_slug": "referral_completed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Medical record request logged → notify HIM (SLA governs the ROI turnaround).
    _wf("record_request_logged", "Record Request Logged", "medical_record_request", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify HIM",
         "is_entry": True, "config": {"template_slug": "record_request_logged"}},
    ], []),

    # Medical record released → notify (the disclosure is captured on the immutable Audit trail).
    _wf("record_released", "Record Released", "medical_record_request", [
        {"slug": "c", "step_type": "condition", "name": "Released?", "is_entry": True,
         "config": {"condition_nql": 'status = "released"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "record_released"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Sterilization cycle result → a PASS marks the linked instrument set STERILE; a FAIL alerts CSSD.
    _wf("sterilization_result", "Sterilization Result", "sterilization_cycle", [
        {"slug": "c", "step_type": "condition", "name": "Passed?", "is_entry": True,
         "config": {"condition_nql": 'status = "passed"'}},
        {"slug": "sterile", "step_type": "action_update_record", "name": "Mark Set Sterile",
         "config": {"entity_slug": "instrument_set", "record_id": "{{record.instrument_set}}",
                    "data": {"status": "sterile"}}},
        {"slug": "pass_notify", "step_type": "action_send_notification", "name": "Notify Passed",
         "config": {"template_slug": "cycle_passed"}},
        {"slug": "fail_c", "step_type": "condition", "name": "Failed?",
         "config": {"condition_nql": 'status = "failed"'}},
        {"slug": "fail_notify", "step_type": "action_send_notification", "name": "Notify Failed",
         "config": {"template_slug": "cycle_failed"}},
    ], [{"source": "c", "target": "sterile", "condition_label": "true"},
        {"source": "sterile", "target": "pass_notify"},
        {"source": "c", "target": "fail_c", "condition_label": "false"},
        {"source": "fail_c", "target": "fail_notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Diet order active → notify the dietary/kitchen team.
    _wf("diet_order_active", "Diet Order Active", "diet_order", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Dietary",
         "is_entry": True, "config": {"template_slug": "diet_order_active"}},
    ], []),

    # Transport requested → notify the transport desk (SLA governs the turnaround).
    _wf("transport_requested", "Transport Requested", "transport_request", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Transport",
         "is_entry": True, "config": {"template_slug": "transport_requested"}},
    ], []),

    # Transport completed → notify.
    _wf("transport_completed", "Transport Completed", "transport_request", [
        {"slug": "c", "step_type": "condition", "name": "Completed?", "is_entry": True,
         "config": {"condition_nql": 'status = "completed"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "transport_completed"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),

    # Death recorded → notify mortuary + administration.
    _wf("death_recorded", "Death Recorded", "death_record", [
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify Mortuary",
         "is_entry": True, "config": {"template_slug": "death_recorded"}},
    ], []),

    # Body released → notify.
    _wf("death_released", "Body Released", "death_record", [
        {"slug": "c", "step_type": "condition", "name": "Released?", "is_entry": True,
         "config": {"condition_nql": 'status = "released"'}},
        {"slug": "notify", "step_type": "action_send_notification", "name": "Notify",
         "config": {"template_slug": "death_released"}},
    ], [{"source": "c", "target": "notify", "condition_label": "true"}],
        trigger_type="record_updated"),
]

# ── H11 data-integrity rules (reuse the Rules engine — block_save; the certified U9/C9 pattern) ─────
def _block_rule(entity, field, op, val, msg, trigger):
    return {"slug": f"validate_{entity}_{field}_{trigger}",
            "name": f"Validate {entity}.{field}", "entity_slug": entity, "trigger_on": trigger,
            "condition_nql": f"{field} {op} {val}",
            "actions": [{"type": "block_save", "message": msg}], "priority": 10}


HOSPITAL_RULES = [
    # Risk score bounded to a 5×5 matrix; audit score is a percentage.
    _block_rule("risk_assessment", "risk_score", ">", "25", "Risk score cannot exceed 25 (5×5 matrix).",
                "before_create"),
    _block_rule("risk_assessment", "risk_score", ">", "25", "Risk score cannot exceed 25 (5×5 matrix).",
                "before_update"),
    _block_rule("quality_audit", "score", ">", "100", "Audit score cannot exceed 100%.",
                "before_create"),
    _block_rule("quality_audit", "score", ">", "100", "Audit score cannot exceed 100%.",
                "before_update"),
    # A CAPA cannot be marked verified/closed until a completion date is recorded (closure integrity).
    # NOTE: the Rules engine compares values as strings, so a boolean flag (stored 0/1) is NOT a reliable
    # guard — an ``is null`` check on the completion date is representation-robust and equally meaningful.
    {"slug": "validate_capa_closure", "name": "Validate CAPA closure",
     "entity_slug": "capa", "trigger_on": "before_update",
     "condition_nql": 'status = "verified" AND completed_date is null',
     "actions": [{"type": "block_save",
                  "message": "A CAPA cannot be verified until its completion date is recorded."}],
     "priority": 10},
    # H13 closure-integrity rules (representation-robust `is null` — NEVER boolean `= false`; H11 lesson).
    {"slug": "validate_death_release", "name": "Validate death-record release",
     "entity_slug": "death_record", "trigger_on": "before_update",
     "condition_nql": 'status = "released" AND release_date is null',
     "actions": [{"type": "block_save",
                  "message": "A body cannot be released without a release date."}], "priority": 10},
    {"slug": "validate_record_disclosure", "name": "Validate ROI disclosure",
     "entity_slug": "medical_record_request", "trigger_on": "before_update",
     "condition_nql": 'status = "released" AND disclosed_to is null',
     "actions": [{"type": "block_save",
                  "message": "Records cannot be released without recording the disclosure recipient."}],
     "priority": 10},
    {"slug": "validate_consent_active", "name": "Validate consent activation",
     "entity_slug": "consent", "trigger_on": "before_update",
     "condition_nql": 'status = "active" AND valid_from is null',
     "actions": [{"type": "block_save",
                  "message": "A consent cannot be active without a valid-from date."}], "priority": 10},
]


# ── H11 SLA response-time policies (reuse the SLA engine; auto-attached on record.created; wall-clock) ─
def _sla(slug, name, entity, minutes, warn=80):
    return {"slug": slug, "name": name, "entity_slug": entity, "applies_when_nql": "",
            "targets": [{"metric": "resolution", "target_minutes": minutes,
                         "warning_at_percent": warn, "business_hours_only": False}]}


HOSPITAL_SLA_POLICIES = [
    _sla("incident_investigation_sla", "Incident Investigation Response", "incident", 2880),   # 48h
    _sla("capa_completion_sla", "CAPA Completion", "capa", 43200, 90),                          # 30d
    _sla("complaint_resolution_sla", "Complaint Resolution", "complaint", 10080),               # 7d
    # H13 ancillary/governance response-time SLAs.
    _sla("referral_response_sla", "Referral Response", "referral", 4320),                       # 3d
    _sla("transport_turnaround_sla", "Transport Turnaround", "transport_request", 120),         # 2h
    _sla("roi_turnaround_sla", "ROI Turnaround", "medical_record_request", 43200, 90),          # 30d
]


# ── H12 patient portal (reuse the frozen Portal Platform — PortalEntityGrant; ZERO new entities). Every
# portal query server-side AND-injects ``patient = portal_user.linked_record_id`` (unspoofable row
# isolation, Phase 1.34). H12 only DECLARES what the patient realm may access; portal USERS are provisioned
# at runtime by an admin (the portal-admin API, F3.7). Mirrors the certified University U8 portals. ═══════
def _grant(entity_slug, *, create=False, portal_type="patient", link_field="patient"):
    return {"entity_slug": entity_slug, "portal_type": portal_type, "link_field": link_field,
            "can_read": True, "can_create": create, "can_update": False}


HOSPITAL_PORTAL_GRANTS = [
    # Patient self-service — READ my clinical record, results, medications and bills (link_field=patient).
    _grant("encounter"),
    _grant("diagnostic_order"),
    _grant("diagnostic_result"),
    _grant("prescription"),
    _grant("invoice"),
    _grant("payment"),
    # Limited WRITE — the patient REQUESTS an appointment (→ the same H3 Guard eligibility confirms/
    # waitlists) and SUBMITS a complaint (→ the H11 complaint_logged workflow). The create path forces the
    # link field, so a patient can never file on behalf of another.
    _grant("appointment", create=True),
    _grant("complaint", create=True),
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
_READ = ["read"]
HOSPITAL_ROLES = [
    _role("hospital_administrator", "Hospital Administrator",
          "Full access to the Hospital solution.", [(None, _FULL + ["admin"])]),
    _role("master_data_manager", "Master Data Manager",
          "Owns facility, wards, beds, services, payers and reference terminologies.",
          [("facility", _FULL), ("clinical_department", _FULL), ("ward", _FULL), ("bed", _FULL),
           ("specialty", _FULL), ("service_catalog", _FULL), ("payer", _FULL),
           ("diagnosis_code", _FULL), ("procedure_code", _FULL), ("drug_formulary", _FULL),
           ("provider", _READ)]),
    _role("medical_staff_office", "Medical Staff Office",
          "Maintains the provider directory and specialties.",
          [("provider", _FULL), ("specialty", _FULL), ("clinical_department", _READ),
           ("facility", _READ)]),
    _role("facility_viewer", "Facility Viewer",
          "Read-only access to the facility and reference masters.",
          [(None, ["read", "export"])]),
    # H2 — patient administration roles.
    _role("registration_clerk", "Registration Clerk",
          "Front-desk patient registration: patients, contacts and insurance coverage.",
          [("patient", _FULL), ("patient_contact", _FULL), ("insurance_policy", _FULL),
           ("facility", _READ), ("payer", _READ)]),
    _role("health_information_manager", "Health Information Manager",
          "Stewards the patient master record (registration, corrections, record management).",
          [("patient", _FULL), ("patient_contact", _READ), ("insurance_policy", _READ)]),
    # H3 — scheduling roles.
    _role("appointment_scheduler", "Appointment Scheduler",
          "Owns provider schedules, exceptions, appointments and the waitlist.",
          [("provider_schedule", _FULL), ("schedule_exception", _FULL), ("appointment", _FULL),
           ("appointment_waitlist", _FULL), ("provider", _READ), ("patient", _READ),
           ("clinical_department", _READ)]),
    _role("receptionist", "Receptionist",
          "Books appointments, checks patients in and manages the waitlist.",
          [("appointment", _FULL), ("appointment_waitlist", ["create", "read", "update"]),
           ("provider_schedule", _READ), ("provider", _READ), ("patient", ["read", "create"])]),
    # H4 — clinical roles.
    _role("physician", "Physician",
          "Owns the clinical encounter: notes, diagnoses, problems, allergies, vitals, care plans.",
          [("encounter", _FULL), ("clinical_note", _FULL), ("diagnosis", _FULL), ("problem", _FULL),
           ("allergy", _FULL), ("vital_sign", _FULL), ("care_plan", _FULL),
           ("past_medical_history", _FULL), ("surgical_history", _FULL), ("family_history", _FULL),
           ("social_history", _FULL), ("patient", _READ),
           ("appointment", ["read", "update"]), ("diagnosis_code", _READ),
           # H5 (cross-phase role accretion, University precedent) — the physician ORDERS tests and
           # reviews validated results (a permission addition, not an H4 architectural change).
           ("diagnostic_order", ["create", "read", "update"]), ("diagnostic_result", _READ),
           ("result_item", _READ), ("service_catalog", _READ),
           # H6 — the physician PRESCRIBES medication and reconciles at transitions of care.
           ("prescription", ["create", "read", "update"]), ("prescription_item", _FULL),
           ("medication_reconciliation", ["create", "read", "update"]),
           ("medication_dispense", _READ), ("medication_administration", _READ),
           ("drug_formulary", _READ),
           # H7 — the physician ADMITS, rounds, transfers and DISCHARGES inpatients.
           ("admission", ["create", "read", "update"]), ("discharge", ["create", "read", "update"]),
           ("transfer", ["create", "read", "update"]), ("ward_round", _FULL),
           ("bed_assignment", _READ), ("nursing_observation", _READ),
           # H8 — the physician refers for surgery / critical care and reads perioperative records.
           ("surgery", ["create", "read"]), ("icu_episode", _READ),
           ("surgical_procedure", _READ), ("procedure_code", _READ),
           # H10 — the physician ORDERS blood and reviews compatibility/transfusion records.
           ("blood_request", ["create", "read", "update"]), ("crossmatch", _READ),
           ("blood_unit", _READ), ("transfusion", _READ),
           ("transfusion_reaction", ["create", "read"]),
           # H11 — the physician REPORTS patient-safety incidents and participates in quality/CAPA.
           ("incident", ["create", "read", "update"]), ("capa", ["read", "update"]),
           ("audit_finding", _READ),
           # H13 — the physician OBTAINS consent, makes referrals and orders diets.
           ("consent", ["create", "read", "update"]), ("referral", ["create", "read", "update"]),
           ("diet_order", ["create", "read", "update"])]),
    _role("nurse", "Nurse",
          "Records vitals, nursing notes and allergies; assists with the clinical record.",
          [("vital_sign", _FULL), ("clinical_note", ["create", "read", "update"]),
           ("allergy", ["create", "read", "update"]),
           ("past_medical_history", ["create", "read", "update"]),
           ("surgical_history", ["create", "read", "update"]),
           ("family_history", ["create", "read", "update"]),
           ("social_history", ["create", "read", "update"]),
           ("care_plan", ["read", "update"]), ("encounter", ["read", "update"]),
           ("problem", _READ), ("diagnosis", _READ), ("patient", _READ),
           # H6 — the nurse ADMINISTERS medication (the MAR events) and reads the active orders.
           ("medication_administration", _FULL), ("prescription", _READ),
           ("prescription_item", _READ), ("drug_formulary", _READ),
           # H7 — the nurse runs inpatient nursing: observations, tasks, handovers, rounds.
           ("nursing_observation", _FULL), ("nursing_task", _FULL), ("nursing_handover", _FULL),
           ("ward_round", ["read", "update"]), ("admission", _READ), ("transfer", _READ),
           ("bed_assignment", ["read", "update"]),
           # H10 — the nurse ADMINISTERS transfusions and reports reactions at the bedside.
           ("transfusion", _FULL), ("transfusion_reaction", ["create", "read", "update"]),
           ("blood_issue", _READ), ("blood_unit", _READ), ("blood_request", ["create", "read"]),
           # H11 — the nurse REPORTS incidents and logs complaints at the point of care.
           ("incident", ["create", "read", "update"]), ("complaint", ["create", "read"]),
           # H13 — the nurse witnesses consent and requests patient transport.
           ("consent", ["create", "read", "update"]), ("transport_request", ["create", "read"]),
           ("diet_order", _READ)]),
    _role("medical_director", "Medical Director",
          "Institution-wide clinical read access + oversight.",
          [("encounter", _READ), ("clinical_note", _READ), ("diagnosis", _READ), ("problem", _READ),
           ("allergy", _READ), ("vital_sign", _READ), ("care_plan", _READ), (None, ["read", "export"])]),
    # H5 — diagnostics roles.
    _role("lab_technician", "Laboratory Technician",
          "Receives specimens and enters/verifies laboratory results.",
          [("specimen", _FULL), ("diagnostic_result", ["create", "read", "update"]),
           ("result_item", _FULL), ("diagnostic_order", ["read", "update"]), ("patient", _READ)]),
    _role("radiologist", "Radiologist",
          "Reads imaging studies and issues/verifies imaging reports.",
          [("diagnostic_result", _FULL), ("result_item", _READ),
           ("diagnostic_order", ["read", "update"]), ("patient", _READ), ("encounter", _READ)]),
    # H6 — pharmacy roles.
    _role("pharmacist", "Pharmacist",
          "Verifies prescriptions, checks drug safety, dispenses and reconciles medications.",
          [("prescription", ["read", "update"]), ("prescription_item", _FULL),
           ("medication_dispense", _FULL), ("medication_reconciliation", _FULL),
           ("drug_formulary", _READ), ("allergy", _READ), ("patient", _READ),
           ("encounter", _READ), ("provider", _READ)]),
    _role("pharmacy_technician", "Pharmacy Technician",
          "Prepares and dispenses verified prescriptions under pharmacist supervision.",
          [("medication_dispense", ["create", "read", "update"]), ("prescription", _READ),
           ("prescription_item", _READ), ("drug_formulary", _READ), ("patient", _READ)]),
    # H7 — inpatient operations roles.
    _role("bed_manager", "Bed Manager",
          "Owns bed allocation, occupancy and transfers across wards.",
          [("bed_assignment", _FULL), ("transfer", _FULL), ("bed", ["read", "update"]),
           ("ward", _READ), ("facility", _READ), ("admission", _READ), ("patient", _READ)]),
    _role("ward_clerk", "Ward Clerk",
          "Manages admissions, discharges and inpatient administration on the ward.",
          [("admission", _FULL), ("discharge", ["create", "read", "update"]),
           ("bed_assignment", ["read", "update"]), ("nursing_handover", _READ),
           ("ward_round", _READ), ("patient", _READ), ("ward", _READ)]),
    # H8 — surgery / OT & critical-care roles.
    _role("surgeon", "Surgeon",
          "Performs surgery: owns the case, procedures, surgical team and implant traceability.",
          [("surgery", _FULL), ("surgical_procedure", _FULL), ("surgical_team_member", _FULL),
           ("surgical_checklist", ["read", "update"]), ("implant_usage", _FULL),
           ("recovery_episode", _READ), ("anaesthesia_record", _READ), ("procedure_code", _READ),
           ("patient", _READ), ("encounter", _READ)]),
    _role("anaesthetist", "Anaesthetist",
          "Owns the anaesthesia record and peri-operative + critical-care management.",
          [("anaesthesia_record", _FULL), ("surgery", ["read", "update"]),
           ("surgical_checklist", ["read", "update"]), ("icu_episode", _FULL),
           ("icu_observation", _FULL), ("recovery_episode", ["read", "update"]),
           ("patient", _READ)]),
    _role("ot_coordinator", "OT Coordinator",
          "Owns theatre scheduling, sessions and surgical bookings.",
          [("operating_theatre", _FULL), ("ot_schedule", _FULL), ("surgery", _FULL),
           ("surgical_team_member", _FULL), ("surgical_checklist", _READ), ("provider", _READ),
           ("patient", _READ)]),
    _role("scrub_nurse", "Theatre Nurse",
          "Runs the surgical safety checklist, records implants and recovery in theatre.",
          [("surgical_checklist", _FULL), ("surgical_team_member", _READ), ("implant_usage", _FULL),
           ("surgery", ["read", "update"]), ("recovery_episode", ["create", "read", "update"]),
           ("patient", _READ)]),
    _role("intensivist", "Intensivist",
          "Owns the ICU episode and critical-care observations.",
          [("icu_episode", _FULL), ("icu_observation", _FULL), ("recovery_episode", _READ),
           ("admission", _READ), ("patient", _READ), ("surgery", _READ)]),
    # H9 — billing & claims roles. Hospital owns clinical charge capture + claim lifecycle only; the GL
    # / settlement / tax stay in the Finance Platform (no finance permissions granted here).
    _role("billing_clerk", "Billing Clerk",
          "Captures charges, raises invoices and records patient payments.",
          [("charge", _FULL), ("invoice", _FULL), ("payment", _FULL),
           ("service_catalog", _READ), ("payer", _READ), ("patient", _READ),
           ("encounter", _READ), ("claim", _READ)]),
    _role("claims_officer", "Claims Officer",
          "Manages insurance claims, pre-authorizations and payer remittances.",
          [("claim", _FULL), ("claim_line", _FULL), ("preauthorization", _FULL),
           ("remittance", _FULL), ("invoice", _READ), ("payer", _READ),
           ("insurance_policy", _READ), ("charge", _READ), ("patient", _READ)]),
    _role("billing_manager", "Billing Manager",
          "Oversees the full revenue-cycle: charges, invoices, claims, remittances and payments.",
          [("charge", _FULL), ("invoice", _FULL), ("payment", _FULL), ("claim", _FULL),
           ("claim_line", _FULL), ("preauthorization", _FULL), ("remittance", _FULL),
           ("service_catalog", _READ), ("payer", _READ), ("insurance_policy", _READ),
           ("patient", _READ), ("encounter", _READ)]),
    # H10 — blood bank / transfusion medicine roles.
    _role("blood_bank_manager", "Blood Bank Manager",
          "Owns the full blood-bank lifecycle: donors, donations, units, testing, crossmatch, "
          "issue, transfusion and haemovigilance.",
          [("donor", _FULL), ("donation", _FULL), ("blood_unit", _FULL), ("blood_test", _FULL),
           ("crossmatch", _FULL), ("blood_request", _FULL), ("blood_issue", _FULL),
           ("transfusion", _FULL), ("transfusion_reaction", _FULL), ("blood_recall", _FULL),
           ("storage_excursion", _FULL), ("patient", _READ)]),
    _role("donor_coordinator", "Donor Coordinator",
          "Manages donor registration, eligibility/deferral and donation collection.",
          [("donor", _FULL), ("donation", _FULL), ("blood_unit", _READ), ("blood_test", _READ)]),
    _role("blood_bank_technologist", "Blood Bank Technologist",
          "Processes units, runs qualification + compatibility testing, crossmatches and issues blood.",
          [("blood_unit", _FULL), ("blood_test", _FULL), ("crossmatch", _FULL),
           ("blood_issue", _FULL), ("storage_excursion", _FULL), ("donation", _READ),
           ("blood_request", ["read", "update"]), ("patient", _READ)]),
    _role("haemovigilance_officer", "Haemovigilance Officer",
          "Investigates transfusion reactions and manages recalls / look-back.",
          [("transfusion_reaction", _FULL), ("blood_recall", _FULL), ("storage_excursion", _FULL),
           ("transfusion", _READ), ("blood_unit", _READ), ("donation", _READ), ("donor", _READ),
           ("patient", _READ)]),
    # H11 — quality · accreditation · patient-safety roles.
    _role("quality_manager", "Quality Manager",
          "Owns the quality-management system: incidents, CAPA, audits, findings, complaints, risk.",
          [("incident", _FULL), ("capa", _FULL), ("quality_audit", _FULL), ("audit_finding", _FULL),
           ("complaint", _FULL), ("risk_assessment", _FULL), ("quality_standard", _FULL),
           ("accreditation", _READ), ("patient", _READ)]),
    _role("patient_safety_officer", "Patient Safety Officer",
          "Manages patient-safety incidents, sentinel events and their corrective actions.",
          [("incident", _FULL), ("capa", _FULL), ("audit_finding", _READ), ("patient", _READ),
           ("encounter", _READ)]),
    _role("accreditation_coordinator", "Accreditation Coordinator",
          "Owns accreditation cycles, standards, surveys and findings.",
          [("accreditation", _FULL), ("quality_standard", _FULL), ("quality_audit", _FULL),
           ("audit_finding", _FULL), ("capa", ["read", "update"])]),
    _role("risk_manager", "Risk Manager",
          "Owns the enterprise/clinical risk register and mitigation tracking.",
          [("risk_assessment", _FULL), ("incident", _READ), ("capa", ["read", "update"]),
           ("audit_finding", _READ)]),
    _role("compliance_officer", "Compliance Officer",
          "Monitors standards compliance, complaints and corrective-action closure.",
          [("quality_standard", _FULL), ("audit_finding", _FULL), ("complaint", _FULL),
           ("capa", ["read", "update"]), ("accreditation", _READ)]),
    # H12 — executive (C-suite) read-only role for cross-module scorecards and dashboards.
    _role("hospital_executive", "Hospital Executive",
          "C-suite read + export across the hospital for executive scorecards and dashboards.",
          [(None, ["read", "export"])]),
    # H13 — ancillary & information-governance roles.
    _role("medical_records_officer", "Medical Records Officer",
          "Owns health-information management: record requests / release of information and consents.",
          [("medical_record_request", _FULL), ("consent", _FULL), ("patient", _READ),
           ("encounter", _READ)]),
    _role("referral_coordinator", "Referral Coordinator",
          "Manages internal and external patient referrals and their feedback.",
          [("referral", _FULL), ("patient", _READ), ("provider", _READ), ("specialty", _READ),
           ("clinical_department", _READ)]),
    _role("cssd_technician", "CSSD Technician",
          "Runs central sterile supply: instrument sets and sterilization cycles.",
          [("instrument_set", _FULL), ("sterilization_cycle", _FULL), ("clinical_department", _READ)]),
    _role("dietitian", "Dietitian",
          "Owns diet orders and therapeutic nutrition (allergy-aware).",
          [("diet_order", _FULL), ("allergy", _READ), ("patient", _READ), ("encounter", _READ)]),
    _role("transport_coordinator", "Transport Coordinator",
          "Dispatches and tracks patient transport requests.",
          [("transport_request", _FULL), ("patient", _READ)]),
    _role("mortuary_officer", "Mortuary Officer",
          "Manages death records, body custody and release.",
          [("death_record", _FULL), ("patient", _READ), ("encounter", _READ)]),
]


# ── reports (reuse the Reporting engine) — master-data only ───────────────────
def _report(slug, name, entity_slug, report_type="table"):
    return {"slug": slug, "name": name, "report_type": report_type,
            "nql_source": f"FROM {entity_slug}"}


HOSPITAL_REPORTS = [
    _report("facilities_report", "Facilities", "facility", "pivot"),
    _report("departments_report", "Clinical Departments", "clinical_department", "pivot"),
    _report("wards_report", "Wards", "ward", "pivot"),
    _report("beds_report", "Beds", "bed", "pivot"),
    _report("providers_report", "Providers", "provider", "pivot"),
    _report("specialties_report", "Specialties", "specialty", "pivot"),
    _report("services_report", "Service Catalog", "service_catalog", "pivot"),
    _report("payers_report", "Payers", "payer", "pivot"),
    _report("diagnosis_codes_report", "Diagnosis Codes", "diagnosis_code", "pivot"),
    _report("procedure_codes_report", "Procedure Codes", "procedure_code", "pivot"),
    _report("formulary_report", "Drug Formulary", "drug_formulary", "pivot"),
    # H2 patient-administration reports.
    _report("patients_report", "Patients", "patient", "pivot"),
    _report("patient_register_report", "Patient Register", "patient"),
    _report("insurance_policies_report", "Insurance Policies", "insurance_policy", "pivot"),
    # H3 scheduling reports.
    _report("appointments_report", "Appointments", "appointment", "pivot"),
    _report("appointment_schedule_report", "Appointment Schedule", "appointment"),
    _report("provider_schedules_report", "Provider Schedules", "provider_schedule", "pivot"),
    _report("appointment_waitlist_report", "Appointment Waitlist", "appointment_waitlist", "pivot"),
    _report("no_shows_report", "No-Shows", "appointment", "pivot"),
    # H4 clinical reports.
    _report("encounters_report", "Clinical Encounters", "encounter", "pivot"),
    _report("diagnoses_report", "Diagnoses", "diagnosis", "pivot"),
    _report("problem_list_report", "Problem List", "problem", "pivot"),
    _report("allergies_report", "Allergies", "allergy", "pivot"),
    _report("vital_signs_report", "Vital Signs", "vital_sign", "pivot"),
    _report("care_plans_report", "Care Plans", "care_plan", "pivot"),
    _report("clinical_notes_report", "Clinical Notes", "clinical_note", "pivot"),
    # H4 history reports (structured — the split enables clean clinical reporting).
    _report("past_medical_history_report", "Past Medical History", "past_medical_history", "pivot"),
    _report("surgical_history_report", "Surgical History", "surgical_history", "pivot"),
    _report("family_history_report", "Family History", "family_history", "pivot"),
    _report("social_history_report", "Social History", "social_history", "pivot"),
    # H5 orders & results reports.
    _report("diagnostic_orders_report", "Diagnostic Orders", "diagnostic_order", "pivot"),
    _report("pending_orders_report", "Pending Orders", "diagnostic_order", "pivot"),
    _report("specimens_report", "Specimens", "specimen", "pivot"),
    _report("diagnostic_results_report", "Diagnostic Results", "diagnostic_result", "pivot"),
    _report("abnormal_results_report", "Abnormal Results", "result_item", "pivot"),
    # H6 pharmacy & medication reports.
    _report("prescriptions_report", "Prescriptions", "prescription", "pivot"),
    _report("active_medications_report", "Active Medications", "prescription_item", "pivot"),
    _report("dispenses_report", "Medication Dispenses", "medication_dispense", "pivot"),
    # The MAR is a DERIVED report over medication_administration events (not a separate entity).
    _report("medication_administration_report", "Medication Administration (MAR)",
            "medication_administration", "pivot"),
    _report("missed_doses_report", "Missed Doses", "medication_administration", "pivot"),
    _report("medication_reconciliation_report", "Medication Reconciliation",
            "medication_reconciliation", "pivot"),
    # H7 inpatient, wards & nursing reports.
    _report("admissions_report", "Admissions", "admission", "pivot"),
    _report("current_inpatients_report", "Current Inpatients", "admission", "pivot"),
    _report("bed_occupancy_report", "Bed Occupancy", "bed_assignment", "pivot"),
    _report("transfers_report", "Transfers", "transfer", "pivot"),
    _report("discharges_report", "Discharges", "discharge", "pivot"),
    _report("nursing_tasks_report", "Nursing Tasks", "nursing_task", "pivot"),
    _report("nursing_observations_report", "Nursing Observations", "nursing_observation", "pivot"),
    _report("ward_rounds_report", "Ward Rounds", "ward_round", "pivot"),
    # H8 surgery / OT & critical-care reports.
    _report("surgeries_report", "Surgeries", "surgery", "pivot"),
    _report("theatre_sessions_report", "Theatre Sessions", "ot_schedule", "pivot"),
    _report("surgical_procedures_report", "Surgical Procedures", "surgical_procedure", "pivot"),
    _report("anaesthesia_report", "Anaesthesia Records", "anaesthesia_record", "pivot"),
    _report("surgical_checklists_report", "Surgical Checklists", "surgical_checklist", "pivot"),
    _report("implant_usage_report", "Implant Traceability", "implant_usage", "pivot"),
    _report("icu_episodes_report", "ICU Episodes", "icu_episode", "pivot"),
    _report("recovery_report", "Recovery (PACU)", "recovery_episode", "pivot"),
    # H9 billing & claims reports (operational — financial statements/aging remain the Finance Platform).
    _report("charges_report", "Charges", "charge", "pivot"),
    _report("invoices_report", "Invoices", "invoice", "pivot"),
    _report("outstanding_invoices_report", "Outstanding Invoices", "invoice"),
    _report("claims_report", "Claims", "claim", "pivot"),
    _report("claim_lines_report", "Claim Lines", "claim_line", "pivot"),
    _report("preauthorizations_report", "Pre-Authorizations", "preauthorization", "pivot"),
    _report("remittances_report", "Remittances", "remittance", "pivot"),
    _report("payments_report", "Payments", "payment", "pivot"),
    # H10 blood bank reports (traceability/availability are tables; the rest pivot).
    _report("donors_report", "Donors", "donor", "pivot"),
    _report("donations_report", "Donations", "donation", "pivot"),
    _report("blood_units_report", "Blood Units", "blood_unit", "pivot"),
    _report("available_units_report", "Available Units", "blood_unit"),
    _report("blood_tests_report", "Blood Tests", "blood_test", "pivot"),
    _report("reactive_tests_report", "Reactive Tests", "blood_test", "pivot"),
    _report("crossmatches_report", "Crossmatches", "crossmatch", "pivot"),
    _report("blood_requests_report", "Blood Requests", "blood_request", "pivot"),
    _report("blood_issues_report", "Blood Issues", "blood_issue", "pivot"),
    _report("transfusions_report", "Transfusions", "transfusion", "pivot"),
    _report("unit_traceability_report", "Unit Traceability", "blood_unit"),
    _report("transfusion_reactions_report", "Transfusion Reactions", "transfusion_reaction", "pivot"),
    _report("blood_recalls_report", "Blood Recalls", "blood_recall", "pivot"),
    _report("storage_excursions_report", "Storage Excursions", "storage_excursion", "pivot"),
    # H11 quality · accreditation · patient-safety reports.
    _report("incidents_report", "Incidents", "incident", "pivot"),
    _report("sentinel_events_report", "Sentinel Events", "incident", "pivot"),
    _report("capas_report", "Corrective / Preventive Actions", "capa", "pivot"),
    _report("open_capas_report", "Open CAPAs", "capa"),
    _report("quality_audits_report", "Quality Audits", "quality_audit", "pivot"),
    _report("audit_findings_report", "Audit Findings", "audit_finding", "pivot"),
    _report("complaints_report", "Complaints", "complaint", "pivot"),
    _report("risk_register_report", "Risk Register", "risk_assessment", "pivot"),
    _report("accreditations_report", "Accreditations", "accreditation", "pivot"),
    _report("quality_standards_report", "Quality Standards", "quality_standard", "pivot"),
    # H13 ancillary & information-governance reports.
    _report("consents_report", "Consents", "consent", "pivot"),
    _report("referrals_report", "Referrals", "referral", "pivot"),
    _report("record_requests_report", "Medical Record Requests", "medical_record_request", "pivot"),
    _report("instrument_sets_report", "Instrument Sets", "instrument_set", "pivot"),
    _report("sterilization_cycles_report", "Sterilization Cycles", "sterilization_cycle", "pivot"),
    _report("diet_orders_report", "Diet Orders", "diet_order", "pivot"),
    _report("transport_requests_report", "Transport Requests", "transport_request", "pivot"),
    _report("death_records_report", "Death Records", "death_record", "pivot"),
]


# ── KPIs (reuse Analytics KPIService) — H1 masters only ───────────────────────
def _kpi(code, name, category, nql_source, *, aggregate="count", value_field="",
         direction="higher_better", unit=""):
    return {"code": code, "name": name, "category": category, "source_type": "nql",
            "nql_source": nql_source, "aggregate": aggregate, "value_field": value_field,
            "direction": direction, "unit": unit}


HOSPITAL_KPIS = [
    _kpi("total_facilities", "Facilities", "master_data",
         'FROM facility WHERE status = "active"'),
    _kpi("total_wards", "Wards", "master_data", 'FROM ward WHERE status = "active"'),
    _kpi("total_beds", "Total Beds", "operations", "FROM bed"),
    _kpi("available_beds", "Available Beds", "operations",
         'FROM bed WHERE status = "available"'),
    _kpi("out_of_service_beds", "Out-of-Service Beds", "operations",
         'FROM bed WHERE status = "out_of_service"', direction="lower_better"),
    _kpi("active_providers", "Active Providers", "master_data",
         'FROM provider WHERE status = "active"'),
    _kpi("active_services", "Active Services", "master_data",
         'FROM service_catalog WHERE status = "active"'),
    _kpi("active_payers", "Active Payers", "master_data",
         'FROM payer WHERE status = "active"'),
    # H2 patient-administration KPIs.
    _kpi("total_patients", "Total Patients", "patient_administration", "FROM patient"),
    _kpi("active_patients", "Active Patients", "patient_administration",
         'FROM patient WHERE status = "active"'),
    _kpi("active_insurance_policies", "Active Insurance Policies", "patient_administration",
         'FROM insurance_policy WHERE status = "active"'),
    # H3 scheduling KPIs.
    _kpi("total_appointments", "Total Appointments", "scheduling", "FROM appointment"),
    _kpi("confirmed_appointments", "Confirmed Appointments", "scheduling",
         'FROM appointment WHERE status = "confirmed"'),
    _kpi("waitlisted_appointments", "Waitlisted Appointments", "scheduling",
         'FROM appointment WHERE status = "waitlisted"', direction="lower_better"),
    _kpi("no_show_appointments", "No-Show Appointments", "scheduling",
         'FROM appointment WHERE status = "no_show"', direction="lower_better"),
    _kpi("cancelled_appointments", "Cancelled Appointments", "scheduling",
         'FROM appointment WHERE status = "cancelled"', direction="lower_better"),
    _kpi("active_provider_schedules", "Active Provider Schedules", "scheduling",
         'FROM provider_schedule WHERE status = "active"'),
    # H4 clinical KPIs.
    _kpi("total_encounters", "Total Encounters", "clinical", "FROM encounter"),
    _kpi("open_encounters", "Open Encounters", "clinical",
         'FROM encounter WHERE status = "in_progress"'),
    _kpi("completed_encounters", "Completed Encounters", "clinical",
         'FROM encounter WHERE status = "completed"'),
    _kpi("active_problems", "Active Problems", "clinical",
         'FROM problem WHERE status = "active"'),
    _kpi("active_care_plans", "Active Care Plans", "clinical",
         'FROM care_plan WHERE status = "active"'),
    _kpi("active_allergies", "Recorded Allergies", "clinical",
         'FROM allergy WHERE status = "active"'),
    # H5 orders & results KPIs.
    _kpi("total_orders", "Total Diagnostic Orders", "diagnostics", "FROM diagnostic_order"),
    _kpi("pending_orders", "Pending Orders", "diagnostics",
         'FROM diagnostic_order WHERE status = "requested"', direction="lower_better"),
    _kpi("in_progress_orders", "In-Progress Orders", "diagnostics",
         'FROM diagnostic_order WHERE status = "in_progress"'),
    _kpi("verified_orders", "Verified Orders", "diagnostics",
         'FROM diagnostic_order WHERE status = "verified"'),
    _kpi("rejected_specimens", "Rejected Specimens", "diagnostics",
         'FROM specimen WHERE status = "rejected"', direction="lower_better"),
    _kpi("released_results", "Released Results", "diagnostics",
         'FROM diagnostic_result WHERE status = "released"'),
    # H6 pharmacy & medication KPIs.
    _kpi("total_prescriptions", "Total Prescriptions", "pharmacy", "FROM prescription"),
    _kpi("prescriptions_awaiting_verification", "Awaiting Verification", "pharmacy",
         'FROM prescription WHERE status = "signed"', direction="lower_better"),
    _kpi("prescriptions_to_dispense", "Awaiting Dispensing", "pharmacy",
         'FROM prescription WHERE status = "verified"'),
    _kpi("dispensed_medications", "Dispensed Medications", "pharmacy",
         'FROM medication_dispense WHERE status = "dispensed"'),
    _kpi("medications_administered", "Doses Administered", "pharmacy",
         'FROM medication_administration WHERE status = "administered"'),
    _kpi("missed_doses", "Missed Doses", "pharmacy",
         'FROM medication_administration WHERE status = "missed"', direction="lower_better"),
    _kpi("medication_items_on_hold", "Items Held for Review", "pharmacy",
         'FROM prescription_item WHERE status = "on_hold"', direction="lower_better"),
    _kpi("pending_reconciliations", "Pending Reconciliations", "pharmacy",
         'FROM medication_reconciliation WHERE status = "pending"', direction="lower_better"),
    # H7 inpatient, wards & nursing KPIs.
    _kpi("total_admissions", "Total Admissions", "inpatient", "FROM admission"),
    _kpi("current_inpatients", "Current Inpatients", "inpatient",
         'FROM admission WHERE status = "admitted"'),
    _kpi("pending_admissions", "Pending Admissions", "inpatient",
         'FROM admission WHERE status = "requested"', direction="lower_better"),
    _kpi("occupied_beds", "Occupied Beds", "inpatient",
         'FROM bed_assignment WHERE status = "occupied"'),
    _kpi("pending_transfers", "Pending Transfers", "inpatient",
         'FROM transfer WHERE status = "requested"', direction="lower_better"),
    _kpi("planned_discharges", "Planned Discharges", "inpatient",
         'FROM discharge WHERE status = "planned"'),
    _kpi("pending_nursing_tasks", "Pending Nursing Tasks", "inpatient",
         'FROM nursing_task WHERE status = "pending"', direction="lower_better"),
    # H8 surgery / OT & critical-care KPIs.
    _kpi("total_surgeries", "Total Surgeries", "surgery", "FROM surgery"),
    _kpi("scheduled_surgeries", "Scheduled Surgeries", "surgery",
         'FROM surgery WHERE status = "booked"'),
    _kpi("completed_surgeries", "Completed Surgeries", "surgery",
         'FROM surgery WHERE status = "completed"'),
    _kpi("cancelled_surgeries", "Cancelled Surgeries", "surgery",
         'FROM surgery WHERE status = "cancelled"', direction="lower_better"),
    _kpi("available_theatres", "Available Theatres", "surgery",
         'FROM operating_theatre WHERE status = "available"'),
    _kpi("active_icu_episodes", "Active ICU Episodes", "critical_care",
         'FROM icu_episode WHERE status = "active"'),
    _kpi("patients_in_recovery", "Patients in Recovery", "critical_care",
         'FROM recovery_episode WHERE status = "in_recovery"'),
    # H9 billing KPIs — OPERATIONAL counts ONLY (revenue-cycle financial ratios [AR days, collection
    # rate, denial-rate %] live in the Financial KPI Library F13, never duplicated here — KPI governance).
    _kpi("unbilled_charges", "Unbilled Charges", "billing",
         'FROM charge WHERE status = "captured"', direction="lower_better"),
    _kpi("open_invoices", "Open Invoices", "billing",
         'FROM invoice WHERE status = "finalized" OR status = "partially_paid"'),
    _kpi("pending_claims", "Pending Claims", "billing",
         'FROM claim WHERE status = "submitted" OR status = "in_review"'),
    _kpi("denied_claims", "Denied Claims", "billing",
         'FROM claim WHERE status = "denied"', direction="lower_better"),
    _kpi("pending_preauthorizations", "Pending Pre-Authorizations", "billing",
         'FROM preauthorization WHERE status = "requested"', direction="lower_better"),
    # H10 blood bank KPIs — OPERATIONAL counts (no financial ratios; those stay in F13).
    _kpi("total_donors", "Total Donors", "blood_bank", "FROM donor"),
    _kpi("active_donors", "Active Donors", "blood_bank", 'FROM donor WHERE status = "active"'),
    _kpi("deferred_donors", "Deferred Donors", "blood_bank",
         'FROM donor WHERE status = "deferred"', direction="lower_better"),
    _kpi("total_donations", "Total Donations", "blood_bank", "FROM donation"),
    _kpi("units_available", "Units Available", "blood_bank",
         'FROM blood_unit WHERE status = "available"'),
    _kpi("units_in_quarantine", "Units in Quarantine", "blood_bank",
         'FROM blood_unit WHERE status = "quarantine"', direction="lower_better"),
    _kpi("units_expired", "Expired Units", "blood_bank",
         'FROM blood_unit WHERE status = "expired"', direction="lower_better"),
    _kpi("reactive_tests", "Reactive Tests", "blood_bank",
         'FROM blood_test WHERE result = "reactive"', direction="lower_better"),
    _kpi("pending_crossmatches", "Pending Crossmatches", "blood_bank",
         'FROM crossmatch WHERE status = "pending"', direction="lower_better"),
    _kpi("open_blood_requests", "Open Blood Requests", "blood_bank",
         'FROM blood_request WHERE status = "requested"'),
    _kpi("transfusions_completed", "Transfusions Completed", "blood_bank",
         'FROM transfusion WHERE status = "completed"'),
    _kpi("transfusion_reactions", "Transfusion Reactions", "blood_bank",
         "FROM transfusion_reaction", direction="lower_better"),
    _kpi("open_recalls", "Open Recalls", "blood_bank",
         'FROM blood_recall WHERE status = "initiated"', direction="lower_better"),
    _kpi("open_storage_excursions", "Open Storage Excursions", "blood_bank",
         'FROM storage_excursion WHERE status = "open"', direction="lower_better"),
    # H11 quality · patient-safety · accreditation KPIs — OPERATIONAL quality counts (via Analytics).
    _kpi("total_incidents", "Total Incidents", "quality", "FROM incident", direction="lower_better"),
    _kpi("sentinel_events", "Sentinel Events", "quality",
         'FROM incident WHERE is_sentinel = true', direction="lower_better"),
    _kpi("open_incidents", "Open Incidents", "quality",
         'FROM incident WHERE status = "under_investigation"', direction="lower_better"),
    _kpi("open_capas", "Open CAPAs", "quality",
         'FROM capa WHERE status = "open" OR status = "in_progress"', direction="lower_better"),
    _kpi("verified_capas", "Verified CAPAs", "quality",
         'FROM capa WHERE status = "verified" OR status = "closed"'),
    _kpi("total_complaints", "Total Complaints", "quality", "FROM complaint",
         direction="lower_better"),
    _kpi("open_complaints", "Open Complaints", "quality",
         'FROM complaint WHERE status = "under_review"', direction="lower_better"),
    _kpi("open_findings", "Open Audit Findings", "quality",
         'FROM audit_finding WHERE status = "open"', direction="lower_better"),
    _kpi("non_compliant_findings", "Non-Compliant Findings", "quality",
         'FROM audit_finding WHERE compliance = "non_compliant"', direction="lower_better"),
    _kpi("high_risks", "High/Extreme Risks", "quality",
         'FROM risk_assessment WHERE residual_risk = "high" OR residual_risk = "extreme"',
         direction="lower_better"),
    _kpi("active_accreditations", "Active Accreditations", "quality",
         'FROM accreditation WHERE status = "accredited"'),
    # H13 ancillary & information-governance KPIs (operational counts via Analytics).
    _kpi("active_consents", "Active Consents", "ancillary",
         'FROM consent WHERE status = "active"'),
    _kpi("open_referrals", "Open Referrals", "ancillary",
         'FROM referral WHERE status = "sent" OR status = "accepted"'),
    _kpi("pending_record_requests", "Pending Record Requests", "ancillary",
         'FROM medical_record_request WHERE status = "requested"', direction="lower_better"),
    _kpi("sterile_sets", "Sterile Instrument Sets", "ancillary",
         'FROM instrument_set WHERE status = "sterile"'),
    _kpi("failed_cycles", "Failed Sterilization Cycles", "ancillary",
         'FROM sterilization_cycle WHERE status = "failed"', direction="lower_better"),
    _kpi("active_diet_orders", "Active Diet Orders", "ancillary",
         'FROM diet_order WHERE status = "active"'),
    _kpi("pending_transports", "Pending Transports", "ancillary",
         'FROM transport_request WHERE status = "requested"', direction="lower_better"),
    _kpi("bodies_in_mortuary", "Bodies in Mortuary", "ancillary",
         'FROM death_record WHERE status = "in_mortuary"'),
]


# ── dashboards (reuse the Dashboard runtime) ──────────────────────────────────
def _w(widget_type, title, x, y, w, h, **kw):
    wd = {"widget_type": widget_type, "title": title, "grid_x": x, "grid_y": y,
          "grid_w": w, "grid_h": h}
    wd.update(kw)
    return wd


HOSPITAL_DASHBOARDS = [
    {"slug": "master_data_dashboard", "name": "Hospital Master Data", "is_default": True,
     "widgets": [
         _w("metric_card", "Facilities", 0, 0, 3, 2),
         _w("metric_card", "Wards", 3, 0, 3, 2),
         _w("metric_card", "Total Beds", 6, 0, 3, 2),
         _w("metric_card", "Active Providers", 9, 0, 3, 2),
         _w("report", "Wards", 0, 2, 6, 4, report_slug="wards_report"),
         _w("report", "Providers", 6, 2, 6, 4, report_slug="providers_report"),
     ]},
    {"slug": "bed_capacity_dashboard", "name": "Bed Capacity", "widgets": [
        _w("metric_card", "Total Beds", 0, 0, 4, 2),
        _w("metric_card", "Available Beds", 4, 0, 4, 2),
        _w("metric_card", "Out-of-Service Beds", 8, 0, 4, 2),
        _w("report", "Beds", 0, 2, 12, 4, report_slug="beds_report"),
    ]},
    {"slug": "patient_administration_dashboard", "name": "Patient Administration", "widgets": [
        _w("metric_card", "Total Patients", 0, 0, 4, 2),
        _w("metric_card", "Active Patients", 4, 0, 4, 2),
        _w("metric_card", "Active Insurance Policies", 8, 0, 4, 2),
        _w("report", "Patients", 0, 2, 6, 4, report_slug="patients_report"),
        _w("report", "Insurance Policies", 6, 2, 6, 4, report_slug="insurance_policies_report"),
    ]},
    {"slug": "scheduling_dashboard", "name": "Scheduling & Appointments", "widgets": [
        _w("metric_card", "Total Appointments", 0, 0, 3, 2),
        _w("metric_card", "Confirmed Appointments", 3, 0, 3, 2),
        _w("metric_card", "Waitlisted Appointments", 6, 0, 3, 2),
        _w("metric_card", "No-Show Appointments", 9, 0, 3, 2),
        _w("report", "Appointments", 0, 2, 6, 4, report_slug="appointments_report"),
        _w("report", "Provider Schedules", 6, 2, 6, 4, report_slug="provider_schedules_report"),
    ]},
    {"slug": "clinical_dashboard", "name": "Clinical", "widgets": [
        _w("metric_card", "Total Encounters", 0, 0, 3, 2),
        _w("metric_card", "Open Encounters", 3, 0, 3, 2),
        _w("metric_card", "Active Problems", 6, 0, 3, 2),
        _w("metric_card", "Active Care Plans", 9, 0, 3, 2),
        _w("report", "Clinical Encounters", 0, 2, 6, 4, report_slug="encounters_report"),
        _w("report", "Diagnoses", 6, 2, 6, 4, report_slug="diagnoses_report"),
    ]},
    {"slug": "diagnostics_dashboard", "name": "Diagnostics — Orders & Results", "widgets": [
        _w("metric_card", "Total Orders", 0, 0, 3, 2),
        _w("metric_card", "Pending Orders", 3, 0, 3, 2),
        _w("metric_card", "In-Progress Orders", 6, 0, 3, 2),
        _w("metric_card", "Rejected Specimens", 9, 0, 3, 2),
        _w("report", "Diagnostic Orders", 0, 2, 6, 4, report_slug="diagnostic_orders_report"),
        _w("report", "Diagnostic Results", 6, 2, 6, 4, report_slug="diagnostic_results_report"),
    ]},
    {"slug": "pharmacy_dashboard", "name": "Pharmacy & Medication", "widgets": [
        _w("metric_card", "Total Prescriptions", 0, 0, 3, 2),
        _w("metric_card", "Awaiting Dispensing", 3, 0, 3, 2),
        _w("metric_card", "Dispensed Medications", 6, 0, 3, 2),
        _w("metric_card", "Missed Doses", 9, 0, 3, 2),
        _w("report", "Prescriptions", 0, 2, 6, 4, report_slug="prescriptions_report"),
        _w("report", "Medication Dispenses", 6, 2, 6, 4, report_slug="dispenses_report"),
    ]},
    {"slug": "inpatient_dashboard", "name": "Inpatient & Beds", "widgets": [
        _w("metric_card", "Current Inpatients", 0, 0, 3, 2),
        _w("metric_card", "Occupied Beds", 3, 0, 3, 2),
        _w("metric_card", "Pending Admissions", 6, 0, 3, 2),
        _w("metric_card", "Planned Discharges", 9, 0, 3, 2),
        _w("report", "Admissions", 0, 2, 6, 4, report_slug="admissions_report"),
        _w("report", "Bed Occupancy", 6, 2, 6, 4, report_slug="bed_occupancy_report"),
    ]},
    {"slug": "nursing_dashboard", "name": "Nursing", "widgets": [
        _w("metric_card", "Pending Nursing Tasks", 0, 0, 4, 2),
        _w("metric_card", "Current Inpatients", 4, 0, 4, 2),
        _w("metric_card", "Occupied Beds", 8, 0, 4, 2),
        _w("report", "Nursing Tasks", 0, 2, 6, 4, report_slug="nursing_tasks_report"),
        _w("report", "Nursing Observations", 6, 2, 6, 4, report_slug="nursing_observations_report"),
    ]},
    {"slug": "surgery_dashboard", "name": "Surgery & Theatres", "widgets": [
        _w("metric_card", "Total Surgeries", 0, 0, 3, 2),
        _w("metric_card", "Scheduled Surgeries", 3, 0, 3, 2),
        _w("metric_card", "Completed Surgeries", 6, 0, 3, 2),
        _w("metric_card", "Available Theatres", 9, 0, 3, 2),
        _w("report", "Surgeries", 0, 2, 6, 4, report_slug="surgeries_report"),
        _w("report", "Theatre Sessions", 6, 2, 6, 4, report_slug="theatre_sessions_report"),
    ]},
    {"slug": "critical_care_dashboard", "name": "Critical Care", "widgets": [
        _w("metric_card", "Active ICU Episodes", 0, 0, 4, 2),
        _w("metric_card", "Patients in Recovery", 4, 0, 4, 2),
        _w("metric_card", "Available Theatres", 8, 0, 4, 2),
        _w("report", "ICU Episodes", 0, 2, 6, 4, report_slug="icu_episodes_report"),
        _w("report", "Recovery (PACU)", 6, 2, 6, 4, report_slug="recovery_report"),
    ]},
    {"slug": "billing_dashboard", "name": "Billing & Revenue Cycle", "widgets": [
        _w("metric_card", "Unbilled Charges", 0, 0, 3, 2),
        _w("metric_card", "Open Invoices", 3, 0, 3, 2),
        _w("metric_card", "Pending Claims", 6, 0, 3, 2),
        _w("metric_card", "Denied Claims", 9, 0, 3, 2),
        _w("report", "Outstanding Invoices", 0, 2, 6, 4, report_slug="outstanding_invoices_report"),
        _w("report", "Claims", 6, 2, 6, 4, report_slug="claims_report"),
    ]},
    {"slug": "blood_bank_dashboard", "name": "Blood Bank", "widgets": [
        _w("metric_card", "Units Available", 0, 0, 3, 2),
        _w("metric_card", "Total Donations", 3, 0, 3, 2),
        _w("metric_card", "Reactive Tests", 6, 0, 3, 2),
        _w("metric_card", "Transfusion Reactions", 9, 0, 3, 2),
        _w("report", "Available Units", 0, 2, 6, 4, report_slug="available_units_report"),
        _w("report", "Blood Requests", 6, 2, 6, 4, report_slug="blood_requests_report"),
    ]},
    {"slug": "haemovigilance_dashboard", "name": "Haemovigilance", "widgets": [
        _w("metric_card", "Transfusion Reactions", 0, 0, 4, 2),
        _w("metric_card", "Open Recalls", 4, 0, 4, 2),
        _w("metric_card", "Open Storage Excursions", 8, 0, 4, 2),
        _w("report", "Transfusion Reactions", 0, 2, 6, 4, report_slug="transfusion_reactions_report"),
        _w("report", "Storage Excursions", 6, 2, 6, 4, report_slug="storage_excursions_report"),
    ]},
    {"slug": "quality_dashboard", "name": "Quality Management", "widgets": [
        _w("metric_card", "Total Incidents", 0, 0, 3, 2),
        _w("metric_card", "Open CAPAs", 3, 0, 3, 2),
        _w("metric_card", "Open Audit Findings", 6, 0, 3, 2),
        _w("metric_card", "Total Complaints", 9, 0, 3, 2),
        _w("report", "Corrective / Preventive Actions", 0, 2, 6, 4, report_slug="capas_report"),
        _w("report", "Audit Findings", 6, 2, 6, 4, report_slug="audit_findings_report"),
    ]},
    {"slug": "patient_safety_dashboard", "name": "Patient Safety", "widgets": [
        _w("metric_card", "Total Incidents", 0, 0, 4, 2),
        _w("metric_card", "Sentinel Events", 4, 0, 4, 2),
        _w("metric_card", "High/Extreme Risks", 8, 0, 4, 2),
        _w("report", "Incidents", 0, 2, 6, 4, report_slug="incidents_report"),
        _w("report", "Risk Register", 6, 2, 6, 4, report_slug="risk_register_report"),
    ]},
    {"slug": "accreditation_dashboard", "name": "Accreditation & Compliance", "widgets": [
        _w("metric_card", "Active Accreditations", 0, 0, 4, 2),
        _w("metric_card", "Open Audit Findings", 4, 0, 4, 2),
        _w("metric_card", "Non-Compliant Findings", 8, 0, 4, 2),
        _w("report", "Quality Audits", 0, 2, 6, 4, report_slug="quality_audits_report"),
        _w("report", "Accreditations", 6, 2, 6, 4, report_slug="accreditations_report"),
    ]},
    # H12 — executive dashboards (reuse existing H1–H11 KPIs across modules; NO new analytics/entities).
    {"slug": "executive_overview_dashboard", "name": "Executive Overview", "widgets": [
        _w("metric_card", "Current Inpatients", 0, 0, 3, 2),
        _w("metric_card", "Available Beds", 3, 0, 3, 2),
        _w("metric_card", "Total Surgeries", 6, 0, 3, 2),
        _w("metric_card", "Open Invoices", 9, 0, 3, 2),
        _w("metric_card", "Total Encounters", 0, 2, 3, 2),
        _w("metric_card", "Units Available", 3, 2, 3, 2),
        _w("metric_card", "Total Incidents", 6, 2, 3, 2),
        _w("metric_card", "Active Accreditations", 9, 2, 3, 2),
        _w("report", "Admissions", 0, 4, 6, 4, report_slug="admissions_report"),
        _w("report", "Surgeries", 6, 4, 6, 4, report_slug="surgeries_report"),
    ]},
    {"slug": "executive_quality_safety_dashboard", "name": "Executive — Quality & Safety", "widgets": [
        _w("metric_card", "Total Incidents", 0, 0, 3, 2),
        _w("metric_card", "Sentinel Events", 3, 0, 3, 2),
        _w("metric_card", "Open CAPAs", 6, 0, 3, 2),
        _w("metric_card", "High/Extreme Risks", 9, 0, 3, 2),
        _w("report", "Incidents", 0, 2, 6, 4, report_slug="incidents_report"),
        _w("report", "Corrective / Preventive Actions", 6, 2, 6, 4, report_slug="capas_report"),
    ]},
    # H13 ancillary & information-governance dashboards.
    {"slug": "ancillary_services_dashboard", "name": "Ancillary Services", "widgets": [
        _w("metric_card", "Active Diet Orders", 0, 0, 3, 2),
        _w("metric_card", "Pending Transports", 3, 0, 3, 2),
        _w("metric_card", "Sterile Instrument Sets", 6, 0, 3, 2),
        _w("metric_card", "Bodies in Mortuary", 9, 0, 3, 2),
        _w("report", "Diet Orders", 0, 2, 6, 4, report_slug="diet_orders_report"),
        _w("report", "Sterilization Cycles", 6, 2, 6, 4, report_slug="sterilization_cycles_report"),
    ]},
    {"slug": "information_governance_dashboard", "name": "Information Governance", "widgets": [
        _w("metric_card", "Active Consents", 0, 0, 4, 2),
        _w("metric_card", "Open Referrals", 4, 0, 4, 2),
        _w("metric_card", "Pending Record Requests", 8, 0, 4, 2),
        _w("report", "Consents", 0, 2, 6, 4, report_slug="consents_report"),
        _w("report", "Medical Record Requests", 6, 2, 6, 4, report_slug="record_requests_report"),
    ]},
]

_ROLE_HOME = [
    ("hospital_administrator", "master_data_dashboard"),
    ("master_data_manager", "master_data_dashboard"),
    ("registration_clerk", "patient_administration_dashboard"),
    ("health_information_manager", "patient_administration_dashboard"),
    ("appointment_scheduler", "scheduling_dashboard"),
    ("receptionist", "scheduling_dashboard"),
    ("physician", "clinical_dashboard"),
    ("nurse", "clinical_dashboard"),
    ("medical_director", "clinical_dashboard"),
    ("lab_technician", "diagnostics_dashboard"),
    ("radiologist", "diagnostics_dashboard"),
    ("pharmacist", "pharmacy_dashboard"),
    ("pharmacy_technician", "pharmacy_dashboard"),
    ("bed_manager", "inpatient_dashboard"),
    ("ward_clerk", "inpatient_dashboard"),
    ("surgeon", "surgery_dashboard"),
    ("ot_coordinator", "surgery_dashboard"),
    ("scrub_nurse", "surgery_dashboard"),
    ("anaesthetist", "critical_care_dashboard"),
    ("intensivist", "critical_care_dashboard"),
    ("billing_clerk", "billing_dashboard"),
    ("claims_officer", "billing_dashboard"),
    ("billing_manager", "billing_dashboard"),
    ("blood_bank_manager", "blood_bank_dashboard"),
    ("donor_coordinator", "blood_bank_dashboard"),
    ("blood_bank_technologist", "blood_bank_dashboard"),
    ("haemovigilance_officer", "haemovigilance_dashboard"),
    ("quality_manager", "quality_dashboard"),
    ("patient_safety_officer", "patient_safety_dashboard"),
    ("accreditation_coordinator", "accreditation_dashboard"),
    ("risk_manager", "patient_safety_dashboard"),
    ("compliance_officer", "accreditation_dashboard"),
    ("hospital_executive", "executive_overview_dashboard"),
    ("medical_records_officer", "information_governance_dashboard"),
    ("referral_coordinator", "information_governance_dashboard"),
    ("cssd_technician", "ancillary_services_dashboard"),
    ("dietitian", "ancillary_services_dashboard"),
    ("transport_coordinator", "ancillary_services_dashboard"),
    ("mortuary_officer", "ancillary_services_dashboard"),
]
_DASH_NAMES = {d["slug"]: d["name"] for d in HOSPITAL_DASHBOARDS}
HOSPITAL_ROLE_HOMES = [
    {"ref": f"home_{rs}", "name": _DASH_NAMES.get(ds, "Home"), "role_slug": rs,
     "widgets": [{"type": "dashboard", "title": _DASH_NAMES.get(ds, "Home"),
                  "config": {"dashboard_slug": ds}}]}
    for rs, ds in _ROLE_HOME
]


# ── notifications (reuse the Notification engine) ─────────────────────────────
HOSPITAL_NOTIFICATIONS = [
    # H3 scheduling notifications.
    {"slug": "appointment_confirmed", "name": "Appointment Confirmed", "channels": ["in_app"],
     "subject_template": "Appointment confirmed",
     "body_template": "Your appointment has been confirmed."},
    {"slug": "appointment_waitlisted", "name": "Appointment Waitlisted", "channels": ["in_app"],
     "subject_template": "Placed on the waitlist",
     "body_template": "The session is full or the provider is unavailable; you are on the waitlist."},
    {"slug": "appointment_checked_in", "name": "Patient Checked In", "channels": ["in_app"],
     "subject_template": "Patient checked in",
     "body_template": "A patient has checked in for their appointment."},
    {"slug": "appointment_cancelled", "name": "Appointment Cancelled", "channels": ["in_app"],
     "subject_template": "Appointment cancelled",
     "body_template": "Your appointment has been cancelled."},
    # H4 clinical notifications.
    {"slug": "visit_completed", "name": "Visit Completed", "channels": ["in_app"],
     "subject_template": "Your visit is complete",
     "body_template": "Your clinical encounter has been completed."},
    # H5 orders & results notifications.
    {"slug": "order_received", "name": "Diagnostic Order Received", "channels": ["in_app"],
     "subject_template": "New diagnostic order",
     "body_template": "A diagnostic order has been placed for a patient."},
    {"slug": "result_available", "name": "Result Available", "channels": ["in_app"],
     "subject_template": "Diagnostic result available",
     "body_template": "A validated diagnostic result is available for your patient."},
    {"slug": "specimen_rejected", "name": "Specimen Rejected", "channels": ["in_app"],
     "subject_template": "Specimen rejected — recollection required",
     "body_template": "A specimen was rejected; please arrange recollection."},
    # H6 pharmacy & medication notifications.
    {"slug": "medication_safety_alert", "name": "Medication Safety Alert", "channels": ["in_app"],
     "subject_template": "Medication safety alert",
     "body_template": "A prescribed item was held for pharmacist review (possible duplicate therapy)."},
    {"slug": "prescription_to_dispense", "name": "Prescription Ready to Dispense",
     "channels": ["in_app"], "subject_template": "Prescription verified",
     "body_template": "A verified prescription is ready for dispensing."},
    {"slug": "medication_ready", "name": "Medication Dispensed", "channels": ["in_app"],
     "subject_template": "Medication dispensed",
     "body_template": "Medication has been dispensed for a patient."},
    {"slug": "medication_missed", "name": "Medication Dose Missed", "channels": ["in_app"],
     "subject_template": "Missed medication dose",
     "body_template": "A scheduled medication dose was missed for a patient."},
    {"slug": "reconciliation_completed", "name": "Reconciliation Completed", "channels": ["in_app"],
     "subject_template": "Medication reconciliation completed",
     "body_template": "A medication reconciliation has been completed for a patient."},
    # H7 inpatient, wards & nursing notifications.
    {"slug": "bed_assigned", "name": "Bed Assigned", "channels": ["in_app"],
     "subject_template": "Bed assigned",
     "body_template": "A bed has been assigned to an inpatient."},
    {"slug": "bed_conflict", "name": "Bed Conflict", "channels": ["in_app"],
     "subject_template": "Bed conflict — already occupied",
     "body_template": "The requested bed is already occupied; please reassign."},
    {"slug": "patient_admitted", "name": "Patient Admitted", "channels": ["in_app"],
     "subject_template": "Patient admitted",
     "body_template": "A patient has been admitted to the ward."},
    {"slug": "transfer_completed", "name": "Transfer Completed", "channels": ["in_app"],
     "subject_template": "Patient transfer completed",
     "body_template": "A patient transfer has been completed."},
    {"slug": "patient_discharged", "name": "Patient Discharged", "channels": ["in_app"],
     "subject_template": "Patient discharged",
     "body_template": "A patient has been discharged."},
    # H8 surgery / OT & critical-care notifications.
    {"slug": "surgery_booked", "name": "Surgery Booked", "channels": ["in_app"],
     "subject_template": "Surgery booked",
     "body_template": "A surgery has been booked into a theatre session."},
    {"slug": "surgery_conflict", "name": "Surgery Booking Conflict", "channels": ["in_app"],
     "subject_template": "Theatre session full",
     "body_template": "The theatre session is fully booked; please reschedule."},
    {"slug": "surgery_completed", "name": "Surgery Completed", "channels": ["in_app"],
     "subject_template": "Surgery completed",
     "body_template": "A surgery has been completed; prepare recovery."},
    {"slug": "icu_stepped_down", "name": "ICU Step-Down", "channels": ["in_app"],
     "subject_template": "ICU step-down",
     "body_template": "A patient has stepped down from ICU; prepare the ward bed."},
    {"slug": "recovery_ready", "name": "Recovery Ready", "channels": ["in_app"],
     "subject_template": "Patient ready for discharge from recovery",
     "body_template": "A patient in recovery is ready for discharge to the ward."},
    # H9 billing & claims notifications.
    {"slug": "invoice_finalized", "name": "Invoice Finalized", "channels": ["in_app"],
     "subject_template": "Invoice finalized",
     "body_template": "An invoice has been finalized and posted to your account."},
    {"slug": "payment_received", "name": "Payment Received", "channels": ["in_app"],
     "subject_template": "Payment received",
     "body_template": "A payment has been received and allocated to the outstanding balance."},
    {"slug": "claim_submitted", "name": "Claim Submitted", "channels": ["in_app"],
     "subject_template": "Insurance claim submitted",
     "body_template": "An insurance claim has been submitted to the payer."},
    {"slug": "remittance_received", "name": "Remittance Received", "channels": ["in_app"],
     "subject_template": "Remittance received",
     "body_template": "A payer remittance has been received and reconciled."},
    {"slug": "preauth_decided", "name": "Pre-Authorization Decided", "channels": ["in_app"],
     "subject_template": "Pre-authorization decision",
     "body_template": "A pre-authorization request has been decided by the payer."},
    # H10 blood bank notifications.
    {"slug": "unit_released", "name": "Blood Unit Released", "channels": ["in_app"],
     "subject_template": "Blood unit released",
     "body_template": "A blood unit has passed qualification testing and is available."},
    {"slug": "unit_quarantined", "name": "Blood Unit Quarantined", "channels": ["in_app"],
     "subject_template": "Blood unit held in quarantine",
     "body_template": "A blood unit could not be released (reactive/incomplete testing) and was quarantined."},
    {"slug": "crossmatch_ready", "name": "Crossmatch Compatible", "channels": ["in_app"],
     "subject_template": "Crossmatch compatible — unit reserved",
     "body_template": "A compatible crossmatch was recorded; the unit is reserved for the patient."},
    {"slug": "crossmatch_incompatible", "name": "Crossmatch Incompatible", "channels": ["in_app"],
     "subject_template": "Crossmatch incompatible",
     "body_template": "A crossmatch returned incompatible; select another unit."},
    {"slug": "blood_issued", "name": "Blood Issued", "channels": ["in_app"],
     "subject_template": "Blood unit issued",
     "body_template": "A crossmatched blood unit has been issued for the patient."},
    {"slug": "blood_issue_rejected", "name": "Blood Issue Rejected", "channels": ["in_app"],
     "subject_template": "Blood issue blocked",
     "body_template": "A blood issue was blocked (no compatible crossmatch / unit unavailable)."},
    {"slug": "emergency_blood_issued", "name": "Emergency Blood Issued", "channels": ["in_app"],
     "subject_template": "EMERGENCY uncrossmatched blood issued",
     "body_template": "An emergency uncrossmatched blood unit was released under authorized override."},
    {"slug": "transfusion_completed", "name": "Transfusion Completed", "channels": ["in_app"],
     "subject_template": "Transfusion completed",
     "body_template": "A transfusion has been completed for the patient."},
    {"slug": "transfusion_reaction_alert", "name": "Transfusion Reaction", "channels": ["in_app"],
     "subject_template": "Transfusion reaction reported",
     "body_template": "A transfusion reaction has been reported; haemovigilance investigation required."},
    {"slug": "storage_excursion_alert", "name": "Storage Excursion", "channels": ["in_app"],
     "subject_template": "Cold-chain storage excursion",
     "body_template": "A storage temperature excursion has been reported; quarantine affected units."},
    {"slug": "blood_recall_alert", "name": "Blood Recall / Look-Back", "channels": ["in_app"],
     "subject_template": "Blood recall initiated",
     "body_template": "A blood recall / look-back investigation has been initiated."},
    {"slug": "donor_deferred", "name": "Donor Deferred", "channels": ["in_app"],
     "subject_template": "Donor deferred",
     "body_template": "A donor has been deferred from donation."},
    # H11 quality · accreditation · patient-safety notifications.
    {"slug": "incident_reported", "name": "Incident Reported", "channels": ["in_app"],
     "subject_template": "Patient-safety incident reported",
     "body_template": "A patient-safety incident has been reported and requires review."},
    {"slug": "sentinel_alert", "name": "Severe / Sentinel Event", "channels": ["in_app"],
     "subject_template": "Severe / sentinel event — leadership review",
     "body_template": "A severe or sentinel patient-safety event was reported; leadership review + RCA required."},
    {"slug": "incident_investigated", "name": "Incident Investigated", "channels": ["in_app"],
     "subject_template": "Incident RCA complete",
     "body_template": "The root-cause analysis for an incident is complete; corrective actions can be planned."},
    {"slug": "capa_assigned", "name": "CAPA Assigned", "channels": ["in_app"],
     "subject_template": "Corrective / preventive action assigned",
     "body_template": "A corrective/preventive action has been assigned to you with a due date."},
    {"slug": "capa_verified", "name": "CAPA Verified", "channels": ["in_app"],
     "subject_template": "CAPA verified / closed",
     "body_template": "A corrective/preventive action has been verified and closed."},
    {"slug": "audit_completed", "name": "Quality Audit Completed", "channels": ["in_app"],
     "subject_template": "Quality audit completed",
     "body_template": "A quality audit has been completed; findings are available for review."},
    {"slug": "finding_raised", "name": "Audit Finding Raised", "channels": ["in_app"],
     "subject_template": "Audit finding raised",
     "body_template": "A non-compliance finding has been raised; a corrective action is required."},
    {"slug": "complaint_logged", "name": "Complaint Logged", "channels": ["in_app"],
     "subject_template": "Complaint logged",
     "body_template": "A patient complaint has been logged and requires a response."},
    {"slug": "complaint_resolved", "name": "Complaint Resolved", "channels": ["in_app"],
     "subject_template": "Complaint resolved",
     "body_template": "A patient complaint has been resolved."},
    {"slug": "accreditation_granted", "name": "Accreditation Granted", "channels": ["in_app"],
     "subject_template": "Accreditation granted",
     "body_template": "An accreditation has been granted to the facility."},
    {"slug": "risk_escalated", "name": "Risk Escalated", "channels": ["in_app"],
     "subject_template": "High residual risk identified",
     "body_template": "A risk assessment with a high/extreme residual risk requires risk-manager attention."},
    # H13 ancillary & information-governance notifications.
    {"slug": "consent_obtained", "name": "Consent Obtained", "channels": ["in_app"],
     "subject_template": "Consent obtained",
     "body_template": "A patient consent has been obtained and is active."},
    {"slug": "referral_sent", "name": "Referral Sent", "channels": ["in_app"],
     "subject_template": "Referral sent",
     "body_template": "A patient referral has been sent to the receiving team."},
    {"slug": "referral_completed", "name": "Referral Completed", "channels": ["in_app"],
     "subject_template": "Referral completed",
     "body_template": "A referral has been completed; feedback is available to the referrer."},
    {"slug": "record_request_logged", "name": "Record Request Logged", "channels": ["in_app"],
     "subject_template": "Medical record request logged",
     "body_template": "A medical-record / release-of-information request has been logged."},
    {"slug": "record_released", "name": "Records Released", "channels": ["in_app"],
     "subject_template": "Medical records released",
     "body_template": "Medical records have been released; the disclosure is on the audit trail."},
    {"slug": "cycle_passed", "name": "Sterilization Passed", "channels": ["in_app"],
     "subject_template": "Sterilization cycle passed",
     "body_template": "A sterilization cycle passed; the instrument set is now sterile."},
    {"slug": "cycle_failed", "name": "Sterilization Failed", "channels": ["in_app"],
     "subject_template": "Sterilization cycle FAILED",
     "body_template": "A sterilization cycle failed; the load must be reprocessed."},
    {"slug": "diet_order_active", "name": "Diet Order Active", "channels": ["in_app"],
     "subject_template": "Diet order active",
     "body_template": "A patient diet order is active; notify the kitchen/dietary team."},
    {"slug": "transport_requested", "name": "Transport Requested", "channels": ["in_app"],
     "subject_template": "Patient transport requested",
     "body_template": "A patient transport has been requested."},
    {"slug": "transport_completed", "name": "Transport Completed", "channels": ["in_app"],
     "subject_template": "Patient transport completed",
     "body_template": "A patient transport has been completed."},
    {"slug": "death_recorded", "name": "Death Recorded", "channels": ["in_app"],
     "subject_template": "Death recorded",
     "body_template": "A patient death has been recorded; mortuary and administration notified."},
    {"slug": "death_released", "name": "Body Released", "channels": ["in_app"],
     "subject_template": "Body released",
     "body_template": "A body has been released from the mortuary."},
]


# ── forms / views / navigation ────────────────────────────────────────────────
def _form_for(slug):
    obj = HOSPITAL_OBJECTS[slug]
    return {"slug": f"{slug}_form", "entity_slug": slug, "name": obj["name"], "is_default": True,
            "layout": [{"section": "Details", "fields": [f["slug"] for f in obj["fields"]]}]}


def _views_for(slug):
    obj = HOSPITAL_OBJECTS[slug]
    field_slugs = {f["slug"] for f in obj["fields"]}
    views = [{"slug": f"{slug}_table", "entity_slug": slug,
              "name": f"All {obj['plural_name']}", "view_type": "table", "is_default": True}]
    if "status" in field_slugs:
        views.append({"slug": f"{slug}_board", "entity_slug": slug, "name": "Board",
                      "view_type": "kanban", "config": {"group_by": "status"}})
    return views


def _nav_group(label, slugs):
    return {"label": label, "items": [
        {"label": HOSPITAL_OBJECTS[s]["plural_name"], "type": "entity", "target": s}
        for s in slugs]}


HOSPITAL_NAV = [
    _nav_group("Facility & Wards", ["facility", "clinical_department", "ward", "bed"]),
    _nav_group("Providers & Services", ["provider", "specialty", "service_catalog"]),
    _nav_group("Reference Data", ["payer", "diagnosis_code", "procedure_code", "drug_formulary"]),
    # H2 patient administration.
    _nav_group("Patients", ["patient"]),
    _nav_group("Patient Records", ["patient_contact", "insurance_policy"]),
    # H3 scheduling & appointments.
    _nav_group("Scheduling", ["provider_schedule", "schedule_exception"]),
    _nav_group("Appointments", ["appointment", "appointment_waitlist"]),
    # H4 clinical encounters.
    _nav_group("Clinical Encounters", ["encounter", "clinical_note"]),
    _nav_group("Clinical Record", ["diagnosis", "problem", "allergy", "vital_sign", "care_plan"]),
    _nav_group("Patient History", ["past_medical_history", "surgical_history", "family_history",
                                   "social_history"]),
    # H5 orders & results.
    _nav_group("Diagnostic Orders", ["diagnostic_order", "specimen"]),
    _nav_group("Results", ["diagnostic_result", "result_item"]),
    # H6 pharmacy & medication.
    _nav_group("Pharmacy — Prescriptions", ["prescription", "prescription_item"]),
    _nav_group("Pharmacy — Dispense & Admin", ["medication_dispense", "medication_administration"]),
    _nav_group("Medication Reconciliation", ["medication_reconciliation"]),
    # H7 inpatient, wards & nursing.
    _nav_group("Inpatient — Admissions", ["admission", "bed_assignment"]),
    _nav_group("Inpatient — Transfers & Discharge", ["transfer", "discharge"]),
    _nav_group("Nursing", ["nursing_observation", "nursing_task", "nursing_handover", "ward_round"]),
    # H8 surgery / OT & critical care.
    _nav_group("Surgery — Scheduling", ["operating_theatre", "ot_schedule", "surgery"]),
    _nav_group("Surgery — Operative", ["surgical_procedure", "anaesthesia_record",
                                       "surgical_team_member", "surgical_checklist"]),
    _nav_group("Surgery — Implants", ["implant", "implant_usage"]),
    _nav_group("Critical Care", ["icu_episode", "icu_observation", "recovery_episode"]),
    # H9 billing & claims.
    _nav_group("Billing — Charges & Invoices", ["charge", "invoice", "payment"]),
    _nav_group("Billing — Claims", ["claim", "claim_line", "preauthorization", "remittance"]),
    # H10 blood bank.
    _nav_group("Blood Bank — Donors", ["donor", "donation"]),
    _nav_group("Blood Bank — Inventory", ["blood_unit", "blood_test", "storage_excursion"]),
    _nav_group("Blood Bank — Transfusion", ["blood_request", "crossmatch", "blood_issue",
                                            "transfusion"]),
    _nav_group("Blood Bank — Haemovigilance", ["transfusion_reaction", "blood_recall"]),
    # H11 quality · accreditation · patient safety.
    _nav_group("Quality — Patient Safety", ["incident", "capa"]),
    _nav_group("Quality — Audits", ["quality_audit", "audit_finding"]),
    _nav_group("Quality — Accreditation", ["accreditation", "quality_standard"]),
    _nav_group("Quality — Risk & Complaints", ["risk_assessment", "complaint"]),
    # H13 ancillary & information governance.
    _nav_group("Clinical Ancillary", ["diet_order", "transport_request"]),
    _nav_group("Sterile Processing (CSSD)", ["instrument_set", "sterilization_cycle"]),
    _nav_group("Information Governance", ["consent", "referral", "medical_record_request"]),
    _nav_group("Mortuary", ["death_record"]),
]


# ── document templates (H9 — reuse the Core Document Engine: apps.document_templates +
# action_generate_document; pure metadata, no Hospital render code) ───────────────────────────────
def _blocks(entity_slug, field_slugs):
    name_by = {f["slug"]: f["name"] for f in HOSPITAL_OBJECTS[entity_slug]["fields"]}
    return [{"field": s, "label": name_by.get(s, s.replace("_", " ").title())} for s in field_slugs]


def _doc(slug, name, entity_slug, title, field_slugs):
    return {"slug": slug, "name": name, "entity_slug": entity_slug,
            "page_config": {"title": title, "subtitle": ""},
            "blocks": _blocks(entity_slug, field_slugs)}


HOSPITAL_DOCUMENTS = [
    _doc("hospital_invoice", "Hospital Invoice", "invoice", "Invoice",
         ["invoice_no", "patient", "payer", "invoice_type", "invoice_date", "due_date",
          "subtotal", "tax_amount", "total_amount", "balance", "status"]),
    _doc("hospital_receipt", "Payment Receipt", "payment", "Payment Receipt",
         ["receipt_no", "invoice", "patient", "payer", "payment_method", "amount",
          "payment_date", "reference", "status"]),
    # H10 blood bank documents (reuse the Core Document Engine; rendered on demand per record).
    _doc("blood_issue_slip", "Blood Issue Slip", "blood_issue", "Blood Issue Slip",
         ["issue_no", "blood_unit", "patient", "blood_request", "crossmatch", "issue_type",
          "issued_to", "issued_at", "issued_by", "authorized_by", "override_reason", "status"]),
    _doc("transfusion_record", "Transfusion Record", "transfusion", "Transfusion Record",
         ["transfusion_no", "patient", "blood_unit", "blood_issue", "started_at", "completed_at",
          "volume_ml", "administered_by", "status"]),
    # H11 quality documents (reuse the Core Document Engine; rendered on demand per record).
    _doc("incident_report", "Incident Report", "incident", "Patient-Safety Incident Report",
         ["incident_no", "incident_type", "severity", "is_sentinel", "patient", "department",
          "location", "occurred_at", "description", "immediate_action", "root_cause", "status"]),
    _doc("capa_form", "CAPA Form", "capa", "Corrective / Preventive Action",
         ["capa_no", "capa_type", "title", "incident", "audit_finding", "owner", "target_date",
          "description", "effectiveness_verified", "status"]),
    # H13 documents (reuse the Core Document Engine; rendered on demand per record).
    _doc("consent_form", "Consent Form", "consent", "Patient Consent",
         ["consent_no", "consent_type", "patient", "surgery", "description", "obtained_by",
          "witnessed_by", "valid_from", "valid_to", "status"]),
    _doc("death_certificate", "Death Certificate", "death_record", "Certificate of Death",
         ["record_no", "patient", "time_of_death", "cause_of_death", "manner", "certified_by",
          "certificate_no", "status"]),
]


# ── package block ─────────────────────────────────────────────────────────────
def _package_block() -> dict:
    return {
        "slug": "hospital", "name": "Hospital Management", "version": "1.13.0",
        "author": "Sridhar ERP",
        "description": "Enterprise Hospital / Health Information System — Master Data & Facility "
                       "(H1): facilities, clinical departments, wards and beds (generic types), the "
                       "provider directory + specialties, the service catalogue, payers, diagnosis "
                       "and procedure terminology masters and the drug formulary — generic objects "
                       "carry *_type discriminators (provider/ward/bed/payer/service), no per-variant "
                       "entities. "
                       "The 1st clinical package; reuses the ERP Core, ships zero native code, "
                       "installs independently. Later phases (H2 patients … H14 hardening) add the "
                       "rest as pure-manifest consumers of the frozen platforms.",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": ["workflow"],
        "requires_capabilities": ["metadata", "dynamic_forms", "views", "workflows",
                                  "reports", "dashboards", "rbac", "notifications",
                                  "numbering", "analytics_kpi",
                                  # H3 — appointment booking eligibility = the Core Guard Framework.
                                  "cross_record_validation"],
        "requires_packages": [],
        # consumed by later phases — pharmacy/stores → Inventory; biomedical/ambulance → Assets.
        "optional_packages": [{"slug": "inventory", "version": "*"},
                              {"slug": "assets", "version": "*"}],
        "conflicts_packages": [],
        "provides_capabilities": ["hospital", "health_information_system", "master_data",
                                  "facility_management", "provider_directory",
                                  "clinical_reference_data",
                                  # H2 — patient administration & registration.
                                  "patient_administration", "patient_registration",
                                  "patient_records",
                                  # H3 — scheduling & appointments.
                                  "appointment_scheduling", "patient_scheduling",
                                  # H4 — clinical encounters (EMR).
                                  "clinical_encounters", "emr", "clinical_documentation",
                                  "clinical_record",
                                  # H5 — orders & results.
                                  "diagnostic_orders", "laboratory", "radiology",
                                  "results_management",
                                  # H6 — pharmacy & medication.
                                  "pharmacy", "medication_management", "prescribing",
                                  "medication_administration", "medication_safety",
                                  # H7 — inpatient, wards & nursing.
                                  "inpatient", "ward_management", "bed_management", "nursing",
                                  "admission_discharge_transfer",
                                  # H8 — surgery / OT & critical care.
                                  "surgery", "operating_theatre", "perioperative", "anaesthesia",
                                  "surgical_safety", "critical_care", "icu", "recovery",
                                  # H10 — blood bank / transfusion medicine.
                                  "blood_bank", "transfusion_medicine", "donor_management",
                                  "blood_inventory", "haemovigilance",
                                  # H11 — quality · accreditation · patient safety.
                                  "quality_management", "patient_safety", "incident_management",
                                  "accreditation", "capa", "risk_management",
                                  # H12 — patient portal & executive analytics.
                                  "patient_portal", "executive_analytics", "executive_dashboards",
                                  # H13 — final functional phase: ancillary & information governance.
                                  "consent_management", "referral_management",
                                  "health_information_management", "sterile_processing",
                                  "dietary_nutrition", "patient_transport", "mortuary_management"],
        "migrations": [],
    }


# ── manifest assembly + seed ─────────────────────────────────────────────────
def build_hospital_manifest() -> dict:
    return {
        "schema_version": 1,
        "package": _package_block(),
        "entities": list(HOSPITAL_OBJECTS.values()),
        "forms": [_form_for(s) for s in HOSPITAL_OBJECTS],
        "views": [v for s in HOSPITAL_OBJECTS for v in _views_for(s)],
        "workflows": HOSPITAL_WORKFLOWS,       # H3 scheduling (Guard eligibility + notifications)
        "rules": HOSPITAL_RULES,               # H11 — data-integrity validation (Rules engine)
        "sla_policies": HOSPITAL_SLA_POLICIES,  # H11 — response-time SLA (SLA engine)
        "reports": HOSPITAL_REPORTS,
        "kpis": HOSPITAL_KPIS,
        "notification_templates": HOSPITAL_NOTIFICATIONS,
        "document_templates": HOSPITAL_DOCUMENTS,
        "roles": HOSPITAL_ROLES,
        "dashboards": HOSPITAL_DASHBOARDS,
        "portal_grants": HOSPITAL_PORTAL_GRANTS,   # H12 — patient portal (frozen Portal Platform)
        "navigations": [{"ref": "main", "name": "Hospital Menu", "scope": "app",
                         "tree": HOSPITAL_NAV}],
        "home_layouts": [{"ref": "home", "name": "Hospital Home", "scope": "app",
                          "widgets": [{"type": "card", "title": "Hospital Management"}]},
                         *HOSPITAL_ROLE_HOMES],
        "applications": [{
            "slug": "hospital", "name": "Hospital Management", "icon": "Stethoscope",
            "color": "#0e7490", "included_entity_slugs": _MAIN,
            "navigation_ref": "main", "home_layout_ref": "home",
            "role_slugs": [r["slug"] for r in HOSPITAL_ROLES], "is_published": True,
        }],
    }


def seed_hospital_template():
    """Upsert the published, system Hospital SolutionTemplate (idempotent by slug)."""
    from apps.solution_templates.models import SolutionTemplate
    tpl, _ = SolutionTemplate.objects.update_or_create(
        slug="hospital",
        defaults={
            "name": "Hospital Management",
            "category": "Healthcare",
            "description": "Enterprise Hospital / Health Information System — Master Data & Facility "
                           "(H1): facilities, departments, wards, beds, providers, specialties, "
                           "services, payers, medical codes and the drug formulary. The 1st clinical "
                           "package; ships zero native code, installs independently.",
            "icon": "Stethoscope", "color": "#0e7490", "publisher": "Sridhar ERP",
            "version": "1.13.0", "manifest": build_hospital_manifest(),
            "is_system": True, "is_published": True,
        })
    return tpl
