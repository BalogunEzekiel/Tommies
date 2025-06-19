import streamlit as st
import streamlit.components.v1 as components
import requests
# import openai
import streamlit_js_eval

# Set OpenAI API Key
# openai.api_key = 'YOUR_OPENAI_API_KEY'

# Initialize session state if not already present
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []

# Function to interact with OpenAI API
# def get_openai_response(user_input):
#     # Call OpenAI API to generate a response
#     response = openai.Completion.create(
#         engine="text-davinci-003",
#         prompt=user_input,
#         max_tokens=150
#     )
#     return response.choices[0].text.strip()

# Function to interact with Rasa API
def get_rasa_response(user_input):
    # Send the user input to the Rasa server for a response
    rasa_url = "http://localhost:5005/webhooks/rest/webhook"
    payload = {"message": user_input}
    headers = {'Content-Type': 'application/json'}
    try:
        response = requests.post(rasa_url, json=payload, headers=headers)
        response.raise_for_status()  # Raise an exception for bad status codes
        response_json = response.json()
        if response_json and len(response_json) > 0 and 'text' in response_json[0]:
            return response_json[0]['text']
        else:
            return "Sorry, I didn't receive a valid response."
    except requests.exceptions.RequestException as e:
        return f"Sorry, I couldn't connect to the Rasa server. Error: {e}"

# Custom HTML + JS + CSS to float the chatbot
chat_html = f"""
<style>
    #chat-container {{
        position: fixed;
        bottom: 20px;
        right: 20px;
        width: 300px;
        max-height: 400px;
        background-color: #f5f5f5;
        border: 1px solid #ccc;
        border-radius: 10px;
        box-shadow: 0 0 10px rgba(0,0,0,0.3);
        display: flex;
        flex-direction: column;
        z-index: 9999;
        resize: both;
        overflow: hidden;
    }}
    #chat-header {{
        background-color: #2e7bcf;
        color: white;
        padding: 10px;
        cursor: move;
        user-select: none;
        font-weight: bold;
    }}
    #chat-messages {{
        flex: 1;
        padding: 10px;
        overflow-y: auto;
        display: flex;
        flex-direction: column-reverse;
    }}
    #chat-input {{
        display: flex;
        padding: 10px;
        border-top: 1px solid #ccc;
    }}
    #chat-input input {{
        flex: 1;
        padding: 5px;
    }}
    #chat-input button {{
        margin-left: 5px;
        padding: 5px 10px;
    }}
</style>

<div id="chat-container">
    <div id="chat-header" onclick="toggleChat()">💬 VetChat</div>
    <div id="chat-body">
        <div id="chat-messages">
            {"".join([f"<div><b>{s}:</b> {m}</div>" for s, m in reversed(st.session_state.chat_history)])}
        </div>
        <div id="chat-input">
            <input type="text" id="user-input" placeholder="Ask VetChat..." />
            <button onclick="sendMessage()">Send</button>
        </div>
    </div>
</div>

<script>
    let dragging = false;
    let offset = [0, 0];
    const chatBox = document.getElementById("chat-container");
    const header = document.getElementById("chat-header");

    header.addEventListener("mousedown", function(e) {{
        dragging = true;
        offset = [
            chatBox.offsetLeft - e.clientX,
            chatBox.offsetTop - e.clientY
        ];
    }});

    document.addEventListener("mouseup", function() {{
        dragging = false;
    }});

    document.addEventListener("mousemove", function(e) {{
        e.preventDefault();
        if (dragging) {{
            chatBox.style.left = (e.clientX + offset[0]) + "px";
            chatBox.style.top = (e.clientY + offset[1]) + "px";
        }}
    }});

    function toggleChat() {{
        const body = document.getElementById("chat-body");
        body.style.display = body.style.display === "none" ? "block" : "none";
    }}

    function sendMessage() {{
        const input = document.getElementById("user-input");
        const msg = input.value;
        if (msg) {{
            window.parent.postMessage({{type: "chatMessage", message: msg}}, "*");
            input.value = "";
        }}
    }}

    window.addEventListener("message", (event) => {{
        if (event.data.type === "updateChat") {{
            const chatDiv = document.getElementById("chat-messages");
            chatDiv.innerHTML = event.data.html;
        }}
    }});
</script>
"""

# Display the chat HTML
components.html(chat_html, height=500, width=0)

# Handling the user input and response
event = streamlit_js_eval.streamlit_js_eval(js_expressions="parent.postMessage({ type: 'ready' }, '*')", key="chat_eval")

if event and event.get("type") == "chatMessage":
    user_input = event.get("message", "")
    if user_input:
        # Use Rasa to get a response
        response = get_rasa_response(user_input)

        # Store the user input and response in the chat history
        st.session_state.chat_history.append(("You", user_input))
        st.session_state.chat_history.append(("VetChat", response))

        # Trigger JS to update the chat window dynamically
        chat_update = "".join([f"<div><b>{s}:</b> {m}</div>" for s, m in reversed(st.session_state.chat_history)])
        st.components.v1.html(f"<script>window.parent.postMessage({{type: 'updateChat', html: `{chat_update}`}}, '*');</script>", height=0)
