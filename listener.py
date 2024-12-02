import tkinter as tk
from tkinter import font as tkFont
import websocket
import json
import threading
import base64
import hashlib
import uuid

# Configuration
host = "ws://192.168.2.234:4455"  # Change to the IP and port of the OBS WebSocket server
password = "H0NL2wrVYRXPefeU"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup

def get_auth_response(password, secret, salt):
    passhash = base64.b64encode(hashlib.sha256((password + salt).encode('utf-8')).digest()).decode('utf-8')
    auth_response = base64.b64encode(hashlib.sha256((passhash + secret).encode('utf-8')).digest()).decode('utf-8')
    return auth_response

def create_overlay():
    overlay = tk.Tk()
    overlay.title("Stream150 Manager")
    overlay.geometry("+{}+{}".format(overlay.winfo_screenwidth() - 150, 50))  # Position close to the top
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True)
    overlay.attributes("-alpha", 0.9)  # Slightly more opaque for better visibility

    # Scene selection dropdown
    scene_var = tk.StringVar(overlay)
    scene_dropdown = tk.OptionMenu(overlay, scene_var, "")  # Initially empty
    scene_dropdown.pack(side="top", fill="x", expand=True)
    scene_var.trace("w", lambda *args: set_scene(scene_var.get()))

    # Button to make the overlay draggable
    move_btn = tk.Button(overlay, text="Move LIVE Indicator", command=lambda: toggle_drag(overlay))
    move_btn.pack(side="top", fill="x", expand=True)

    canvas = tk.Canvas(overlay, width=100, height=50, bg='red', bd=0, highlightthickness=0)
    canvas.pack()

    # Rectangle for the live indicator
    canvas.create_rectangle(10, 10, 90, 40, fill="red", outline="red", width=2)

    # Text configuration for "LIVE"
    live_font = tkFont.Font(family="Arial", size=12, weight="bold")
    live_text = canvas.create_text(50, 25, text="LIVE", fill="white", font=live_font)

    return overlay, canvas, scene_var, scene_dropdown, live_text

def flash_live_indicator(canvas, live_text, is_flashing):
    current_color = canvas.itemcget(live_text, "fill")
    new_color = "white" if current_color == "red" else "red"
    canvas.itemconfig(live_text, fill=new_color)
    if is_flashing:
        canvas.after(500, flash_live_indicator, canvas, live_text, is_flashing)

def toggle_drag(window):
    if window.overrideredirect():
        window.overrideredirect(False)
        window.config(cursor="fleur")
    else:
        window.overrideredirect(True)
        window.config(cursor="")

def set_scene(scene):
    global target_scene
    target_scene = scene
    print(f"Scene selected: {scene}")

def update_overlay_visibility(overlay, canvas, live_text, scene_name):
    if scene_name == target_scene:
        overlay.attributes("-topmost", True)  # Only be topmost when the selected scene is active
        overlay.deiconify()
        flash_live_indicator(canvas, live_text, True)
    else:
        overlay.attributes("-topmost", False)  # No longer topmost, but still open and accessible
        overlay.iconify()  # Minimize instead of completely hiding
        flash_live_indicator(canvas, live_text, False)

def run_websocket(overlay, canvas, scene_var, scene_dropdown, live_text):
    def on_message(ws, message):
        data = json.loads(message)
        print("Message received:", data)
        if data['op'] == 0:  # Hello message with auth challenge
            print("Processing authentication...")
            secret = data['d']['authentication']['challenge']
            salt = data['d']['authentication']['salt']
            auth_response = get_auth_response(password, secret, salt)
            auth_payload = {
                'op': 1,  # Identify operation
                'd': {
                    'rpcVersion': 1,
                    'authentication': auth_response,
                    'eventSubscriptions': 5  # Subscribe to scene events
                }
            }
            ws.send(json.dumps(auth_payload))
        elif data['op'] == 2:  # Authentication success message
            print("Authentication successful, requesting scenes...")
            scene_request_payload = {
                'op': 6,  # Scene request operation
                'd': {
                    'resource': 'ScenesService',
                    'requestType': 'GetSceneList',
                    'requestId': str(uuid.uuid4())
                }
            }
            ws.send(json.dumps(scene_request_payload))
        elif data['op'] == 7 and data['d']['requestType'] == 'GetSceneList':
            scenes = [scene['sceneName'] for scene in data['d']['responseData']['scenes']]
            print("Scenes fetched:", scenes)
            overlay.after(0, lambda: update_scene_dropdown(scene_dropdown, scenes))
        elif data['op'] == 5 and data['d']['eventType'] == 'CurrentProgramSceneChanged':
            current_scene = data['d']['eventData']['sceneName']
            update_overlay_visibility(overlay, canvas, live_text, current_scene)

    def on_error(ws, error):
        print(f"WebSocket Error: {error}")

    def on_close(ws, status_code, msg):
        print("### Connection Closed ###")
        print(f"Closed with status code: {status_code}, message: {msg}")

    def on_open(ws):
        print("WebSocket connection opened. Waiting for authentication...")

    ws = websocket.WebSocketApp(host,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    ws.run_forever()

def update_scene_dropdown(scene_dropdown, scenes):
    menu = scene_dropdown["menu"]
    menu.delete(0, "end")
    for scene in scenes:
        menu.add_command(label=scene, command=lambda value=scene: scene_dropdown.setvar(scene_dropdown.cget("textvariable"), value))

if __name__ == "__main__":
    overlay, canvas, scene_var, scene_dropdown, live_text = create_overlay()
    threading.Thread(target=run_websocket, args=(overlay, canvas, scene_var, scene_dropdown, live_text)).start()
    overlay.mainloop()