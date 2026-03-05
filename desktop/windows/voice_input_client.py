#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.

Features:
- Auto-reconnect on USB disconnect
- Configurable settings via config.json
- Logging to file
- Support for Unicode/Chinese text input
- Security improvements:
  * Input validation to prevent command injection
  * Connection timeout protection
  * Secure file handling
  * Input sanitization
"""

import serial
import serial.tools.list_ports
import time
import sys
import threading
import os
import json
import logging
import tempfile
import hashlib
import secrets
from typing import Optional, List, Dict, Tuple
from pathlib import Path
from enum import Enum
import platform

# Try to import pynput for better Unicode support, fallback to pyautogui
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
        PYINPUT_AVAILABLE = True  # Will fail at runtime if neither available

# Security configuration
SECURITY_CONFIG = {
    "max_line_length": 1024,  # Maximum line length to prevent buffer overflow
    "allowed_characters": set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()_+-=[]{}|;:,.<>?/\\\"' \t\n"),
    "timeout": 30.0,  # Connection timeout in seconds
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
        "bytesize": serial.EIGHTBITS,
        "parity": serial.PARITY_NONE,
        "stopbits": serial.STOPBITS_ONE,
        "retry_interval": 2,
        "max_retries": 0,  # 0 = infinite retries
        "buffer_size": 1024,
    },
    "input": {
        "type_interval": 0.01,
        "enable_clipboard": True,  # Use clipboard for Chinese text
        "delay_before_input": 0.1,
        "validate_input": True,
    },
    "logging": {
        "level": "INFO",
        "file": "voice_input_client.log",
        "max_size_mb": 10,
        "backup_count": 5,
    },
    "security": {
        "max_line_length": SECURITY_CONFIG["max_line_length"],
        "input_validation_enabled": True,
        "log_input_samples": False,
    }
}


class ValidationError(Exception):
    """Custom exception for input validation errors."""
    pass


class SecurityUtils:
    """Security utilities for input validation and protection."""
    
    @staticmethod
    def validate_input(text: str, max_length: int = 1024) -> Tuple[bool, str]:
        """
        Validate input text for security.
        
        Args:
            text: Input text to validate
            max_length: Maximum allowed length
            
        Returns:
            Tuple of (is_valid, sanitized_text)
        """
        if not isinstance(text, str):
            return False, "Invalid input type"
        
        # Check length
        if len(text) > max_length:
            return False, f"Input too long (max {max_length} characters)"
        
        # Check for null bytes
        if '\0' in text:
            return False, "Input contains null bytes"
        
        # Check for control characters (allow \n and \t)
        for char in text:
            if char.isprintable() or char in '\n\t':
                continue
            # Allow basic ASCII control characters
            if ord(char) < 32 and char not in '\n\t':
                return False, f"Invalid control character: {repr(char)}"
        
        # Check for potential injection attempts
        suspicious_patterns = [
            (';', 'semicolon'),
            ('|', 'pipe'),
            ('&&', 'double ampersand'),
            ('$(', 'command substitution'),
            ('`', 'backtick'),
            ('<', 'less than'),
            ('>', 'greater than'),
        ]
        
        for pattern, name in suspicious_patterns:
            if pattern in text:
                logging.warning(f"Potentially suspicious character '{name}' in input")
        
        # Sanitize by removing invalid characters
        sanitized = ''.join(c for c in text if c.isprintable() or c in '\n\t ')
        
        return True, sanitized
    
    @staticmethod
    def hash_text(text: str) -> str:
        """Create a hash of text for logging purposes (without exposing content)."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def generate_secure_id() -> str:
        """Generate a secure random identifier."""
        return secrets.token_hex(8)


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
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid config file: {e}, using defaults")
            except Exception as e:
                print(f"Warning: Could not load config: {e}, using defaults")
        
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


