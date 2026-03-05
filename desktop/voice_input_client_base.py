#!/usr/bin/env python3
"""
Voice Input Tool - Base Client Module
Provides shared functionality for all platform-specific clients.

This module contains:
- Configuration management
- Security utilities
- Logging setup
- Serial communication base class
- Abstract client interface
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from enum import Enum
import hashlib
import secrets

# Optional imports with graceful degradation
try:
    from pynput.keyboard import Controller as KeyboardController
    from pynput import keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


class ValidationError(Exception):
    """Custom exception for input validation errors."""
    pass


class ConnectionError(Exception):
    """Custom exception for connection errors."""
    pass


@dataclass
class SerialConfig:
    """Serial port configuration."""
    baudrate: int = 9600
    timeout: float = 1.0
    read_timeout: float = 1.0
    write_timeout: float = 1.0
    bytesize: int = 8
    parity: str = 'N'
    stopbits: int = 1
    retry_interval: float = 2.0
    max_retries: int = 0  # 0 = infinite
    buffer_size: int = 1024
    
    def validate(self) -> Tuple[bool, str]:
        """Validate serial configuration."""
        valid_baudrates = [9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600]
        if self.baudrate not in valid_baudrates:
            return False, f"Invalid baudrate: {self.baudrate}"
        
        if self.timeout <= 0:
            return False, "Timeout must be positive"
        
        if self.buffer_size < 64 or self.buffer_size > 65536:
            return False, "Buffer size out of range (64-65536)"
        
        return True, "Valid"


@dataclass
class InputConfig:
    """Input method configuration."""
    type_interval: float = 0.01
    enable_clipboard: bool = True
    delay_before_input: float = 0.1
    validate_input: bool = True
    
    def validate(self) -> Tuple[bool, str]:
        """Validate input configuration."""
        if self.type_interval < 0 or self.type_interval > 1.0:
            return False, "Type interval must be between 0 and 1 second"
        
        if self.delay_before_input < 0 or self.delay_before_input > 5.0:
            return False, "Delay before input must be between 0 and 5 seconds"
        
        return True, "Valid"


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"
    file: str = "voice_input_client.log"
    max_size_mb: int = 10
    backup_count: int = 5
    
    def validate(self) -> Tuple[bool, str]:
        """Validate logging configuration."""
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.level.upper() not in valid_levels:
            return False, f"Invalid log level: {self.level}"
        
        if self.max_size_mb < 1 or self.max_size_mb > 1000:
            return False, "Max size must be between 1 and 1000 MB"
        
        return True, "Valid"


@dataclass
class SecurityConfig:
    """Security configuration."""
    max_line_length: int = 1024
    input_validation_enabled: bool = True
    log_input_samples: bool = False
    allowed_characters: Optional[str] = None
    
    def validate(self) -> Tuple[bool, str]:
        """Validate security configuration."""
        if self.max_line_length < 1 or self.max_line_length > 10000:
            return False, "Max line length out of range"
        
        return True, "Valid"


@dataclass
class AppConfig:
    """Application configuration container."""
    serial: SerialConfig = field(default_factory=SerialConfig)
    input: InputConfig = field(default_factory=InputConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AppConfig':
        """Create config from dictionary."""
        return cls(
            serial=SerialConfig(**data.get('serial', {})),
            input=InputConfig(**data.get('input', {})),
            logging=LoggingConfig(**data.get('logging', {})),
            security=SecurityConfig(**data.get('security', {}))
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return {
            'serial': asdict(self.serial),
            'input': asdict(self.input),
            'logging': asdict(self.logging),
            'security': asdict(self.security)
        }
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate entire configuration."""
        errors = []
        
        valid, msg = self.serial.validate()
        if not valid:
            errors.append(f"Serial config: {msg}")
        
        valid, msg = self.input.validate()
        if not valid:
            errors.append(f"Input config: {msg}")
        
        valid, msg = self.logging.validate()
        if not valid:
            errors.append(f"Logging config: {msg}")
        
        valid, msg = self.security.validate()
        if not valid:
            errors.append(f"Security config: {msg}")
        
        return len(errors) == 0, errors


