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
import logging
from typing import Optional, List
import json
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("voice_input_client.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class VoiceInputClient:
    def __init__(self):
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device = None
        self.config = self.load_config()
        
    def load_config(self) -> dict:
        """Load configuration from file or return defaults."""
        config_path = "voice_input_config.json"
        default_config = {
            "baudrate": 9600,
            "timeout": 1,
            "auto_reconnect": True,
            "reconnect_interval": 5,
            "input_delay": 0.1,
            "typing_interval": 0.01,
            "device_identifiers": ["usb", "serial", "ch340", "cp210", "ftdi"]
        }
        
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    # Merge with defaults to ensure all keys exist
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                    logger.info(f"Loaded configuration from {config_path}")
                    return config
            except Exception as e:
                logger.error(f"Failed to load config file: {e}. Using defaults.")
                
        logger.info("Using default configuration")
        return default_config
    
    def save_config(self):
        """Save current configuration to file."""
        try:
            with open("voice_input_config.json", 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved successfully")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            # Check against configured device identifiers
            port_desc_lower = port.description.lower()
            if any(keyword in port_desc_lower for keyword in self.config["device_identifiers"]):
                logger.info(f"Found potential device: {port.device} - {port.description}")
                return port.device
                
        return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device."""
        device_port = self.find_voice_input_device()
        
        if not device_port:
            logger.warning("No VoiceInputTool device found. Please connect your phone via USB.")
            return False
            
        try:
            self.serial_port = serial.Serial(
                port=device_port,
                baudrate=self.config["baudrate"],
                timeout=self.config["timeout"],
                bytesize=8,
                parity='N',
                stopbits=1
            )
            self.connected_device = device_port
            logger.info(f"Connected to VoiceInputTool on {device_port}")
            return True
            
        except serial.SerialException as e:
            logger.error(f"Failed to connect to {device_port}: {e}")
            return False
    
    def listen_for_text(self):
        """Listen for incoming text from the device."""
        while self.is_running and self.serial_port and self.serial_port.is_open:
            try:
                if self.serial_port.in_waiting > 0:
                    # Read line (assuming text is sent with newline terminator)
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if line:
                        logger.info(f"Received text: {line}")
                        self.input_text_at_cursor(line)
                        
            except UnicodeDecodeError:
                logger.warning("Received invalid UTF-8 data, skipping...")
                continue
            except serial.SerialException as e:
                logger.error(f"Serial communication error: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break
                
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position."""
        try:
            # Add a small delay to ensure we're ready to type
            time.sleep(self.config["input_delay"])
            
            # Type the text character by character
            pyautogui.typewrite(text, interval=self.config["typing_interval"])
            
            logger.info(f"Successfully input text at cursor position")
            
        except Exception as e:
            logger.error(f"Failed to input text: {e}")
    
    def start(self):
        """Start the voice input client."""
        logger.info("Starting Voice Input Tool - Windows Client")
        logger.info("Waiting for VoiceInputTool device...")
        
        # Keep trying to connect until successful
        while not self.connect_to_device():
            if not self.config["auto_reconnect"]:
                logger.error("Auto-reconnect disabled. Exiting.")
                return
            time.sleep(self.config["reconnect_interval"])
        
        self.is_running = True
        
        # Start listening thread
        listener_thread = threading.Thread(target=self.listen_for_text, daemon=True)
        listener_thread.start()
        
        logger.info("Voice Input Tool is running! Speak into your phone and text will appear on your computer.")
        logger.info("Press Ctrl+C to exit.")
        
        try:
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\nShutting down Voice Input Tool...")
            self.stop()
    
    def stop(self):
        """Stop the voice input client."""
        self.is_running = False
        
        if self.serial_port:
            self.serial_port.close()
            logger.info("Disconnected from VoiceInputTool device.")

def main():
    """Main entry point."""
    # Check if required dependencies are available
    try:
        import serial
        import pyautogui
    except ImportError as e:
        logger.error(f"Missing required dependency: {e}")
        print("Please install dependencies with: pip install pyserial pyautogui")
        sys.exit(1)
    
    client = VoiceInputClient()
    client.start()

if __name__ == "__main__":
    main()