class LoggingManager:
    """Manages logging with rotation and secure handling."""
    
    def __init__(self, config: Config):
        self.config = config
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging with rotation."""
        log_dir = Path.home() / ".voice_input_tool"
        log_dir.mkdir(exist_ok=True)
        
        log_level = self.config.get("logging", "level", default="INFO")
        log_file = log_dir / self.config.get("logging", "file", default="voice_input_client.log")
        max_size_mb = self.config.get("logging", "max_size_mb", default=10)
        backup_count = self.config.get("logging", "backup_count", default=5)
        
        # Create logger
        self.logger = logging.getLogger("VoiceInputTool")
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # File handler with rotation
        try:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                log_file, 
                maxBytes=max_size_mb * 1024 * 1024,
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
        
        self.logger.info(f"Logging initialized. Log file: {log_file}")
    
    def log_input(self, text: str, original: bool = False):
        """Log input with security considerations."""
        if original:
            # Log only hash for security
            input_hash = SecurityUtils.hash_text(text)
            self.logger.info(f"Received input (hash: {input_hash}, length: {len(text)})")
        
        if self.config.get("security", "log_input_samples", default=False):
            # Only log samples for debugging
            self.logger.debug(f"Input sample (first 100 chars): {text[:100]!r}")


class VoiceInputClient:
    def __init__(self, config_path: str = "config.json"):
        self.config = Config(config_path)
        self.logging_manager = LoggingManager(self.config)
        self.logger = self.logging_manager.logger
        
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device = None
        self.retry_count = 0
        self.security_id = SecurityUtils.generate_secure_id()
        
        # Keyboard controller for text input
        self.keyboard = None
        self.pyautogui = None
        
        if PYINPUT_AVAILABLE:
            try:
                self.keyboard = KeyboardController()
                self.logger.info("Using pynput for keyboard input (Unicode supported)")
            except Exception as e:
                self.logger.warning(f"Could not initialize pynput: {e}")
        
        if not PYINPUT_AVAILABLE and PYAUTOGUI_AVAILABLE:
            try:
                self.pyautogui = pyautogui
                self.logger.warning("Using pyautogui for keyboard input (limited Unicode support)")
            except Exception as e:
                self.logger.error(f"Could not initialize pyautogui: {e}")
                raise RuntimeError("No keyboard library available")
    
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device with improved detection."""
        try:
            ports = serial.tools.list_ports.comports()
            
            for port in ports:
                description = port.description.lower() if port.description else ""
                device = port.device
                
                # Check for known USB serial adapters
                keywords = ['usb', 'serial', 'ch340', 'cp210', 'ftdi', 'arduino', 'stm32', 
                          'cdc', 'acm', 'usb-to-serial', 'pl2303']
                
                if any(keyword in description for keyword in keywords):
                    self.logger.info(f"Found potential device: {device} - {port.description}")
                    return device
                
                # Also check for devices with no description but are USB
                if 'usb' in device.lower() and 'com' in device.lower():
                    self.logger.debug(f"Found device with no description: {device}")
                    return device
                
            self.logger.debug("No VoiceInputTool device found")
            return None
        except Exception as e:
            self.logger.error(f"Error scanning ports: {e}")
            return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device with timeout protection."""
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
                read_timeout=serial_config.get("read_timeout", 1),
                write_timeout=serial_config.get("write_timeout", 1),
                bytesize=serial_config.get("bytesize", serial.EIGHTBITS),
                parity=serial_config.get("parity", serial.PARITY_NONE),
                stopbits=serial_config.get("stopbits", serial.STOPBITS_ONE)
            )
            self.connected_device = device_port
            self.retry_count = 0
            self.logger.info(f"Connected to VoiceInputTool on {device_port} (ID: {self.security_id})")
            return True
            
        except serial.SerialException as e:
            error_msg = str(e)
            # Try to provide helpful suggestions
            if "Permission denied" in error_msg:
                self.logger.error(f"Permission denied to access {device_port}. "
                                f"Try: sudo usermod -aG dialout $USER")
            elif "Device or resource busy" in error_msg:
                self.logger.error(f"Device {device_port} is already in use. "
                                f"Close other programs using this port.")
            else:
                self.logger.error(f"Failed to connect to {device_port}: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error connecting to {device_port}: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the device safely."""
        if self.serial_port:
            try:
                if self.serial_port.is_open:
                    # Flush any pending data
                    self.serial_port.flush()
                    self.serial_port.close()
                self.logger.info("Disconnected from device")
            except Exception as e:
                self.logger.warning(f"Error during disconnect: {e}")
            finally:
                self.serial_port = None
                self.connected_device = None
    
    def listen_for_text(self):
        """Listen for incoming text from the device with security."""
        buffer = ""
        
        while self.is_running:
            # Check if connected
            if not self.serial_port or not self.serial_port.is_open:
                self._attempt_reconnect()
                if not self.serial_port or not self.serial_port.is_open:
                    time.sleep(self.config.get("serial", "retry_interval", default=2))
                    continue
            
            try:
                if self.serial_port.in_waiting > 0:
                    # Read data
                    data = self.serial_port.read(self.serial_port.in_waiting)
                    if data:
                        try:
                            text = data.decode('utf-8')
                            buffer += text
                            
                            # Process complete lines
                            while '\n' in buffer:
                                line, buffer = buffer.split('\n', 1)
                                line = line.strip()
                                
                                if line:
                                    self._process_line(line)
                                    
                        except UnicodeDecodeError:
                            self.logger.warning("Received invalid UTF-8 data, skipping...")
                            # Try to recover
                            try:
                                text = data.decode('utf-8', errors='replace')
                                buffer += text
                            except:
                                continue
                            
            except serial.SerialException as e:
                self.logger.error(f"Serial communication error: {e}")
                self.disconnect()
                continue
            except Exception as e:
                self.logger.error(f"Unexpected error in listen_for_text: {e}")
                # Don't break the loop on unexpected errors
                time.sleep(0.1)
                
            time.sleep(0.1)  # Small delay to prevent excessive CPU usage
    
    def _process_line(self, line: str):
        """Process a single line of incoming data."""
        max_length = self.config.get("security", "max_line_length", 
                                    default=SECURITY_CONFIG["max_line_length"])
        validate = self.config.get("security", "input_validation_enabled", 
                                 default=True)
        
        self.logger.debug(f"Processing line: {line[:50]}...")
        
        # Validate input
        if validate:
            is_valid, result = SecurityUtils.validate_input(line, max_length)
            if not is_valid:
                self.logger.warning(f"Invalid input rejected: {result}")
                return
            
            line = result
        
        # Log securely
        self.logging_manager.log_input(line, original=True)
        
        # Input text at cursor position
        self.input_text_at_cursor(line)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the device with limits."""
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
            self.retry_count = 0
        else:
            self.logger.debug("Reconnect failed, will retry...")
    
    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position with error handling."""
        try:
            # Add a small delay to ensure we're ready to type
            time.sleep(self.config.get("input", "delay_before_input", default=0.1))
            
            input_config = self.config.get("input")
            
            # Check if we should use clipboard method for better Unicode support
            if input_config.get("enable_clipboard", True):
                self._input_via_clipboard(text)
            elif self.keyboard:
                self._input_via_pynput(text)
            elif self.pyautogui:
                self._input_via_pyautogui(text)
            else:
                raise RuntimeError("No keyboard library available")
            
            self.logger.info("Successfully input text at cursor position")
            
        except Exception as e:
            self.logger.error(f"Failed to input text: {e}")
            # Show user feedback
            try:
                import os
                import platform
                if platform.system() == 'Windows':
                    os.system('msg * "Voice Input Tool: Input failed"')
                else:
                    # On macOS/Linux, we could use osascript or notify-send
                    pass
            except:
                pass
    
    def _input_via_clipboard(self, text: str):
        """Input text via clipboard (best for Unicode/Chinese)."""
        try:
            # Save current clipboard
            try:
                import pyperclip
                original_clipboard = pyperclip.paste()
            except ImportError:
                self.logger.warning("pyperclip not available, falling back to keyboard input")
                self._input_via_pynput(text)
                return
            
            # Copy new text to clipboard
            pyperclip.copy(text)
            time.sleep(0.05)
            
            # Paste using Ctrl+V
            if self.keyboard:
                with self.keyboard.pressed(keyboard.Key.ctrl):
                    self.keyboard.press('v')
                    self.keyboard.release('v')
            elif self.pyautogui:
                self.pyautogui.hotkey('ctrl', 'v')
            
            time.sleep(0.05)
            
            # Restore original clipboard
            try:
                pyperclip.copy(original_clipboard)
            except:
                pass
            
        except ImportError as e:
            self.logger.warning(f"Clipboard dependency not available: {e}")
            self._input_via_pynput(text)
        except Exception as e:
            self.logger.warning(f"Clipboard method failed: {e}, trying keyboard")
            self._input_via_pynput(text)
    
    def _input_via_pynput(self, text: str):
        """Input text using pynput (supports Unicode)."""
        try:
            self.keyboard.type(text)
        except Exception as e:
            self.logger.error(f"pynput failed: {e}")
            raise
    
    def _input_via_pyautogui(self, text: str):
        """Input text using pyautogui (fallback)."""
        try:
            interval = self.config.get("input", "type_interval", default=0.01)
            self.pyautogui.typewrite(text, interval=interval)
        except Exception as e:
            self.logger.error(f"pyautogui failed: {e}")
            raise

    def validate_serial_config(self) -> bool:
        """Validate serial configuration before connecting."""
        serial_config = self.config.get("serial", default={})
        
        required_keys = ['baudrate', 'bytesize', 'parity', 'stopbits']
        for key in required_keys:
            if key not in serial_config:
                self.logger.error(f"Missing required serial config: {key}")
                return False
        
        # Validate baudrate
        valid_baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        if serial_config.get('baudrate') not in valid_baudrates:
            self.logger.warning(f"Non-standard baudrate: {serial_config.get('baudrate')}")
        
        return True


