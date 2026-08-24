"""
Standard Business Object Library — entity specs (manifest ``entities`` fragments).

Covers the spec's standard objects: Customer, Contact, Vendor, Employee, Product,
Warehouse, Asset, Project, Task, Contract, Ticket, Invoice, Purchase Order, Sales Order.
Relationships are modelled as ``lookup`` fields whose ``config.target_entity_slug`` points
at another object — they resolve through the existing relationship engine, not custom CRUD.
"""


def _f(slug, name, field_type, **kw):
    f = {"slug": slug, "name": name, "field_type": field_type, "is_promoted": True}
    f.update(kw)
    return f


def _lookup(slug, name, target):
    return _f(slug, name, "lookup", config={"target_entity_slug": target})


# Common leading fields every object gets (a human title + status).
def _entity(slug, name, plural, fields):
    return {"slug": slug, "name": name, "plural_name": plural, "fields": fields}


BUSINESS_OBJECTS: dict[str, dict] = {
    "customer": _entity("customer", "Customer", "Customers", [
        _f("name", "Name", "text", is_required=True),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("industry", "Industry", "text"),
        _f("status", "Status", "status", config={"choices": ["active", "inactive", "prospect"]}),
        _f("website", "Website", "url"),
    ]),
    "contact": _entity("contact", "Contact", "Contacts", [
        _f("name", "Full Name", "text", is_required=True),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("title", "Job Title", "text"),
        _lookup("customer", "Customer", "customer"),
    ]),
    "vendor": _entity("vendor", "Vendor", "Vendors", [
        _f("name", "Name", "text", is_required=True),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("tax_id", "Tax ID", "text"),
        _f("status", "Status", "status", config={"choices": ["active", "inactive", "blocked"]}),
    ]),
    "employee": _entity("employee", "Employee", "Employees", [
        _f("name", "Name", "text", is_required=True),
        _f("email", "Work Email", "email"),
        _f("job_title", "Job Title", "text"),
        _f("hire_date", "Hire Date", "date"),
        _f("status", "Status", "status", config={"choices": ["active", "on_leave", "terminated"]}),
    ]),
    "product": _entity("product", "Product", "Products", [
        _f("name", "Name", "text", is_required=True),
        _f("sku", "SKU", "text", is_unique=True),
        _f("price", "Price", "currency"),
        _f("category", "Category", "text"),
        _f("is_active", "Active", "boolean", default_value=True),
    ]),
    "warehouse": _entity("warehouse", "Warehouse", "Warehouses", [
        _f("name", "Name", "text", is_required=True),
        _f("code", "Code", "text", is_unique=True),
        _f("address", "Address", "textarea"),
    ]),
    "asset": _entity("asset", "Asset", "Assets", [
        _f("name", "Name", "text", is_required=True),
        _f("asset_tag", "Asset Tag", "text", is_unique=True),
        _f("acquired_on", "Acquired On", "date"),
        _f("value", "Value", "currency"),
        _f("status", "Status", "status", config={"choices": ["in_use", "in_storage", "retired"]}),
    ]),
    "project": _entity("project", "Project", "Projects", [
        _f("name", "Name", "text", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("status", "Status", "status", config={"choices": ["planned", "active", "on_hold", "done"]}),
        _lookup("customer", "Customer", "customer"),
    ]),
    "task": _entity("task", "Task", "Tasks", [
        _f("title", "Title", "text", is_required=True),
        _f("due_date", "Due Date", "date"),
        _f("priority", "Priority", "select", config={"choices": ["low", "medium", "high", "urgent"]}),
        _f("status", "Status", "status", config={"choices": ["todo", "in_progress", "done"]}),
        _lookup("project", "Project", "project"),
        _f("assignee", "Assignee", "user"),
    ]),
    "contract": _entity("contract", "Contract", "Contracts", [
        _f("title", "Title", "text", is_required=True),
        _f("start_date", "Start Date", "date"),
        _f("end_date", "End Date", "date"),
        _f("value", "Value", "currency"),
        _f("status", "Status", "status", config={"choices": ["draft", "active", "expired", "terminated"]}),
        _lookup("customer", "Customer", "customer"),
    ]),
    "ticket": _entity("ticket", "Ticket", "Tickets", [
        _f("subject", "Subject", "text", is_required=True),
        _f("description", "Description", "textarea"),
        _f("priority", "Priority", "select", config={"choices": ["low", "medium", "high", "urgent"]}),
        _f("status", "Status", "status", config={"choices": ["new", "open", "pending", "resolved", "closed"]}),
        _lookup("customer", "Customer", "customer"),
        _f("assignee", "Assignee", "user"),
    ]),
    "invoice": _entity("invoice", "Invoice", "Invoices", [
        _f("number", "Invoice Number", "text", is_unique=True),
        _f("issue_date", "Issue Date", "date"),
        _f("due_date", "Due Date", "date"),
        _f("amount", "Amount", "currency"),
        _f("status", "Status", "status", config={"choices": ["draft", "sent", "paid", "overdue", "void"]}),
        _lookup("customer", "Customer", "customer"),
    ]),
    "purchase_order": _entity("purchase_order", "Purchase Order", "Purchase Orders", [
        _f("number", "PO Number", "text", is_unique=True),
        _f("order_date", "Order Date", "date"),
        _f("amount", "Amount", "currency"),
        _f("status", "Status", "status", config={"choices": ["draft", "submitted", "approved", "received", "closed"]}),
        _lookup("vendor", "Vendor", "vendor"),
    ]),
    "sales_order": _entity("sales_order", "Sales Order", "Sales Orders", [
        _f("number", "SO Number", "text", is_unique=True),
        _f("order_date", "Order Date", "date"),
        _f("amount", "Amount", "currency"),
        _f("status", "Status", "status", config={"choices": ["draft", "confirmed", "fulfilled", "invoiced", "closed"]}),
        _lookup("customer", "Customer", "customer"),
    ]),
    # Industry objects (e.g. Healthcare) — same first-class shape; recommended by presets.
    "patient": _entity("patient", "Patient", "Patients", [
        _f("name", "Name", "text", is_required=True),
        _f("dob", "Date of Birth", "date"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
        _f("gender", "Gender", "select", config={"choices": ["female", "male", "other", "undisclosed"]}),
        _f("status", "Status", "status", config={"choices": ["active", "inactive"]}),
    ]),
    "practitioner": _entity("practitioner", "Practitioner", "Practitioners", [
        _f("name", "Name", "text", is_required=True),
        _f("specialty", "Specialty", "text"),
        _f("email", "Email", "email"),
        _f("phone", "Phone", "phone"),
    ]),
    "appointment": _entity("appointment", "Appointment", "Appointments", [
        _f("title", "Title", "text", is_required=True),
        _f("appointment_date", "Appointment Date", "datetime"),
        _f("status", "Status", "status", config={"choices": ["scheduled", "completed", "cancelled", "no_show"]}),
        _lookup("patient", "Patient", "patient"),
        _lookup("practitioner", "Practitioner", "practitioner"),
    ]),
    "medical_record": _entity("medical_record", "Medical Record", "Medical Records", [
        _f("title", "Title", "text", is_required=True),
        _f("record_date", "Record Date", "date"),
        _f("notes", "Notes", "textarea"),
        _lookup("patient", "Patient", "patient"),
    ]),
}
