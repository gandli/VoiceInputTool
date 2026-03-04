#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.

Features (Round 2):
- Auto-reconnect with exponential backoff
- Log rotation for persistent debugging
- Enhanced Chinese/Unicode input stability with retry mechanism
- Text post-processing (auto-punctuation, auto-enter)
- Command-line arguments support
- Better device detection
"""

import serial
import serial.tools.list_ports
import time
import sys
import threading
import os
import json
import logging
import argparse
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
        "max_retries": 0,
        "exponential_backoff": True,
        "max_retry_interval": 60
    },
    "input": {
        "type_interval": 0.01,
        "enable_clipboard": True,
        "retry_count": 3,
        "retry_delay": 0.2,
        "auto_enter_after_ms": 0,
        "post_process": {
            "trim_whitespace": True,
            "auto_punctuate": False,
            "punctuation_marks": "。！？；："
        }
    },
    "logging": {
        "level": "INFO",
        "file": "voice_input_client.log",
        "max_bytes": 1048576,  # 1MB
        "backup_count": 3
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
    
    def update(self, **kwargs):
        """Update config with key-value pairs."""
        self.config.update(kwargs)


class VoiceInputClient:
    def __init__(self, config_path: str = "config.json", args=None):
        self.args = args or {}
        self.config = Config(config_path)
        
        # Override config with command-line arguments
        if self.args.get('baudrate'):
            self.config.config.setdefault('serial', {})['baudrate'] = self.args.get('baudrate')
        if self.args.get('log_level'):
            self.config.config.setdefault('logging', {})['level'] = self.args.get('log_level')
        
        self._setup_logging()
        
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device = None
        self.retry_count = 0
        self.current_retry_interval = 2
        
        # Keyboard controller for text input
        if PYINPUT_AVAILABLE:
            self.keyboard = KeyboardController()
            self.logger.info("Using pynput for keyboard input (Unicode supported)")
        else:
            self.logger.warning("pynput not available, falling back to pyautogui")
    
    def _setup_logging(self):
        """Setup logging with rotation to file and console."""
        log_level = self.config.get("logging", "level", default="INFO")
        log_file = self.config.get("logging", "file", default="voice_input_client.log")
        max_bytes = self.config.get("logging", "max_bytes", default=1048576)
        backup_count = self.config.get("logging", "backup_count", default=3)
        
        # Create logger
        self.logger = logging.getLogger("VoiceInputTool")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Prevent duplicate handlers
        if self.logger.handlers:
            self.logger.handlers.clear()
        
        # File handler with rotation
        try:
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=max_bytes,
                backupCount=backup_count,
                encoding='utf-8'
            )
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
        
        # Filter for USB serial devices
        candidates = []
        for port in ports:
            description = port.description.lower() if port.description else ""
            device = port.device
            
            # Check for known USB serial adapters (prioritized)
            priority = 0
            if 'ch340' in description:  # Most common for Android
                priority = 3
            elif 'cp210' in description:
                priority = 2
            elif 'ftdi' in description:
                priority = 2
            elif 'arduino' in description:
                priority = 1
            elif 'usb' in description and 'serial' in description:
                priority = 1
            
            if priority > 0:
                candidates.append((priority, device, port.description))
        
        if candidates:
            # Return highest priority device
            candidates.sort(key=lambda x: -x[0])
            device = candidates[0][1]
            self.logger.info(f"Found device: {device} - {candidates[0][2]}")
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
            self.current_retry_interval = serial_config.get("retry_interval", 2)
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
                    self.logger.debug(f"Waiting {self.current_retry_interval}s before retry...")
                    time.sleep(self.current_retry_interval)
                    continue
            
            try:
                if self.serial_port.in_waiting > 0:
                    # Read line (assuming text is sent with newline terminator)
                    line = self.serial_port.readline().decode('utf-8').strip()
                    
                    if line:
                        self.logger.info(f"Received text: {line}")
                        
                        # Post-process the text
                        processed_text = self._post_process_text(line)
                        
                        # Input text at cursor
                        self.input_text_at_cursor(processed_text)
                        
                        # Auto-enter if configured
                        auto_enter = self.config.get("input", "auto_enter_after_ms", default=0)
                        if auto_enter > 0:
                            time.sleep(auto_enter / 1000.0)
                            self._send_enter()
                        
            except UnicodeDecodeError:
                self.logger.warning("Received invalid UTF-8 data, skipping...")
                continue
            except serial.SerialException as e:
                self.logger.error(f"Serial communication error: {e}")
                self.disconnect()
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}", exc_info=True)
                break
                
            time.sleep(0.05)  # Small delay to prevent excessive CPU usage
    
    def _post_process_text(self, text: str) -> str:
        """Post-process recognized text."""
        post_config = self.config.get("input", "post_process", default={})
        
        result = text
        
        # Trim whitespace
        if post_config.get("trim_whitespace", True):
            result = result.strip()
            # Remove excess internal whitespace
            result = ' '.join(result.split())
        
        # Auto-punctuate (add punctuation if missing)
        if post_config.get("auto_punctuate", False):
            punctuation = post_config.get("punctuation_marks", "。！？；：")
            if result and result[-1] not in punctuation:
                # Simple heuristic: add 。 for statements, ？ or ！ for questions
                if '吗' in result or '什么' in result or '怎么' in result or '?' in result.lower():
                    result += '？'
                else:
                    result += '。'
        
        return result
    
    def _attempt_reconnect(self):
        """Attempt to reconnect with exponential backoff."""
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
            # Reset retry interval on successful connection
            self.current_retry_interval = serial_config.get("retry_interval", 2)
        else:
            # Exponential backoff
            if serial_config.get("exponential_backoff", True):
                max_interval = serial_config.get("max_retry_interval", 60)
                self.current_retry_interval = min(
                    self.current_retry_interval * 2,
                    max_interval
                )
            self.logger.debug(f"Reconnect failed, will retry in {self.current_retry_interval}s...")
    
    def _send_enter(self):
        """Send Enter key."""
        try:
            if PYINPUT_AVAILABLE:
                self.keyboard.press(keyboard.Key.enter)
                self.keyboard.release(keyboard.Key.enter)
            else:
                pyautogui.press('enter')
        except Exception as e:
            self.logger.warning(f"Failed to send enter key: {e}")
    
    def _contains_unicode(self, text: str) -> bool:
        """Check if text contains non-ASCII characters."""
        return any(ord(c) > 127 for c in text)
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position with retry mechanism."""
        input_config = self.config.get("input")
        retry_count = input_config.get("retry_count", 3)
        retry_delay = input_config.get("retry_delay", 0.2)
        
        # Determine input method based on content
        use_clipboard = input_config.get("enable_clipboard", True)
        
        # Try multiple input methods with retries
        last_error = None
        for attempt in range(retry_count):
            try:
                if use_clipboard and self._contains_unicode(text):
                    # Use clipboard for Unicode/Chinese text
                    if self._input_via_clipboard(text):
                        self.logger.info(f"Successfully input text (clipboard, attempt {attempt + 1})")
                        return
                elif PYINPUT_AVAILABLE:
                    # Use pynput for better compatibility
                    if self._input_via_pynput(text):
                        self.logger.info(f"Successfully input text (pynput, attempt {attempt + 1})")
                        return
                else:
                    # Fallback to pyautogui
                    if self._input_via_pyautogui(text):
                        self.logger.info(f"Successfully input text (pyautogui, attempt {attempt + 1})")
                        return
                        
            except Exception as e:
                last_error = e
                self.logger.warning(f"Input attempt {attempt + 1} failed: {e}")
                
            if attempt < retry_count - 1:
                time.sleep(retry_delay)
        
        # All methods failed
        self.logger.error(f"Failed to input text after {retry_count} attempts: {last_error}")
    
    def _input_via_clipboard(self, text: str) -> bool:
        """Input text via clipboard (best for Unicode/Chinese)."""
        try:
            import pyperclip
        except ImportError:
            self.logger.warning("pyperclip not available")
            return False
        
        try:
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
            return True
            
        except Exception as e:
            self.logger.warning(f"Clipboard method failed: {e}")
            raise
    
    def _input_via_pynput(self, text: str) -> bool:
        """Input text using pynput (supports Unicode)."""
        try:
            self.keyboard.type(text)
            return True
        except Exception as e:
            self.logger.warning(f"pynput method failed: {e}")
            raise
    
    def _input_via_pyautogui(self, text: str) -> bool:
        """Input text using pyautogui (fallback)."""
        try:
            interval = self.config.get("input", "type_interval", default=0.01)
            pyautogui.typewrite(text, interval=interval)
            return True
        except Exception as e:
            self.logger.warning(f"pyautogui method failed: {e}")
            raise
    
    def start(self):
        """Start the voice input client."""
        self.logger.info("=" * 50)
        self.logger.info("Starting Voice Input Tool - Windows Client (v2)")
        self.logger.info("=" * 50)
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


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Voice Input Tool - Windows Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python voice_input_client.py                    # Run with default config
  python voice_input_client.py -c myconfig.json   # Use custom config
  python voice_input_client.py --baudrate 115200  # Override baudrate
  python voice_input_client.py --log-level DEBUG  # Enable debug logging
        """
    )
    
    parser.add_argument(
        '-c', '--config',
        default='config.json',
        help='Path to config file (default: config.json)'
    )
    parser.add_argument(
        '-b', '--baudrate',
        type=int,
        help='Serial baudrate (overrides config)'
    )
    parser.add_argument(
        '-l', '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        help='Logging level (overrides config)'
    )
    parser.add_argument(
        '-v', '--version',
        action='store_true',
        help='Show version information'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    if args.version:
        print("Voice Input Tool - Windows Client v2.0")
        print("Round 2 enhancements: log rotation, exponential backoff, enhanced input stability")
        return
    
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
    if not os.path.exists(args.config):
        try:
            with open(args.config, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
            print(f"Created default config: {args.config}")
        except Exception as e:
            print(f"Warning: Could not create config: {e}")
    
    # Convert args to dict
    args_dict = {
        'baudrate': args.baudrate,
        'log_level': args.log_level
    }
    
    client = VoiceInputClient(config_path=args.config, args=args_dict)
    client.start()


if __name__ == "__main__":
    main()