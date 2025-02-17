-- Test data setup script for price_history table

-- Clear existing test data if needed (commented out for safety)
-- TRUNCATE price_history RESTART IDENTITY;

-- Insert historical hourly price data with predictions
INSERT INTO price_history (
    timestamp, 
    hourly_price, 
    day_ahead_price, 
    predicted_price,
    prediction_confidence
)
VALUES 
    (NOW() - interval '1 hour', 2.8, 3.1, 2.9, 75.0),
    (NOW() - interval '2 hours', 2.9, 3.2, 3.0, 80.0),
    (NOW() - interval '3 hours', 3.1, 3.4, 3.2, 85.0);

-- Verify data
SELECT 
    COUNT(*) as total_records,
    AVG(hourly_price) as avg_price,
    MIN(hourly_price) as min_price,
    MAX(hourly_price) as max_price
FROM price_history;

-- Example query for viewing recent predictions
SELECT 
    timestamp,
    hourly_price,
    predicted_price,
    prediction_accuracy,
    prediction_confidence
FROM price_history
WHERE predicted_price IS NOT NULL
ORDER BY timestamp DESC
LIMIT 5;