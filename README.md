# NDILiveIndi: A Live Indicator for Multi-PC NDI Stream Setups

## Overview
**NDILiveIndi** is a utility designed for **multi-PC streaming setups** using **OBS and NDI technology**. It provides a **live indicator** that activates when a specific scene or source is active on the main streaming computer. Additionally, it integrates **Twitch and YouTube chat overlays**, making it ideal for streamers handling **multi-camera, gameplay, and live event setups**.

## Features
- **Dynamic Scene Selection:**  
  - Automatically detects and lists all available scenes from OBS on the main streaming PC.
  - Users can select which scene to monitor through a simple GUI.
  
- **Live Indicator Overlay:**  
  - Displays a **"LIVE"** indicator on the source PC when the selected scene is active.
  - Pulsating effect to enhance visibility.

- **Multi-PC Compatibility:**  
  - Works seamlessly with **NDI-enabled setups** where multiple computers send video feeds to the main streaming PC.

- **Twitch & YouTube Chat Integration:**  
  - Displays chat messages in an **overlay**.
  - Supports **Twitch** chat via a bot.
  - Fetches **YouTube Live Chat** dynamically, with automatic retries if no live stream is found.

- **Auto-Reconnect & Robust WebSocket Communication:**  
  - Automatically reconnects to OBS WebSocket if the connection drops.

## Requirements
### Software
- **OBS Studio** with the **OBS WebSocket Plugin** installed (for remote control).
- **Python** environment with required dependencies installed.

### Hardware
- At least **two computers**:
  - **Main Streaming PC:** Runs OBS and manages the stream.
  - **Source PCs:** Send video feeds via **NDI** and display the **LIVE** indicator.
- **Network Connectivity:**  
  - All PCs must be on the **same network** to support NDI streaming and WebSocket communication.

## Installation & Setup
### 1. Install Dependencies
Ensure you have **Python** installed, then install the required libraries:
```
pip install websocket-client requests aiohttp twitchio
```
### 2. Install & Configure OBS WebSocket Plugin
- Download the **OBS WebSocket plugin** from [here](https://github.com/obsproject/obs-websocket).
- Enable the WebSocket server in OBS:
  - **Tools → WebSocket Server Settings**
  - Enable WebSocket
  - Set a **password** for security.

### 3. Configure the Script
Modify the **configuration variables** in the script:

#### OBS WebSocket Settings
```
host = "ws://<OBS-PC-IP>:<PORT>"  # Replace with the OBS WebSocket IP and Port
password = "your_OBS_websocket_password"
```
#### Twitch Chat Configuration
```
TWITCH_CHANNEL = "your_twitch_channel"
TWITCH_TOKEN = "oauth:your_twitch_oauth_token"  # Generate from https://twitchtokengenerator.com/
```
#### YouTube Live Chat Configuration
```
YOUTUBE_API_KEY = "your_google_cloud_api_key"
YOUTUBE_CHANNEL_ID = "your_youtube_channel_id"
```
### 4. Run the Script
Run the script on each **source PC** where you want the **LIVE** indicator to appear:

## Usage
1. **Select the Scene to Monitor:**  
   - When the script starts, it will retrieve scenes from OBS.
   - A popup will appear, allowing you to **select the scene** that will trigger the live indicator.
  
2. **Monitor the Stream:**  
   - The selected PC will display a **LIVE indicator** whenever the chosen scene is active in OBS.
   - The **chat overlay** will fetch messages from **Twitch & YouTube**.

3. **Automatic Handling:**  
   - The script will **reconnect automatically** if OBS WebSocket disconnects.
   - YouTube live chat will retry fetching messages every **30 seconds** if no live stream is found.

## Troubleshooting
### OBS WebSocket Not Connecting?
- Ensure OBS WebSocket is **enabled** and the correct **IP & Port** are configured.
- Check that the WebSocket **password matches** the one in the script.

### Twitch or YouTube Chat Not Appearing?
- Verify that the **Twitch OAuth token** is correct.
- Ensure the **YouTube API key** is valid and linked to your channel.

### Live Indicator Not Appearing?
- Confirm that the **OBS scene name matches** the one selected in the script.
- Ensure that **NDI is properly configured** between PCs.

## License
**NDILiveIndi** is released under the **MIT License**. Feel free to modify and distribute it.
