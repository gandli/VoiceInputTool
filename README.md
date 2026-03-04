# VoiceInputTool 🎤

Transform your smartphone into a USB-connected voice input device for your computer, enabling **older computers** to leverage **mobile AI capabilities** and **multi-speaker dialogue recognition**!

## 🎯 Core Features

- **Voice-to-Text for Legacy Systems**: Enable voice input on older computers (Windows XP+, macOS 10.6+, Linux) that lack modern microphones or processing power
- **Mobile AI Integration**: Utilize your smartphone's powerful large language models for intelligent text correction and formatting
- **Multi-Speaker Dialogue Recognition**: Automatically distinguish between different speakers in conversations (interviews, meetings, legal interrogations)
- **Plug-and-Play**: Automatic detection and configuration upon USB connection
- **Offline Operation**: No internet required - all processing happens locally on your phone

## 🚀 Use Cases

### Legal & Law Enforcement
- **Interrogation Records**: Automatically generate formatted interrogation transcripts with speaker labels
- **Evidence Documentation**: Create accurate records during field investigations
- **Compliance**: Ensure proper legal terminology and procedural compliance

### Business & Professional  
- **Meeting Minutes**: Generate structured meeting notes with speaker identification
- **Interview Transcripts**: Create professional interview records with automatic formatting
- **Medical Notes**: Document patient consultations with role-based formatting

### Accessibility & Legacy Systems
- **Old Computer Modernization**: Give decade-old computers modern voice input capabilities
- **Cost-Effective Upgrade**: No need to purchase new hardware or external microphones
- **Privacy-Focused**: All processing happens locally, no data leaves your devices

## 🔧 Technical Architecture

### Phase 1: Basic Multi-Speaker Recognition
```
Phone Microphone → System Voice Recognition → Speaker Role Assignment → USB Transfer → Computer Cursor Input
```

### Phase 2: Advanced Speaker Diarization  
```
Phone Microphone → Voice Activity Detection → Speaker Diarization → ASR → LLM Processing → Formatted Output → USB Transfer
```

### Phase 3: Full AI Integration
```
Phone Microphone → Real-time Speaker Separation → Local LLM Processing → Intelligent Formatting → Real-time Output to Computer
```

## 📱 Platform Support

| Platform | Status | Technical Approach |
|----------|--------|-------------------|
| Android + Windows | In Development | USB Accessory Mode + Serial |
| Android + macOS | Planned | USB Network Tethering + WebRTC |
| Android + Linux | Planned | USB OTG + Serial |

**Note**: iOS support is limited due to Apple's restrictions on USB audio functionality.

## ⚙️ Configuration

The app now includes a settings screen where you can:
- Select voice recognition language
- Enable/disable multi-speaker mode
- Configure speaker roles (Interviewer, Interviewee, etc.)
- Adjust sensitivity for voice detection
- Choose text output format (plain text, formatted dialogue, etc.)

## 🛠️ Quick Start

### Android + Windows

1. **Build Android App**:
   ```bash
   cd android
   ./gradlew assembleDebug
   # Install app-debug.apk on your Android phone
   ```

2. **Install Windows Client**:
   ```bash
   cd desktop/windows
   pip install -r requirements.txt
   python voice_input_client.py
   ```

3. **Connect**: USB cable between phone and computer  
4. **Use**: Select conversation template and start speaking

### System Requirements

**Computer**: Any system with USB port and basic Python support (Windows XP+, macOS 10.6+, Linux)
**Phone**: Android 8.0+ with decent microphone quality

## 📊 Roadmap

- **Week 1**: Multi-speaker role assignment (preset roles) + Legacy system compatibility
- **Week 2**: Speaker diarization with voiceprint recognition  
- **Week 3**: Local LLM integration for intelligent text processing
- **Week 4**: Professional templates (Legal, Meeting, Medical, General)

## 🤝 Contributing

Contributions are welcome! Please feel free to submit code, report issues, or suggest new features.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

**Made with ❤️ to bring AI-powered voice input to everyone, regardless of their hardware!**