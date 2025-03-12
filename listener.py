import ctypes
import tkinter as tk
from tkinter import font as tkFont
import websocket
import json
import threading
import base64
import hashlib
import uuid
import time
import keyboard

# OBS WebSocket Configuration
host = "ws://ip:port"  # Change to the IP and port of the OBS WebSocket server
password = "WSPasswrd"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup
chat_locked = False  # Track if the chat box should be locked
ws_connection = None # Global websocket connection 
hotkey_registered = False  # Track if F8 hotkey is registered

# Chat API Configuration
CHAT_API_URL = "ws://watch.stream150.com/api/chat"  # Your chat API WebSocket URL
chat_api_key = None  # Will be set after fetching from server
chat_ws = None  # Global chat WebSocket connection
chat_reconnect_attempts = 0
chat_max_reconnect_attempts = 5
chat_reconnect_delay = 3000  # Base delay in milliseconds

# Minimize console window
def minimize_console():
    """Minimize console"""
    hWnd = ctypes.windll.kernel32.GetConsoleWindow()
    if hWnd:
        ctypes.windll.user32.ShowWindow(hWnd, 6)

minimize_console()

def get_auth_response(password, secret, salt):
    passhash = base64.b64encode(hashlib.sha256((password + salt).encode('utf-8')).digest()).decode('utf-8')
    auth_response = base64.b64encode(hashlib.sha256((passhash + secret).encode('utf-8')).digest()).decode('utf-8')
    return auth_response

def create_overlay():
    overlay = tk.Tk()
    overlay.title("Live Indicator")
    overlay.geometry("+{}+{}".format(overlay.winfo_screenwidth() - 200, 500))  # Adjusted position
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True)
    overlay.attributes("-alpha", 0.85)  # Adjust transparency

    # Canvas for "LIVE" indicator
    canvas = tk.Canvas(overlay, width=120, height=50, bg='red', bd=0, highlightthickness=0)
    canvas.pack()

    live_font = tkFont.Font(family="Helvetica", size=15, weight="bold")
    live_text = canvas.create_text(60, 25, text="LIVE", fill="white", font=live_font)

    # Pulsating effect
    def pulsate():
        current_color = canvas.itemcget(live_text, "fill")
        new_color = "white" if current_color == "red" else "red"
        canvas.itemconfig(live_text, fill=new_color)
        overlay.after(1000, pulsate)

    pulsate()

    return overlay, canvas

def create_chat_overlay():
    chat_overlay = tk.Toplevel()
    chat_overlay.title("Chat Overlay")
    chat_overlay.geometry("+800+200")  # Initial position
    chat_overlay.attributes("-topmost", True)
    
    chat_frame = tk.Frame(chat_overlay, bg="black")
    chat_frame.pack(fill="both", expand=True, padx=0, pady=0)  # Remove padding

    chat_box = tk.Text(chat_frame, wrap="word", height=15, width=45, 
                       bg="black", fg="white", font=("Helvetica", 14, "bold"), 
                       bd=0, highlightthickness=0) 
    chat_box.pack(expand=True, fill="both")
    chat_box.insert("end", "Connecting to chat...\n")
    chat_box.config(state="disabled")

    # Define color tags for different platforms
    chat_box.tag_configure("twitch", foreground="white", background="purple")
    chat_box.tag_configure("youtube", foreground="white", background="red")
    chat_box.tag_configure("web", foreground="white", background="blue")

    return chat_overlay, chat_box

def lock_chat_position():
    global chat_locked
    chat_locked = True

def update_chat_box(chat_box, message, platform):
    """Insert a message into the chat box with color formatting."""
    chat_box.config(state="normal")
    msg = f"{platform} | {message['username']}: {message['message']}\n"
    chat_box.insert("end", msg, platform.lower())
    chat_box.yview("end")  # Auto-scroll
    chat_box.config(state="disabled")

