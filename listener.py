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
import win32gui
import win32con
import win32api

# Server WebSocket Configuration
SERVER_WS_URL = "ws://watch.stream150.com:3001"  # WebSocket URL for your server

# OBS WebSocket Configuration
host = "ws://OBSip:port"  # Change to the IP and port of the OBS WebSocket server
password = "OBSPassword"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup
chat_locked = False  # Track if the chat box should be locked
ws_connection = None # Global websocket connection for OBS
server_ws = None  # Global websocket connection for server
hotkey_registered = False  # Track if F8 hotkey is registered
f9_registered = False  # Track if F9 hotkey is registered

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

def make_window_clickthrough(hwnd):
    """Make a window transparent to mouse clicks and improve visual transparency."""
    # Add layered and transparent styles
    ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
    win32gui.SetWindowLong(hwnd, win32con.GWL_EXSTYLE,
                          ex_style | win32con.WS_EX_LAYERED | win32con.WS_EX_TRANSPARENT)
    
    # Set transparency level (0-255, where 255 is fully opaque)
    # Using 200 for text visibility while keeping it somewhat transparent
    win32gui.SetLayeredWindowAttributes(hwnd, win32api.RGB(0, 0, 0), 200, win32con.LWA_ALPHA | win32con.LWA_COLORKEY)

def create_overlay():
    overlay = tk.Tk()
    overlay.title("Live Indicator")
    overlay.geometry("+{}+{}".format(overlay.winfo_screenwidth() - 200, 500))  # Adjusted position
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True)
    overlay.attributes("-alpha", 0.85)  # Adjust transparency
    
    # Make window click-through
    overlay.attributes('-transparentcolor', 'black')
    overlay.wm_attributes("-disabled", True)
    
    # Get HWND of the overlay - using the correct method
    overlay.update_idletasks()  # Make sure window exists
    hwnd = overlay.winfo_id()
    make_window_clickthrough(hwnd)

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
    global chat_frame  # Make chat_frame accessible globally
    
    chat_overlay = tk.Toplevel()
    chat_overlay.title("Chat Overlay")
    chat_overlay.geometry("+800+200")  # Initial position
    chat_overlay.attributes("-topmost", True)
    
    # Initially allow interaction
    chat_overlay.overrideredirect(False)  # Allow window decorations initially
    
    # Configure for transparency
    chat_overlay.config(bg="black")
    
    chat_frame = tk.Frame(chat_overlay, bg="black")
    chat_frame.pack(fill="both", expand=True, padx=0, pady=0)  # Remove padding

    chat_box = tk.Text(chat_frame, wrap="word", height=15, width=45, 
                       bg="black", fg="white", font=("Helvetica", 14, "bold"), 
                       bd=0, highlightthickness=0)
    chat_box.pack(expand=True, fill="both")
    chat_box.insert("end", "Connecting to server chat...\n")
    chat_box.config(state="disabled")

    # Define color tags with enhanced colors for better visibility
    chat_box.tag_configure("twitch", foreground="#ffffff", background=None)  # White text
    chat_box.tag_configure("youtube", foreground="#ffaaaa", background=None)  # Brighter red text
    chat_box.tag_configure("web", foreground="#aaddff", background=None)  # Brighter blue text

    return chat_overlay, chat_box


def lock_chat_position():
    global chat_locked
    chat_locked = True

# Function to run the server WebSocket connection
def run_server_websocket(chat_box):
    global server_ws
    
    def on_message(ws, message):
        try:
            data = json.loads(message)
            
            if data.get('type') == 'CHAT_MESSAGE':
                platform = data.get('platform', 'web')
                username = data.get('username', 'Anonymous')
                msg_content = data.get('message', '')
                
                # Format message based on platform
                msg = f"{platform.capitalize()} | {username}: {msg_content}\n"
                
                # Update chat box with appropriate tag
                chat_box.config(state="normal")
                chat_box.insert("end", msg, platform.lower())
                chat_box.yview("end")  # Auto-scroll
                chat_box.config(state="disabled")
            
            elif data.get('type') == 'CHAT_HISTORY':
                messages = data.get('messages', [])
                
                chat_box.config(state="normal")
                chat_box.delete("1.0", "end")  # Clear existing content
                
                for msg_data in messages:
                    platform = msg_data.get('platform', 'web')
                    username = msg_data.get('username', 'Anonymous')
                    msg_content = msg_data.get('message', '')
                    
                    # Format message based on platform
                    msg = f"{platform.capitalize()} | {username}: {msg_content}\n"
                    
                    # Insert with appropriate tag
                    chat_box.insert("end", msg, platform.lower())
                
                chat_box.yview("end")  # Auto-scroll
                chat_box.config(state="disabled")
        
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def on_error(ws, error):
        print(f"Server WebSocket Error: {error}")
    
    def on_close(ws, close_status_code, close_msg):
        print(f"Server WebSocket connection closed: {close_status_code}, {close_msg}")
        # Attempt to reconnect after a delay
        time.sleep(5)
        connect_to_server()
    
    def on_open(ws):
        print("Connected to server WebSocket")
        # Request chat history when connected
        ws.send(json.dumps({"type": "REQUEST_CHAT_HISTORY"}))
    
    def connect_to_server():
        global server_ws
        try:
            ws = websocket.WebSocketApp(SERVER_WS_URL,
                                        on_message=on_message,
                                        on_error=on_error,
                                        on_close=on_close,
                                        on_open=on_open)
            server_ws = ws
            ws.run_forever()
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            time.sleep(5)
            connect_to_server()
    
    # Start connection
    connect_to_server()

