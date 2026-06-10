-- V001 — Initial schema (cardiolab v0.1.0)
-- Creates the 7 base tables. Safe to run on an empty database.
-- All CREATE statements use IF NOT EXISTS so this script is idempotent.

-- ── Resting HRV ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_features (
    id          SERIAL PRIMARY KEY,
    user_id     TEXT  NOT NULL,
    date        DATE  NOT NULL,
    rmssd       FLOAT,
    ln_rmssd    FLOAT,
    sdnn        FLOAT,
    pnn50       FLOAT,
    mean_hr     FLOAT,
    vlf         FLOAT,
    lf          FLOAT,
    hf          FLOAT,
    lf_hf       FLOAT,
    hf_pct      FLOAT,
    lf_nu       FLOAT,
    hf_nu       FLOAT,
    hf_hr       FLOAT,
    sd1         FLOAT,
    sd2         FLOAT,
    sd_ratio    FLOAT,
    dfa_alpha1  FLOAT,
    duration    FLOAT,
    score       FLOAT,
    method      TEXT,
    UNIQUE(user_id, date)
);

-- ── Orthostatic ───────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_orthostatic (
    id                       SERIAL PRIMARY KEY,
    user_id                  TEXT NOT NULL,
    date                     DATE NOT NULL,
    -- Supine phase
    supine_rmssd             FLOAT, supine_ln_rmssd    FLOAT, supine_sdnn        FLOAT,
    supine_pnn50             FLOAT, supine_mean_hr     FLOAT, supine_vlf         FLOAT,
    supine_lf                FLOAT, supine_hf          FLOAT, supine_lf_hf       FLOAT,
    supine_hf_pct            FLOAT, supine_lf_nu       FLOAT, supine_hf_nu       FLOAT,
    supine_hf_hr             FLOAT, supine_sd1         FLOAT, supine_sd2         FLOAT,
    supine_sd_ratio          FLOAT, supine_dfa_alpha1  FLOAT,
    supine_duration_sec      FLOAT,
    -- Transition
    transition_start_sec     FLOAT, transition_end_sec      FLOAT,
    transition_duration_sec  FLOAT, transition_delta_hr     FLOAT,
    transition_peak_hr       FLOAT,
    transition_rmssd         FLOAT, transition_ln_rmssd     FLOAT, transition_sdnn       FLOAT,
    transition_pnn50         FLOAT, transition_mean_hr      FLOAT, transition_vlf        FLOAT,
    transition_lf            FLOAT, transition_hf           FLOAT, transition_lf_hf      FLOAT,
    transition_hf_pct        FLOAT, transition_lf_nu        FLOAT, transition_hf_nu      FLOAT,
    transition_hf_hr         FLOAT, transition_sd1          FLOAT, transition_sd2        FLOAT,
    transition_sd_ratio      FLOAT, transition_dfa_alpha1   FLOAT,
    -- Standing phase
    standing_rmssd           FLOAT, standing_ln_rmssd       FLOAT, standing_sdnn         FLOAT,
    standing_pnn50           FLOAT, standing_mean_hr        FLOAT, standing_vlf          FLOAT,
    standing_lf              FLOAT, standing_hf             FLOAT, standing_lf_hf        FLOAT,
    standing_hf_pct          FLOAT, standing_lf_nu          FLOAT, standing_hf_nu        FLOAT,
    standing_hf_hr           FLOAT, standing_sd1            FLOAT, standing_sd2          FLOAT,
    standing_sd_ratio        FLOAT, standing_dfa_alpha1     FLOAT,
    standing_duration_sec    FLOAT,
    -- Derived autonomic response
    hr_response              FLOAT,
    lf_hf_ratio_change       FLOAT,
    hf_response_pct          FLOAT,
    hf_hr_pct_change         FLOAT,
    interpretation           TEXT,
    spectral_method          TEXT,
    score                    FLOAT DEFAULT 0.0,
    UNIQUE(user_id, date)
);

-- ── Cardiac coherence ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_coherence (
    id                    SERIAL PRIMARY KEY,
    user_id               TEXT  NOT NULL,
    date                  DATE  NOT NULL,
    coherence_score       FLOAT,
    resonance_freq        FLOAT,
    peak_power            FLOAT,
    total_power_resonance FLOAT,
    rmssd                 FLOAT,
    sdnn                  FLOAT,
    mean_hr               FLOAT,
    duration              FLOAT,
    score                 FLOAT DEFAULT 0.0,
    UNIQUE(user_id, date)
);

-- ── Heart Rate Recovery ───────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_hrr (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT NOT NULL,
    date             DATE NOT NULL,
    hr_peak          FLOAT,
    hr_at_60s        FLOAT,
    hr_at_120s       FLOAT,
    hrr_60           FLOAT,
    hrr_120          FLOAT,
    hrr_60_category  TEXT,
    hrr_120_category TEXT,
    duration         FLOAT,
    score            FLOAT DEFAULT 0.0,
    UNIQUE(user_id, date)
);

-- ── Cardiac drift ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_drift (
    id               SERIAL PRIMARY KEY,
    user_id          TEXT    NOT NULL,
    date             DATE    NOT NULL,
    drift_rate       FLOAT,
    drift_magnitude  FLOAT,
    r_squared        FLOAT,
    drift_detected   BOOLEAN,
    initial_hr       FLOAT,
    final_hr         FLOAT,
    n_windows        INTEGER,
    interpretation   TEXT,
    duration         FLOAT,
    score            FLOAT DEFAULT 0.0,
    UNIQUE(user_id, date)
);

-- ── VO2max estimation ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_vo2max (
    id                SERIAL PRIMARY KEY,
    user_id           TEXT NOT NULL,
    date              DATE NOT NULL,
    vo2max_uth        FLOAT,
    vo2max_esco_flatt FLOAT,
    vo2max_ln_rmssd   FLOAT,
    hr_rest           FLOAT,
    hr_max            FLOAT,
    rmssd_used        FLOAT,
    ln_rmssd_used     FLOAT,
    fitness_category  TEXT,
    score             FLOAT DEFAULT 0.0,
    UNIQUE(user_id, date)
);

-- ── Raw RR sessions ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS hrv_raw_sessions (
    id           SERIAL PRIMARY KEY,
    user_id      TEXT      NOT NULL,
    session_date DATE      NOT NULL,
    protocol     TEXT      NOT NULL,
    rr_intervals FLOAT[]   NOT NULL,
    source_file  TEXT,
    device       TEXT      DEFAULT 'hrv_elite',
    duration_sec FLOAT,
    beat_count   INT,
    created_at   TIMESTAMP DEFAULT NOW(),
    metadata     JSONB     DEFAULT '{}',
    UNIQUE(user_id, session_date, protocol)
);
