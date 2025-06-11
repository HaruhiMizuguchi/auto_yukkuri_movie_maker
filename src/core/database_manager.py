# Database Manager
import sqlite3
import logging
import os
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional


class DatabaseError(Exception):
    """Custom exception for database-related errors"""
    pass


class MigrationError(Exception):
    """Custom exception for database migration errors"""
    pass


class DatabaseManager:
    """Database manager for the Yukkuri video generation system."""
    
    def __init__(self, db_path: str = "data/yukkuri_system.db"):
        """Initialize DatabaseManager."""
        self.db_path = Path(db_path)
        self.logger = logging.getLogger(__name__)
        self._connection = None
        self._in_transaction = False
        
        # Ensure database directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def initialize(self):
        """Initialize database with complete schema."""
        try:
            with self.get_connection() as conn:
                self._create_all_tables(conn)
                
                # Insert initial migration record
                conn.execute(
                    "INSERT OR IGNORE INTO schema_migrations (version, description) VALUES (?, ?)",
                    ("1.0.0", "Initial schema creation")
                )
                
                conn.commit()
                self.logger.info("Database initialized successfully")
                
        except Exception as e:
            raise DatabaseError(f"Failed to initialize database: {str(e)}")
    
    @contextmanager
    def get_connection(self):
        """Get a database connection."""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self.db_path))
            self._connection.row_factory = sqlite3.Row
            self._connection.execute("PRAGMA foreign_keys = ON")
        
        try:
            yield self._connection
        except Exception as e:
            self._connection.rollback()
            raise DatabaseError(f"Database connection error: {str(e)}")
    
    def close_connection(self):
        """Close the database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
    
    @contextmanager
    def transaction(self):
        """Database transaction context manager."""
        with self.get_connection() as conn:
            self._in_transaction = True
            try:
                conn.execute("BEGIN")
                yield conn
                conn.commit()
            except Exception as e:
                conn.rollback()
                raise DatabaseError(f"Transaction failed: {str(e)}")
            finally:
                self._in_transaction = False
    
    def _create_all_tables(self, conn: sqlite3.Connection):
        """Create all database tables."""
        # Schema migrations table (create first)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version TEXT NOT NULL UNIQUE,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Projects table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                theme TEXT NOT NULL,
                target_length_minutes REAL DEFAULT 5,
                status TEXT NOT NULL DEFAULT 'created',
                config_json TEXT DEFAULT '{}',
                output_summary_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (status IN ('created', 'in_progress', 'completed', 'failed', 'cancelled', 'interrupted', 'running'))
            )
        """)
        
        # Workflow steps table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS workflow_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                step_number INTEGER NOT NULL,
                step_name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                started_at TIMESTAMP NULL,
                completed_at TIMESTAMP NULL,
                input_data TEXT DEFAULT '{}',
                output_data TEXT DEFAULT '{}',
                error_message TEXT NULL,
                retry_count INTEGER DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped')),
                UNIQUE(project_id, step_number)
            )
        """)
        
        # Project files table  
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_category TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_size INTEGER DEFAULT 0,
                mime_type TEXT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT DEFAULT '{}',
                is_temporary BOOLEAN DEFAULT 0,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                CHECK (file_type IN ('script', 'audio', 'video', 'image', 'subtitle', 'thumbnail', 'config', 'metadata'))
            )
        """)
        
        # Project statistics table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS project_statistics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL,
                total_duration REAL DEFAULT 0,
                audio_duration REAL DEFAULT 0,
                video_file_size INTEGER DEFAULT 0,
                processing_time REAL DEFAULT 0,
                api_calls_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            )
        """)
        
        # API usage table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                api_name TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                project_id TEXT NULL,
                request_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_time REAL NOT NULL,
                status_code INTEGER NOT NULL,
                tokens_used INTEGER DEFAULT 0,
                cost REAL DEFAULT 0.0,
                error_message TEXT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE SET NULL
            )
        """)
        
        # System config table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS system_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                data_type TEXT NOT NULL DEFAULT 'string',
                description TEXT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CHECK (data_type IN ('string', 'integer', 'float', 'boolean', 'json'))
            )
        """)
    
    def get_table_names(self) -> List[str]:
        """Get list of table names in the database."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )
            return [row[0] for row in cursor.fetchall()]
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """Get schema information for a specific table."""
        with self.get_connection() as conn:
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            return [
                {
                    'cid': row[0],
                    'name': row[1],
                    'type': row[2],
                    'notnull': bool(row[3]),
                    'dflt_value': row[4],
                    'pk': bool(row[5])
                }
                for row in cursor.fetchall()
            ]
    
    def validate_schema(self) -> bool:
        """Validate database schema integrity."""
        required_tables = [
            'projects', 'workflow_steps', 'project_files',
            'project_statistics', 'api_usage', 'system_config', 'schema_migrations'
        ]
        
        try:
            existing_tables = self.get_table_names()
            
            missing_tables = set(required_tables) - set(existing_tables)
            if missing_tables:
                self.logger.error(f"Missing tables: {missing_tables}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Schema validation failed: {str(e)}")
            return False
    
    def get_migration_version(self) -> int:
        """Get current migration version."""
        try:
            with self.get_connection() as conn:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM schema_migrations"
                )
                return cursor.fetchone()[0]
        except:
            return 0
    
    def is_migration_applied(self, version: int) -> bool:
        """Check if a migration version is applied."""
        try:
            current_version = self.get_migration_version()
            return current_version >= version
        except:
            return False
    
    def create_backup(self, backup_path: str):
        """Create database backup."""
        import shutil
        
        backup_path = Path(backup_path)
        backup_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            shutil.copy2(str(self.db_path), str(backup_path))
            self.logger.info(f"Database backup created: {backup_path}")
            
        except Exception as e:
            raise DatabaseError(f"Backup creation failed: {str(e)}")
    
    def restore_from_backup(self, backup_path: str):
        """Restore database from backup."""
        import shutil
        
        backup_path = Path(backup_path)
        if not backup_path.exists():
            raise DatabaseError(f"Backup file not found: {backup_path}")
        
        try:
            # Close connection before restoring
            self.close_connection()
            
            # Restore backup
            shutil.copy2(str(backup_path), str(self.db_path))
            
            self.logger.info(f"Database restored from backup: {backup_path}")
            
        except Exception as e:
            raise DatabaseError(f"Backup restore failed: {str(e)}")
    
    def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        health_status = {
            "status": "healthy",
            "db_path": str(self.db_path),
            "db_size_bytes": 0,
            "table_count": 0
        }
        
        try:
            with self.get_connection() as conn:
                # Check database connectivity
                conn.execute("SELECT 1")
                
                # Get database size
                if self.db_path.exists():
                    health_status["db_size_bytes"] = self.db_path.stat().st_size
                
                # Get table count
                health_status["table_count"] = len(self.get_table_names())
                
        except Exception as e:
            health_status["status"] = "unhealthy"
            health_status["error"] = str(e)
        
        return health_status
    
    def execute_query(self, query: str, params: tuple = ()) -> int:
        """Execute a query and return the number of affected rows."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            # トランザクション外の場合のみコミット
            if not self._in_transaction:
                conn.commit()
            return cursor.rowcount
    
    def fetch_one(self, query: str, params: tuple = ()) -> Optional[tuple]:
        """Fetch one row from a query."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchone()
    
    def fetch_all(self, query: str, params: tuple = ()) -> List[tuple]:
        """Fetch all rows from a query."""
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return cursor.fetchall()
    
    def cleanup_temporary_files(self):
        """Clean up temporary files."""
        try:
            with self.transaction() as conn:
                # Get temporary files to clean up
                cursor = conn.execute(
                    "SELECT file_path FROM project_files WHERE is_temporary = 1"
                )
                temp_files = [row[0] for row in cursor.fetchall()]
                
                # Delete physical files
                deleted_count = 0
                for file_path in temp_files:
                    try:
                        if Path(file_path).exists():
                            Path(file_path).unlink()
                            deleted_count += 1
                    except:
                        pass  # Ignore individual file deletion errors
                
                # Remove database records
                conn.execute("DELETE FROM project_files WHERE is_temporary = 1")
                
                self.logger.info(f"Cleaned up {deleted_count} temporary files")
                
        except Exception as e:
            self.logger.error(f"Temp file cleanup failed: {str(e)}")
    
    def close(self):
        """Explicit close method for cleanup."""
        self.close_connection()
    
    def __del__(self):
        """Cleanup when DatabaseManager is destroyed."""
        if hasattr(self, '_connection') and self._connection:
            self._connection.close()
