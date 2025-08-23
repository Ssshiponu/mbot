import os
from .models import SeytemPrompt

def get_prompt():
    prompt = ""
    prompt_parts = []
    prompts_dir = os.path.join(os.path.dirname(__file__), "..", "prompts")
    prompts_dir = os.path.abspath(prompts_dir)
    p = SeytemPrompt.objects.first()
    
    try:
        if p:
            prompt = f'{p.base_prompt}\n\n{p.custom_instructions}\n\n{p.custom_data}'
        elif prompts_dir and prompt:
            for file in sorted(os.listdir(prompts_dir)):
                if file.endswith(".txt"):
                    file_path = os.path.join(prompts_dir, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        prompt_parts.append(f.read().strip())

            if not prompt_parts:
                raise Exception("No prompt files found in the prompts directory")

            prompt = "\n\n".join(prompt_parts)
    except Exception as e:
        print(f"Error reading prompt files: {e}")
        prompt = (
            "You are an AI customer service assistant for a Facebook page business. "
            "Your prompts may not be set up yet."
        )

    return prompt