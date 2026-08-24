-- NexusERP PostgreSQL bootstrap script.
-- Run once as a superuser: psql -U postgres -f setup_postgres.sql

-- 1. Role & database
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'nexus') THEN
        CREATE ROLE nexus WITH LOGIN PASSWORD 'nexus' CREATEDB;
    END IF;
END
$$;

CREATE DATABASE nexus_dev OWNER nexus ENCODING 'UTF8' LC_COLLATE 'en_US.UTF-8' LC_CTYPE 'en_US.UTF-8' TEMPLATE template0;

\connect nexus_dev

-- 2. Global sequence for domain_events.global_sequence
CREATE SEQUENCE IF NOT EXISTS domain_event_global_seq
    START WITH 1 INCREMENT BY 1 NO MAXVALUE CACHE 100 OWNED BY NONE;

GRANT USAGE ON SEQUENCE domain_event_global_seq TO nexus;

-- 3. Row-Level Security helper function
--    Called at the start of every request: SET LOCAL app.workspace_id = '<uuid>';
--    RLS policies read it via current_setting('app.workspace_id', true).

CREATE OR REPLACE FUNCTION current_workspace_id() RETURNS uuid AS $$
    SELECT NULLIF(current_setting('app.workspace_id', true), '')::uuid;
$$ LANGUAGE sql STABLE;

-- 4. Enable RLS on tenant tables and create policies.
--    Run AFTER Django migrate has created all tables.

-- domain_events
ALTER TABLE domain_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE domain_events FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON domain_events
    USING (workspace_id = current_workspace_id());

-- records
ALTER TABLE records ENABLE ROW LEVEL SECURITY;
ALTER TABLE records FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON records
    USING (workspace_id = current_workspace_id());

-- record_versions
ALTER TABLE record_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE record_versions FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON record_versions
    USING (workspace_id = current_workspace_id());

-- workflows (definition)
ALTER TABLE workflow_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_definitions FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON workflow_definitions
    USING (workspace_id = current_workspace_id());

-- workflow_runs
ALTER TABLE workflow_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE workflow_runs FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON workflow_runs
    USING (workspace_id = current_workspace_id());

-- audit_logs
ALTER TABLE audit_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE audit_logs FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON audit_logs
    USING (workspace_id = current_workspace_id());

-- entity_definitions (metadata)
ALTER TABLE entity_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE entity_definitions FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON entity_definitions
    USING (workspace_id = current_workspace_id());

-- field_definitions (metadata)
ALTER TABLE field_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE field_definitions FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON field_definitions
    USING (workspace_id = current_workspace_id());

-- reports
ALTER TABLE reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE reports FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON reports
    USING (workspace_id = current_workspace_id());

-- dashboards
ALTER TABLE dashboards ENABLE ROW LEVEL SECURITY;
ALTER TABLE dashboards FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON dashboards
    USING (workspace_id = current_workspace_id());

-- documents
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON documents
    USING (workspace_id = current_workspace_id());

-- notifications
ALTER TABLE notifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON notifications
    USING (workspace_id = current_workspace_id());

-- business_rules
ALTER TABLE business_rules ENABLE ROW LEVEL SECURITY;
ALTER TABLE business_rules FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON business_rules
    USING (workspace_id = current_workspace_id());

-- sla_records
ALTER TABLE sla_records ENABLE ROW LEVEL SECURITY;
ALTER TABLE sla_records FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON sla_records
    USING (workspace_id = current_workspace_id());

-- portal_users
ALTER TABLE portal_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE portal_users FORCE ROW LEVEL SECURITY;
CREATE POLICY ws_isolation ON portal_users
    USING (workspace_id = current_workspace_id());

-- 5. Trigger: make domain_event_global_seq populate global_sequence automatically
--    Run AFTER Django migrate.
CREATE OR REPLACE FUNCTION set_domain_event_sequence()
RETURNS trigger AS $$
BEGIN
    NEW.global_sequence := nextval('domain_event_global_seq');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_domain_event_seq ON domain_events;
CREATE TRIGGER trg_domain_event_seq
    BEFORE INSERT ON domain_events
    FOR EACH ROW EXECUTE FUNCTION set_domain_event_sequence();

-- 6. Trigger: prevent UPDATE/DELETE on audit_logs (belt + suspenders)
CREATE OR REPLACE FUNCTION deny_audit_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit_logs are immutable — UPDATE and DELETE are prohibited';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_immutable ON audit_logs;
CREATE TRIGGER trg_audit_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION deny_audit_mutation();

-- 7. Trigger: prevent UPDATE/DELETE on domain_events
CREATE OR REPLACE FUNCTION deny_event_mutation()
RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'domain_events are immutable — UPDATE and DELETE are prohibited';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_event_immutable ON domain_events;
CREATE TRIGGER trg_event_immutable
    BEFORE UPDATE OR DELETE ON domain_events
    FOR EACH ROW EXECUTE FUNCTION deny_event_mutation();

-- 8. Grant table privileges to nexus role
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO nexus;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO nexus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO nexus;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO nexus;

-- Done
\echo 'NexusERP PostgreSQL bootstrap complete.'
