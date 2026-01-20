import asyncio

from chat import chat_once, new_history


def _print_exception(e: BaseException) -> None:
    try:
        import traceback

        traceback.print_exception(e)
    except Exception:
        pass


async def main() -> None:
    history = new_history()
    while True:
        user_text = input("> ").strip()
        if not user_text:
            return
        try:
            history = await chat_once(history, user_text)
            print(history[-1].content)
        except BaseExceptionGroup as eg:  # Python 3.11+
            print("ERROR: unhandled errors in a TaskGroup")
            for i, sub in enumerate(eg.exceptions, start=1):
                print(f"\n--- sub-exception {i}/{len(eg.exceptions)} ---")
                _print_exception(sub)
        except BaseException as e:
            _print_exception(e)
            print(f"ERROR: {e!r}")

if __name__ == "__main__":
    asyncio.run(main())
