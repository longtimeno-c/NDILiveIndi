import ctypes
import tkinter as tk
from tkinter import font as tkFont
import websocket
import json
import threading
import base64
import hashlib
import uuid
import asyncio
import time
import aiohttp
import keyboard
from twitchio.ext import commands

# Twitch Configuration
TWITCH_CHANNEL = "twitchusername"  # Change this to your Twitch channel name
TWITCH_TOKEN = "oauth:twitchaccess"  # Generate at https://twitchtokengenerator.com/

# YouTube Configuration
YOUTUBE_API_KEY = "cloud-key"  # Get from Google Developer Console
YOUTUBE_CHANNEL_ID = "channel-key"  # Find from YouTube channel URL
YOUTUBE_LIVE_CHAT_ID = None  # Will be fetched dynamically

# OBS WebSocket Configuration
host = "ws://ip:port"  # Change to the IP and port of the OBS WebSocket server
password = "WSPasswrd"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup
chat_locked = False  # Track if the chat box should be locked
ws_connection = None # Global websocket connection 
hotkey_registered = False  # Track if F8 hotkey is registered

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
    chat_box.insert("end", "Connecting to Twitch and YouTube chat...\n")
    chat_box.config(state="disabled")

    # Define color tags
    chat_box.tag_configure("twitch", foreground="white", background="purple")  # Twitch messages highlighted
    chat_box.tag_configure("youtube", foreground="white", background="red")  # YouTube messages highlighted

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
        msg = f"Twitch | {message.author.name}: {message.content}\n"
        self.update_chat_box(msg, "twitch")

    def update_chat_box(self, msg, tag):
        """Insert a message into the chat box with color formatting."""
        self.chat_box.config(state="normal")
        self.chat_box.insert("end", msg, tag)
        self.chat_box.yview("end")  # Auto-scroll
        self.chat_box.config(state="disabled")

# Function to run the Twitch bot in a thread
def run_twitch_chat(chat_box):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    bot = TwitchChatBot(chat_box)
    loop.run_until_complete(bot.start())  # Ensures bot starts within the event loop

# YouTube Chat Fetcher with Auto-Retry
class YouTubeChatFetcher:
    def __init__(self, chat_box):
        self.chat_box = chat_box
        self.running = True
        self.live_chat_id = None
        self.retry_interval = 30  # Retry every 30 seconds
        self.api_key = YOUTUBE_API_KEY
        self.channel_id = YOUTUBE_CHANNEL_ID
        self.processed_message_ids = set()  # Track processed message IDs

    async def get_live_chat_id(self):
        """Retrieve the Live Chat ID for the current live stream, retrying every 30s if not found."""
        while self.running:
            search_url = f"https://www.googleapis.com/youtube/v3/search?part=id,snippet&channelId={self.channel_id}&eventType=live&type=video&key={self.api_key}"

            async with aiohttp.ClientSession() as session:
                async with session.get(search_url) as response:
                    search_response = await response.json()

            if "items" in search_response and search_response["items"]:
                video_id = None
                for item in search_response["items"]:
                    if item["snippet"]["liveBroadcastContent"] == "live":
                        video_id = item["id"]["videoId"]
                        break

                if video_id:
                    chat_url = f"https://www.googleapis.com/youtube/v3/videos?part=liveStreamingDetails&id={video_id}&key={self.api_key}"

                    async with aiohttp.ClientSession() as session:
                        async with session.get(chat_url) as response:
                            chat_response = await response.json()

                    if "items" in chat_response and chat_response["items"]:
                        self.live_chat_id = chat_response["items"][0]["liveStreamingDetails"]["activeLiveChatId"]
                        print(f"✅ Live Chat ID Found: {self.live_chat_id}")
                        return
                    else:
                        print("❌ Live stream found, but no active chat detected.")
                else:
                    print("❌ No live video found.")
            else:
                print("❌ No active YouTube live stream found. Retrying in 30 seconds...")

            await asyncio.sleep(self.retry_interval)  # Async wait before retrying

    async def fetch_chat_messages(self):
        """Continuously fetch live chat messages from YouTube."""
        await self.get_live_chat_id()  # Wait until a live chat ID is found

        if not self.live_chat_id:
            print("❌ No live chat available. Exiting chat fetcher.")
            return

        url = f"https://www.googleapis.com/youtube/v3/liveChat/messages?liveChatId={self.live_chat_id}&part=snippet,authorDetails&key={self.api_key}"

        while self.running:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    chat_response = await response.json()

            if "items" in chat_response:
                for item in chat_response["items"]:
                    message_id = item["id"]  # Unique message ID

                    # Only process new messages
                    if message_id in self.processed_message_ids:
                        continue
                    self.processed_message_ids.add(message_id)  # Mark message as processed

                    author = item["authorDetails"]["displayName"]
                    message = item["snippet"]["displayMessage"]
                    msg = f"YouTube | {author}: {message}\n"
                    self.update_chat_box(msg, "youtube")
            
            await asyncio.sleep(5)  # Wait before fetching the next batch of messages

    def update_chat_box(self, msg, tag):
        """Insert a message into the chat box with color formatting."""
        self.chat_box.config(state="normal")
        self.chat_box.insert("end", msg, tag)
        self.chat_box.yview("end")  # Auto-scroll
        self.chat_box.config(state="disabled")

    def stop(self):
        """Stop fetching chat messages."""
        self.running = False

# Function to run YouTube chat in a thread
def run_youtube_chat(chat_box):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    fetcher = YouTubeChatFetcher(chat_box)
    loop.run_until_complete(fetcher.fetch_chat_messages())

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
    overlay, canvas = create_overlay()
    chat_overlay, chat_box = create_chat_overlay()

    # Start Twitch Chat in a separate thread
    threading.Thread(target=run_twitch_chat, args=(chat_box,), daemon=True).start()

     # Start YouTube Chat in a separate thread with retry logic
    threading.Thread(target=run_youtube_chat, args=(chat_box,), daemon=True).start()

    # Start OBS WebSocket connection in another thread
    threading.Thread(target=run_websocket, args=(overlay, canvas), daemon=True).start()

    overlay.mainloop()
    chat_overlay.mainloop()
