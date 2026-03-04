#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.

Features:
- Auto-reconnect on USB disconnect
- Configurable settings via config.json
- Logging to file
- Support for Unicode/Chinese text input
"""

import serial
import serial.tools.list_ports
import time
import sys
import threading
import os
import json
import logging
from typing import Optional, List, Dict
from pathlib import Path

# Try to import pynput for better Unicode support, fallback to pyautogui
try:
    from pynput.keyboard import Controller as KeyboardController
    from pynput import keyboard
    PYINPUT_AVAILABLE = True
except ImportError:
    PYINPUT_AVAILABLE = False
    import pyautogui

# Default configuration
DEFAULT_CONFIG = {
    "serial": {
        "baudrate": 9600,
        "timeout": 1,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "retry_interval": 2,
        "max_retries": 0  # 0 = infinite retries
    },
    "input": {
        "type_interval": 0.01,
        "enable_clipboard": True  # Use clipboard for Chinese text
    },
    "logging": {
        "level": "INFO",
        "file": "voice_input_client.log"
    }
}

class Config:
    """Configuration manager for VoiceInputTool client."""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load configuration from file or use defaults."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    user_config = json.load(f)
                # Merge with defaults
                config = DEFAULT_CONFIG.copy()
                self._merge_config(config, user_config)
                return config
            except Exception as e:
                print(f"Failed to load config: {e}, using defaults")
        
        return DEFAULT_CONFIG.copy()
    
    def _merge_config(self, base: Dict, user: Dict):
        """Recursively merge user config into base config."""
        for key, value in user.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge_config(base[key], value)
            else:
                base[key] = value
    
    def get(self, *keys, default=None):
        """Get nested config value."""
        result = self.config
        for key in keys:
            if isinstance(result, dict) and key in result:
                result = result[key]
            else:
                return default
        return result


class VoiceInputClient:
    def __init__(self, config_path: str = "config.json"):
        self.config = Config(config_path)
        self._setup_logging()
        
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device = None
        self.retry_count = 0
        
        # Keyboard controller for text input
        if PYINPUT_AVAILABLE:
            self.keyboard = KeyboardController()
            self.logger.info("Using pynput for keyboard input (Unicode supported)")
        else:
            self.logger.warning("pynput not available, falling back to pyautogui")
    
    def _setup_logging(self):
        """Setup logging to file and console."""
        log_level = self.config.get("logging", "level", default="INFO")
        log_file = self.config.get("logging", "file", default="voice_input_client.log")
        
        # Create logger
        self.logger = logging.getLogger("VoiceInputTool")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler
        try:
            file_handler = logging.FileHandler(log_file, encoding='utf-8')
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        self.logger.addHandler(console_handler)
    
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        ports = serial.tools.list_ports.comports()
        
        for port in ports:
            # Look for common USB-to-serial adapters
            description = port.description.lower() if port.description else ""
            device = port.device
            
            # Check for known USB serial adapters
            if any(keyword in description for keyword in ['usb', 'serial', 'ch340', 'cp210', 'ftdi', 'arduino']):
                self.logger.info(f"Found potential device: {device} - {port.description}")
                return device
                
        self.logger.debug("No VoiceInputTool device found")
        return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device."""
        device_port = self.find_voice_input_device()
        
        if not device_port:
            self.logger.info("No VoiceInputTool device found. Please connect your phone via USB.")
            return False
        
        # Already connected to same device
        if self.serial_port and self.serial_port.is_open and self.connected_device == device_port:
            return True
        
        # Close existing connection if different device
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception as e:
                self.logger.warning(f"Error closing previous connection: {e}")
        
        try:
            serial_config = self.config.get("serial")
            self.serial_port = serial.Serial(
                port=device_port,
                baudrate=serial_config.get("baudrate", 9600),
                timeout=serial_config.get("timeout", 1),
                bytesize=serial_config.get("bytesize", 8),
                parity=serial_config.get("parity", 'N'),
                stopbits=serial_config.get("stopbits", 1)
            )
            self.connected_device = device_port
            self.retry_count = 0
            self.logger.info(f"Connected to VoiceInputTool on {device_port}")
            return True
            
        except serial.SerialException as e:
            self.logger.error(f"Failed to connect to {device_port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the device."""
        if self.serial_port:
            try:
                if self.serial_port.is_open:
                    self.serial_port.close()
                self.logger.info("Disconnected from device")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self.serial_port = None
                self.connected_device = None
    
    def listen_for_text(self):
        """Listen for incoming text from the device."""
        while self.is_running:
            # Check if connected
            if not self.serial_port or not self.serial_port.is_open:
                self._attempt_reconnect()
                if not self.serial_port or not self.serial_port.is_open:
                    time.sleep(self.config.get("serial", "retry_interval", default=2))
                    continue
            
            try:
                if self.serial_port.in_waiting > 0:
                    # Read line (assuming text is sent with newline terminator)
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if line:
                        self.logger.info(f"Received text: {line}")
                        self.input_text_at_cursor(line)
                        
            except UnicodeDecodeError:
                self.logger.warning("Received invalid UTF-8 data, skipping...")
                continue
            except serial.SerialException as e:
                self.logger.error(f"Serial communication error: {e}")
                self.disconnect()
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                break
                
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the device."""
        serial_config = self.config.get("serial")
        max_retries = serial_config.get("max_retries", 0)
        
        if max_retries > 0 and self.retry_count >= max_retries:
            self.logger.error(f"Max retries ({max_retries}) reached, giving up")
            self.is_running = False
            return
        
        self.retry_count += 1
        self.logger.info(f"Attempting to reconnect (attempt {self.retry_count})...")
        
        if self.connect_to_device():
            self.logger.info("Reconnected successfully")
        else:
            self.logger.debug("Reconnect failed, will retry...")
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position."""
        try:
            # Add a small delay to ensure we're ready to type
            time.sleep(0.1)
            
            input_config = self.config.get("input")
            
            # Check if we should use clipboard method for better Unicode support
            if input_config.get("enable_clipboard", True):
                self._input_via_clipboard(text)
            elif PYINPUT_AVAILABLE:
                self._input_via_pynput(text)
            else:
                self._input_via_pyautogui(text)
            
            self.logger.info("Successfully input text at cursor position")
            
        except Exception as e:
            self.logger.error(f"Failed to input text: {e}")
    
    def _input_via_clipboard(self, text: str):
        """Input text via clipboard (best for Unicode/Chinese)."""
        try:
            # Save current clipboard
            import pyperclip
            original_clipboard = pyperclip.paste()
            
            # Copy new text to clipboard
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # Paste using Ctrl+V
            if PYINPUT_AVAILABLE:
                self.keyboard.press(keyboard.Key.ctrl)
                self.keyboard.press('v')
                self.keyboard.release('v')
                self.keyboard.release(keyboard.Key.ctrl)
            else:
                pyautogui.hotkey('ctrl', 'v')
            
            time.sleep(0.05)
            
            # Restore original clipboard (optional)
            # pyperclip.copy(original_clipboard)
            
        except ImportError:
            self.logger.warning("pyperclip not available, falling back to keyboard input")
            self._input_via_pynput(text)
        except Exception as e:
            self.logger.warning(f"Clipboard method failed: {e}, trying keyboard")
            self._input_via_pynput(text)
    
    def _input_via_pynput(self, text: str):
        """Input text using pynput (supports Unicode)."""
        with self.keyboard.pressed(keyboard.Key.shift):
            pass  # Not needed for typing
        
        self.keyboard.type(text)
    
    def _input_via_pyautogui(self, text: str):
        """Input text using pyautogui (fallback)."""
        interval = self.config.get("input", "type_interval", default=0.01)
        pyautogui.typewrite(text, interval=interval)
    
    def start(self):
        """Start the voice input client."""
        self.logger.info("Starting Voice Input Tool - Windows Client")
        self.logger.info("Waiting for VoiceInputTool device...")
        
        # Keep trying to connect until successful
        serial_config = self.config.get("serial")
        max_retries = serial_config.get("max_retries", 0)
        
        while not self.connect_to_device():
            if max_retries > 0 and self.retry_count >= max_retries:
                self.logger.error("Max connection retries reached, exiting")
                return
            
            time.sleep(serial_config.get("retry_interval", 2))
            self.retry_count += 1
        
        self.is_running = True
        
        # Start listening thread
        listener_thread = threading.Thread(target=self.listen_for_text, daemon=True)
        listener_thread.start()
        
        self.logger.info("Voice Input Tool is running! Speak into your phone and text will appear on your computer.")
        self.logger.info("Press Ctrl+C to exit.")
        
        try:
            # Keep main thread alive
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("\nShutting down Voice Input Tool...")
            self.stop()
    
    def stop(self):
        """Stop the voice input client."""
        self.is_running = False
        self.disconnect()
        self.logger.info("Voice Input Tool stopped")


def main():
    """Main entry point."""
    # Check if required dependencies are available
    try:
        import serial
    except ImportError as e:
        print(f"Missing required dependency: {e}")
        print("Please install dependencies with: pip install pyserial")
        sys.exit(1)
    
    # Check for optional dependencies
    missing_optional = []
    if not PYINPUT_AVAILABLE:
        missing_optional.append("pynput")
    try:
        import pyperclip
    except ImportError:
        missing_optional.append("pyperclip")
    
    if missing_optional:
        print(f"Note: For better Unicode/Chinese support, install: pip install {' '.join(missing_optional)}")
    
    # Create default config if not exists
    if not os.path.exists("config.json"):
        try:
            with open("config.json", 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            print("Created default config.json")
        except Exception as e:
            print(f"Warning: Could not create config.json: {e}")
    
    client = VoiceInputClient()
    client.start()

if __name__ == "__main__":
    main()