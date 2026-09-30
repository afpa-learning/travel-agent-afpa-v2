"""
Flask UI that consumes the DocumentDB MCP server.

Routes:
    GET  /            -> chat UI
    GET  /analysis    -> agentic analysis UI
    GET  /api/status  -> MCP connection + LLM availability + list MCP tools
    POST /api/ask     -> natural-language question -> tool-calling loop -> answer
    POST /api/call    -> manually invoke a tool (name + JSON arguments)
    POST /api/analyze -> multi-step agentic analysis -> markdown report
    GET /api/history  -> retrieve all historic messages for a conversation
    GET /api/history/reset    -> delete all historic messages for actual conversation
"""

from flask import Flask, render_template, request, jsonify, session
from pathlib import Path
import sys
import os
from history import new_conv_id, save_message, load_history, load_full_history, clear_history

# Get the absolute path of the current file
current_file = Path(__file__).resolve()

# Get the parent directory 
parent_directory = current_file.parent.parent

# Add the parent to sys.path
sys.path.append(str(parent_directory))


from agent.mcp_client import MCPClientManager
from agent.orchestrator import run_turn, run_analysis
from dotenv import load_dotenv

load_dotenv()

mcp_manager = MCPClientManager(groq_api_key=os.getenv("GROQ_API_KEY"))

import atexit
atexit.register(mcp_manager.shutdown)

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "MySuperSecretPhrase123!")  # obligatoire pour session

def get_conv_id() -> str:
    if "conv_id" not in session:
        session["conv_id"] = new_conv_id()
    return session["conv_id"]

@app.route('/')
def index():
   return render_template('index.html')

@app.route('/analysis')
def analysis():
   return render_template('analysis.html')

@app.route("/api/status")
def status():
    mcp = mcp_manager.get_session()
    llm= mcp_manager.get_groq_client()
    
    return jsonify({
        "mcp_connected": mcp is not None,
        "llm_connected": llm is not None,
        "max_messages":int(os.environ.get("MCP_MAX_RESULTS", "20")),
        "tools": [
            {"name": t.name, "description": t.description, "schema": t.input_schema}
            for t in mcp.mcp_tools
        ],
    })

@app.route("/api/ask", methods=["POST"])
def ask():
    data = request.get_json(silent=True)
    if not data or "question" not in data:
        return jsonify({"error": "Missing 'question' field"}), 400

    conv_id = get_conv_id()
    question = data["question"]

    history = load_history(conv_id)
    history.append({"role": "user", "content": question})

    async def _ask(session, groq_client):
        return await run_turn(session, groq_client, history)

    try:
        result = mcp_manager.call(_ask)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    # on ne persiste qu'après un succès
    save_message(conv_id, "user", question)
    save_message(conv_id, "assistant", result["reply"] or "", trace=result.get("trace"))

    return jsonify(result)

@app.route("/api/call", methods=["POST"])
def call_tool():
    data = request.get_json()
    if not data or "tool_name" not in data:
        return jsonify({"error": "Missing 'tool_name' field"}), 400

    tool_name = data["tool_name"]
    arguments = data.get("arguments", {})

    async def _call(session, groq_client):
        return await session.call_tool(tool_name, arguments)

    try:
        result = mcp_manager.call(_call)
    except Exception as e:
        
        return jsonify({"error": str(e)}), 500

    return jsonify({"result": result})

@app.route("/api/analyze", methods=["POST"])
def analyze():
    data = request.get_json() or {}
    topic = data.get("topic")
    if not topic:
        return jsonify({"error": "Missing 'topic' field"}), 400

    async def _analyze(session, groq_client):
        return await run_analysis(session, groq_client, topic)

    try:
        report_markdown = mcp_manager.call(_analyze, timeout=180)  # plus long, plusieurs étapes
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"report": report_markdown})

@app.route("/api/history", methods=["GET"])
def get_history():
    return jsonify({"conv_id": get_conv_id(), "history": load_full_history(get_conv_id())})


@app.route("/api/history/reset", methods=["GET"])
def reset_history():
    clear_history(get_conv_id())
    session.pop("conv_id", None)
    return jsonify({"ok": True})

if __name__ == '__main__':
   app.run(debug=True)