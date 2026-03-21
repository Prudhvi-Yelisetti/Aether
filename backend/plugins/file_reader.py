def read_file(prompt: str):
    try:
        # Extract file path (basic)
        parts = prompt.split()
        file_path = None

        for p in parts:
            if "." in p:  # simple detection
                file_path = p
                break

        if not file_path:
            return "No file specified"

        with open(file_path, "r") as f:
            content = f.read()

        return f"File content:\n{content[:2000]}"  # limit size

    except Exception as e:
        return f"Error reading file: {str(e)}"