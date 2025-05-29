# Pipecat Voice Bot Pipeline

An open-source voice bot pipeline project built on the Pipecat framework. This project provides a foundation for creating voice-based conversational AI applications.

## Overview

This project implements a voice bot pipeline using the Pipecat framework and follows the CAI base structure. It provides components for speech recognition, natural language processing, and speech synthesis to create interactive voice experiences.


## Getting Started

### Prerequisites

- Docker
- Git

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/Aniket-think41/Open-Source-CAI-Pipecat.git
   cd Open-Source-CAI-Pipecat/core
   ```

2. Manual setup:
   ```bash
   # Create and activate virtual environment
   python3 -m venv venv
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt
   ```

3. Start the backend:
   ```bash
   uvicorn main:app --reload
   ```

4. Start the frontend:
   ```bash
   pnpm i
   pnpm dev
   ```

5. Build the Docker image:
   ```bash
   docker build -t pipecat-voice-bot .
   ```

6. Run the Docker container:
   ```bash
   docker run -p 8000:8000 pipecat-voice-bot
   ```

7. Access the application at `http://localhost:8000`

## Usage

Once the application is running, you can interact with the voice bot through the web interface or API endpoints.

## API Documentation

API documentation is available at `http://localhost:8000/docs` when the server is running.

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
# foundational-ai-server
