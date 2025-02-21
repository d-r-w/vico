import base64
import duckdb
from threading import Lock

db_path = '../data/memories.duckdb'

class _MemoriesStorageService:
    _instance = None
    _lock = Lock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._connection = duckdb.connect(database=db_path, read_only=False)
                cls._instance._initialize_schema()
        return cls._instance
    
    def _initialize_schema(self):
        cursor = self._connection.cursor()
        cursor.execute("""
            CREATE SEQUENCE IF NOT EXISTS memories_id_seq START 1;
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER DEFAULT nextval('memories_id_seq') PRIMARY KEY,
                memory TEXT,
                image BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._connection.commit()
        cursor.close()
    
    def _get_connection(self):
        return self._connection

def process_memory_rows(rows):
    processed_rows = []
    for memory_row in rows:
        memory_id, memory, image, created_at = memory_row
        
        if image:
            image = base64.b64encode(image).decode('utf-8')
            
        processed_rows.append((memory_id, memory, image, created_at))
    
    return processed_rows

def _execute_query(query, params=(), fetch=False):
    storage = _MemoriesStorageService()
    conn = storage._get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall() if fetch else None
    conn.commit()
    cursor.close()
    return results

def save_memory(memory, media = None):
    _execute_query("""
        INSERT INTO memories (memory, media) VALUES (?, ?);
    """, (memory, media))
    
def get_recent_memories(n):
    rows = _execute_query("""
        SELECT * FROM memories ORDER BY created_at DESC LIMIT ?;
    """, (n,), fetch=True)
    
    return process_memory_rows(rows)

def search_memories(search):
    rows = _execute_query("""
        SELECT * FROM memories WHERE LOWER(memory) LIKE CONCAT('%', LOWER(?), '%') ORDER BY created_at DESC LIMIT 50;
    """, (search,), fetch=True)

    return process_memory_rows(rows)
    
def get_all_memories():
    return _execute_query("""
        SELECT id, created_at, memory FROM memories ORDER BY created_at;
    """, fetch=True)