class ConfigManager:
    """Manages application configuration loading and saving."""
    
    DEFAULT_CONFIG_NAME = "config.json"
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config = self._load_or_create()
    
    def _get_default_config_path(self) -> str:
        """Get default configuration path."""
        config_dir = Path.home() / ".voice_input_tool"
        config_dir.mkdir(exist_ok=True)
        return str(config_dir / self.DEFAULT_CONFIG_NAME)
    
    def _load_or_create(self) -> AppConfig:
        """Load existing config or create default."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                config = AppConfig.from_dict(data)
                valid, errors = config.validate()
                if not valid:
                    print(f"Warning: Invalid config values: {', '.join(errors)}")
                    print("Using defaults for invalid values")
                return config
            except json.JSONDecodeError as e:
                print(f"Warning: Invalid JSON in config file: {e}")
            except Exception as e:
                print(f"Warning: Could not load config: {e}")
        
        # Create default config
        config = AppConfig()
        self.save(config)
        return config
    
    def save(self, config: Optional[AppConfig] = None) -> bool:
        """Save configuration to file."""
        config = config or self.config
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config.to_dict(), f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Warning: Could not save config: {e}")
            return False


class SecurityUtils:
    """Security utilities for input validation and protection."""
    
    # Suspicious patterns that might indicate injection attempts
    SUSPICIOUS_PATTERNS = [
        (';', 'semicolon'),
        ('|', 'pipe'),
        ('&&', 'double ampersand'),
        ('$(', 'command substitution'),
        ('`', 'backtick'),
        ('<', 'less than'),
        ('>', 'greater than'),
    ]
    
    @staticmethod
    def validate_input(text: str, max_length: int = 1024) -> Tuple[bool, str]:
        """
        Validate input text for security.
        
        Args:
            text: Input text to validate
            max_length: Maximum allowed length
            
        Returns:
            Tuple of (is_valid, result_or_error)
        """
        if not isinstance(text, str):
            return False, "Invalid input type: expected string"
        
        # Check length
        if len(text) > max_length:
            return False, f"Input too long ({len(text)} > {max_length})"
        
        # Check for null bytes
        if '\0' in text:
            return False, "Input contains null bytes"
        
        # Check for control characters (allow \n and \t)
        for i, char in enumerate(text):
            if char.isprintable() or char in '\n\t':
                continue
            if ord(char) < 32:
                return False, f"Invalid control character at position {i}: {repr(char)}"
        
        # Log suspicious patterns
        for pattern, name in SecurityUtils.SUSPICIOUS_PATTERNS:
            if pattern in text:
                logging.getLogger("VoiceInputTool").warning(
                    f"Potentially suspicious character '{name}' detected in input"
                )
        
        return True, text
    
    @staticmethod
    def hash_text(text: str) -> str:
        """Create a hash of text for logging purposes."""
        return hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    
    @staticmethod
    def generate_secure_id() -> str:
        """Generate a secure random identifier."""
        return secrets.token_hex(8)


class LoggingManager:
    """Manages application logging with rotation."""
    
    def __init__(self, config: LoggingConfig, app_name: str = "VoiceInputTool"):
        self.config = config
        self.app_name = app_name
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup logging with file rotation."""
        logger = logging.getLogger(self.app_name)
        logger.setLevel(getattr(logging, self.config.level.upper()))
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # File handler with rotation
        try:
            from logging.handlers import RotatingFileHandler
            log_dir = Path.home() / ".voice_input_tool"
            log_dir.mkdir(exist_ok=True)
            
            log_file = log_dir / self.config.file
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=self.config.max_size_mb * 1024 * 1024,
                backupCount=self.config.backup_count,
                encoding='utf-8'
            )
            file_handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(file_handler)
        except Exception as e:
            print(f"Warning: Could not create log file: {e}")
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            '%(levelname)s: %(message)s'
        ))
        logger.addHandler(console_handler)
        
        return logger
    
    def log_input(self, text: str, log_samples: bool = False):
        """Log input securely."""
        input_hash = SecurityUtils.hash_text(text)
        self.logger.info(f"Received input (hash: {input_hash}, length: {len(text)})")
        
        if log_samples:
            self.logger.debug(f"Input sample: {text[:100]!r}")


