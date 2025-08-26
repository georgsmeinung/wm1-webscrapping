# Codespace Configuration for Web Scraping Project

This repository is configured with GitHub Codespaces for Python development focused on web scraping and text mining.

## What's Included

### Environment
- **Python 3.11** base environment
- **Git** and **GitHub CLI** pre-installed
- Automatic installation of project dependencies

### VS Code Extensions
- **Python Development**: Python, Pylance, Pylint, Black formatter, Flake8
- **Jupyter Support**: Full Jupyter notebook support with renderers and tools
- **Code Quality**: Ruff linter, formatting tools
- **File Support**: TOML, XML, JSON syntax highlighting

### Development Tools
- **Black** code formatting (runs on save)
- **Pylint** and **Flake8** linting
- **Auto import organization** on save
- **Ruff** for fast Python linting

### Project Dependencies
The following packages are automatically installed:
- `scrapy` - Web scraping framework
- `beautifulsoup4` - HTML parsing
- `pandas` - Data manipulation
- `scikit-learn` - Machine learning
- `nltk` - Natural language processing
- `gensim` - Topic modeling
- `joblib` - Model persistence
- And more (see `requirements.txt`)

## Getting Started

1. **Open in Codespace**: Click the "Code" button and select "Codespaces" → "Create codespace on main"
2. **Wait for setup**: The environment will automatically install all dependencies
3. **Start coding**: Everything is ready for web scraping development!

## Usage Examples

### Run the web scraper:
```bash
python 1-web-scrapping.py
```

### Process HTML to dataframe:
```bash
python 2-html-a-dataframe.py
```

### Train and evaluate models:
```bash
python 3-entrenar-y-evaluar.py
```

### Work with Jupyter notebooks:
Open any `.ipynb` file in the `web_mining_python/` directory.

## Project Structure

- `1-web-scrapping.py` - Main web scraping script
- `2-html-a-dataframe.py` - HTML processing and feature extraction
- `3-entrenar-y-evaluar.py` - Model training and evaluation
- `web_mining_python/` - Additional utilities and notebooks
- `config/` - Configuration files (stopwords, etc.)

## Environment Variables

The following environment variables are set:
- `PYTHONPATH`: Points to the workspace root
- `PYTHONUNBUFFERED`: Ensures Python output is not buffered

## Port Forwarding

Ports 8000 and 8080 are automatically forwarded for development servers.