"""
Database schema and access helpers for StyleSync fashion catalog.
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "products.db")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            brand TEXT NOT NULL,
            category TEXT NOT NULL,
            color TEXT NOT NULL,
            price REAL NOT NULL,
            description TEXT,
            image_url TEXT NOT NULL,
            shopping_url TEXT NOT NULL,
            embedding TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query_image_path TEXT,
            top_category TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_all_products(category=None, color=None, min_price=None, max_price=None, sort_by=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM products WHERE 1=1"
    params = []
    
    if category and category.lower() != "all":
        query += " AND LOWER(category) = LOWER(?)"
        params.append(category)
        
    if color and color.lower() != "all":
        query += " AND LOWER(color) = LOWER(?)"
        params.append(color)
        
    if min_price is not None:
        query += " AND price >= ?"
        params.append(float(min_price))
        
    if max_price is not None:
        query += " AND price <= ?"
        params.append(float(max_price))
        
    if sort_by == "price_asc":
        query += " ORDER BY price ASC"
    elif sort_by == "price_desc":
        query += " ORDER BY price DESC"
    elif sort_by == "newest":
        query += " ORDER BY id DESC"
    else:
        query += " ORDER BY id ASC"
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    products = [dict(row) for row in rows]
    conn.close()
    return products

def get_product_by_id(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def insert_product(name, brand, category, color, price, description, image_url, shopping_url, embedding=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    emb_json = json.dumps(embedding.tolist() if hasattr(embedding, "tolist") else embedding) if embedding is not None else None
    cursor.execute("""
        INSERT INTO products (name, brand, category, color, price, description, image_url, shopping_url, embedding)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (name, brand, category, color, float(price), description, image_url, shopping_url, emb_json))
    product_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return product_id

def update_product(product_id, name, brand, category, color, price, description, image_url, shopping_url, embedding=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    if embedding is not None:
        emb_json = json.dumps(embedding.tolist() if hasattr(embedding, "tolist") else embedding)
        cursor.execute("""
            UPDATE products 
            SET name=?, brand=?, category=?, color=?, price=?, description=?, image_url=?, shopping_url=?, embedding=?
            WHERE id=?
        """, (name, brand, category, color, float(price), description, image_url, shopping_url, emb_json, product_id))
    else:
        cursor.execute("""
            UPDATE products 
            SET name=?, brand=?, category=?, color=?, price=?, description=?, image_url=?, shopping_url=?
            WHERE id=?
        """, (name, brand, category, color, float(price), description, image_url, shopping_url, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def log_search(image_path, top_category="General"):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO search_history (query_image_path, top_category) VALUES (?, ?)", (image_path, top_category))
    conn.commit()
    conn.close()

def get_recent_searches(limit=6):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM search_history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