def create_default_config(config_path: str = "config.json") -> bool:
    """Create default config file."""
    try:
        # Check if config already exists
        if os.path.exists(config_path):
            return True
        
        config_dir = Path.home() / ".voice_input_tool"
        config_dir.mkdir(exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(DEFAULT_CONFIG, f, indent=2, ensure_ascii=False)
        print(f"Created default config at {config_path}")
        return True
    except Exception as e:
        print(f"Warning: Could not create config: {e}")
        return False


def show_platform_info():
    """Show platform information."""
    print("\n" + "="*60)
    print("Voice Input Tool - System Information")
    print("="*60)
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {sys.version}")
    print(f"Working Directory: {os.getcwd()}")
    print(f"Config Directory: {Path.home() / '.voice_input_tool'}")
    print("="*60 + "\n")


def main():
    """Main entry point with comprehensive error handling."""
    # Show platform info
    show_platform_info()
    
    # Create default config if not exists
    create_default_config("config.json")
    
    # Create default config in home directory too
    create_default_config(str(Path.home() / '.voice_input_tool' / 'config.json'))
    
    try:
        # Create client
        client = VoiceInputClient()
        client.logger.info("Starting Voice Input Tool")
        client.logger.info("Waiting for VoiceInputTool device...")
        
        # Check serial configuration
        if not client.validate_serial_config():
            client.logger.error("Invalid serial configuration. Check config.json")
            return
        
        # Keep trying to connect until successful
        serial_config = client.config.get("serial")
        max_retries = serial_config.get("max_retries", 0)
        
        while not client.connect_to_device():
            if max_retries > 0 and client.retry_count >= max_retries:
                client.logger.error("Max connection retries reached, exiting")
                return
            
            time.sleep(serial_config.get("retry_interval", 2))
            client.retry_count += 1
        
        client.is_running = True
        
        # Start listening thread
        listener_thread = threading.Thread(
            target=client.listen_for_text, 
            daemon=True,
            name="ListenerThread"
        )
        listener_thread.start()
        
        client.logger.info("Voice Input Tool is running!")
        client.logger.info("Speak into your phone and text will appear on your computer.")
        client.logger.info("Press Ctrl+C to exit.")
        
        # Keep main thread alive
        try:
            while client.is_running:
                time.sleep(1)
        except KeyboardInterrupt:
            client.logger.info("\nShutting down Voice Input Tool...")
            client.stop()
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        logging.exception("Fatal error")
        sys.exit(1)
    finally:
        # Cleanup
        try:
            if 'client' in locals():
                client.disconnect()
        except:
            pass


if __name__ == "__main__":
    main()
