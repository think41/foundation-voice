# 🚀 Foundational AI Server

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

A robust Python framework for building AI-powered voice applications using the Pipecat framework. This package provides essential tools and integrations for creating sophisticated voice-based conversational AI applications with ease.

## ✨ Features

- 🎙️ Voice interaction capabilities
- 🤖 AI-powered conversation management
- 🛠️ Extensible plugin architecture
- 🔌 Multiple AI provider integrations (OpenAI, Deepgram, etc.)
- 🚀 FastAPI-based web server
- 📊 Real-time analytics and monitoring
- 🔄 WebRTC support for real-time communication

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Git
- pip (Python package manager)

### Installation

You can install the package directly from GitHub using pip:

```bash
# Using HTTPS
pip install git+https://github.com/think41/foundational-ai-server.git

# Or using SSH (if you have SSH keys set up)
pip install git+ssh://git@github.com/think41/foundational-ai-server.git
```

Or add it to your `requirements.txt`:

```
git+https://github.com/think41/foundational-ai-server.git#egg=foundational_ai_server
```

## 🏗️ Project Structure

```
foundational-ai-server/
├── foundational_ai_server/     # Main package
│   ├── agent/                  # Agent implementation
│   ├── agent_configure/        # Agent configuration
│   ├── custom_plugins/         # Custom plugins
│   │   ├── frames/            # Frame definitions
│   │   ├── processors/        # Data processors
│   │   └── services/          # Service integrations
│   └── utils/                  # Utility functions
├── examples/                   # Example implementations
├── tests/                      # Test suite
├── .env.example               # Example environment variables
├── pyproject.toml             # Project configuration
└── README.md                  # This file
```

## 🛠️ Configuration

1. Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

2. Update the `.env` file with your API keys and configuration:

```env
OPENAI_API_KEY=your_openai_api_key
DEEPGRAM_API_KEY=your_deepgram_api_key
DAILY_API_KEY=your_daily_api_key
DAILY_SAMPLE_ROOM_URL=your_daily_room_url
```

## 🚀 Running the Example

1. Navigate to the examples directory:

```bash
cd examples
```

2. Run the example server:

```bash
uvicorn main:app --reload
```

3. Open your browser and navigate to `http://localhost:8000`

## 🧪 Running Tests

```bash
# Install test dependencies
pip install -r requirements-test.txt

# Run tests
pytest
```

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

Please read our [Contributing Guidelines](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 📞 Support

For support, please open an issue in the GitHub repository.

## 📚 Documentation

For detailed documentation, please refer to our [Documentation](https://github.com/think41/foundational-ai-server/wiki).

---

Made with ❤️ by Think41
