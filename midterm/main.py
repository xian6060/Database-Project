

from flask import Flask, render_template, request, session, redirect, url_for
from flask_socketio import join_room, leave_room, send, SocketIO
import random
from string import ascii_uppercase
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch
import sqlite3

tokenizer = AutoTokenizer.from_pretrained("microsoft/DialoGPT-medium")
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-medium")
def get_Chat_response(text):
    global chat_history_ids

    for step in range(5):
        # encode the new user input, add the eos_token and return a tensor in Pytorch
        new_user_input_ids = tokenizer.encode(str(text) + tokenizer.eos_token, return_tensors='pt')

        # append the new user input tokens to the chat history
        bot_input_ids = torch.cat([chat_history_ids, new_user_input_ids], dim=-1) if step > 0 else new_user_input_ids

        # generated a response while limiting the total chat history to 1000 tokens,
        chat_history_ids = model.generate(bot_input_ids, max_length=1000, pad_token_id=tokenizer.eos_token_id)

        # pretty print last ouput tokens from bot
        return tokenizer.decode(chat_history_ids[:, bot_input_ids.shape[-1]:][0], skip_special_tokens=True)



app = Flask(__name__)
app.config["SECRET_KEY"] = "hjhjsdahhds"
socketio = SocketIO(app)
#資料庫的東西
def database(name, email, amount):
    conn = sqlite3.connect('templates/sponsor.db')
    cursor = conn.cursor()

    cursor.execute('CREATE TABLE IF NOT EXISTS SPONSOR('
                   'NAME TEXT , '
                   'EMAIL TEXT, '
                   'AMOUNT TEXT)')
    insert_query = 'INSERT INTO SPONSOR VALUES(?, ?, ?)'

    sponsors = []
    sponsors.append((name, email, amount,))
    cursor.executemany(insert_query, sponsors)

    conn.commit()
    conn.close()
#資料庫結束
rooms = {}


def generate_unique_code(length):
    while True:
        code = ""
        for _ in range(length):
            code += random.choice(ascii_uppercase)

        if code not in rooms:
            break

    return code



@app.route("/", methods=["POST", "GET"])
def home():
    session.clear()
    if request.method == "POST":
        name = request.form.get("name")
        code = request.form.get("code")
        join = request.form.get("join", False)
        create = request.form.get("create", False)
        chatbot = request.form.get("chatbot", False)
        sponsor = request.form.get("sponsor", False)

        if sponsor != False:
            return render_template("sponsor.html")
        if not name:
            return render_template("home.html", error="你這老登 都叫你輸入暱稱了", code=code, name=name)

        if join != False and not code:
            return render_template("home.html", error="記得輸入房號喔親", code=code, name=name)
        if chatbot != False:
            return render_template("chat.html")
        room = code
        if create != False:
            room = generate_unique_code(4)
            rooms[room] = {"members": 0, "messages": []}
        elif code not in rooms:
            return render_template("home.html", error="房間尚未建立", code=code, name=name)

        session["room"] = room
        session["name"] = name
        return redirect(url_for("room"))

    return render_template("home.html")

@app.route("/get", methods=["GET", "POST"])
def chat():
    msg = request.form["msg"]
    input = msg
    return get_Chat_response(input)


@app.route('/submit_form', methods=['POST'])
def submit_form():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        amount = request.form['amount']

        # 在這裡你可以對這些資料進行處理，例如儲存到資料庫、進行計算等
        # 這裡只是一個簡單的例子，將資料印出到控制台
        print(f"Name: {name}, Email: {email}, Amount: {amount}")
        database(name, email, amount)
        return render_template("success.html")


@app.route("/room")
def room():
    room = session.get("room")
    if room is None or session.get("name") is None or room not in rooms:
        return redirect(url_for("home"))

    return render_template("room.html", code=room, messages=rooms[room]["messages"])


@socketio.on("message")
def message(data):
    room = session.get("room")
    if room not in rooms:
        return

    content = {
        "name": session.get("name"),
        "message": data["data"]
    }
    send(content, to=room)
    rooms[room]["messages"].append(content)
    print(f"{session.get('name')} said: {data['data']}")


@socketio.on("connect")
def connect(auth):
    room = session.get("room")
    name = session.get("name")
    if not room or not name:
        return
    if room not in rooms:
        leave_room(room)
        return

    join_room(room)
    send({"name": name, "message": "加入這個溫馨的大家庭"}, to=room)
    rooms[room]["members"] += 1
    print(f"{name} joined room {room}")


@socketio.on("disconnect")
def disconnect():
    room = session.get("room")
    name = session.get("name")
    leave_room(room)

    if room in rooms:
        rooms[room]["members"] -= 1
        if rooms[room]["members"] <= 0:
            del rooms[room]

    send({"name": name, "message": "已離開 永遠懷念他"}, to=room)
    print(f"{name} has left the room {room}")


if __name__ == "__main__":
    socketio.run(app, debug=True)