# Chat API WebSocket Handler
def run_chat_client(chat_box):
    global chat_api_key, chat_ws, chat_reconnect_attempts

    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if data['type'] == 'AUTH_SUCCESS':
                print("Successfully authenticated with chat server")
                global chat_reconnect_attempts
                chat_reconnect_attempts = 0  # Reset reconnect attempts on successful auth
            elif data['type'] == 'CHAT_MESSAGE':
                update_chat_box(chat_box, data, data['platform'])
            elif data['type'] == 'ERROR':
                print(f"Chat server error: {data['message']}")
        except Exception as e:
            print(f"Error processing chat message: {e}")

    def on_error(ws, error):
        print(f"Chat WebSocket error: {error}")

    def on_close(ws, close_status_code, close_msg):
        global chat_reconnect_attempts
        print(f"Chat connection closed: {close_status_code} - {close_msg}")
        
        # Implement exponential backoff for reconnection
        if chat_reconnect_attempts < chat_max_reconnect_attempts:
            delay = min(chat_reconnect_delay * (2 ** chat_reconnect_attempts), 300000)  # Max 5 minutes
            chat_reconnect_attempts += 1
            print(f"Attempting to reconnect in {delay/1000}s (attempt {chat_reconnect_attempts}/{chat_max_reconnect_attempts})...")
            time.sleep(delay/1000)  # Convert ms to seconds
            connect_chat()
        else:
            print("Maximum reconnection attempts reached. Please restart the application.")

    def on_open(ws):
        print("Connected to chat server")
        # Authenticate with the server
        ws.send(json.dumps({
            'type': 'AUTH',
            'apiKey': chat_api_key
        }))

    def connect_chat():
        global chat_ws
        try:
            # Create WebSocket connection
            chat_ws = websocket.WebSocketApp(
                CHAT_API_URL,
                on_message=on_message,
                on_error=on_error,
                on_close=on_close,
                on_open=on_open
            )
            chat_ws.run_forever()
        except Exception as e:
            print(f"Error creating WebSocket connection: {e}")
            # Trigger reconnection through on_close
            on_close(None, 1006, str(e))

    # First, get an API key with retry
    while True:
        try:
            response = requests.post('http://localhost:3001/api/keys')
            data = response.json()
            chat_api_key = data['apiKey']
            print("Obtained chat API key")
            
            # Start WebSocket connection
            connect_chat()
            break
        except Exception as e:
            print(f"Failed to get chat API key: {e}")
            time.sleep(5)  # Wait before retrying to get API key

def select_scene(scene, window):
    global target_scene
    target_scene = scene
    lock_chat_position()
    chat_overlay.overrideredirect(True)  # Lock chat box in overlay mode
    chat_overlay.lower(overlay)
    chat_overlay.attributes("-transparentcolor", "black")
    window.destroy()

