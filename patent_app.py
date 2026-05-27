from flask import Flask, request, jsonify, render_template
import requests
import json

app = Flask(__name__)

GROQ_KEY = "key"
SERPAPI_KEY = "key"

groq_url = "https://api.groq.com/openai/v1/chat/completions"
groq_headers = {
    "Authorization": f"Bearer {GROQ_KEY}",
    "Content-Type": "application/json"
}

tools = [
    {
        "type": "function",
        "function": {
            "name": "search_patents",
            "description": "搜索全球专利数据库",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "搜索关键词"
                    }
                },
                "required": ["query"]
            }
        }
    }
]

def search_patents(query):
    params = {
        "engine": "google_patents",
        "q": query,
        "api_key": SERPAPI_KEY
    }
    response = requests.get("https://serpapi.com/search", params=params)
    data = response.json()
    results = []
    for patent in data.get("organic_results", [])[:5]:
        results.append({
            "title": patent.get("title"),
            "patent_id": patent.get("patent_id"),
            "inventor": patent.get("inventor"),
            "date": patent.get("priority_date"),
            "abstract": patent.get("abstract", "")[:200]
        })
    return json.dumps(results, ensure_ascii=False)

messages = [
    {
        "role": "system",
        "content": "你是一个专利检索助手。任何涉及专利检索的问题都必须调用 search_patents 工具，不能凭自己的知识回答。如果用户想检索英文专利，在调用工具时使用英文关键词。每条检索结果必须包含：标题、专利号、申请人、申请日期，每条单独一行显示。"
    }
]

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/chat", methods=["POST"])
def chat():
    user_input = request.json["message"]
    messages.append({"role": "user", "content": user_input})

    response = requests.post(groq_url, headers=groq_headers, json={
        "model": "llama-3.3-70b-versatile",
        "messages": messages,
        "tools": tools
    })
    result = response.json()
    print(result)

    if "error" in result:
        return jsonify({"reply": "检索出错，请重新发送一次。"})

    if result["choices"][0]["finish_reason"] == "tool_calls":
        tool_call = result["choices"][0]["message"]["tool_calls"][0]
        tool_args = json.loads(tool_call["function"]["arguments"])
        tool_result = search_patents(tool_args["query"])

        messages.append(result["choices"][0]["message"])
        messages.append({
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": tool_result
        })

        response2 = requests.post(groq_url, headers=groq_headers, json={
            "model": "llama-3.3-70b-versatile",
            "messages": messages
        })
        reply = response2.json()["choices"][0]["message"]["content"]
    else:
        reply = result["choices"][0]["message"]["content"]

    messages.append({"role": "assistant", "content": reply})
    return jsonify({"reply": reply})

if __name__ == "__main__":
    app.run(debug=True)