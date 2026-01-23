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

# In the game, we can use "games" and "players" instead of "rooms" and "chatters"


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
    session["current_room"] = room_id
    room = rooms[room_id]

    # Assign a chatter ID based on the username, or on the session ID if not logged in
    chatter_id = "user_" + g.user if g.user is not None else "guest_" + session.sid
    session["chatter_id"] = chatter_id
    
    # If the same chatter is already connected to this room on another socket, refuse the connection
    if chatter_id in room["chatters"] and room["chatters"][chatter_id]["socket_id"] is not None:
        return "Already connected"

    return render_template("chat.html", room_id=room_id, messages=room["messages"])

@socketio.on("connect")
def handle_connect(*args):
    chatter_id = session["chatter_id"]
    room_id = session["current_room"]
    room = rooms[room_id]
    
    # Check if this chatter is already connected to this room, or was previously
    if chatter_id in room["chatters"] and room["chatters"][chatter_id]["socket_id"] is not None:
        # If the same chatter is already connected to this room on another socket, refuse the connection
        # This shouldn't be possible given the checks in the chat page, but this is included to be safe
        disconnect(request.sid)
        return
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

    join_room(room_id)
          
# Handle new user joining
# @socketio.on("join")
# def handle_join(room_id):
#     print("Print test")

#     room_id = int(room_id)

#     chatter_id = session["chatter_id"]
#     room = rooms[room_id]
    
#     # Check if this chatter is already connected to this room, or was previously
#     if chatter_id in room["chatters"] and room["chatters"][chatter_id]["socket_id"] is not None:
#         # If the same chatter is already connected to this room on another socket, refuse the connection
#         # This shouldn't be possible given the checks in the chat page, but this is included to be safe
#         disconnect(request.sid)
#         return
#     elif chatter_id in room["chatters"] and time() - room["chatters"][chatter_id]["disconnect_time"] < 60:
#         # If the chatter disconnected within the last minute, allow them to reconnect
#         # This reconnect feature doesn't really have much point here, it's more to test if something like this will work for the game
#         room["chatters"][chatter_id]["socket_id"] = request.sid
#         room["chatters"][chatter_id]["disconnect_time"] = None
#     else:
#         room["chatters"][chatter_id] = {
#             "chatter_id": chatter_id,
#             "socket_id": request.sid,
#             "user": None,
#             "display_name": "user" + str(randint(100, 999)),
#             "disconnect_time": None
#         }

#     socket_dict[request.sid] = (room_id, chatter_id)

#     join_room(room_id)


# Handle disconnects
@socketio.on("disconnect")
def handle_disconnect(*args):
    t = time()

    chatter_id = session["chatter_id"]
    room_id = session["current_room"]

    chatter = rooms[room_id]["chatters"][chatter_id]
    chatter["socket_id"] = None
    chatter["disconnect_time"] = t

    # In the game, the current game should be deleted when the last player disconnects


# Handle user messages
@socketio.on("chat_message")
def handle_chat_message(message):
    chatter_id = session["chatter_id"]
    room_id = session["current_room"]
    room = rooms[room_id]

    display_name = room["chatters"][chatter_id]["display_name"]

    room["messages"].append((display_name, message))

    send("%s: %s" % (display_name, message), to=room_id)