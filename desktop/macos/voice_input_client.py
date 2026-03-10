#!/usr/bin/env python3
"""
Voice Input Tool - macOS Client
Receives text from Android device via USB serial and inputs it at cursor position.

Features:
- Auto-reconnect on USB disconnect
- Configurable settings via config.json
- Logging to file
- Support for Unicode/Chinese text input
- macOS-specific optimizations
- Security improvements
"""

import serial
import serial.tools.list_ports
import time
import sys
import threading
import os
import json
import logging
from typing import Optional, Dict
from pathlib import Path
import platform

# Import platform-specific libraries
try:
    from pynput.keyboard import Controller as KeyboardController
    from pynput import keyboard
    PYINPUT_AVAILABLE = True
except ImportError:
    PYINPUT_AVAILABLE = False
    try:
        import pyautogui
        PYAUTOGUI_AVAILABLE = True
    except ImportError:
        PYAUTOGUI_AVAILABLE = False
        PYINPUT_AVAILABLE = True  # Will fail at runtime

# Security configuration
SECURITY_CONFIG = {
    "max_line_length": 1024,
    "timeout": 30.0,
    "max_reconnect_attempts": 5,
    "input_validation_enabled": True,
}

# Default configuration
DEFAULT_CONFIG = {
    "serial": {
        "baudrate": 9600,
        "timeout": 1,
        "read_timeout": 1,
        "write_timeout": 1,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "retry_interval": 2,
        "max_retries": 0,
        "buffer_size": 1024,
    },
    "input": {
        "type_interval": 0.01,
        "enable_clipboard": True,
        "delay_before_input": 0.1,
        "validate_input": True,
    },
    "logging": {
        "level": "INFO",
        "file": "voice_input_client_mac.log",
        "max_size_mb": 10,
        "backup_count": 5,
    },
    "security": {
        "max_line_length": SECURITY_CONFIG["max_line_length"],
        "input_validation_enabled": True,
    }
}


class SecurityUtils:
    """Security utilities for input validation."""
    
    @staticmethod
    def validate_input(text: str, max_length: int = 1024) -> tuple:
        """Validate input text for security."""
        if not isinstance(text, str):
            return False, "Invalid input type"
        
        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        if '\0' in text:
            return False, "Input contains null bytes"
        
        return True, text


