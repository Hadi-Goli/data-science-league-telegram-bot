import os
from dotenv import load_dotenv

load_dotenv(override=True)
import asyncio
from telegram.ext import Application
from telegram.request import HTTPXRequest
from telegram.error import NetworkError
from bot import setup_handlers


def main():
    token = os.getenv("BOT_TOKEN")

    if not token:
        print("Error: BOT_TOKEN environment variable not set!")
        print("Please set it using: export BOT_TOKEN='your-bot-token'")
        return

    print("Starting Tehran Linux User Group Q&A Bot...")
    
    # Debug: Print proxy settings
    print(f"HTTP_PROXY: {os.getenv('HTTP_PROXY')}")
    print(f"HTTPS_PROXY: {os.getenv('HTTPS_PROXY')}")
    print(f"ALL_PROXY: {os.getenv('ALL_PROXY')}")

    use_proxy = os.getenv("TELEGRAM_USE_PROXY", "").lower() in {"1", "true", "yes"}
    if use_proxy:
        print("Proxy mode: enabled (using *_PROXY environment variables)")
    else:
        print("Proxy mode: disabled (ignoring *_PROXY environment variables)")

    def build_application(trust_env: bool) -> Application:
        """Create an Application configured with or without env-based proxies."""
        httpx_kwargs = {"trust_env": trust_env}
        request = HTTPXRequest(http_version="1.1", httpx_kwargs=httpx_kwargs)

        app = (
            Application.builder()
            .token(token)
            .request(request)
            .get_updates_request(request)
            .build()
        )
        setup_handlers(app)
        return app

    def run_bot(trust_env: bool):
        mode = "enabled" if trust_env else "disabled"
        print(f"Bot is running (proxy {mode}). Press Ctrl+C to stop.")

        # PTB binds to the current running loop; if a run fails, the loop can be closed.
        # Give each run its own fresh loop so a proxy failure won't poison the fallback run.
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            app = build_application(trust_env)
            # Prevent PTB from closing the loop so we can tidy up deterministically here.
            app.run_polling(allowed_updates=["message"], close_loop=False)
        finally:
            # Clean shutdown to avoid "Event loop is closed" on subsequent runs.
            if not loop.is_closed():
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
            asyncio.set_event_loop(None)

    try:
        run_bot(use_proxy)
    except NetworkError as err:
        print(f"Network error while contacting Telegram: {err}")
        if use_proxy:
            print("Proxy hint: ensure your proxy at *_PROXY is reachable.")
            print("Automatic fallback: retrying once without proxy...")
            run_bot(False)
        else:
            print("Hint: if you need a proxy, set TELEGRAM_USE_PROXY=1 along with *_PROXY env vars.")
            raise


if __name__ == "__main__":
    main()
