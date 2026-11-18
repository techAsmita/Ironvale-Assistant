-- Access control for Text-to-SQL. Run after schema.sql and the seed, as the database owner.
--
-- One read-only role per app role. Each role gets its own schema of views named exactly like the
-- tables (sup.downtime_events, qe.defects ...), so the model writes ordinary SQL and the role can only
-- reach the views it is allowed. Row scope comes from Row-Level Security policies that read
-- current_setting('app.user_id'), which the API sets per request inside the transaction.

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ironvale_views') THEN CREATE ROLE ironvale_views NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ironvale_sup')   THEN CREATE ROLE ironvale_sup   NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ironvale_qe')    THEN CREATE ROLE ironvale_qe    NOLOGIN; END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'ironvale_head')  THEN CREATE ROLE ironvale_head  NOLOGIN; END IF;
END $$;
-- The API's login role may switch into the three query roles with SET LOCAL ROLE.
GRANT ironvale_sup, ironvale_qe, ironvale_head TO CURRENT_USER;

-- Scope helper: true when the current request's user may see rows of this line.
-- SECURITY DEFINER so it can read users; it trusts only app.user_id, never anything in the SQL text.
CREATE OR REPLACE FUNCTION public.app_can_see_line(p_line int) RETURNS boolean
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.users u
    WHERE u.user_id = current_setting('app.user_id', true)
      AND (u.role IN ('quality_engineer', 'plant_head') OR u.line = p_line)
  );
$$;
REVOKE ALL ON FUNCTION public.app_can_see_line(int) FROM PUBLIC;
-- RLS policy expressions run with the querying role's rights, so the query roles need EXECUTE too.
-- Safe: it returns only a boolean and reads nothing but app.user_id.
GRANT EXECUTE ON FUNCTION public.app_can_see_line(int) TO ironvale_views, ironvale_sup, ironvale_qe, ironvale_head;

-- Row-Level Security on the scoped tables. The view owner (ironvale_views) is subject to it.
ALTER TABLE machines        ENABLE ROW LEVEL SECURITY;
ALTER TABLE work_orders     ENABLE ROW LEVEL SECURITY;
ALTER TABLE downtime_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE defects         ENABLE ROW LEVEL SECURITY;
ALTER TABLE supplier_parts  ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS scope_machines ON machines;
DROP POLICY IF EXISTS scope_wo ON work_orders;
DROP POLICY IF EXISTS scope_dt ON downtime_events;
DROP POLICY IF EXISTS scope_defects ON defects;
DROP POLICY IF EXISTS scope_sp ON supplier_parts;
CREATE POLICY scope_machines ON machines        FOR SELECT TO ironvale_views USING (app_can_see_line(line));
CREATE POLICY scope_wo       ON work_orders     FOR SELECT TO ironvale_views USING (
    app_can_see_line((SELECT m.line FROM machines m WHERE m.machine_id = work_orders.machine_id)));
CREATE POLICY scope_dt       ON downtime_events FOR SELECT TO ironvale_views USING (
    app_can_see_line((SELECT m.line FROM machines m WHERE m.machine_id = downtime_events.machine_id)));
CREATE POLICY scope_defects  ON defects         FOR SELECT TO ironvale_views USING (
    app_can_see_line((SELECT m.line FROM work_orders w JOIN machines m USING (machine_id) WHERE w.wo_id = defects.wo_id)));
CREATE POLICY scope_sp       ON supplier_parts  FOR SELECT TO ironvale_views USING (
    current_setting('app.user_id', true) IS NOT NULL);

GRANT USAGE ON SCHEMA public TO ironvale_views;
GRANT SELECT ON machines, work_orders, downtime_events, defects, supplier_parts TO ironvale_views;

-- Query roles must not reach the base tables or other schemas directly.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO CURRENT_USER;

-- Per-role view schemas
DROP SCHEMA IF EXISTS sup CASCADE;
DROP SCHEMA IF EXISTS qe CASCADE;
DROP SCHEMA IF EXISTS head CASCADE;
CREATE SCHEMA sup  AUTHORIZATION ironvale_views;
CREATE SCHEMA qe   AUTHORIZATION ironvale_views;
CREATE SCHEMA head AUTHORIZATION ironvale_views;

SET ROLE ironvale_views;
-- line_supervisor: machines, work_orders, downtime_events · own line only (RLS)
CREATE VIEW sup.machines        WITH (security_barrier) AS SELECT * FROM public.machines;
CREATE VIEW sup.work_orders     WITH (security_barrier) AS SELECT * FROM public.work_orders;
CREATE VIEW sup.downtime_events WITH (security_barrier) AS SELECT * FROM public.downtime_events;
-- quality_engineer: the above + defects + supplier_parts without unit_price_inr · all lines
CREATE VIEW qe.machines         WITH (security_barrier) AS SELECT * FROM public.machines;
CREATE VIEW qe.work_orders      WITH (security_barrier) AS SELECT * FROM public.work_orders;
CREATE VIEW qe.downtime_events  WITH (security_barrier) AS SELECT * FROM public.downtime_events;
CREATE VIEW qe.defects          WITH (security_barrier) AS SELECT * FROM public.defects;
CREATE VIEW qe.supplier_parts   WITH (security_barrier) AS SELECT part_no, supplier, valid_from FROM public.supplier_parts;
-- plant_head: everything
CREATE VIEW head.machines        WITH (security_barrier) AS SELECT * FROM public.machines;
CREATE VIEW head.work_orders     WITH (security_barrier) AS SELECT * FROM public.work_orders;
CREATE VIEW head.downtime_events WITH (security_barrier) AS SELECT * FROM public.downtime_events;
CREATE VIEW head.defects         WITH (security_barrier) AS SELECT * FROM public.defects;
CREATE VIEW head.supplier_parts  WITH (security_barrier) AS SELECT * FROM public.supplier_parts;
RESET ROLE;

GRANT USAGE ON SCHEMA sup TO ironvale_sup;
GRANT SELECT ON ALL TABLES IN SCHEMA sup TO ironvale_sup;
GRANT USAGE ON SCHEMA qe TO ironvale_qe;
GRANT SELECT ON ALL TABLES IN SCHEMA qe TO ironvale_qe;
GRANT USAGE ON SCHEMA head TO ironvale_head;
GRANT SELECT ON ALL TABLES IN SCHEMA head TO ironvale_head;

ALTER ROLE ironvale_sup  SET statement_timeout = '5s';
ALTER ROLE ironvale_qe   SET statement_timeout = '5s';
ALTER ROLE ironvale_head SET statement_timeout = '5s';
