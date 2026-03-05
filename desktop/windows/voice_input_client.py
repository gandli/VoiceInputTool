#!/usr/bin/env python3
"""
Voice Input Tool - Windows Client
Receives text from Android device via USB serial and inputs it at cursor position.

Usage:
    python voice_input_client.py [options]

Options:
    -c, --config PATH    Path to configuration file
    -v, --verbose        Enable verbose logging
    --version            Show version information
"""

import sys
import os

# Add parent directory to path for importing base module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_input_client_base import (
    VoiceInputClientBase,
    create_argument_parser,
    ConfigManager
)


class WindowsVoiceInputClient(VoiceInputClientBase):
    """Windows-specific implementation of Voice Input Tool client."""
    
    # USB device patterns specific to Windows
    USB_PATTERNS = [
        'usb', 'serial', 'ch340', 'cp210', 'ftdi', 'pl2303',
        'arduino', 'stm32', 'cdc', 'acm', 'com'
    ]
    
    def __init__(self, config_path: str = None):
        super().__init__("Windows", config_path)
    
    def get_usb_device_patterns(self) -> list:
        """Return Windows-specific USB device patterns."""
        return self.USB_PATTERNS
    
    def get_paste_key(self) -> str:
        """Return Windows paste key (ctrl)."""
        return 'ctrl'
    
    def _show_permission_help(self):
        """Show Windows-specific permission help."""
        self.logger.error("Permission denied. Try running as Administrator")
        self.logger.error("Or check Device Manager for driver issues")


def main():
    """Main entry point for Windows client."""
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Load or create config
    config_manager = ConfigManager(args.config)
    
    # Override log level if verbose
    if args.verbose:
        config_manager.config.logging.level = "DEBUG"
    
    try:
        client = WindowsVoiceInputClient(args.config)
        client.start()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"\nFatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
