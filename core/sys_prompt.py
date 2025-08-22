import os

def get_prompt():
    prompt_parts = []
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    try:
        for file in sorted(os.listdir(prompts_dir)):
            if file.endswith(".txt"):
                file_path = os.path.join(prompts_dir, file)
                with open(file_path, "r", encoding="utf-8") as f:
                    prompt_parts.append(f.read().strip())

        if not prompt_parts:
            raise FileNotFoundError("No .txt prompt files found.")

        prompt = "\n\n".join(prompt_parts)

    except Exception as e:
        print(f"Error reading prompt files: {e}")
        prompt = (
            "You are an AI customer service assistant for a Facebook page business. "
            "Your prompts may not be set up yet."
        )

    return prompt