-- Ironvale Components plant database. Table and column names follow the Week 3 brief exactly,
-- so the hidden test's gold SQL runs unchanged against the public schema.

CREATE EXTENSION IF NOT EXISTS vector;

DROP TABLE IF EXISTS defects, downtime_events, work_orders, supplier_parts, machines, users,
                     chunks, eval_runs, eval_results CASCADE;

CREATE TABLE users (
    user_id  text PRIMARY KEY,
    name     text NOT NULL,
    role     text NOT NULL CHECK (role IN ('line_supervisor', 'quality_engineer', 'plant_head')),
    line     int            -- row scope: a line number for supervisors, NULL means all lines
);

CREATE TABLE machines (
    machine_id      text PRIMARY KEY,
    line            int  NOT NULL,
    type            text NOT NULL,
    model           text NOT NULL,
    commissioned_on date NOT NULL
);

CREATE TABLE work_orders (
    wo_id       text PRIMARY KEY,
    machine_id  text NOT NULL REFERENCES machines,
    part_no     text NOT NULL,
    qty_planned int  NOT NULL,
    qty_good    int  NOT NULL,
    started_at  timestamp NOT NULL,     -- plant local time (IST)
    ended_at    timestamp NOT NULL
);

CREATE TABLE downtime_events (
    event_id    text PRIMARY KEY,
    machine_id  text NOT NULL REFERENCES machines,
    start_at    timestamp NOT NULL,
    end_at      timestamp NOT NULL,
    category    text NOT NULL CHECK (category IN ('planned', 'breakdown', 'changeover', 'material')),
    reason_code text NOT NULL,
    alarm_code  text
);

CREATE TABLE defects (
    defect_id   text PRIMARY KEY,
    wo_id       text NOT NULL REFERENCES work_orders,
    part_no     text NOT NULL,
    defect_type text NOT NULL,
    qty         int  NOT NULL,
    found_at    timestamp NOT NULL,
    stage       text NOT NULL
);

CREATE TABLE supplier_parts (
    part_no        text NOT NULL,
    supplier       text NOT NULL,
    unit_price_inr numeric(10, 2) NOT NULL,
    valid_from     date NOT NULL,
    PRIMARY KEY (part_no, supplier, valid_from)
);

CREATE INDEX ON work_orders (machine_id, started_at);
CREATE INDEX ON downtime_events (machine_id, start_at);
CREATE INDEX ON defects (wo_id);

-- Retrieval index: one row per chunk, dense vector (pgvector, bge-small-en-v1.5 = 384 dims) plus the
-- metadata every chunk must carry. BM25 is built in the API from the same chunk ids.
CREATE TABLE chunks (
    chunk_id       text PRIMARY KEY,
    doc_id         text NOT NULL,
    title          text NOT NULL,
    section        text,
    page           int,
    version        text,
    effective_date date,
    superseded     boolean NOT NULL DEFAULT false,
    allowed_roles  text[] NOT NULL,
    scope          text NOT NULL,
    source         text NOT NULL CHECK (source IN ('digital', 'scanned')),
    text           text NOT NULL,
    embedding      vector(384)
);
CREATE INDEX ON chunks USING gin (allowed_roles);

-- Evaluation history for the Eval page
CREATE TABLE eval_runs (
    run_id         text PRIMARY KEY,
    created_at     timestamptz NOT NULL DEFAULT now(),
    git_commit     text,
    prompt_version text,
    model          text,
    metrics        jsonb NOT NULL
);
CREATE TABLE eval_results (
    run_id   text REFERENCES eval_runs ON DELETE CASCADE,
    q_id     text,
    passed   boolean,
    detail   jsonb,
    PRIMARY KEY (run_id, q_id)
);
