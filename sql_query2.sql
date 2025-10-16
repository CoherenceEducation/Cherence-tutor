-- Check tables
SHOW TABLES;

-- Check structure
DESCRIBE students;
DESCRIBE conversation_history;
DESCRIBE flagged_content;
DESCRIBE analytics_summary;

SELECT * FROM students WHERE student_id = 'test_safety_001';
SELECT * FROM conversation_history WHERE student_id = 'test_001' ORDER BY created_at DESC;
-- Check if flagged
SELECT * FROM flagged_content ORDER BY flagged_at DESC LIMIT 5;

SHOW TABLES;

