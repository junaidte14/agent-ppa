from typing import Any
from agent import run_agent_turn
from litellm_adapter import LiteLLMAdapter
from llm_interface import LLMClient
from prompts import SYSTEM_PROMPT

def main():

    print("=" * 55)
    print("     MY FIRST TOOL-USING AI AGENT    ")
    print("=" * 55)

    llm: LLMClient = LiteLLMAdapter()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    print("\n Agent is ready!")
    print("Type /exit to quit.")
    print("Type /reset to clear the messages history.")

    while True:
        user_input = input("\n You: ").strip()
        if not user_input:
            continue

        if user_input.lower() == "/exit":
            print("\n Good bye!")
            break

        if user_input.lower() == "/reset":
            messages = [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                }
            ]
            print("\nConversation history is cleared")
            continue

        #saving the history length
        previous_history_length = len(messages)

        messages.append({
            "role": "user",
            "content": user_input
        })

        try:

            answer = run_agent_turn(llm=llm, messages=messages)

            print(f"\nAssistant: {answer}")

        except Exception as err:
            del messages[previous_history_length:] # remove all messages from the failed turn
            print(f"Error: {err}")

if __name__ == "__main__":
    main()
