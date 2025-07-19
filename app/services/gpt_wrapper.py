# gpt_wrapper.py
import os
from dotenv import load_dotenv
import openai

load_dotenv()

OPENAI_API_KEY = os.getenv("OPEN_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPEN_API_KEY not set in environment")

client = openai.OpenAI(api_key=OPENAI_API_KEY)

def gpt_completion(prompt, model="gpt-3.5-turbo-0125", max_tokens=256, temperature=0.7):
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=max_tokens,
        temperature=temperature,
    )
    message = response.choices[0].message.content.strip()
    usage = response.usage
    total_tokens = usage.total_tokens
    prompt_tokens = usage.prompt_tokens
    completion_tokens = usage.completion_tokens

    # Optional cost estimate
    COST_PER_1K_INPUT = {
        "gpt-3.5-turbo-0125": 0.0005,
    }
    COST_PER_1K_OUTPUT = {
        "gpt-3.5-turbo-0125": 0.0015,
    }
    input_cost = (prompt_tokens / 1000) * COST_PER_1K_INPUT.get(model, 0.001)
    output_cost = (completion_tokens / 1000) * COST_PER_1K_OUTPUT.get(model, 0.002)
    estimated_cost = input_cost + output_cost

    print(f"\n--- GPT Call Summary ---")
    print(f"Prompt Tokens: {prompt_tokens}")
    print(f"Completion Tokens: {completion_tokens}")
    print(f"Total Tokens: {total_tokens}")
    print(f"Estimated Cost: ${estimated_cost:.6f}")
    print(f"Model Used: {model}\n")

    return message
