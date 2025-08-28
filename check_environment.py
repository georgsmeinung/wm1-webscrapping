#!/usr/bin/env python3
"""
Getting Started with Web Scraping Project
==========================================

This script helps you get started with the web scraping project.
Run this to verify your environment is set up correctly.
"""

def check_environment():
    """Check if all required packages are available."""
    print("🔍 Checking Python environment...")
    
    try:
        import scrapy
        print(f"✅ scrapy {scrapy.__version__}")
    except ImportError:
        print("❌ scrapy not found")
        return False
    
    try:
        import pandas as pd
        print(f"✅ pandas {pd.__version__}")
    except ImportError:
        print("❌ pandas not found")
        return False
    
    try:
        import bs4
        print("✅ beautifulsoup4")
    except ImportError:
        print("❌ beautifulsoup4 not found")
        return False
    
    try:
        import sklearn
        print(f"✅ scikit-learn {sklearn.__version__}")
    except ImportError:
        print("❌ scikit-learn not found")
        return False
    
    try:
        import joblib
        print(f"✅ joblib {joblib.__version__}")
    except ImportError:
        print("❌ joblib not found")
        return False
    
    # Optional packages
    optional_packages = ['nltk', 'gensim']
    for package in optional_packages:
        try:
            __import__(package)
            print(f"✅ {package} (optional)")
        except ImportError:
            print(f"⚠️  {package} not found (optional)")
    
    return True

def show_project_structure():
    """Show the main project files and their purposes."""
    print("\n📁 Project Structure:")
    print("├── 1-web-scrapping.py      # Main web scraping script")
    print("├── 2-html-a-dataframe.py   # Convert HTML to dataset")
    print("├── 3-entrenar-y-evaluar.py # Train and evaluate models")
    print("├── web_mining_python/      # Additional utilities")
    print("│   ├── scrap_pagina12.py   # Alternative scraper")
    print("│   └── *.ipynb             # Jupyter notebooks")
    print("├── config/                 # Configuration files")
    print("└── requirements.txt        # Python dependencies")

def show_next_steps():
    """Show suggested next steps."""
    print("\n🚀 Next Steps:")
    print("1. Review the README.md for project details")
    print("2. Start with 1-web-scrapping.py to collect data")
    print("3. Use 2-html-a-dataframe.py to process HTML files")
    print("4. Train models with 3-entrenar-y-evaluar.py")
    print("5. Explore Jupyter notebooks in web_mining_python/")
    print("\n💡 Tips:")
    print("- Use VS Code's debugger with the pre-configured launch settings")
    print("- Check .vscode/launch.json for debug configurations")
    print("- The 'paginas' directory will be created to store scraped data")

if __name__ == "__main__":
    print("🕷️  Web Scraping Project - Environment Check")
    print("=" * 50)
    
    if check_environment():
        print("\n✅ Environment is ready!")
        show_project_structure()
        show_next_steps()
    else:
        print("\n❌ Environment setup incomplete.")
        print("Please run: pip install -r requirements.txt")