#!/usr/bin/env python3
"""
Voice Input Tool - macOS Client
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
import platform

# Add parent directory to path for importing base module
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from voice_input_client_base import (
    VoiceInputClientBase,
    create_argument_parser,
    ConfigManager
)


class MacOSVoiceInputClient(VoiceInputClientBase):
    """macOS-specific implementation of Voice Input Tool client."""
    
    # USB device patterns specific to macOS
    USB_PATTERNS = [
        'usbserial', 'usbmodem', 'cu.usbserial', 'tty.usbserial',
        'usbserial', 'cdcacm', 'tty.usbmodem'
    ]
    
    def __init__(self, config_path: str = None):
        super().__init__("macOS", config_path)
    
    def get_usb_device_patterns(self) -> list:
        """Return macOS-specific USB device patterns."""
        return self.USB_PATTERNS
    
    def get_paste_key(self) -> str:
        """Return macOS paste key (cmd)."""
        return 'cmd'
    
    def _show_permission_help(self):
        """Show macOS-specific permission help."""
        self.logger.error("Permission denied. Try:")
        self.logger.error("  1. Add your user to the 'dialout' group:")
        self.logger.error("     sudo dseditgroup -o edit -a $USER -t user dialout")
        self.logger.error("  2. Or check System Preferences > Security & Privacy")
        self.logger.error("  3. Log out and log back in after changes")


def show_system_info():
    """Display system information."""
    print(f"\n{'='*60}")
    print("Voice Input Tool - macOS Client")
    print(f"{'='*60}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Python: {platform.python_version()}")
    print(f"Architecture: {platform.machine()}")
    print(f"{'='*60}\n")


def main():
    """Main entry point for macOS client."""
    show_system_info()
    
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Load or create config
    config_manager = ConfigManager(args.config)
    
    # Override log level if verbose
    if args.verbose:
        config_manager.config.logging.level = "DEBUG"
    
    try:
        client = MacOSVoiceInputClient(args.config)
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
