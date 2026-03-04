# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed - Android

- **Missing Import**: Added missing `PendingIntent` import
- **Resource Leaks**: Properly close all streams using `closeQuietly()` helper method
- **Thread Safety**: Added synchronized blocks for USB connection operations
- **USB Detachment**: Added broadcast receiver for `ACTION_USB_ACCESSORY_DETACHED`
- **Permission Handling**: Properly register and handle USB permission requests
- **String Externalization**: Moved all hardcoded strings to `strings.xml`
- **Encoding**: Use `StandardCharsets.UTF_8` instead of default platform encoding

### Fixed - Windows Client

- **Exception Handling**: Improved error handling with specific exception types
- **Reconnection Logic**: Added automatic reconnection with exponential backoff
- **Buffer Management**: Implemented proper line-based buffering for serial data
- **Configuration**: Extracted serial config into `SerialConfig` dataclass
- **CLI Interface**: Added command-line arguments for configuration
- **Logging**: Replaced print statements with proper logging
- **Dependencies**: Added runtime dependency checks

### Added

- `.gitignore` file for Android and Python projects
- String resources file (`strings.xml`)
- Comprehensive documentation and comments
- Thread-safe connection handling
- Auto-reconnect functionality

### Changed

- Refactored code structure for better maintainability
- Improved code documentation with JavaDoc-style comments
- Enhanced error messages and user feedback
