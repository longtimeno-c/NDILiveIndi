import tkinter as tk
from tkinter import font as tkFont
import websocket
import json
import threading
import base64
import hashlib
import uuid
import ctypes
import asyncio
from twitchio.ext import commands

# Twitch Configuration
TWITCH_CHANNEL = "twitchusername"  # Change this to your Twitch channel name
TWITCH_TOKEN = "oauth:twitchaccess"  # Generate at https://twitchtokengenerator.com/

# OBS WebSocket Configuration
host = "ws://ip:port"  # Change to the IP and port of the OBS WebSocket server
password = "WSPasswrd"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup
chat_locked = False  # Track if the chat box should be locked

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

    live_font = tkFont.Font(family="Helvetica", size=12, weight="bold")
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
    global chat_locked
    chat_overlay = tk.Toplevel()
    chat_overlay.title("Twitch Chat")
    chat_overlay.geometry("+300+100")  # Initial position
    chat_overlay.attributes("-topmost", True)

    # Allow window resizing before it's locked
    chat_overlay.resizable(True, True)  # Enable resizing

    chat_frame = tk.Frame(chat_overlay, bg="black")
    chat_frame.pack(fill="both", expand=True, padx=5, pady=5)

    chat_box = tk.Text(chat_frame, wrap="word", height=10, width=30, bg="black", fg="white", font=("Helvetica", 10))
    chat_box.pack(expand=True, fill="both")
    chat_box.insert("end", "Connecting to Twitch chat...\n")
    chat_box.config(state="disabled")

    return chat_overlay, chat_box


def lock_chat_position():
    global chat_locked
    chat_locked = True

# Twitch Chat Bot
class TwitchChatBot(commands.Bot):
    def __init__(self, chat_box):
        super().__init__(token=TWITCH_TOKEN, prefix="!", initial_channels=[TWITCH_CHANNEL])
        self.chat_box = chat_box

    async def event_ready(self):
        print(f"Connected to Twitch chat as {self.nick}")

    async def event_message(self, message):
        if message.author is None:
            return

        msg = f"{message.author.name}: {message.content}\n"

        # Update chat box in the Tkinter overlay
        self.chat_box.config(state="normal")
        self.chat_box.insert("end", msg)
        self.chat_box.yview("end")  # Auto-scroll
        self.chat_box.config(state="disabled")

# Function to run the Twitch bot in a thread
def run_twitch_chat(chat_box):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = TwitchChatBot(chat_box)
    loop.run_until_complete(bot.start())  # Ensures bot starts within the event loop

def select_scene(scene, window):
    global target_scene
    target_scene = scene
    lock_chat_position()
    chat_overlay.overrideredirect(True)  # Lock chat box in overlay mode
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
    if scene_name == target_scene:
        overlay.deiconify()  # Show overlay if selected scene is active
    else:
        overlay.withdraw()  # Hide overlay otherwise

# Function to run the OBS WebSocket connection
def run_websocket(overlay, canvas):
    def on_message(ws, message):
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

    def on_open(ws):
        print("Connected to OBS WebSocket.")

    ws = websocket.WebSocketApp(host,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close,
                                on_open=on_open)
    ws.run_forever()

if __name__ == "__main__":
    overlay, canvas = create_overlay()
    chat_overlay, chat_box = create_chat_overlay()

    # Start Twitch Chat in a separate thread
    threading.Thread(target=run_twitch_chat, args=(chat_box,), daemon=True).start()

    # Start OBS WebSocket connection in another thread
    threading.Thread(target=run_websocket, args=(overlay, canvas), daemon=True).start()

    overlay.mainloop()
    chat_overlay.mainloop()
