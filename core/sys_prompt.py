import os
from .models import SystemPrompt


def get_prompt():
    prompt_parts = []
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)

    try:
        # Try from database
        prompts = SystemPrompt.objects.all()
        if prompts.exists():
            for prompt in prompts:
                prompt_parts.append(prompt.prompt.strip())
            return "\n\n".join(prompt_parts)

        # Try from prompts directory
        if os.path.isdir(prompts_dir):
            for file in sorted(os.listdir(prompts_dir)):
                if file.endswith(".txt"):
                    file_path = os.path.join(prompts_dir, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        prompt_parts.append(f.read().strip())

            if prompt_parts:
                return "\n\n".join(prompt_parts)

        # If no prompts found at all
        raise FileNotFoundError("No prompts found in database or prompts directory")

    except Exception as e:
        print(f"Error getting prompt: {e}")

    # Fallback
    return (
        "You are an AI customer service assistant for a Facebook page business. "
        "Your prompts may not be set up yet."
    )
