import tkinter as tk
from tkinter import font as tkFont
from tkinter import font as tkfont
import websocket
import json
import threading
import base64
import hashlib
import uuid

# Configuration
host = "ws://obshost:obsport"  # Change to the IP and port of the OBS WebSocket server
password = "obsWSpassword"  # Your OBS WebSocket password
target_scene = None  # This will store the scene selected from the popup

def get_auth_response(password, secret, salt):
    passhash = base64.b64encode(hashlib.sha256((password + salt).encode('utf-8')).digest()).decode('utf-8')
    auth_response = base64.b64encode(hashlib.sha256((passhash + secret).encode('utf-8')).digest()).decode('utf-8')
    return auth_response

def create_overlay():
    overlay = tk.Tk()
    overlay.title("Live Indicator")
    overlay.geometry("+{}+{}".format(overlay.winfo_screenwidth() - 150, 500))  # Slightly adjusted position for aesthetics
    overlay.attributes("-topmost", True)
    overlay.overrideredirect(True)
    overlay.attributes("-alpha", 0.85)  # Adjust transparency of the window

    # Use a more modern looking canvas with rounded corners
    canvas = tk.Canvas(overlay, width=100, height=50, bg='red', bd=0, highlightthickness=0)
    canvas.pack()

    # Create a rounded rectangle (if your system supports it)
    try:
        canvas.create_rectangle(10, 10, 90, 40, fill="red", outline="red", width=2, smooth=True)
    except:
        canvas.create_rectangle(10, 10, 90, 40, fill="red", outline="red", width=2)  # Fallback for older Tk versions

    # Use a better font and styling for the text
    live_font = tkfont.Font(family="Helvetica", size=12, weight="bold")
    canvas.create_text(50, 25, text="LIVE", fill="white", font=live_font)

    # Adding a pulsating effect to the "LIVE" text
    def pulsate():
        current_color = canvas.itemcget(live_text, "fill")
        new_color = "white" if current_color == "red" else "red"
        canvas.itemconfig(live_text, fill=new_color)
        overlay.after(1000, pulsate)  # Change color every second

    live_text = canvas.create_text(50, 25, text="LIVE", fill="white", font=live_font)
    pulsate()  # Start the pulsating effect

    return overlay, canvas

def show_scene_selection(scenes, overlay):
    print("Showing scene selection popup...")
    selection_window = tk.Toplevel(overlay)
    selection_window.title("Select Scene")
    selection_window.geometry("600x400+100+100")  # Adjusted size for tile display
    selection_window.resizable(False, False)
    selection_window.configure(background='#2D2D2D')  # Dark background for a modern look

    frame = tk.Frame(selection_window, bg='#2D2D2D')
    frame.pack(expand=True, fill='both', padx=20, pady=20)  # Padding for aesthetics

    # Styling
    button_style = {'font': ('Helvetica', 12, 'bold'), 'background': '#4CAF50', 'foreground': 'white', 'activebackground': '#66BB6A', 'activeforeground': 'white', 'relief': 'flat', 'bd': 0, 'highlightthickness': 0}
    hover_style = {'background': '#388E3C'}

    def on_enter(e, btn):
        btn.config(background=hover_style['background'])  # Change to hover background color

    def on_leave(e, btn):
        btn.config(background=button_style['background'])  # Revert to normal background color

    # Create a button for each scene with modern styling and hover effects
    num_cols = 3
    num_rows = (len(scenes) + num_cols - 1) // num_cols
    button_width = 180  # Adjusted for internal padding
    button_height = 80

    for index, scene_name in enumerate(scenes):
        btn = tk.Button(frame, text=scene_name, command=lambda name=scene_name: set_scene(name, selection_window), **button_style)
        btn.grid(row=index // num_cols, column=index % num_cols, padx=10, pady=10, sticky='nsew', ipadx=button_width // 2 - 50, ipady=button_height // 2 - 25)
        btn.bind("<Enter>", lambda e, btn=btn: on_enter(e, btn))
        btn.bind("<Leave>", lambda e, btn=btn: on_leave(e, btn))

    # Ensuring the grid cells expand equally and buttons fill their cells
    for i in range(num_cols):
        frame.grid_columnconfigure(i, weight=1, uniform="group1")
    for i in range(num_rows):
        frame.grid_rowconfigure(i, weight=1, uniform="group1")

def set_scene(scene, window):
    global target_scene
    target_scene = scene
    print(f"Scene selected: {scene}")
    window.destroy()

def update_overlay_visibility(overlay, canvas, scene_name):
    if scene_name == target_scene:
        overlay.deiconify()  # Show the overlay if the selected scene is active
    else:
        overlay.withdraw()  # Hide the overlay otherwise

def run_websocket(overlay, canvas):
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
            overlay.after(0, lambda: show_scene_selection(scenes, overlay))
        elif data['op'] == 5 and data['d']['eventType'] == 'CurrentProgramSceneChanged':
            current_scene = data['d']['eventData']['sceneName']
            update_overlay_visibility(overlay, canvas, current_scene)

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

if __name__ == "__main__":
    overlay, canvas = create_overlay()
    threading.Thread(target=run_websocket, args=(overlay, canvas)).start()
    overlay.mainloop()
