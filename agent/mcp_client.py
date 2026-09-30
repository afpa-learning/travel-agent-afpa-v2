import asyncio
import threading
from agent.orchestrator import MCPSession, run_turn
from groq import AsyncGroq

class MCPClientManager:
    def __init__(self, groq_api_key):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._session = None
        self._groq_client = None
        self._groq_api_key = groq_api_key
        self._lock = threading.Lock()

    def _run_loop(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def _run_coro(self, coro, timeout=60):
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    def get_session(self):
        with self._lock:
            if self._session is None:
                self._session = self._run_coro(MCPSession().start())
        return self._session

    def get_groq_client(self):
        # AsyncGroq doit être instancié dans la même boucle que celle
        # qui exécutera ses appels réseau (httpx.AsyncClient sous le capot)
        with self._lock:
            if self._groq_client is None:
                async def _make():
                    return AsyncGroq(api_key=self._groq_api_key)
                self._groq_client = self._run_coro(_make())
        return self._groq_client

    def call(self, coro_factory, timeout=60):
        """coro_factory: callable(session, groq_client) -> coroutine"""
        session = self.get_session()
        groq_client = self.get_groq_client()
        return self._run_coro(coro_factory(session, groq_client), timeout=timeout)

    def shutdown(self):
        if self._session is not None:
            self._run_coro(self._session.close())
        self._loop.call_soon_threadsafe(self._loop.stop)