# NDILiveIndi: A Live Indicator for Multi-PC NDI Stream Setups
## Overview
NDILiveIndi is a utility designed for multi-PC streaming setups using OBS and NDI technology. It provides a live indicator that activates when a specific scene or source is active on the main streaming computer. This tool is particularly useful for setups where multiple computers manage different elements of a broadcast, such as game streaming, live performances, or multi-camera setups.

## Features
Dynamic Scene Selection: Automatically detects and lists all available scenes from the OBS setup on the main streaming computer, allowing users to select which scene or source to monitor through a user-friendly interface.
Live Indicator Overlay: Displays a live indicator on the computer that is currently being used as the source in the stream whenever the selected scene is active.
Multi-PC Compatibility: Designed to work seamlessly in environments where multiple computers are connected via NDI for streaming purposes.
## Requirements
OBS Studio with the OBS WebSocket plugin installed to enable remote control capabilities.
Python environment with the necessary libraries installed (tkinter for the GUI and websocket-client for WebSocket communication).
At least two computers: One serving as the main streaming PC and others as sources, all connected in a network that supports NDI streaming.
## Setup and Operation
Install OBS WebSocket Plugin: Ensure that OBS Studio on the main streaming PC has the OBS WebSocket plugin installed and configured.
Configure IP and Password: Modify the script to include the IP address and WebSocket password of the main streaming PC to establish a secure connection.
Run the Script: Execute the script on each source PC where you want the live indicator to appear. The script will automatically connect to the main streaming PC, retrieve the list of available scenes, and prompt the user to select the source to monitor.
Select the Scene: Use the generated GUI to select the scene that, when live, will trigger the live indicator on the current PC.
Monitor the Stream: The live indicator will automatically display on the source PC whenever the selected scene is active on the main streaming PC.
## Use Case
This tool is perfect for live streamers who use multiple computers to manage different elements of their stream, such as gaming, chatting, or handling multimedia sources. It enhances control and awareness, ensuring smooth transitions and professional-quality streaming.