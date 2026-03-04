# VoiceInputTool 🎤

Transform your smartphone into a USB-connected voice input device for your computer, eliminating the need for dedicated hardware microphones!

## 🎯 Core Features

- **Voice-to-Text**: Speak into your phone's microphone and have text automatically input at your computer's cursor position
- **Plug-and-Play**: Automatic detection and configuration upon USB connection
- **Cross-Platform Support**: Android/iOS + Windows/Mac
- **Low Latency**: Real-time text input experience

## 🚀 Use Cases

- **Document Writing**: Speak while writing to boost productivity
- **Code Comments**: Quickly add code documentation
- **Chat Input**: Use voice input in any application
- **Accessibility**: Provide便利 for users with special needs

## 🔧 Technical Architecture

### Phase 1: Basic Version
```
Phone Speech → System Voice Recognition → USB Transfer → Computer Cursor Input
```

### Phase 2: AI Proofreading Version
```
Phone Speech → System Recognition → AI Dialogue Proofreading → USB Transfer → Computer Input
```

### Phase 3: Real-time Collaboration Version
```
Phone Speech → Real-time AI Processing → Intelligent Optimization → Real-time Output to Computer
```

## 📱 Platform Support

| Platform | Status | Technical Approach |
|----------|--------|-------------------|
| Android + Windows | In Development | USB Accessory Mode + Serial |
| iOS + Mac | Planned | USB Network Tethering + WebRTC |
| Android + Mac | Planned | USB OTG + Serial |
| iOS + Windows | Planned | USB Network + Socket |

## 🛠️ Quick Start

### Android + Windows

1. **Mobile**: Install VoiceInputTool APK
2. **Computer**: Run Windows client
3. **Connect**: USB cable between phone and computer  
4. **Use**: Tap record button to start voice input

### Development Environment

```bash
# Clone project
git clone https://github.com/gandli/VoiceInputTool.git
cd VoiceInputTool

# Android Development
cd android
./gradlew build

# Desktop Development  
cd desktop
npm install
npm start
```

## 📊 Roadmap

- **Week 1**: Android + Windows MVP
- **Week 2**: iOS + Mac support
- **Week 3**: AI proofreading integration
- **Week 4**: Real-time collaboration and multi-language support

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

**Made with ❤️ for developers who love voice input!**