class VoiceInputClientBase(ABC):
    """
    Abstract base class for voice input clients.
    Provides common functionality for all platform implementations.
    """
    
    def __init__(self, platform_name: str, config_path: Optional[str] = None):
        if not SERIAL_AVAILABLE:
            raise RuntimeError("pyserial is required. Install with: pip install pyserial")
        
        self.platform_name = platform_name
        self.config_manager = ConfigManager(config_path)
        self.config = self.config_manager.config
        
        # Setup logging
        self.logging_manager = LoggingManager(self.config.logging, f"VoiceInputTool-{platform_name}")
        self.logger = self.logging_manager.logger
        
        # State
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device: Optional[str] = None
        self.retry_count = 0
        self.security_id = SecurityUtils.generate_secure_id()
        
        # Threading
        self._lock = threading.Lock()
        self._read_thread: Optional[threading.Thread] = None
        
        # Initialize keyboard controller
        self._init_keyboard()
        
        self.logger.info(f"{platform_name} client initialized (ID: {self.security_id})")
    
    def _init_keyboard(self):
        """Initialize keyboard controller."""
        self.keyboard = None
        self.pyautogui = None
        
        if PYNPUT_AVAILABLE:
            try:
                self.keyboard = KeyboardController()
                self.logger.info("Using pynput for keyboard input")
            except Exception as e:
                self.logger.warning(f"Could not initialize pynput: {e}")
        
        if not self.keyboard and PYAUTOGUI_AVAILABLE:
            self.pyautogui = pyautogui
            self.logger.warning("Using pyautogui for keyboard input (fallback)")
        
        if not self.keyboard and not self.pyautogui:
            raise RuntimeError("No keyboard library available. Install pynput or pyautogui")
    
    @abstractmethod
    def get_usb_device_patterns(self) -> List[str]:
        """Return list of USB device patterns for this platform."""
        pass
    
    @abstractmethod
    def get_paste_key(self) -> str:
        """Return the paste key combination for this platform (ctrl or cmd)."""
        pass
    
    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        try:
            ports = serial.tools.list_ports.comports()
            patterns = self.get_usb_device_patterns()
            
            for port in ports:
                description = (port.description or "").lower()
                device = port.device.lower()
                
                # Check against platform-specific patterns
                for pattern in patterns:
                    if pattern in device or pattern in description:
                        self.logger.info(f"Found device: {port.device} ({port.description})")
                        return port.device
                
                # Generic USB check
                if 'usb' in description and any(x in device for x in ['tty', 'com', 'usb']):
                    self.logger.debug(f"Found USB device: {port.device}")
                    return port.device
            
            return None
        except Exception as e:
            self.logger.error(f"Error scanning ports: {e}")
            return None
    
    def connect_to_device(self) -> bool:
        """Connect to the VoiceInputTool device."""
        device_port = self.find_voice_input_device()
        
        if not device_port:
            self.logger.debug("No VoiceInputTool device found")
            return False
        
        with self._lock:
            # Close existing connection
            if self.serial_port and self.serial_port.is_open:
                try:
                    self.serial_port.close()
                except Exception as e:
                    self.logger.warning(f"Error closing previous connection: {e}")
            
            try:
                cfg = self.config.serial
                self.serial_port = serial.Serial(
                    port=device_port,
                    baudrate=cfg.baudrate,
                    timeout=cfg.timeout,
                    write_timeout=cfg.write_timeout,
                    bytesize=cfg.bytesize,
                    parity=cfg.parity,
                    stopbits=cfg.stopbits
                )
                self.connected_device = device_port
                self.retry_count = 0
                self.logger.info(f"Connected to {device_port}")
                return True
                
            except serial.SerialException as e:
                self._handle_connection_error(device_port, e)
                return False
            except Exception as e:
                self.logger.error(f"Unexpected error connecting: {e}")
                return False
    
    def _handle_connection_error(self, device_port: str, error: Exception):
        """Handle connection errors with helpful messages."""
        error_msg = str(error)
        
        if "Permission denied" in error_msg:
            self.logger.error(f"Permission denied for {device_port}")
            self._show_permission_help()
        elif "Device or resource busy" in error_msg:
            self.logger.error(f"Device {device_port} is busy")
        else:
            self.logger.error(f"Failed to connect to {device_port}: {error}")
    
    @abstractmethod
    def _show_permission_help(self):
        """Show platform-specific permission help."""
        pass
    
    def disconnect(self):
        """Disconnect from the device safely."""
        with self._lock:
            if self.serial_port:
                try:
                    if self.serial_port.is_open:
                        self.serial_port.flush()
                        self.serial_port.close()
                    self.logger.info("Disconnected from device")
                except Exception as e:
                    self.logger.warning(f"Error during disconnect: {e}")
                finally:
                    self.serial_port = None
                    self.connected_device = None
    
    def listen_for_text(self):
        """Listen for incoming text from the device."""
        buffer = bytearray()
        
        while self.is_running:
            with self._lock:
                if not (self.serial_port and self.serial_port.is_open):
                    break
            
            try:
                with self._lock:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        buffer.extend(data)
                
                # Process complete lines
                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end]
                    buffer = buffer[line_end + 1:]
                    
                    # Remove carriage return
                    if line.endswith(b'\r'):
                        line = line[:-1]
                    
                    if line:
                        self._process_line(line.decode('utf-8', errors='replace'))
                
                time.sleep(0.01)
                
            except serial.SerialException as e:
                self.logger.error(f"Serial error: {e}")
                break
            except Exception as e:
                self.logger.error(f"Unexpected error: {e}")
                time.sleep(0.1)
        
        # Handle disconnection
        if self.is_running:
            self._attempt_reconnect()
    
    def _process_line(self, line: str):
        """Process a single line of incoming data."""
        # Validate input
        if self.config.security.input_validation_enabled:
            is_valid, result = SecurityUtils.validate_input(
                line, self.config.security.max_line_length
            )
            if not is_valid:
                self.logger.warning(f"Invalid input rejected: {result}")
                return
            line = result
        
        # Log securely
        self.logging_manager.log_input(
            line, self.config.security.log_input_samples
        )
        
        # Input text
        self.input_text_at_cursor(line)
    
    def _attempt_reconnect(self):
        """Attempt to reconnect to the device."""
        max_retries = self.config.serial.max_retries
        
        if max_retries > 0 and self.retry_count >= max_retries:
            self.logger.error(f"Max retries ({max_retries}) reached")
            self.is_running = False
            return
        
        self.retry_count += 1
        self.logger.info(f"Reconnect attempt {self.retry_count}...")
        
        if self.connect_to_device():
            self.retry_count = 0
            self._start_listener()
    
    def _start_listener(self):
        """Start the listener thread."""
        self._read_thread = threading.Thread(
            target=self.listen_for_text,
            daemon=True,
            name="SerialListener"
        )
        self._read_thread.start()
    
    def input_text_at_cursor(self, text: str):
        """Input text at cursor position."""
        try:
            time.sleep(self.config.input.delay_before_input)
            
            if self.config.input.enable_clipboard:
                self._input_via_clipboard(text)
            elif self.keyboard:
                self._input_via_pynput(text)
            elif self.pyautogui:
                self._input_via_pyautogui(text)
            
            self.logger.debug("Text input successful")
            
        except Exception as e:
            self.logger.error(f"Failed to input text: {e}")
    
    def _input_via_clipboard(self, text: str):
        """Input text via clipboard paste."""
        try:
            import pyperclip
            
            original = pyperclip.paste()
            pyperclip.copy(text)
            time.sleep(0.05)
            
            paste_key = self.get_paste_key()
            if self.keyboard:
                modifier = keyboard.Key.cmd if paste_key == 'cmd' else keyboard.Key.ctrl
                with self.keyboard.pressed(modifier):
                    self.keyboard.press('v')
                    self.keyboard.release('v')
            elif self.pyautogui:
                self.pyautogui.hotkey(paste_key, 'v')
            
            time.sleep(0.05)
            pyperclip.copy(original)
            
        except ImportError:
            self.logger.debug("pyperclip not available, using keyboard")
            self._input_via_pynput(text)
        except Exception as e:
            self.logger.warning(f"Clipboard failed: {e}")
            self._input_via_pynput(text)
    
    def _input_via_pynput(self, text: str):
        """Input text using pynput."""
        if self.keyboard:
            self.keyboard.type(text)
        else:
            raise RuntimeError("pynput not available")
    
    def _input_via_pyautogui(self, text: str):
        """Input text using pyautogui."""
        if self.pyautogui:
            self.pyautogui.typewrite(text, interval=self.config.input.type_interval)
        else:
            raise RuntimeError("pyautogui not available")
    
    def start(self):
        """Start the voice input client."""
        self.logger.info(f"Starting Voice Input Tool - {self.platform_name}")
        
        # Validate config
        valid, errors = self.config.validate()
        if not valid:
            self.logger.error(f"Invalid configuration: {', '.join(errors)}")
            return
        
        # Connect
        while not self.connect_to_device():
            if self.config.serial.max_retries > 0 and self.retry_count >= self.config.serial.max_retries:
                self.logger.error("Max connection retries reached")
                return
            time.sleep(self.config.serial.retry_interval)
            self.retry_count += 1
        
        self.is_running = True
        self._start_listener()
        
        self.logger.info("Voice Input Tool is running! Press Ctrl+C to exit.")
        
        try:
            while self.is_running:
                time.sleep(1)
                with self._lock:
                    if not (self.serial_port and self.serial_port.is_open):
                        self._attempt_reconnect()
                        if not self.is_running:
                            break
        except KeyboardInterrupt:
            self.logger.info("Shutting down...")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the voice input client."""
        self.is_running = False
        self.disconnect()
        self.logger.info("Voice Input Tool stopped")


def create_argument_parser() -> argparse.ArgumentParser:
    """Create standard argument parser for all platforms."""
    parser = argparse.ArgumentParser(
        description="Voice Input Tool - Desktop Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run with default settings
  %(prog)s --config ~/myconfig.json  # Use custom config
  %(prog)s --verbose                 # Enable debug logging
        """
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to configuration file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose (debug) logging'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='%(prog)s 2.0.0'
    )
    
    return parser