def select_scene(scene, window):
    global target_scene, chat_overlay, chat_box, chat_frame
    target_scene = scene
    print(f"🎯 Target scene selected: {target_scene}")
    
    # Request current scene to immediately check visibility
    if ws_connection:
        current_scene_payload = {
            'op': 6,
            'd': {'requestType': 'GetCurrentProgramScene', 'requestId': str(uuid.uuid4())}
        }
        ws_connection.send(json.dumps(current_scene_payload))
    
    # Now lock the chat overlay and make it click-through
    chat_overlay.overrideredirect(True)  # Remove window decorations
    
    # Make window fully transparent in tkinter first
    chat_overlay.attributes("-transparentcolor", "black")
    
    # Disable interaction
    chat_overlay.wm_attributes("-disabled", True)
    
    # Ensure click-through works by applying it after window is configured
    chat_overlay.update_idletasks()
    hwnd = chat_overlay.winfo_id()
    make_window_clickthrough(hwnd)
    
    chat_overlay.lower(overlay)
    
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
    global target_scene
    print(f"Scene changed to: {scene_name}, Target scene: {target_scene}")
    if scene_name == target_scene:
        print("📍 SHOWING live indicator")
        overlay.deiconify()  # Show overlay if selected scene is active
    else:
        print("📍 HIDING live indicator")
        overlay.withdraw()  # Hide overlay otherwise

# Function to save the OBS replay buffer
def save_replay():
    """Save the OBS replay buffer using the WebSocket connection."""
    global ws_connection

    if not ws_connection:
        print("⚠️ WebSocket not connected. Replay save failed.")
        return

    # Send request to save replay buffer
    save_replay_payload = {
        "op": 6,
        "d": {
            "requestId": str(uuid.uuid4()),
            "requestType": "SaveReplayBuffer",
        }
    }

    try:
        ws_connection.send(json.dumps(save_replay_payload))
        print("🎥 Saving replay buffer...")
    except Exception as e:
        print(f"⚠️ Failed to save replay: {e}")

# Function to run the OBS WebSocket connection with reconnect logic
def run_websocket(overlay, canvas):
    global ws_connection, hotkey_registered, f9_registered

    def on_message(ws, message):
        global ws_connection, hotkey_registered, f9_registered
        try:
            data = json.loads(message)
            if data['op'] == 0:  # Hello message with auth challenge
                secret = data['d']['authentication']['challenge']
                salt = data['d']['authentication']['salt']
                auth_response = get_auth_response(password, secret, salt)
                auth_payload = {
                    'op': 1,
                    'd': {'rpcVersion': 1, 'authentication': auth_response, 'eventSubscriptions': 31}  # Increased subscription value
                }
                ws.send(json.dumps(auth_payload))
                print("🔑 Authentication sent to OBS")
            elif data['op'] == 2:  # Auth success
                ws_connection = ws
                print("✅ Successfully authenticated with OBS")

                # Bind the hotkeys only if they're not already registered
                if not hotkey_registered:
                    keyboard.add_hotkey("F8", switch_scene)
                    hotkey_registered = True
                    print("🎯 F8 hotkey bound to switch scenes.")
                
                if not f9_registered:
                    keyboard.add_hotkey("F9", save_replay)
                    f9_registered = True
                    print("🎥 F9 hotkey bound to save replay buffer.")

                # Request current scene and scene list
                current_scene_payload = {
                    'op': 6,
                    'd': {'requestType': 'GetCurrentProgramScene', 'requestId': str(uuid.uuid4())}
                }
                ws.send(json.dumps(current_scene_payload))
                
                scene_request_payload = {
                    'op': 6,
                    'd': {'requestType': 'GetSceneList', 'requestId': str(uuid.uuid4())}
                }
                ws.send(json.dumps(scene_request_payload))
                print("📋 Requested scene list from OBS")
            elif data['op'] == 7 and data['d']['requestType'] == 'GetSceneList':
                scenes = [scene['sceneName'] for scene in data['d']['responseData']['scenes']]
                print(f"📋 Received scene list: {scenes}")
                overlay.after(0, lambda: show_scene_selection(scenes, overlay))
            elif data['op'] == 7 and data['d']['requestType'] == 'GetCurrentProgramScene':
                current_scene = data['d']['responseData']['sceneName']
                print(f"📺 Current program scene: {current_scene}")
                overlay.after(0, lambda: update_overlay_visibility(overlay, canvas, current_scene))
            elif data['op'] == 5:  # Event
                if data['d']['eventType'] == 'CurrentProgramSceneChanged':
                    current_scene = data['d']['eventData']['sceneName']
                    print(f"🔄 Scene changed to: {current_scene}")
                    overlay.after(0, lambda: update_overlay_visibility(overlay, canvas, current_scene))
                # Log any other events for debugging
                else:
                    print(f"📝 Received event: {data['d']['eventType']}")
        except Exception as e:
            print(f"⚠️ Error processing message: {e}")
            print(f"⚠️ Message content: {message[:200]}...")  # Print first 200 chars of message

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
    overlay, canvas = create_overlay()
    chat_overlay, chat_box = create_chat_overlay()

    # Start Server WebSocket connection in a separate thread
    threading.Thread(target=run_server_websocket, args=(chat_box,), daemon=True).start()

    # Start OBS WebSocket connection in another thread
    threading.Thread(target=run_websocket, args=(overlay, canvas), daemon=True).start()

    overlay.mainloop()
    chat_overlay.mainloop()