# Function to show the scene selection popup
def show_scene_selection(scenes, overlay):
    global target_scene

    rows = (len(scenes) // 3) + (1 if len(scenes) % 3 else 0)
    window_width = 450  # Adjust width dynamically if needed
    window_height = max(100 + (rows * 80), 300)  # Adjust height based on rows

    selection_window = tk.Toplevel(overlay)
    selection_window.title("Select Scene")
    selection_window.geometry(f"{window_width}x{window_height}")
    selection_window.configure(bg='black')
    selection_window.attributes("-topmost", True)

    label = tk.Label(selection_window, text="Select the scene to show overlay:", fg='white', bg='black')
    label.pack(pady=5)

    scene_var = tk.StringVar(value=scenes[0] if scenes else "")

    grid_frame = tk.Frame(selection_window, bg='black')
    grid_frame.pack(pady=5, padx=5, fill=tk.BOTH, expand=True)

    for index, scene in enumerate(scenes):
        row, col = divmod(index, 3)  # Arrange in grid (3 per row)
        
        btn = tk.Button(grid_frame, text=scene, width=20, height=4, bg='green', fg='black', 
                        command=lambda s=scene: select_scene(s, selection_window))
        btn.grid(row=row, column=col, padx=5, pady=5, sticky='nsew')
    
    for i in range(3):
        grid_frame.columnconfigure(i, weight=1)
    for i in range(rows):
        grid_frame.rowconfigure(i, weight=1)

# Function to update overlay visibility based on OBS scenes
def update_overlay_visibility(overlay, canvas, scene_name):
    if scene_name == target_scene:
        overlay.deiconify()  # Show overlay if selected scene is active
    else:
        overlay.withdraw()  # Hide overlay otherwise

# Function to run the OBS WebSocket connection with reconnect logic
def run_websocket(overlay, canvas):
    global ws_connection, hotkey_registered

    def on_message(ws, message):
        global ws_connection, hotkey_registered
        data = json.loads(message)
        if data['op'] == 0:  # Hello message with auth challenge
            secret = data['d']['authentication']['challenge']
            salt = data['d']['authentication']['salt']
            auth_response = get_auth_response(password, secret, salt)
            auth_payload = {
                'op': 1,
                'd': {'rpcVersion': 1, 'authentication': auth_response, 'eventSubscriptions': 5}
            }
            ws.send(json.dumps(auth_payload))
        elif data['op'] == 2:  # Auth success
            ws_connection = ws

            # Bind the F8 hotkey only if it's not already registered
            if not hotkey_registered:
                keyboard.add_hotkey("F8", switch_scene)
                hotkey_registered = True
                print("🎯 F8 hotkey bound to switch scenes.")

            scene_request_payload = {
                'op': 6,
                'd': {'resource': 'ScenesService', 'requestType': 'GetSceneList', 'requestId': str(uuid.uuid4())}
            }
            ws.send(json.dumps(scene_request_payload))
        elif data['op'] == 7 and data['d']['requestType'] == 'GetSceneList':
            scenes = [scene['sceneName'] for scene in data['d']['responseData']['scenes']]
            overlay.after(0, lambda: show_scene_selection(scenes, overlay))
        elif data['op'] == 5 and data['d']['eventType'] == 'CurrentProgramSceneChanged':
            current_scene = data['d']['eventData']['sceneName']
            update_overlay_visibility(overlay, canvas, current_scene)

    def on_error(ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(ws, status_code, msg):
        print(f"### OBS Connection Closed ### {status_code}, message: {msg}")
        global ws_connection
        ws_connection = None # Clear connection on close
        reconnect()

    def on_open(ws):
        print("Connected to OBS WebSocket.")

    def connect():
        ws = websocket.WebSocketApp(host,
                                    on_message=on_message,
                                    on_error=on_error,
                                    on_close=on_close,
                                    on_open=on_open)
        ws.run_forever()

    def reconnect():
        print("Reconnecting in 5 seconds...")
        time.sleep(5)  # Wait before reconnecting
        connect()

    # Initial connection
    connect()

def switch_scene():
    """Switch the OBS scene to the target scene using the existing WebSocket connection."""
    global ws_connection

    if not ws_connection:
        print("⚠️ WebSocket not connected. Scene switch failed.")
        return
    if not target_scene:
        print("⚠️ No target scene selected. Scene switch failed.")
        return

    # Send request to change scene
    change_scene_payload = {
        "op": 6,
        "d": {
            "requestId": str(uuid.uuid4()),
            "requestType": "SetCurrentProgramScene",
            "requestData": {
                "sceneName": target_scene
            }
        }
    }

    try:
        ws_connection.send(json.dumps(change_scene_payload))
        print(f"🔄 Switched to scene: {target_scene}")
    except Exception as e:
        print(f"⚠️ Failed to switch scene: {e}")

if __name__ == "__main__":
    # Import requests here to avoid potential import issues
    import requests
    
    overlay, canvas = create_overlay()
    chat_overlay, chat_box = create_chat_overlay()

    # Start Chat Client in a separate thread
    threading.Thread(target=run_chat_client, args=(chat_box,), daemon=True).start()

    # Start OBS WebSocket connection in another thread
    threading.Thread(target=run_websocket, args=(overlay, canvas), daemon=True).start()

    overlay.mainloop()
    chat_overlay.mainloop()