from flask import Flask, render_template, request, session, g
from flask_socketio import SocketIO, send, emit, join_room, leave_room, disconnect
from flask_session import Session
from random import randint
from time import time
from datetime import datetime
from sys import stderr
from gevent import monkey

monkey.patch_all()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

socketio = SocketIO(app, async_mode="gevent", cors_allowed_origins="*")

def log(message):
    # Logs a message to stderr with a timestamp
    # This is useful when running on the PythonAnywhere server
    t = datetime.strftime(datetime.now(), "\n[%Y-%m-%d %H-%M-%S]")
    print(t, message, file=stderr)



# In the game, we can use "players" instead of "chatters"


# Some hardcoded rooms for the example
rooms = {
    1: {
        "chatters": {
            # "chatter_id": {
            #     "socket_id": -,       # Set to None if the chatter disconnects
            #     "user": -,            # None if not logged in
            #     "display_name": -,    # Same as user if logged in
            #     "disconnect_time": -  # 
            # }
        },
        "messages": [
            ("System", "Welcome to Room 1")
        ]
    },
    2: {
        "chatters": {},
        "messages": [
            ("System", "Welcome to Room 2")
        ]
    },
    3: {
        "chatters": {},
        "messages": [
            ("System", "Welcome to Room 3")
        ]
    }
}

#Maps socket ID to room ID
socket_rooms = {}

@app.before_request
def get_username():
    g.user = session.get("user", None)

    # Assign a chatter ID based on the username, or on the session ID if not logged in
    if "chatter_id" not in session:
        # Change when logging in
        if g.user is None:
            session["chatter_id"] = "guest_" + session.sid
        else:
            session["chatter_id"] = "user_" + g.user

@app.route('/')
def index():
    log("Async mode", socketio.async_mode)
    return render_template('index.html', rooms=rooms)

@app.route("/chat/<room_id>")
def chat(room_id):
    room_id = int(room_id)
    room = rooms[room_id]

    
    chatter_id = "user_" + g.user if g.user is not None else "guest_" + session.sid
    session["chatter_id"] = chatter_id

    # If the same chatter is already connected to this room on another socket, refuse the connection
    if chatter_id in room["chatters"] and room["chatters"][chatter_id]["socket_id"] is not None:
        return "Already connected"

    return render_template("chat.html", room_id=room_id, messages=room["messages"])

@socketio.on("join")
def handle_join(room_id):
    room_id = int(room_id)
    room = rooms[room_id]
    chatter_id = session["chatter_id"]
    
    # Check if this chatter is already connected to this room, or was previously
    if chatter_id in room["chatters"] and room["chatters"][chatter_id]["socket_id"] is not None:
        # If the same chatter is already connected to this room on another socket, disconnect the previous socket
        # This will typically occur if a client disconnects suddenly and tries to reconnect
        # (Time limit???)
        prev_socket = room["chatters"][chatter_id]["socket_id"]
        room["chatters"][chatter_id]["socket_id"] = request.sid
        room["chatters"][chatter_id]["disconnect_time"] = None
        del socket_rooms[prev_socket]
        disconnect(prev_socket)

    elif chatter_id in room["chatters"] and time() - room["chatters"][chatter_id]["disconnect_time"] < 60:
        # If the chatter disconnected within the last minute, allow them to reconnect
        # This reconnect feature doesn't really have much point here, it's more to test if something like this will work for the game
        room["chatters"][chatter_id]["socket_id"] = request.sid
        room["chatters"][chatter_id]["disconnect_time"] = None

    else:
        room["chatters"][chatter_id] = {
            "chatter_id": chatter_id,
            "socket_id": request.sid,
            "user": None,
            "display_name": "user" + str(randint(100, 999)),
            "disconnect_time": None
        }

    socket_rooms[request.sid] = room_id
    join_room(room_id)

# Handle disconnects
@socketio.on("disconnect")
def handle_disconnect(*args):
    t = time()

    if request.sid not in socket_rooms:
        # If this socket is not in the dictionary, do nothing
        # This should only occur if the socket was disconnected because the chatter connected to the room on a new socket
        # (typically reconnecting after being suddenly disconnected)
        return

    room_id = socket_rooms.pop(request.sid)
    chatter_id = session["chatter_id"]

    chatter = rooms[room_id]["chatters"][chatter_id]
    chatter["socket_id"] = None
    chatter["disconnect_time"] = t

    # In the game, the current game should be deleted when the last player disconnects

# Handle user messages
@socketio.on("chat_message")
def handle_chat_message(message):
    chatter_id = session["chatter_id"]
    room_id = socket_rooms[request.sid]
    room = rooms[room_id]

    display_name = room["chatters"][chatter_id]["display_name"]

    room["messages"].append((display_name, message))

    send("%s: %s" % (display_name, message), to=room_id)

if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)