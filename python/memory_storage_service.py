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
                media BLOB,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        self._connection.commit()
        cursor.close()
    
    def _get_connection(self):
        return self._connection

def _execute_query(query, params=(), fetch=False):
    storage = _MemoriesStorageService()
    conn = storage._get_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    results = cursor.fetchall() if fetch else None
    conn.commit()
    cursor.close()
    return results

def save_memory(memory, media):
    _execute_query("""
        INSERT INTO memories (memory, media) VALUES (?, ?);
    """, (memory, media))

def get_recent_memories(n):
    return _execute_query("""
        SELECT * FROM memories ORDER BY created_at DESC LIMIT ?;
    """, (n,), fetch=True)
    
def get_all_memories():
    return _execute_query("""
        SELECT * FROM memories ORDER BY created_at;
    """, fetch=True)