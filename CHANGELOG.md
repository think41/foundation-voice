# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **Centralized Provider Import Handling**: Introduced a new utility to dynamically import provider services (LLM, TTS, STT). This centralizes error handling for missing optional dependencies and provides clear installation instructions to the user.
- **Specific API Key Error Messages**: Refactored API key handling to raise errors that specify exactly which provider's key is missing and which environment variable needs to be set.

### Changed
- **Modular Installation with Extras**: The core `foundation-voice` package is now lightweight and includes only the basic SDK. To use services from providers like OpenAI, Deepgram, Cerebras, etc., you must install them as extras.

### Installation Guide

To install the basic SDK directly from the GitHub repository, run:
```bash
pip install "git+https://github.com/think41/foundation-voice.git#egg=foundation-voice"
```

To install with support for a specific provider, use extras. For example, to use OpenAI services (LLM, TTS, STT), install with:
```bash
pip install "git+https://github.com/think41/foundation-voice.git#egg=foundation-voice[openai]"
```

You can also combine extras to install support for multiple providers at once:
```bash
pip install "git+https://github.com/think41/foundation-voice.git#egg=foundation-voice[openai,deepgram,cartesia]"
```

This approach keeps the core installation minimal and allows you to only install the dependencies you need.
