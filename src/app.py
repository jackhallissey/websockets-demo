from flask import Flask, render_template, request, session, g
from flask_socketio import SocketIO, send, emit, join_room, leave_room, disconnect
from flask_session import Session
from random import randint
from time import time

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'

# app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

async_mode = None
socketio = SocketIO(app, async_mode=async_mode, cors_allowed_origins="*")

rooms = {
    1: {
        "chatters": {
            # "chatter_id": {
            #     "socket_id": -,       # Set to None if the chatter disconnects
            #     "user": -,            # None if not logged in
            #     "display_name": -,    # Same as user if logged in
            #     "last_disconnect": -  # 
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

# Maps each socket id to a pair of (room id, chatter id)
socket_dict = {}


@app.before_request
def get_username():
    if "user" not in session:
        session["user"] = None          # Need to store something in session to ensure a session ID is created
        g.user = None
    else:
        g.user = session["user"]

@app.route('/')
def index():
    return render_template('index.html', rooms=rooms)

@app.route("/chat/<room_id>")
def chat(room_id):
    room_id = int(room_id)

    # Generate a chatter ID based on the username, or the session ID if not logged in
    # Need to ensure a username cannot match a guest ID
    chatter_id = g.user if g.user is not None else "guest_" + session.sid
    session["chatter_id"] = chatter_id
    room = rooms[room_id]

    # If the same chatter is already connected to this room on another socket, refuse the connection
    for c_id, chatter in room["chatters"].items():
        if c_id == chatter_id and chatter["socket_id"] is not None:
            return "Already connected"

    return render_template("chat.html", room_id=room_id, messages=room["messages"])




# Handle new user joining
@socketio.on('join')
def handle_join(room_id):
    # Also handle reconnecting
    room_id = int(room_id)

    chatter_id = session["chatter_id"]
    room = rooms[room_id]
    
    # Check if this chatter is already connected to this room, or was previously
    for c_id, chatter in room["chatters"].items():
        if c_id == chatter_id:
            if chatter["socket_id"] is not None:
                # If the same chatter is already connected to this room on another socket, refuse the connection
                # This shouldn't be possible, but this is included to be safe
                disconnect(request.sid)
                return
            elif time() - chatter["last_disconnect"] < 60:
                # If the chatter disconnected within the last minute (TBD), allow them to reconnect
                room["chatters"][chatter_id]["socket_id"] = request.sid
                room["chatters"][chatter_id]["last_disconnect"] = None
            else:
                del room["chatters"][chatter_id]
            break

    if chatter_id not in room["chatters"]:
        room["chatters"][chatter_id] = {
            "chatter_id": chatter_id,
            "socket_id": request.sid,
            "user": None,
            "display_name": "user" + str(randint(100, 999)),
            "last_disconnect": None
        }

    socket_dict[request.sid] = (room_id, chatter_id)

    join_room(room_id)


# Handle disconnects
@socketio.on('disconnect')
def handle_disconnect():
    t = time()

    if request.sid not in socket_dict:
        return
    
    room_id, chatter_id = socket_dict.pop(request.sid)

    chatter = rooms[room_id]["chatters"][chatter_id]
    chatter["socket_id"] = None
    chatter["last_disconnect"] = t

    # If the creation of rooms is allowed, the room should be deleted when the last chatter disconnects


# Handle user messages
@socketio.on('message')
def handle_message(data):
    room_id, chatter_id = socket_dict[request.sid]
    room = rooms[room_id]

    display_name = room["chatters"][chatter_id]["display_name"]

    room["messages"].append((display_name, data))

    send("%s: %s" % (display_name, data), to=room_id)