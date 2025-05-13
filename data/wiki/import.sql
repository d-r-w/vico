INSTALL fts;  
LOAD fts;

CREATE TABLE IF NOT EXISTS articles AS
SELECT title, text
FROM read_json_auto('extracted_json/*/*');

PRAGMA create_fts_index('articles', 'rowid', 'text');
