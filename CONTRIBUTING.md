# Contributing to TwitchNet Analytics

First off, thank you for considering contributing to TwitchNet Analytics! 🎉

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Development Setup](#development-setup)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

This project and everyone participating in it is governed by our commitment to providing a welcoming and inclusive environment. Please be respectful and constructive in all interactions.

## How Can I Contribute?

### 🐛 Reporting Bugs

Before creating bug reports, please check existing issues to avoid duplicates. When creating a bug report, include:

- **Clear title** describing the issue
- **Steps to reproduce** the behavior
- **Expected behavior** vs. what actually happened
- **Screenshots** if applicable
- **Environment details**: OS, Python version, browser

### 💡 Suggesting Features

Feature suggestions are welcome! Please include:

- **Clear description** of the feature
- **Use case** explaining why this would be useful
- **Possible implementation** if you have ideas

### 🔧 Pull Requests

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Run tests and linting
5. Commit with clear messages (`git commit -m 'Add amazing feature'`)
6. Push to your branch (`git push origin feature/amazing-feature`)
7. Open a Pull Request

## Development Setup

### Prerequisites

- Python 3.9+
- Git
- Twitch Developer Account

### Local Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/twitchnet-analytics.git
cd twitchnet-analytics

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or
.\.venv\Scripts\Activate.ps1  # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Copy environment template
cp .env.example .env
# Edit .env with your Twitch credentials

# Run the application
streamlit run app.py
```

### Running Tests

```bash
# Run the test suite
python -m pytest

# Run with coverage
python -m pytest --cov=twitchnet

# Lint (pyflakes, import order, whitespace; configured in pyproject.toml)
python -m ruff check .
```

### Project Layout

- `twitchnet/` - core library (data collection, storage, network analysis, recommendations)
- `ui/` - Streamlit pages, routed by `app.py`
- `app.py`, `main.py`, `tracker.py`, `auth.py` - entry points
- `tests/` - pytest suite (no network access needed)
- `scripts/` - utility scripts

## Pull Request Process

1. **Update documentation** if you're changing functionality
2. **Add tests** for new features
3. **Follow the style guide** (see below)
4. **Update the README** if needed
5. **Request review** from maintainers

### Commit Message Format

Use clear, descriptive commit messages:

```
type: short description

Longer description if needed.

Fixes #123
```

Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Style Guidelines

### Python Code Style

- Follow **PEP 8** conventions
- Use **type hints** for function parameters and returns
- Write **docstrings** for all public functions and classes
- Maximum line length: **100 characters**
- Import from the package: `from twitchnet.database import DatabaseManager`
- Use **meaningful variable names**

```python
# Good
def calculate_centrality_score(graph: nx.Graph, node_id: str) -> float:
    """
    Calculate the centrality score for a given node.

    Args:
        graph: The NetworkX graph object
        node_id: The unique identifier of the node

    Returns:
        The calculated centrality score between 0 and 1
    """
    ...

# Bad
def calc(g, n):
    ...
```

### Documentation

- Keep README up to date
- Add inline comments for complex logic
- Update docstrings when changing function behavior

---

Thank you for contributing! 🙏
