-- Exploratory example: bind canonical_events to canonical source rows first.
SELECT meter_id, event_time_utc, COUNT(*) AS multiplicity
FROM canonical_events GROUP BY meter_id, event_time_utc HAVING COUNT(*) > 1;