class VoiceInputClient:
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self._setup_logging()
        
        self.serial_port = None
        self.is_running = False
        self.connected_device = None
        self.retry_count = 0
        
        # Keyboard controller
        if PYINPUT_AVAILABLE:
            try:
                self.keyboard = KeyboardController()
                self.logger.info("Using pynput for keyboard input (Unicode supported)")
            except Exception as e:
                self.logger.warning(f"Could not initialize pynput: {e}")
        elif PYAUTOGUI_AVAILABLE:
            self.logger.warning("Using pyautogui for keyboard input")
        else:
            raise RuntimeError("No keyboard library available")
    
    def _load_config(self, config_path: str) -> dict:
        """Load configuration from file or use defaults."""
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self._log_warning(f"Failed to load config: {e}, using defaults")
        
        return DEFAULT_CONFIG.copy()
    
    def _setup_logging(self):
        """Setup logging to file and console."""
        log_level = self.config.get("logging", {}).get("level", "INFO")
        log_file = self.config.get("logging", {}).get("file", "voice_input_client_mac.log")
        
        self.logger = logging.getLogger("VoiceInputToolMac")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler
        try:
            from logging.handlers import RotatingFileHandler
            log_dir = Path.home() / ".voice_input_tool"
            log_dir.mkdir(exist_ok=True)
            
            file_handler = RotatingFileHandler(
                log_dir / log_file,
                maxBytes=self.config.get("logging", {}).get("max_size_mb", 10) * 1024 * 1024,
                backupCount=self.config.get("logging", {}).get("backup_count", 5),
                encoding='utf-8'
            )
            file_handler.setFormatter(
                logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
            )
            self.logger.addHandler(file_handler)
        except Exception as e:
            self._log_warning(f"Could not create log file: {e}")
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(
            logging.Formatter('%(levelname)s: %(message)s')
        )
        self.logger.addHandler(console_handler)
        
        self.logger.info(f"macOS client initialized (ID: {platform.node()})")
    
    def _log_warning(self, message: str):
        """Log warning message."""
        if hasattr(self, 'logger'):
            self.logger.warning(message)
        else:
            print(f"WARNING: {message}")
    
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        try:
            ports = serial.tools.list_ports.comports()
            
            # Common macOS USB serial device patterns
            device_patterns = [
                'usbserial', 'usbmodem', 'cu.usbserial', 'tty.usbserial',
                'usbserial', 'cdcacm', 'tty.usbmodem'
            ]
            
            for port in ports:
                description = port.description.lower() if port.description else ""
                device = port.device
                
                # Check for known USB serial adapters
                if any(pattern in device.lower() for pattern in device_patterns):
                    self.logger.info(f"Found potential device: {device} - {port.description}")
                    return device
                
                # Also check for generic USB serial
                if 'usb' in description.lower():
                    self.logger.debug(f"Found USB device: {device}")
                    return device
                    
            self.logger.debug("No VoiceInputTool device found")
            return None
        except Exception as e:
            self.logger.error(f"Error scanning ports: {e}")
            return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device."""
        device_port = self.find_voice_input_device()
        
        if not device_port:
            self.logger.info("No VoiceInputTool device found. Please connect your phone via USB.")
            return False
        
        # Close existing connection
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.close()
            except Exception as e:
                self.logger.warning(f"Error closing previous connection: {e}")
        
        try:
            serial_config = self.config.get("serial", {})
            self.serial_port = serial.Serial(
                port=device_port,
                baudrate=serial_config.get("baudrate", 9600),
                timeout=serial_config.get("timeout", 1),
                read_timeout=serial_config.get("read_timeout", 1),
                write_timeout=serial_config.get("write_timeout", 1),
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
            
            # Provide helpful suggestions
            if "Permission denied" in str(e):
                self.logger.error("Permission denied. Try:")
                self.logger.error("  sudo usermod -aG dialout $USER")
                self.logger.error("  Then log out and log back in")
            
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting: {e}")
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
            if not self.serial_port or not self.serial_port.is_open:
                self._attempt_reconnect()
                if not self.serial_port or not self.serial_port.is_open:
                    time.sleep(self.config.get("serial", {}).get("retry_interval", 2))
                    continue
            
            try:
                if self.serial_port.in_waiting > 0:
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
                time.sleep(0.1)
                
            time.sleep(0.1)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the device."""
        serial_config = self.config.get("serial", {})
        max_retries = serial_config.get("max_retries", 0)
        
        if max_retries > 0 and self.retry_count >= max_retries:
            self.logger.error(f"Max retries ({max_retries}) reached")
            self.is_running = False
            return
        
        self.retry_count += 1
        self.logger.info(f"Attempting to reconnect (attempt {self.retry_count})...")
        
        if self.connect_to_device():
            self.logger.info("Reconnected successfully")
            self.retry_count = 0
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position."""
        try:
            time.sleep(self.config.get("input", {}).get("delay_before_input", 0.1))
            
            input_config = self.config.get("input", {})
            
            if input_config.get("enable_clipboard", True):
                self._input_via_clipboard(text)
            elif self.keyboard:
                self._input_via_pynput(text)
            elif hasattr(self, 'pyautogui'):
                self._input_via_pyautogui(text)
            
            self.logger.info("Successfully input text at cursor position")
            
        except Exception as e:
            self.logger.error(f"Failed to input text: {e}")
    
    def _input_via_clipboard(self, text: str):
        """Input text via clipboard (best for Unicode/Chinese)."""
        try:
            import pyperclip
            original_clipboard = pyperclip.paste()
            
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # On macOS, use Cmd+V
            if self.keyboard:
                with self.keyboard.pressed(keyboard.Key.cmd):
                    self.keyboard.press('v')
                    self.keyboard.release('v')
            elif hasattr(self, 'pyautogui'):
                self.pyautogui.hotkey('cmd', 'v')
            
            time.sleep(0.05)
            
            # Restore clipboard
            pyperclip.copy(original_clipboard)
            
        except ImportError:
            self.logger.warning("pyperclip not available, falling back to keyboard")
            self._input_via_pynput(text)
        except Exception as e:
            self.logger.warning(f"Clipboard method failed: {e}")
            self._input_via_pynput(text)
    
    def _input_via_pynput(self, text: str):
        """Input text using pynput."""
        self.keyboard.type(text)
    
    def _input_via_pyautogui(self, text: str):
        """Input text using pyautogui."""
        interval = self.config.get("input", {}).get("type_interval", 0.01)
        self.pyautogui.typewrite(text, interval=interval)
    
    def start(self):
        """Start the voice input client."""
        self.logger.info("Starting Voice Input Tool - macOS Client")
        
        # Keep trying to connect
        serial_config = self.config.get("serial", {})
        max_retries = serial_config.get("max_retries", 0)
        
        while not self.connect_to_device():
            if max_retries > 0 and self.retry_count >= max_retries:
                self.logger.error("Max connection retries reached")
                return
            
            time.sleep(serial_config.get("retry_interval", 2))
            self.retry_count += 1
        
        self.is_running = True
        
        # Start listening thread
        listener_thread = threading.Thread(
            target=self.listen_for_text,
            daemon=True
        )
        listener_thread.start()
        
        self.logger.info("Voice Input Tool is running! Speak into your phone.")
        self.logger.info("Press Ctrl+C to exit.")
        
        try:
            while self.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
            self.stop()
    
    def stop(self):
        """Stop the voice input client."""
        self.is_running = False
        self.disconnect()
        self.logger.info("Voice Input Tool stopped")


def main():
    """Main entry point."""
    print(f"Voice Input Tool - macOS Client")
    print(f"Platform: {platform.system()} {platform.release()}")
    print()
    
    # Check dependencies
    try:
        import serial
    except ImportError:
        print("Error: pyserial is required. Install with: pip install pyserial")
        sys.exit(1)
    
    if not (PYINPUT_AVAILABLE or PYAUTOGUI_AVAILABLE):
        print("Error: pynput or pyautogui is required for keyboard control")
        print("Install with: pip install pynput")
        sys.exit(1)
    
    try:
        client = VoiceInputClient()
        client.start()
    except KeyboardInterrupt:
        print("\nInterrupted")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
