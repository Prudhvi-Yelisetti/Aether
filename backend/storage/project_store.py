from db.database import conn, cursor


def create_project(name: str):
    try:
        cursor.execute(
            "INSERT INTO projects (name) VALUES (?)",
            (name,)
        )
        conn.commit()
        return cursor.lastrowid
    except:
        return None


def get_projects():
    cursor.execute("SELECT * FROM projects")
    projects = cursor.fetchall()

    result = {}

    for proj in projects:
        project_id = str(proj[0])
        result[project_id] = {
            "name": proj[1],
            "chats": []
        }

        # fetch chats for this project
        cursor.execute(
            "SELECT prompt, response, model FROM chats WHERE project_id=?",
            (project_id,)
        )
        chats = cursor.fetchall()

        for chat in chats:
            result[project_id]["chats"].append({
                "prompt": chat[0],
                "response": chat[1],
                "model": chat[2]
            })

    return result

def get_project_chats(project_id: str):
    cursor.execute(
        "SELECT DISTINCT chat_id FROM chats WHERE project_id=?",
        (project_id,)
    )
    return [row[0] for row in cursor.fetchall()]

def create_chat(project_id: str):
    cursor.execute(
        "SELECT MAX(chat_id) FROM chats WHERE project_id=?",
        (project_id,)
    )
    last = cursor.fetchone()[0]
    new_chat_id = (last + 1) if last else 1
    return new_chat_id

def add_chat(project_id: str, chat_id: int, chat: dict):
    cursor.execute(
        "INSERT INTO chats (project_id, chat_id, prompt, response, model) VALUES (?, ?, ?, ?, ?)",
        (project_id, chat_id, chat["prompt"], chat["response"], chat["model"])
    )
    conn.commit()

def project_exists(project_id: str) -> bool:
    cursor.execute("SELECT 1 FROM projects WHERE id=?", (project_id,))
    return cursor.fetchone() is not None

def save_memory(project_id: str, key: str, value: str):
    cursor.execute(
        "INSERT INTO memory (project_id, key, value) VALUES (?, ?, ?)",
        (project_id, key, value)
    )
    conn.commit()


def get_memory(project_id: str):
    cursor.execute(
        "SELECT key, value FROM memory WHERE project_id=?",
        (project_id,)
    )
    return cursor.fetchall()

def get_project_full_data(project_id: str):
    cursor.execute(
        """
        SELECT chat_id, prompt, response 
        FROM chats 
        WHERE project_id=? 
        ORDER BY id ASC
        """,
        (project_id,)
    )

    rows = cursor.fetchall()

    chats = {}

    for chat_id, prompt, response in rows:
        if chat_id not in chats:
            chats[chat_id] = []

        chats[chat_id].append({
            "prompt": prompt,
            "response": response
        })

    return chats

def get_chat_history(project_id: str, chat_id: int, limit: int = 10):
    cursor.execute(
        """
        SELECT prompt, response 
        FROM chats 
        WHERE project_id=? AND chat_id=? 
        ORDER BY id DESC 
        LIMIT ?
        """,
        (project_id, chat_id, limit)
    )
    return cursor.fetchall()[::-1]