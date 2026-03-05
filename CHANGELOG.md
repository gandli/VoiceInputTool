# Changelog

All notable changes to VoiceInputTool will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Complete Android app implementation with enhanced features
- macOS client for cross-platform support
- Linux client for cross-platform support
- Security utilities with input validation
- Logging rotation for all clients
- Comprehensive error handling and recovery
- Security ID generation for traceability
- Platform-specific keyboard control (Cmd on macOS, Ctrl on Windows/Linux)
- Improved USB device detection

### Changed
- Enhanced Android client with SpeechRecognizer for better accuracy
- Added security filtering to desktop clients
- Improved configuration management with validation
- better error messages and user feedback
- All clients now support Unicode/Chinese text
- Added security features to prevent command injection

### Deprecated

### Removed

### Fixed
- Missing Android app components (AndroidManifest, resources, dependencies)
- Incomplete Android implementation (now fully functional)
- Missing configuration files for desktop clients
- Error handling in USB communication
- Unicode text input across all platforms

### Security
- Added input validation to prevent command injection
- Added security ID for tracking sessions
- Input sanitization for special characters
- Null byte protection
- Connection timeout protection
- Secure file handling with rotation
- Line length limits to prevent buffer overflow
- Secure_ID generation for session tracking

## [2.0.0] - 2026-03-05

### Added
- **Base Client Module** (`voice_input_client_base.py`): Unified base class for all desktop clients
  - Abstract `VoiceInputClientBase` class with common functionality
  - Configuration management with dataclasses and validation
  - Security utilities with comprehensive input validation
  - Logging manager with rotation support
  - Standardized argument parser for all platforms
- **String Resources**: Complete Android string resources for internationalization
  - USB connection strings
  - Voice recognition error messages
  - Recording and text transfer strings

### Changed
- **Android MainActivity.java**: Major refactoring for code quality
  - Replaced boolean flags with `AtomicBoolean` for thread safety
  - Added proper resource cleanup in `onDestroy()`
  - Improved exception handling with specific error messages
  - Extracted all hardcoded strings to `strings.xml`
  - Added background thread management for USB reading
  - Better separation of concerns with private helper methods
  - Fixed potential memory leaks in stream handling

- **Desktop Clients Refactoring**: All three platform clients refactored to use base class
  - Windows client: Reduced from ~600 lines to ~70 lines
  - macOS client: Reduced from ~400 lines to ~90 lines  
  - Linux client: Reduced from ~350 lines to ~100 lines
  - Eliminated ~80% code duplication across platforms
  - Consistent CLI interface with `--config`, `--verbose`, `--version` options

### Code Quality Improvements
- **Type Safety**: Full type hints throughout Python codebase
- **Configuration Validation**: Automatic validation of all config values
- **Error Handling**: Consistent exception handling with helpful error messages
- **Documentation**: Comprehensive docstrings for all public APIs
- **Security**: Centralized security utilities with pattern detection

### Developer Experience
- Added unified `requirements.txt` for all desktop platforms
- Simplified maintenance with single source of truth in base module
- Easier testing with separated concerns
- Better debugging with structured logging

## [1.0.0] - 2026-03-04

### Added
- Project initialization
- Core concept definition
- Three-phase development roadmap
- Cross-platform support matrix

### Changed

### Deprecated

### Removed

### Fixed

### Security
