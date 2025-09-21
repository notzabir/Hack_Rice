import sqlite3
import json
import logging

DATABASE_NAME = "video_analysis.db"

def get_db_connection():
    """Establishes a connection to the database."""
    conn = sqlite3.connect(DATABASE_NAME, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database and creates tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # User table to store user info from Auth0
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            auth0_user_id TEXT UNIQUE NOT NULL,
            email TEXT,
            name TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Videos table to store video metadata
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            twelvelabs_video_id TEXT UNIQUE,
            filename TEXT,
            status TEXT NOT NULL, -- e.g., 'processing', 'ready', 'failed'
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # Analyses table to store results like summaries, chapters, etc.
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id INTEGER NOT NULL,
            analysis_type TEXT NOT NULL, -- e.g., 'summary', 'chapters', 'highlights'
            result TEXT NOT NULL, -- Storing the result as a JSON string
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (video_id) REFERENCES videos (id),
            UNIQUE(video_id, analysis_type)
        )
    ''')

    conn.commit()
    conn.close()
    logging.info("Database initialized successfully.")

def get_or_create_user(user_info):
    """
    Finds a user by their Auth0 user_id or creates a new one.
    Returns the internal user ID.
    """
    auth0_user_id = user_info.get('sub')
    email = user_info.get('email')
    name = user_info.get('name')

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE auth0_user_id = ?", (auth0_user_id,))
    user = cursor.fetchone()

    if user:
        user_id = user['id']
    else:
        cursor.execute(
            "INSERT INTO users (auth0_user_id, email, name) VALUES (?, ?, ?)",
            (auth0_user_id, email, name)
        )
        conn.commit()
        user_id = cursor.lastrowid
    
    conn.close()
    return user_id

def add_video(user_id, filename, twelvelabs_video_id, status='processing'):
    """Adds a new video record to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO videos (user_id, filename, twelvelabs_video_id, status) VALUES (?, ?, ?, ?)",
        (user_id, filename, twelvelabs_video_id, status)
    )
    conn.commit()
    video_id = cursor.lastrowid
    conn.close()
    return video_id

def update_video_status(twelvelabs_video_id, status):
    """Updates the processing status of a video."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE videos SET status = ? WHERE twelvelabs_video_id = ?",
        (status, twelvelabs_video_id)
    )
    conn.commit()
    conn.close()

def get_user_videos(user_id):
    """Retrieves all videos for a given user."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    videos = cursor.fetchall()
    conn.close()
    return videos

def get_video_by_id(video_id):
    """Retrieves a single video by its internal ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
    video = cursor.fetchone()
    conn.close()
    return video

def save_analysis(video_id, analysis_type, result_data):
    """Saves the result of an analysis to the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    result_json = json.dumps(result_data)
    cursor.execute(
        "INSERT OR REPLACE INTO analyses (video_id, analysis_type, result) VALUES (?, ?, ?)",
        (video_id, analysis_type, result_json)
    )
    conn.commit()
    conn.close()

def get_analysis(video_id, analysis_type):
    """Retrieves a previously saved analysis result."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT result FROM analyses WHERE video_id = ? AND analysis_type = ?", (video_id, analysis_type))
    analysis = cursor.fetchone()
    conn.close()
    if analysis:
        return json.loads(analysis['result'])
    return None
