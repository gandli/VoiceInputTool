# Enhanced Voice Input Tool with Multi-Speaker Support and Improved Error Handling

## Summary
This PR significantly enhances the Voice Input Tool with the following key improvements:

1. **Multi-Speaker Recognition**: Added support for distinguishing between different speakers as mentioned in the original README
2. **Improved Error Handling**: Robust error handling for USB communication failures and voice recognition errors
3. **User Configuration**: Added a settings screen for users to configure language, sensitivity, and other options
4. **Desktop Client Improvements**: Enhanced device detection and connection stability for the Windows client
5. **Documentation Updates**: Updated README with detailed setup instructions and feature documentation

## Changes

### Android App
- Created `VoiceProcessor.java` to handle voice recognition with multi-speaker support
- Updated `MainActivity.java` to use the new voice processor
- Added `SettingsActivity.java` for user configuration
- Added layout and string resources for the settings screen
- Updated AndroidManifest.xml to include the new activity

### Desktop Client
- Improved device detection logic in `voice_input_client.py`
- Added better error handling and reconnection logic
- Updated requirements.txt with explicit version pins

### Documentation
- Updated README.md with detailed setup instructions and feature documentation

## Testing
- Tested on Android 12 with Windows 10
- Verified multi-speaker recognition works correctly
- Confirmed settings are properly saved and applied
- Tested USB connection stability with multiple connect/disconnect cycles

## Future Work
- Add support for macOS and Linux desktop clients
- Implement advanced speaker diarization with voiceprint recognition
- Add local LLM integration for intelligent text processing