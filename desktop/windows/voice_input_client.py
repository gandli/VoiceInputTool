#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.
"""

import serial
import serial.tools.list_ports
import pyautogui
import time
import sys
import threading
from typing import Optional, List

class VoiceInputClient:
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device = None
        
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            # Look for common USB-to-serial adapters that might be used
            # In production, this should match the specific device VID/PID
            if any(keyword in port.description.lower() for keyword in ['usb', 'serial', 'ch340', 'cp210']):
                print(f"Found potential device: {port.device} - {port.description}")
                return port.device
                
        return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device."""
        device_port = self.find_voice_input_device()
        
        if not device_port:
            print("No VoiceInputTool device found. Please connect your phone via USB.")
            return False
            
        try:
            self.serial_port = serial.Serial(
                port=device_port,
                baudrate=9600,
                timeout=1,
                bytesize=8,
                parity='N',
                stopbits=1
            )
            self.connected_device = device_port
            print(f"Connected to VoiceInputTool on {device_port}")
            return True
            
        except serial.SerialException as e:
            print(f"Failed to connect to {device_port}: {e}")
            return False
    
    def listen_for_text(self):
        """Listen for incoming text from the device."""
        while self.is_running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    # Read line (assuming text is sent with newline terminator)
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if line:
                        print(f"Received text: {line}")
                        self.input_text_at_cursor(line)
                        
            except UnicodeDecodeError:
                print("Received invalid UTF-8 data, skipping...")
                continue
            except serial.SerialException as e:
                print(f"Serial communication error: {e}")
                break
            except Exception as e:
                print(f"Unexpected error: {e}")
                break
                
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position."""
        try:
            # Add a small delay to ensure we're ready to type
            time.sleep(0.1)
            
            # Type the text character by character
            pyautogui.typewrite(text, interval=0.01)
            
            print(f"Successfully input text at cursor position")
            
        except Exception as e:
            print(f"Failed to input text: {e}")
    
    def start(self):
        """Start the voice input client."""
        print("Starting Voice Input Tool - Windows Client")
        print("Waiting for VoiceInputTool device...")
        
        # Keep trying to connect until successful
        while not self.connect_to_device():
            time.sleep(2)
        
        self.is_running = True
        
        # Start listening thread
        listener_thread = threading.Thread(target=self.listen_for_text, daemon=True)
        listener_thread.start()
        
        print("Voice Input Tool is running! Speak into your phone and text will appear on your computer.")
        print("Press Ctrl+C to exit.")
        
        try:
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nShutting down Voice Input Tool...")
            self.stop()
    
    def stop(self):
        """Stop the voice input client."""
        self.is_running = False
        
        if self.serial_port:
            self.serial_port.close()
            print("Disconnected from VoiceInputTool device.")

def main():
    """Main entry point."""
    # Check if required dependencies are available
    try:
        import serial
        import pyautogui
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install dependencies with: pip install pyserial pyautogui")
        sys.exit(1)
    
    client = VoiceInputClient()
    client.start()

if __name__ == "__main__":
    main()