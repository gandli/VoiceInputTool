# VoiceInputTool 🎤

让手机通过 USB 连接充当电脑的语音输入设备，摆脱硬件麦克风束缚！

## 🎯 核心功能

- **语音转文字**：使用手机麦克风说话，文字自动输入到电脑光标位置
- **即插即用**：USB 连接后自动识别和配置
- **跨平台支持**：Android/iOS + Windows/Mac
- **低延迟**：实时文字输入体验

## 🚀 使用场景

- **文档写作**：边说边写，提高创作效率
- **代码注释**：快速添加代码说明
- **聊天输入**：在任何应用中使用语音输入
- **无障碍辅助**：为有特殊需求的用户提供便利

## 🔧 技术架构

### 阶段 1: 基础版
```
手机说话 → 系统语音识别 → USB传输 → 电脑光标输入
```

### 阶段 2: AI 校对版
```
手机说话 → 系统识别 → AI对话校对 → USB传输 → 电脑输入
```

### 阶段 3: 实时协作版
```
手机说话 → 实时AI处理 → 智能优化 → 实时输出到电脑
```

## 📱 平台支持

| 平台 | 状态 | 技术方案 |
|------|------|----------|
| Android + Windows | 开发中 | USB Accessory Mode + Serial |
| iOS + Mac | 计划中 | USB Network Tethering + WebRTC |
| Android + Mac | 计划中 | USB OTG + Serial |
| iOS + Windows | 计划中 | USB Network + Socket |

## 🛠️ 快速开始

### Android + Windows

1. **手机端**：安装 VoiceInputTool APK
2. **电脑端**：运行 Windows 客户端
3. **连接**：USB 数据线连接手机和电脑
4. **使用**：点击录音按钮开始语音输入

### 开发环境

```bash
# 克隆项目
git clone https://github.com/your-username/VoiceInputTool.git
cd VoiceInputTool

# Android 开发
cd android
./gradlew build

# Desktop 开发  
cd desktop
npm install
npm start
```

## 📊 路线图

- **Week 1**: Android + Windows 基础版 MVP
- **Week 2**: iOS + Mac 支持
- **Week 3**: AI 校对功能集成
- **Week 4**: 实时协作和多语言支持

## 🤝 贡献指南

欢迎贡献代码、报告问题或提出新功能建议！

1. Fork 本仓库
2. 创建你的特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交你的更改 (`git commit -m 'Add some amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

## 📄 许可证

MIT License - 详情请见 [LICENSE](LICENSE) 文件。

---

**Made with ❤️ for developers who love voice input!**