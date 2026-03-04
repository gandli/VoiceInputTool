#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.
"""

import argparse
import logging
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

import serial
import serial.tools.list_ports

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


@dataclass
class SerialConfig:
    """Serial port configuration."""
    baudrate: int = 9600
    bytesize: int = 8
    parity: str = 'N'
    stopbits: int = 1
    timeout: float = 1.0
    write_timeout: float = 1.0


class VoiceInputClient:
    """Client for receiving voice input from Android device via USB serial."""

    # Common USB-to-serial chip identifiers
    USB_SERIAL_KEYWORDS = ['usb', 'serial', 'ch340', 'cp210', 'ftdi', 'pl2303', 'arduino']

    def __init__(self, config: SerialConfig = None):
        self.config = config or SerialConfig()
        self.serial_port: Optional[serial.Serial] = None
        self.is_running = False
        self.connected_device: Optional[str] = None
        self._lock = threading.Lock()

    def find_voice_input_device(self) -> Optional[str]:
        """Find the VoiceInputTool USB device."""
        ports = serial.tools.list_ports.comports()

        for port in ports:
            desc_lower = port.description.lower()
            if any(keyword in desc_lower for keyword in self.USB_SERIAL_KEYWORDS):
                logger.info(f"Found potential device: {port.device} - {port.description}")
                return port.device

        return None

    def connect_to_device(self, max_retries: int = 3) -> bool:
        """Connect to the VoiceInputTool device with retry logic."""
        for attempt in range(max_retries):
            device_port = self.find_voice_input_device()

            if not device_port:
                logger.warning("No VoiceInputTool device found. Please connect your phone via USB.")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                continue

            try:
                self.serial_port = serial.Serial(
                    port=device_port,
                    baudrate=self.config.baudrate,
                    timeout=self.config.timeout,
                    write_timeout=self.config.write_timeout,
                    bytesize=self.config.bytesize,
                    parity=self.config.parity,
                    stopbits=self.config.stopbits
                )
                self.connected_device = device_port
                logger.info(f"Connected to VoiceInputTool on {device_port}")
                return True

            except serial.SerialException as e:
                logger.error(f"Failed to connect to {device_port}: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)

        return False

    def reconnect(self) -> bool:
        """Attempt to reconnect to the device."""
        with self._lock:
            if self.serial_port:
                try:
                    self.serial_port.close()
                except Exception:
                    pass
                self.serial_port = None

        logger.info("Attempting to reconnect...")
        return self.connect_to_device()

    def listen_for_text(self):
        """Listen for incoming text from the device."""
        buffer = bytearray()

        while self.is_running:
            try:
                with self._lock:
                    if not (self.serial_port and self.serial_port.is_open):
                        break

                    # Read available data
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        buffer.extend(data)

                # Process complete lines from buffer
                while b'\n' in buffer:
                    line_end = buffer.index(b'\n')
                    line = buffer[:line_end]
                    buffer = buffer[line_end + 1:]

                    # Remove carriage return if present
                    if line.endswith(b'\r'):
                        line = line[:-1]

                    if line:
                        try:
                            text = line.decode('utf-8').strip()
                            if text:
                                logger.info(f"Received text: {text}")
                                self.input_text_at_cursor(text)
                        except UnicodeDecodeError:
                            logger.warning("Received invalid UTF-8 data, skipping...")

                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

            except serial.SerialException as e:
                logger.error(f"Serial communication error: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

        # Handle disconnection
        if self.is_running:
            logger.warning("Connection lost. Attempting to reconnect...")
            if self.reconnect():
                self.listen_for_text()  # Restart listening

    def input_text_at_cursor(self, text: str):
        """Input text at the current cursor position using pyautogui."""
        try:
            import pyautogui

            # Add a small delay to ensure we're ready to type
            time.sleep(0.1)

            # Type the text character by character
            pyautogui.typewrite(text, interval=0.01)

            logger.info("Successfully input text at cursor position")

        except ImportError:
            logger.error("pyautogui not installed. Cannot input text.")
        except Exception as e:
            logger.error(f"Failed to input text: {e}")

    def start(self, auto_reconnect: bool = True):
        """Start the voice input client."""
        logger.info("Starting Voice Input Tool - Windows Client")
        logger.info("Waiting for VoiceInputTool device...")

        # Keep trying to connect until successful
        while not self.connect_to_device():
            if not auto_reconnect:
                logger.error("Failed to connect and auto-reconnect is disabled.")
                sys.exit(1)
            time.sleep(2)

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
                # Check if connection is still alive
                with self._lock:
                    if not (self.serial_port and self.serial_port.is_open):
                        if auto_reconnect:
                            if not self.reconnect():
                                logger.error("Reconnection failed. Exiting...")
                                break
                        else:
                            logger.error("Connection lost. Exiting...")
                            break
        except KeyboardInterrupt:
            logger.info("\nShutting down Voice Input Tool...")
        finally:
            self.stop()

    def stop(self):
        """Stop the voice input client."""
        self.is_running = False

        with self._lock:
            if self.serial_port:
                try:
                    self.serial_port.close()
                except Exception as e:
                    logger.warning(f"Error closing serial port: {e}")
                self.serial_port = None

        logger.info("Disconnected from VoiceInputTool device.")


def check_dependencies() -> bool:
    """Check if required dependencies are available."""
    missing = []

    try:
        import serial
    except ImportError:
        missing.append("pyserial")

    try:
        import pyautogui
    except ImportError:
        missing.append("pyautogui")

    if missing:
        logger.error(f"Missing required dependencies: {', '.join(missing)}")
        logger.error("Please install dependencies with: pip install " + " ".join(missing))
        return False

    return True


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Voice Input Tool - Windows Client",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Run with default settings
  %(prog)s --baudrate 115200         # Use custom baudrate
  %(prog)s --no-reconnect            # Disable auto-reconnect
  %(prog)s -v                        # Enable verbose logging
        """
    )

    parser.add_argument(
        '--baudrate', '-b',
        type=int,
        default=9600,
        help='Serial baudrate (default: 9600)'
    )

    parser.add_argument(
        '--timeout', '-t',
        type=float,
        default=1.0,
        help='Serial timeout in seconds (default: 1.0)'
    )

    parser.add_argument(
        '--no-reconnect',
        action='store_true',
        help='Disable auto-reconnect on connection loss'
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_arguments()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not check_dependencies():
        sys.exit(1)

    config = SerialConfig(
        baudrate=args.baudrate,
        timeout=args.timeout
    )

    client = VoiceInputClient(config)
    client.start(auto_reconnect=not args.no_reconnect)


if __name__ == "__main__":
    main()
