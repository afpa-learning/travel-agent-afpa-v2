"""The MCP client + Groq tool-calling agent loop.

Talking to the MCP server is a real protocol round trip, not a local function call:
MCPSession spawns server.py as a subprocess and speaks MCP over its stdin/stdout
(JSON-RPC messages). The agent loop below asks Groq for a reply, and whenever Groq
asks for a tool, that call is forwarded to the server over that same MCP session.
"""
import json
import os
from contextlib import AsyncExitStack
from datetime import date
from pathlib import Path

from groq import AsyncGroq
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

GROQ_MODEL = os.getenv("GROQ_MODEL_AGENT", "openai/gpt-oss-120b")

SYSTEM_PROMPT = """You are a helpful assistant with access to the flights, airlines and destinations \
through MCP tools. Today is {today}.

Rules:
- After a tool call, summarize what changed in one or two short sentences.
"""


class MCPSession:
    """Owns the MCP server subprocess + ClientSession, and the Groq-shaped tool list."""

    def __init__(self):
        self._stack = AsyncExitStack()
        self.session: ClientSession | None = None
        self.groq_tools: list[dict] = []
        self.mcp_tools: list = []
        self.resources: list = []
        self.prompts: list = []

    def get_project_root(self) -> Path:
        return Path(__file__).parent.parent

    def read_mcp_json(self,file_path):
        """
        Reads and parses an MCP JSON file safely.
        
        :param file_path: Path to the mcp.json file
        :return: Parsed Python dictionary or None if error
        """
        # Check if file exists
        if not os.path.isfile(file_path):
            self.last_error=f"Error: File '{file_path}' not found."
            return None

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)  # Parse JSON into Python dict
            return data
        except json.JSONDecodeError as e:
            self.last_error=f"Error: Invalid JSON format in '{file_path}': {e}"
        except Exception as e:
            self.last_error=f"Error reading '{file_path}': {e}"
        
        return None

    async def start(self):
        # env=None would only inherit a safe allowlist (not MCP_DB_PATH, etc.) - this
        # server is our own trusted code, so give it the full parent environment.
        # Absolute path + explicit cwd: the subprocess inherits the launcher's cwd, which
        # isn't necessarily this file's directory (e.g. uvicorn's --app-dir doesn't chdir).
        #server_script = str(Path(__file__).parent.parent / "serveur_mcp_local" / "server.py")
        
        root_path=str(self.get_project_root())
        data = self.read_mcp_json(str(Path(root_path) / ".vscode" / "mcp.json"))

        first_key = next(iter(data["servers"]))

        server_params = StdioServerParameters(
            command=data["servers"][first_key]["command"], args=data["servers"][first_key]["args"], env=data["servers"][first_key]["env"], cwd=root_path
        )
        read, write = await self._stack.enter_async_context(stdio_client(server_params))
        self.session = await self._stack.enter_async_context(ClientSession(read, write))
        await self.session.initialize()

        tools = await self.session.list_tools()
       
        self.mcp_tools = tools.tools
        # MCP tool schemas are already OpenAI-style JSON schema, so wrapping them for
        # Groq's function-calling API is a direct pass-through, not a translation.
        self.groq_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description or "",
                    "parameters": t.input_schema,
                },
            }
            for t in self.mcp_tools
        ]
        
        self.resources = (await self.session.list_resources()).resources
        self.prompts = (await self.session.list_prompts()).prompts
        
        return self

    async def call_tool(self, name: str, arguments: dict) -> dict:
        
        result = await self.session.call_tool(name, arguments)
        
        if result.structured_content is not None:
            content = result.structured_content
            
            # FastMCP wraps non-object returns (list, number, ...) as {"result": <value>}
            # since a JSON Schema's top level must be an object - unwrap it back.
            if list(content.keys()) == ["result"]:
                return content["result"]
            return content
        text = "".join(block.text for block in result.content if block.type == "text")
        
        try:
            
            return json.loads(text)
        except json.JSONDecodeError:
            
            return {"result": text}

    async def read_resource(self, uri: str):
        result = await self.session.read_resource(uri)
        text = result.contents[0].text
        return json.loads(text)

    async def get_prompt(self, name: str) -> str:
        result = await self.session.get_prompt(name)
        return result.messages[0].content.text

    async def close(self):
        await self._stack.aclose()


async def run_turn(mcp_session: MCPSession, groq: AsyncGroq, history: list[dict]) -> dict:
    """Run one user turn to completion (looping through however many tool calls Groq asks for).

    Returns {"reply": str, "trace": [{"tool", "arguments", "result"}, ...]}.
    """
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT.format(today=date.today().isoformat())}, *history]
    trace = []
    
    for _ in range(8):  # hard cap so a confused model can't loop forever
        response = await groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=mcp_session.groq_tools,
            tool_choice="auto",
            temperature=0,
        )
        msg = response.choices[0].message
        
        messages.append(msg.model_dump(exclude_none=True))

        if not msg.tool_calls:
            return {"reply": msg.content, "trace": trace}

        for call in msg.tool_calls:
            arguments = json.loads(call.function.arguments or "{}")
            result = await mcp_session.call_tool(call.function.name, arguments)
            trace.append({"tool": call.function.name, "arguments": arguments, "result": result})
            messages.append({
                "role": "tool",
                "tool_call_id": call.id,
                "content": json.dumps(result),
            })

    return {"reply": "I couldn't finish that in a reasonable number of steps.", "trace": trace}

async def run_analysis(mcp_session: MCPSession, groq: AsyncGroq, topic):
    
    system_prompt = (
        "Tu es un analyste. Utilise les outils disponibles pour rassembler des données "
        "pertinentes sur le sujet demandé, puis rédige un rapport structuré en Markdown "
        "(titre, sections, listes à puces, tableau si pertinent). "
        "N'hésite pas à faire plusieurs appels d'outils successifs si nécessaire avant de conclure."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Sujet d'analyse : {topic}"},
    ]

    max_steps = 20  # une analyse peut nécessiter plus d'étapes qu'une simple question
    for _ in range(max_steps):
        response = await groq.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            tools=mcp_session.groq_tools,
            tool_choice="auto",
            temperature=0,
        )

        message = response.choices[0].message

        if not message.tool_calls:
            # Le modèle a fini de rassembler les données -> rapport final
            return message.content

        messages.append({
            "role": "assistant",
            "content": message.content,
            "tool_calls": [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in message.tool_calls
            ],
        })

        for tc in message.tool_calls:
            args = json.loads(tc.function.arguments)
            try:
                result = await mcp_session.call_tool(tc.function.name, args)
                result_content = json.dumps(result, default=str)
            except Exception as e:
                result_content = json.dumps({"error": str(e)})

            messages.append({
                "role": "tool",
                "tool_call_id": tc.id,
                "content": result_content,
            })

    return "# Analyse incomplète\n\nLe nombre maximum d'étapes a été atteint avant de pouvoir conclure."