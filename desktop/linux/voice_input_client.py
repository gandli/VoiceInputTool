#!/usr/bin/env python3
"""
Voice Input Tool - Linux Client
Receives text from Android device via USB serial and inputs it at cursor position.

Usage:
    python voice_input_client.py [options]

Options:
    -c, --config PATH    Path to configuration file
    -v, --verbose        Enable verbose logging
    --version            Show version information

Note:
    This client may require additional permissions for serial port access.
    Run with sudo or add your user to the 'dialout' group.
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


class LinuxVoiceInputClient(VoiceInputClientBase):
    """Linux-specific implementation of Voice Input Tool client."""
    
    # USB device patterns specific to Linux
    USB_PATTERNS = [
        'ttyUSB', 'ttyACM', 'ttyS', 'usbserial', 'cdc_acm'
    ]
    
    def __init__(self, config_path: str = None):
        super().__init__("Linux", config_path)
    
    def get_usb_device_patterns(self) -> list:
        """Return Linux-specific USB device patterns."""
        return self.USB_PATTERNS
    
    def get_paste_key(self) -> str:
        """Return Linux paste key (ctrl)."""
        return 'ctrl'
    
    def _show_permission_help(self):
        """Show Linux-specific permission help."""
        self.logger.error("Permission denied. Try one of the following:")
        self.logger.error("")
        self.logger.error("Option 1: Add user to dialout group")
        self.logger.error("  sudo usermod -aG dialout $USER")
        self.logger.error("  Then log out and log back in")
        self.logger.error("")
        self.logger.error("Option 2: Run with sudo (not recommended)")
        self.logger.error("  sudo python voice_input_client.py")
        self.logger.error("")
        self.logger.error("Option 3: Fix device permissions")
        self.logger.error("  sudo chmod 666 /dev/ttyUSB*  # or /dev/ttyACM*")


def show_system_info():
    """Display system information."""
    print(f"\n{'='*60}")
    print("Voice Input Tool - Linux Client")
    print(f"{'='*60}")
    print(f"Platform: {platform.system()} {platform.release()}")
    print(f"Distribution: {platform.freedesktop_os_release().get('PRETTY_NAME', 'Unknown') if hasattr(platform, 'freedesktop_os_release') else 'Unknown'}")
    print(f"Python: {platform.python_version()}")
    print(f"Architecture: {platform.machine()}")
    print(f"{'='*60}\n")


def main():
    """Main entry point for Linux client."""
    show_system_info()
    
    parser = create_argument_parser()
    args = parser.parse_args()
    
    # Load or create config
    config_manager = ConfigManager(args.config)
    
    # Override log level if verbose
    if args.verbose:
        config_manager.config.logging.level = "DEBUG"
    
    try:
        client = LinuxVoiceInputClient(args.config)
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
