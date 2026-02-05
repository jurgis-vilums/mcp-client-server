import asyncio

from core import chat_once, new_history, RUNTIME


def _print_exception(e: BaseException) -> None:
    try:
        import traceback

        traceback.print_exception(e)
    except Exception:
        pass


async def main() -> None:
    print("=" * 60)
    print("🎬 [DEBUG] MCP Client Starting...")
    print("=" * 60)
    
    await RUNTIME.start()
    
    try:
        print("\n📝 [DEBUG] Creating new conversation history...")
        history = new_history()
        print(f"   History initialized with {len(history)} message(s) (system prompt)")
        print("\n" + "=" * 60)
        print("💡 Type a message and press Enter. Empty input exits.")
        print("   Try: 'Search for laptops' to see tool calls!")
        print("=" * 60 + "\n")
        
        while True:
            user_text = input("> ").strip()
            if not user_text:
                print("\n👋 [DEBUG] Empty input, exiting...")
                return
            try:
                history = await chat_once(history, user_text)
                print("\n" + "-" * 40)
                print("🤖 ASSISTANT RESPONSE:")
                print("-" * 40)
                print(history[-1].content)
                print("-" * 40 + "\n")
            except BaseExceptionGroup as eg:  # Python 3.11+
                print("ERROR: unhandled errors in a TaskGroup")
                for i, sub in enumerate(eg.exceptions, start=1):
                    print(f"\n--- sub-exception {i}/{len(eg.exceptions)} ---")
                    _print_exception(sub)
            except BaseException as e:
                _print_exception(e)
                print(f"ERROR: {e!r}")
    finally:
        await RUNTIME.aclose()

if __name__ == "__main__":
    asyncio.run(main())

