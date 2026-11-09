-- V007 — Exercise tests: DFA α1 thresholds and Lamberts submaximal cycle test (cardiolab v0.6.0)
-- Two new tables, nothing changed in the existing ones. Safe to re-run (IF NOT EXISTS).
-- Both hold user data: they are listed in USER_DATA_TABLE_ATTRS (delete_user_data).

-- ── DFA α1 thresholds ─────────────────────────────────────────────────────────
-- One row per test (or per thresholds entry): HRVT1 (α1 = 0.75) and HRVT2
-- (α1 = 0.5), the power or speed at each, the highest heart rate held 5 s.
-- source: dfa (incremental test analysed by cardiolab) · manual (values entered
-- by hand, e.g. laboratory test) — both give the training zones.
-- *_status: detected · not_reached · unreliable. Zones are sport-specific.
CREATE TABLE IF NOT EXISTS hrv_dfa_thresholds (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT    NOT NULL,
    date             DATE    NOT NULL,
    sport            TEXT,
    source           TEXT    NOT NULL DEFAULT 'dfa'
                     CHECK (source IN ('dfa', 'manual')),
    vt1_hr           FLOAT,
    vt2_hr           FLOAT,
    vt1_status       TEXT CHECK (vt1_status IN ('detected', 'not_reached', 'unreliable')),
    vt2_status       TEXT CHECK (vt2_status IN ('detected', 'not_reached', 'unreliable')),
    vt1_intensity    FLOAT,
    vt2_intensity    FLOAT,
    intensity_unit   TEXT,
    vt1_r_squared    FLOAT,
    vt2_r_squared    FLOAT,
    hr_max_observed  FLOAT,
    quality          JSONB,
    UNIQUE(user_id, date)
);

-- ── Lamberts submaximal cycle test (LSCT) ─────────────────────────────────────
-- Stages at 60 / 80 / 90 % of hr_max (6, 6, 3 min): mean power and heart rate,
-- heart rate over the last minute, target reached, perceived exertion
-- (as entered, NULL if not). hrr_60: heart rate drop 60 s after stage 3.
CREATE TABLE IF NOT EXISTS hrv_lsct (
    id                     SERIAL PRIMARY KEY,
    user_id                TEXT    NOT NULL,
    date                   DATE    NOT NULL,
    hr_max                 FLOAT,
    start_sec              FLOAT,
    hrr_60                 FLOAT,
    stage1_power           FLOAT,
    stage1_hr              FLOAT,
    stage1_hr_end          FLOAT,
    stage1_target_reached  BOOLEAN,
    stage1_rpe             FLOAT,
    stage2_power           FLOAT,
    stage2_hr              FLOAT,
    stage2_hr_end          FLOAT,
    stage2_target_reached  BOOLEAN,
    stage2_rpe             FLOAT,
    stage3_power           FLOAT,
    stage3_hr              FLOAT,
    stage3_hr_end          FLOAT,
    stage3_target_reached  BOOLEAN,
    stage3_rpe             FLOAT,
    UNIQUE(user_id, date)
);
