"""
Local CLI Chatbot for AI Dota 2 Tracker.
Allows interacting with the LangChain SQL Agent directly from the terminal.
Usage:
    python bot.py
"""
import sys
import asyncio
from app.services.chatbot import get_chat_response

async def chat_loop():
    print("=" * 60)
    print("AI Dota 2 Tracker - Interactive Terminal Chatbot")
    print("Type your questions below (or type 'exit' / 'quit' to stop).")
    print("=" * 60 + "\n")

    while True:
        try:
            user_input = input("You: ").strip()
            if user_input.lower() in ["exit", "quit"]:
                print("Goodbye!")
                break

            if not user_input:
                continue

            print("Bot is thinking...\n")
            reply = await get_chat_response(user_input)
            print("-" * 60)
            print(f"Bot: {reply}")
            print("-" * 60 + "\n")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"\nAn error occurred: {e}\n")

if __name__ == "__main__":
    asyncio.run(chat_loop())
