-- Integrity checksum of register readings, not consumed energy.
-- Exploratory example: bind canonical_events to canonical source rows first.
SELECT meter_id, unit, decimal_scale, COUNT(*) AS event_count, SUM(scaled_value) AS scaled_sum
FROM canonical_events GROUP BY meter_id, unit, decimal_scale;
