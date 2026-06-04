-- V004 — Add user_profiles table (cardiolab v0.2.4)
-- Stores per-user settings and physical data used in HRV calculations.
-- user_id is the primary key (same UUID used across all other tables).

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id          TEXT      PRIMARY KEY,
    primary_protocol TEXT      NOT NULL DEFAULT 'resting',
    sex              TEXT,
    birth_year       INT,
    height_cm        FLOAT,
    hr_max           INT,
    hr_rest          INT,
    weight_kg        FLOAT,
    created_at       TIMESTAMP DEFAULT NOW(),
    updated_at       TIMESTAMP DEFAULT NOW()
);
