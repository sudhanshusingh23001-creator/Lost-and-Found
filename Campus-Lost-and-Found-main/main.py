from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, Response
from pydantic import BaseModel
from typing import Optional
import sqlite3
from datetime import datetime
import os

app = FastAPI(title="KhoyaPaaya - Campus Lost & Found")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = "lost_found.db"

ADMIN_DATA = {
    "CS/IT": {
        "office_location": "CS/IT HOD Office, 2nd Floor",
        "contact_number": "+91 98765 43210 (Mr. Negi)",
        "timings": "9:00 AM - 5:00 PM"
    },
    "Chanakya": {
        "office_location": "Ground Floor Reception, Chanakya Block",
        "contact_number": "+91 98765 43211 (Ms. Sharma)",
        "timings": "9:30 AM - 4:30 PM"
    },
    "KP Nautiyal": {
        "office_location": "Administrative Block, Room 102",
        "contact_number": "+91 98765 43212 (Mr. Bisht)",
        "timings": "10:00 AM - 5:00 PM"
    },
    "BTech": {
        "office_location": "B.Tech Admin Office, Block A",
        "contact_number": "+91 98765 43213 (Mr. Rawat)",
        "timings": "9:00 AM - 5:30 PM"
    },
    "Paramedical": {
        "office_location": "Paramedical Staff Room, 1st Floor",
        "contact_number": "+91 98765 43214 (Dr. Verma)",
        "timings": "9:00 AM - 4:00 PM"
    },
    "Mechanical": {
        "office_location": "Mechanical HOD Office, 2nd Floor",
        "contact_number": "+91 98765 43215 (Mr. Gupta)",
        "timings": "9:00 AM - 5:00 PM"
    }
}

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name       TEXT NOT NULL,
            category        TEXT NOT NULL,
            description     TEXT NOT NULL,
            location        TEXT NOT NULL,
            date_reported   TEXT NOT NULL,
            status          TEXT NOT NULL DEFAULT 'active',
            reporter_name   TEXT NOT NULL,
            reporter_contact TEXT NOT NULL,
            item_type       TEXT NOT NULL,
            flags           INTEGER DEFAULT 0,
            reporter_ip     TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS item_flags (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id     INTEGER NOT NULL,
            reporter_ip TEXT NOT NULL,
            UNIQUE(item_id, reporter_ip)
        )
    """)
    conn.commit()
    conn.close()

init_db()

class Item(BaseModel):
    item_name:        str
    category:         str
    description:      str
    location:         str
    reporter_name:    str
    reporter_contact: str
    item_type:        str          
    date_reported:    Optional[str] = None

class ItemUpdate(BaseModel):
    status: str     

def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Suppress browser favicon 404 noise."""
    return Response(status_code=204)

@app.get("/", response_class=HTMLResponse)
async def read_root():
    html_path = os.path.join(BASE_DIR, "templates", "index_1.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(content=f.read())

@app.get("/style1.css")
async def serve_css():
    return FileResponse(os.path.join(BASE_DIR, "static", "css", "style1.css"), media_type="text/css")

@app.get("/script.js")
async def serve_js():
    return FileResponse(
        os.path.join(BASE_DIR, "static", "js", "script.js"),
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/admin/{block_name:path}")
async def get_admin_info(block_name: str):
    """Return contact details for a specific campus block."""
    admin_info = ADMIN_DATA.get(block_name)
    if not admin_info:
        raise HTTPException(status_code=404, detail="Admin details not found for this block")
    return admin_info

def cleanup_old_items():
    """Automatically delete active items older than 7 days."""
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM items WHERE status = 'active' AND date_reported < datetime('now', '-7 days')")
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Cleanup Error: {e}")

@app.post("/api/items", status_code=201)
async def create_item(item: Item, request: Request):
    client_ip = request.client.host
    try:
        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT 1 FROM items 
            WHERE reporter_ip = ? 
            AND date_reported > datetime('now', '-5 minutes')
        """, (client_ip,))
        
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait 5 minutes between reports.")

        cleanup_old_items()

        date_reported = item.date_reported or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO items
                (item_name, category, description, location,
                 date_reported, status, reporter_name, reporter_contact, item_type, reporter_ip)
            VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """, (
            item.item_name, item.category, item.description, item.location,
            date_reported, item.reporter_name, item.reporter_contact, item.item_type, client_ip
        ))
        conn.commit()
        item_id = cursor.lastrowid
        conn.close()
        return {"message": "Item created successfully", "id": item_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/items/{item_id}/flag")
async def flag_item(item_id: int, request: Request):
    """Increment flag count and delete if it reaches 3, ensuring one flag per IP."""
    client_ip = request.client.host
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM item_flags WHERE item_id = ? AND reporter_ip = ?", (item_id, client_ip))
        if cursor.fetchone():
            conn.close()
            raise HTTPException(status_code=400, detail="You have already flagged this item.")
            
        cursor.execute("INSERT INTO item_flags (item_id, reporter_ip) VALUES (?, ?)", (item_id, client_ip))
        
        cursor.execute("UPDATE items SET flags = flags + 1 WHERE id = ?", (item_id,))
        
        cursor.execute("SELECT flags FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        
        if row and row['flags'] >= 3:
            cursor.execute("DELETE FROM item_flags WHERE item_id = ?", (item_id,))
            cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
            conn.commit()
            conn.close()
            return {"message": "Item deleted due to multiple flags", "deleted": True}
        
        conn.commit()
        conn.close()
        return {"message": "Item flagged successfully", "deleted": False}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/items")
async def get_items(
    item_type: Optional[str] = None,
    category:  Optional[str] = None,
    status:    Optional[str] = None,
    search:    Optional[str] = None
):
    try:
        cleanup_old_items()
        
        conn = get_db()
        cursor = conn.cursor()
        query  = "SELECT * FROM items WHERE 1=1"
        params = []

        if item_type:
            query += " AND item_type = ?"
            params.append(item_type)
        if category:
            query += " AND category = ?"
            params.append(category)
        if status:
            query += " AND status = ?"
            params.append(status)
        if search:
            query += " AND (item_name LIKE ? OR description LIKE ? OR location LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%", f"%{search}%"])

        query += " ORDER BY date_reported DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/items/{item_id}")
async def get_item(item_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM items WHERE id = ?", (item_id,))
        row = cursor.fetchone()
        conn.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Item not found")
        return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/items/{item_id}")
async def update_item_status(item_id: int, item_update: ItemUpdate):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Item not found")
        cursor.execute("UPDATE items SET status = ? WHERE id = ?", (item_update.status, item_id))
        conn.commit()
        conn.close()
        return {"message": "Item status updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/items/{item_id}")
async def delete_item(item_id: int):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM items WHERE id = ?", (item_id,))
        if cursor.fetchone() is None:
            conn.close()
            raise HTTPException(status_code=404, detail="Item not found")
        cursor.execute("DELETE FROM items WHERE id = ?", (item_id,))
        conn.commit()
        conn.close()
        return {"message": "Item deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/stats")
async def get_stats():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM items WHERE item_type='lost' AND status='active'")
        active_lost = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM items WHERE item_type='found' AND status='active'")
        active_found = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM items WHERE status IN ('resolved', 'claimed')")
        resolved = cursor.fetchone()[0]
        conn.close()
        return {
            "active_lost":  active_lost,
            "active_found": active_found,
            "resolved":     resolved
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)