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

## [0.1.0] - 2026-03-04

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
