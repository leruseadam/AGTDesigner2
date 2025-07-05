import sqlite3
import json
import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import pandas as pd
from pathlib import Path
from functools import lru_cache
import threading

logger = logging.getLogger(__name__)

# Performance optimization: disable debug logging in production
DEBUG_ENABLED = False

def timed_operation(operation_name):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                return func(self, *args, **kwargs)
            finally:
                elapsed = time.time() - start_time
                # You can log or store timing here if you want
                if elapsed > 0.1:
                    logger.warning(f"⏱️  {operation_name}: {elapsed:.3f}s")
        return wrapper
    return decorator

class ProductDatabase:
    """Database for storing and managing product and strain information."""
    
    def __init__(self, db_path: str = "product_database.db"):
        self.db_path = db_path
        self._connection_pool = {}
        self._cache = {}
        self._cache_lock = threading.Lock()
        self._initialized = False
        self._init_lock = threading.Lock()
        
        # Performance timing
        self._timing_stats = {
            'queries': 0,
            'total_time': 0.0,
            'cache_hits': 0,
            'cache_misses': 0
        }
    
    def _get_connection(self):
        """Get a database connection, reusing if possible."""
        thread_id = threading.get_ident()
        if thread_id not in self._connection_pool:
            self._connection_pool[thread_id] = sqlite3.connect(self.db_path)
        return self._connection_pool[thread_id]
    
    def init_database(self):
        """Initialize the database with required tables (lazy initialization)."""
        if self._initialized:
            return
            
        with self._init_lock:
            if self._initialized:  # Double-check pattern
                return
                
            start_time = time.time()
            logger.info("Initializing product database...")
            
            try:
                conn = self._get_connection()
                cursor = conn.cursor()
                
                # Create strains table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS strains (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strain_name TEXT UNIQUE NOT NULL,
                        normalized_name TEXT NOT NULL,
                        canonical_lineage TEXT,
                        first_seen_date TEXT NOT NULL,
                        last_seen_date TEXT NOT NULL,
                        total_occurrences INTEGER DEFAULT 1,
                        lineage_confidence REAL DEFAULT 0.0,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                ''')
                
                # Create products table
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS products (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        product_name TEXT NOT NULL,
                        normalized_name TEXT NOT NULL,
                        strain_id INTEGER,
                        product_type TEXT NOT NULL,
                        vendor TEXT,
                        brand TEXT,
                        description TEXT,
                        weight TEXT,
                        units TEXT,
                        price TEXT,
                        lineage TEXT,
                        first_seen_date TEXT NOT NULL,
                        last_seen_date TEXT NOT NULL,
                        total_occurrences INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        FOREIGN KEY (strain_id) REFERENCES strains (id),
                        UNIQUE(product_name, vendor, brand)
                    )
                ''')
                
                # Create lineage_history table for tracking lineage changes
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS lineage_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strain_id INTEGER,
                        old_lineage TEXT,
                        new_lineage TEXT,
                        change_date TEXT NOT NULL,
                        change_reason TEXT,
                        FOREIGN KEY (strain_id) REFERENCES strains (id)
                    )
                ''')
                
                # Create strain-brand lineage overrides
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS strain_brand_lineage (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        strain_name TEXT NOT NULL,
                        brand TEXT NOT NULL,
                        lineage TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(strain_name, brand)
                    )
                ''')
                
                # Create indexes for better performance
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_strains_normalized ON strains(normalized_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_normalized ON products(normalized_name)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_strain ON products(strain_id)')
                cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_vendor_brand ON products(vendor, brand)')
                
                conn.commit()
                self._initialized = True
                
                elapsed = time.time() - start_time
                logger.info(f"Product database initialized successfully in {elapsed:.3f}s")
                
            except Exception as e:
                logger.error(f"Error initializing database: {e}")
                raise
    
    def _get_cache_key(self, operation: str, *args) -> str:
        """Generate a cache key for the given operation and arguments."""
        return f"{operation}:{hash(str(args))}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """Get value from cache with thread safety."""
        with self._cache_lock:
            if cache_key in self._cache:
                self._timing_stats['cache_hits'] += 1
                return self._cache[cache_key]
            self._timing_stats['cache_misses'] += 1
            return None
    
    def _set_cache(self, cache_key: str, value: Any, ttl: int = 300):
        """Set value in cache with thread safety and TTL."""
        with self._cache_lock:
            self._cache[cache_key] = {
                'value': value,
                'expires': time.time() + ttl
            }
    
    def _clean_expired_cache(self):
        """Remove expired cache entries."""
        current_time = time.time()
        with self._cache_lock:
            expired_keys = [
                key for key, data in self._cache.items()
                if data['expires'] < current_time
            ]
            for key in expired_keys:
                del self._cache[key]
    
    @timed_operation("add_or_update_strain")
    def add_or_update_strain(self, strain_name: str, lineage: str = None) -> int:
        """Add a new strain or update existing strain information."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            normalized_name = self._normalize_strain_name(strain_name)
            current_date = datetime.now().isoformat()
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if strain exists
            cursor.execute('''
                SELECT id, canonical_lineage, total_occurrences, lineage_confidence
                FROM strains 
                WHERE normalized_name = ?
            ''', (normalized_name,))
            
            existing = cursor.fetchone()
            
            if existing:
                strain_id, existing_lineage, occurrences, confidence = existing
                
                # Update existing strain
                new_occurrences = occurrences + 1
                
                # Update lineage if provided and different
                if lineage and lineage != existing_lineage:
                    # Log lineage change
                    cursor.execute('''
                        INSERT INTO lineage_history (strain_id, old_lineage, new_lineage, change_date, change_reason)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (strain_id, existing_lineage, lineage, current_date, 'New data upload'))
                    
                    # Update strain with new lineage
                    cursor.execute('''
                        UPDATE strains 
                        SET canonical_lineage = ?, total_occurrences = ?, last_seen_date = ?, updated_at = ?
                        WHERE id = ?
                    ''', (lineage, new_occurrences, current_date, current_date, strain_id))
                    
                    if DEBUG_ENABLED:
                        logger.debug(f"Updated strain '{strain_name}' lineage from '{existing_lineage}' to '{lineage}'")
                else:
                    # Just update occurrence count
                    cursor.execute('''
                        UPDATE strains 
                        SET total_occurrences = ?, last_seen_date = ?, updated_at = ?
                        WHERE id = ?
                    ''', (new_occurrences, current_date, current_date, strain_id))
                
                conn.commit()
                
                # Invalidate cache for this strain
                cache_key = self._get_cache_key("strain_info", normalized_name)
                with self._cache_lock:
                    if cache_key in self._cache:
                        del self._cache[cache_key]
                
                return strain_id
            else:
                # Add new strain
                cursor.execute('''
                    INSERT INTO strains (strain_name, normalized_name, canonical_lineage, first_seen_date, last_seen_date, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (strain_name, normalized_name, lineage, current_date, current_date, current_date, current_date))
                
                strain_id = cursor.lastrowid
                conn.commit()
                if DEBUG_ENABLED:
                    logger.debug(f"Added new strain '{strain_name}' with lineage '{lineage}'")
                return strain_id
                
        except Exception as e:
            logger.error(f"Error adding/updating strain '{strain_name}': {e}")
            raise
    
    @timed_operation("add_or_update_product")
    def add_or_update_product(self, product_data: Dict[str, Any]) -> int:
        """Add a new product or update existing product information."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            product_name = product_data.get('ProductName', '')
            normalized_name = self._normalize_product_name(product_name)
            current_date = datetime.now().isoformat()
            
            # Get or create strain
            strain_name = product_data.get('Product Strain', '')
            strain_id = None
            if strain_name:
                strain_id = self.add_or_update_strain(strain_name, product_data.get('Lineage'))
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Check if product exists (based on name, vendor, brand combination)
            cursor.execute('''
                SELECT id, total_occurrences
                FROM products 
                WHERE normalized_name = ? AND vendor = ? AND brand = ?
            ''', (normalized_name, product_data.get('Vendor'), product_data.get('Product Brand')))
            
            existing = cursor.fetchone()
            
            if existing:
                product_id, occurrences = existing
                
                # Update existing product
                new_occurrences = occurrences + 1
                cursor.execute('''
                    UPDATE products 
                    SET total_occurrences = ?, last_seen_date = ?, updated_at = ?
                    WHERE id = ?
                ''', (new_occurrences, current_date, current_date, product_id))
                
                conn.commit()
                return product_id
            else:
                # Add new product
                cursor.execute('''
                    INSERT INTO products (
                        product_name, normalized_name, strain_id, product_type, vendor, brand,
                        description, weight, units, price, lineage, first_seen_date, last_seen_date, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    product_name, normalized_name, strain_id, product_data.get('Product Type*'),
                    product_data.get('Vendor'), product_data.get('Product Brand'),
                    product_data.get('Description'), product_data.get('Weight*'),
                    product_data.get('Units'), product_data.get('Price'),
                    product_data.get('Lineage'), current_date, current_date, current_date, current_date
                ))
                
                product_id = cursor.lastrowid
                conn.commit()
                if DEBUG_ENABLED:
                    logger.debug(f"Added new product '{product_name}'")
                return product_id
                
        except Exception as e:
            logger.error(f"Error adding/updating product '{product_data.get('ProductName', '')}': {e}")
            raise
    
    @timed_operation("get_strain_info")
    def get_strain_info(self, strain_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific strain (with caching)."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            normalized_name = self._normalize_strain_name(strain_name)
            cache_key = self._get_cache_key("strain_info", normalized_name)
            
            # Check cache first
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT id, strain_name, canonical_lineage, total_occurrences, lineage_confidence, first_seen_date, last_seen_date
                FROM strains 
                WHERE normalized_name = ?
            ''', (normalized_name,))
            
            result = cursor.fetchone()
            if result:
                strain_info = {
                    'id': result[0],
                    'strain_name': result[1],
                    'canonical_lineage': result[2],
                    'total_occurrences': result[3],
                    'lineage_confidence': result[4],
                    'first_seen_date': result[5],
                    'last_seen_date': result[6]
                }
                
                # Cache the result for 5 minutes
                self._set_cache(cache_key, strain_info, ttl=300)
                return strain_info
            return None
            
        except Exception as e:
            logger.error(f"Error getting strain info for '{strain_name}': {e}")
            return None
    
    @timed_operation("get_product_info")
    def get_product_info(self, product_name: str, vendor: str = None, brand: str = None) -> Optional[Dict[str, Any]]:
        """Get information about a specific product (with caching)."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            normalized_name = self._normalize_product_name(product_name)
            cache_key = self._get_cache_key("product_info", normalized_name, vendor, brand)
            
            # Check cache first
            cached_result = self._get_from_cache(cache_key)
            if cached_result is not None:
                return cached_result
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            if vendor and brand:
                cursor.execute('''
                    SELECT p.id, p.product_name, p.product_type, p.vendor, p.brand, p.lineage,
                           s.strain_name, s.canonical_lineage, p.total_occurrences, p.first_seen_date, p.last_seen_date
                    FROM products p
                    LEFT JOIN strains s ON p.strain_id = s.id
                    WHERE p.normalized_name = ? AND p.vendor = ? AND p.brand = ?
                ''', (normalized_name, vendor, brand))
            else:
                cursor.execute('''
                    SELECT p.id, p.product_name, p.product_type, p.vendor, p.brand, p.lineage,
                           s.strain_name, s.canonical_lineage, p.total_occurrences, p.first_seen_date, p.last_seen_date
                    FROM products p
                    LEFT JOIN strains s ON p.strain_id = s.id
                    WHERE p.normalized_name = ?
                ''', (normalized_name,))
            
            result = cursor.fetchone()
            if result:
                product_info = {
                    'id': result[0],
                    'product_name': result[1],
                    'product_type': result[2],
                    'vendor': result[3],
                    'brand': result[4],
                    'lineage': result[5],
                    'strain_name': result[6],
                    'canonical_lineage': result[7],
                    'total_occurrences': result[8],
                    'first_seen_date': result[9],
                    'last_seen_date': result[10]
                }
                
                # Cache the result for 5 minutes
                self._set_cache(cache_key, product_info, ttl=300)
                return product_info
            return None
            
        except Exception as e:
            logger.error(f"Error getting product info for '{product_name}': {e}")
            return None
    
    def validate_and_suggest_lineage(self, strain_name: str, proposed_lineage: str = None) -> Dict[str, Any]:
        """Validate strain lineage against database and suggest corrections."""
        try:
            strain_info = self.get_strain_info(strain_name)
            
            if not strain_info:
                return {
                    'valid': True,
                    'suggestion': proposed_lineage,
                    'confidence': 0.0,
                    'reason': 'New strain'
                }
            
            canonical_lineage = strain_info['canonical_lineage']
            occurrences = strain_info['total_occurrences']
            
            if not canonical_lineage:
                return {
                    'valid': True,
                    'suggestion': proposed_lineage,
                    'confidence': 0.0,
                    'reason': 'Strain exists but no lineage recorded'
                }
            
            # Calculate confidence based on occurrences
            confidence = min(occurrences / 10.0, 1.0)  # Max confidence at 10+ occurrences
            
            if proposed_lineage == canonical_lineage:
                return {
                    'valid': True,
                    'suggestion': canonical_lineage,
                    'confidence': confidence,
                    'reason': 'Matches database'
                }
            elif proposed_lineage:
                return {
                    'valid': False,
                    'suggestion': canonical_lineage,
                    'confidence': confidence,
                    'reason': f'Database suggests {canonical_lineage} (seen {occurrences} times)'
                }
            else:
                return {
                    'valid': True,
                    'suggestion': canonical_lineage,
                    'confidence': confidence,
                    'reason': f'Database suggests {canonical_lineage} (seen {occurrences} times)'
                }
                
        except Exception as e:
            logger.error(f"Error validating lineage for '{strain_name}': {e}")
            return {
                'valid': True,
                'suggestion': proposed_lineage,
                'confidence': 0.0,
                'reason': 'Error occurred during validation'
            }
    
    @timed_operation("get_strain_statistics")
    def get_strain_statistics(self) -> Dict[str, Any]:
        """Get statistics about strains in the database, excluding MIXED, CBD Blend, and Paraphernalia from stats."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Total strains
            cursor.execute('SELECT COUNT(*) FROM strains')
            total_strains = cursor.fetchone()[0]
            
            # Strains by lineage (exclude unwanted)
            cursor.execute('''
                SELECT canonical_lineage, COUNT(*) 
                FROM strains 
                WHERE canonical_lineage IS NOT NULL 
                GROUP BY canonical_lineage
            ''')
            lineage_counts = dict(cursor.fetchall())
            # Exclude unwanted
            exclude_keys = {k.lower() for k in ['MIXED', 'CBD Blend', 'Paraphernalia']}
            lineage_counts = {k: v for k, v in lineage_counts.items() if k and k.strip().lower() not in exclude_keys}
            
            # Most common strains (exclude unwanted)
            cursor.execute('''
                SELECT strain_name, total_occurrences, canonical_lineage
                FROM strains 
                ORDER BY total_occurrences DESC 
                LIMIT 50
            ''')
            top_strains_raw = cursor.fetchall()
            top_strains = [
                {'name': name, 'occurrences': count}
                for name, count, lineage in top_strains_raw
                if lineage and lineage.strip().lower() not in exclude_keys and name and name.strip().lower() not in exclude_keys
            ][:10]
            
            # Total products
            cursor.execute('SELECT COUNT(*) FROM products')
            total_products = cursor.fetchone()[0]
            
            return {
                'total_strains': total_strains,
                'total_products': total_products,
                'lineage_distribution': lineage_counts,
                'top_strains': top_strains
            }
            
        except Exception as e:
            logger.error(f"Error getting strain statistics: {e}")
            return {}
    
    def export_database(self, output_path: str):
        """Export database to Excel file."""
        try:
            self.init_database()  # Ensure DB is initialized
            
            conn = self._get_connection()
            
            # Export strains
            strains_df = pd.read_sql_query('''
                SELECT strain_name, canonical_lineage, total_occurrences, first_seen_date, last_seen_date
                FROM strains
                ORDER BY total_occurrences DESC
            ''', conn)
            
            # Export products
            products_df = pd.read_sql_query('''
                SELECT p.product_name, p.product_type, p.vendor, p.brand, p.lineage,
                       s.strain_name, p.total_occurrences, p.first_seen_date, p.last_seen_date
                FROM products p
                LEFT JOIN strains s ON p.strain_id = s.id
                ORDER BY p.total_occurrences DESC
            ''', conn)
            
            # Export to Excel
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                strains_df.to_excel(writer, sheet_name='Strains', index=False)
                products_df.to_excel(writer, sheet_name='Products', index=False)
            
            logger.info(f"Database exported to {output_path}")
            
        except Exception as e:
            logger.error(f"Error exporting database: {e}")
            raise
    
    def get_performance_stats(self) -> Dict[str, Any]:
        """Get performance statistics for the database."""
        self._clean_expired_cache()
        return {
            'total_queries': self._timing_stats['queries'],
            'total_time': self._timing_stats['total_time'],
            'average_time': self._timing_stats['total_time'] / max(self._timing_stats['queries'], 1),
            'cache_hits': self._timing_stats['cache_hits'],
            'cache_misses': self._timing_stats['cache_misses'],
            'cache_hit_rate': self._timing_stats['cache_hits'] / max(self._timing_stats['cache_hits'] + self._timing_stats['cache_misses'], 1),
            'cache_size': len(self._cache),
            'initialized': self._initialized
        }
    
    def clear_cache(self):
        """Clear the cache."""
        with self._cache_lock:
            self._cache.clear()
        self._timing_stats['cache_hits'] = 0
        self._timing_stats['cache_misses'] = 0
    
    def close_connections(self):
        """Close all database connections."""
        for conn in self._connection_pool.values():
            conn.close()
        self._connection_pool.clear()
    
    def _normalize_strain_name(self, strain_name: str) -> str:
        """Normalize strain name for consistent matching."""
        if not isinstance(strain_name, str):
            return ""
        
        # Use the existing normalization function
        from .excel_processor import normalize_strain_name
        return normalize_strain_name(strain_name)
    
    def _normalize_product_name(self, product_name: str) -> str:
        """Normalize product name for consistent matching."""
        if not isinstance(product_name, str):
            return ""
        
        # Use the existing normalization function
        from .excel_processor import normalize_name
        return normalize_name(product_name)
    
    def upsert_strain_brand_lineage(self, strain_name: str, brand: str, lineage: str):
        """Insert or update lineage for a (strain_name, brand) pair."""
        try:
            self.init_database()
            conn = self._get_connection()
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            cursor.execute('''
                INSERT INTO strain_brand_lineage (strain_name, brand, lineage, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(strain_name, brand) DO UPDATE SET lineage=excluded.lineage, updated_at=excluded.updated_at
            ''', (strain_name, brand, lineage, now, now))
            conn.commit()
            logger.info(f"Upserted lineage for ({strain_name}, {brand}) -> {lineage}")
        except Exception as e:
            logger.error(f"Error upserting strain_brand_lineage: {e}")
            raise 