from db.database import conn, cursor


def create_project(name: str):
    cursor.execute("INSERT INTO projects (name) VALUES (?)", (name,))
    conn.commit()
    return str(cursor.lastrowid)


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


def add_chat(project_id: str, chat: dict):
    cursor.execute(
        "INSERT INTO chats (project_id, prompt, response, model) VALUES (?, ?, ?, ?)",
        (project_id, chat["prompt"], chat["response"], chat["model"])
    )
    conn.commit()

def project_exists(project_id: str) -> bool:
    cursor.execute("SELECT 1 FROM projects WHERE id=?", (project_id,))
    return cursor.fetchone() is not None

def get_chat_history(project_id: str, limit: int = 10):
    cursor.execute(
        """
        SELECT prompt, response 
        FROM chats 
        WHERE project_id=? 
        ORDER BY id DESC 
        LIMIT ?
        """,
        (project_id, limit)
    )
    
    history = cursor.fetchall()
    
    # reverse to maintain order
    return history[::-1]