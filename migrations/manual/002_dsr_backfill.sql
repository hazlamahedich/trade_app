-- Backfill n_trials and sr_variance for existing experiments
-- MANDATORY for Story 4.5 statistical consistency
UPDATE experiments 
SET n_trials = 1, sr_variance = 0.0 
WHERE status = 'completed' AND n_trials IS NULL;
