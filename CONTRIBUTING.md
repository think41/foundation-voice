# Contributing to Foundation Voice SDK

Thank you for your interest in contributing to the Foundation Voice SDK! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Making Changes](#making-changes)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Documentation](#documentation)
- [Code Style](#code-style)

## Code of Conduct

By participating in this project, you agree to maintain a respectful and inclusive environment for everyone. Please be kind and courteous in all interactions.

## Getting Started

1. Fork the repository
2. Clone your fork:
   ```bash
   git clone https://github.com/YOUR_USERNAME/foundation-voice.git
   cd foundation-voice
   ```
3. Add the upstream repository:
   ```bash
   git remote add upstream https://github.com/think41/foundation-voice.git
   ```

## Development Setup

1. Create and activate a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install development dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Set up your environment variables in a `.env` file:
   ```
   OPENAI_API_KEY="your_openai_api_key"
   DEEPGRAM_API_KEY="your_deepgram_api_key"
   CARTESIA_API_KEY="your_cartesia_api_key"
   DAILY_API_KEY="your_daily_api_key"
   ```

## Making Changes

1. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

2. Make your changes following the code style guidelines below

3. Write or update tests as needed

4. Update documentation if necessary

## Testing

1. Run the test suite:
   ```bash
   pytest
   ```

2. Ensure all tests pass before submitting a pull request

3. Add new tests for new features or bug fixes

## Pull Request Process

1. Update the README.md with details of changes if needed
2. Update the documentation if you've changed functionality
3. The PR will be merged once you have the sign-off of at least one other developer
4. Ensure your PR description clearly describes the problem and solution

## Documentation

1. Keep documentation up to date with your changes
2. Follow the existing documentation style
3. Include docstrings for all new functions and classes
4. Update examples if you've changed functionality

## Code Style

1. Follow PEP 8 guidelines
2. Use type hints for all function parameters and return values
3. Write clear, descriptive commit messages
4. Keep functions small and focused
5. Use meaningful variable and function names

### Python Code Style

```python
def example_function(param1: str, param2: int) -> bool:
    """
    Example function with proper docstring.

    Args:
        param1 (str): Description of param1
        param2 (int): Description of param2

    Returns:
        bool: Description of return value
    """
    # Implementation
    return True
```

## Questions and Support

If you have any questions or need help, please:
1. Check the existing documentation
2. Open an issue for bugs or feature requests
3. Join our community discussions

Thank you for contributing to Foundation Voice SDK!
