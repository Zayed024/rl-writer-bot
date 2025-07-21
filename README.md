# AI-Powered Publishing Workflow


---

## 📚 Table of Contents

- [Introduction](#introduction)
- [Key Features](#key-features)
  - [Dynamic Web Scraping & Validation](#dynamic-web-scraping--validation)
  - [AI Content Generation (Spinning) & Review](#ai-content-generation-spinning--review)
  - [Human-in-the-Loop (HITL) Workflow](#human-in-the-loop-hitl-workflow)
  - [Adaptive Prompt Learning (RL-Based Inference)](#adaptive-prompt-learning-rl-based-inference)
  - [Content Versioning & Semantic Search](#content-versioning--semantic-search)
  - [Voice Output](#voice-output)
  - [Modular & Asynchronous Architecture](#modular--asynchronous-architecture)
- [How It Works](#how-it-works)
- [Setup & Installation](#setup--installation)
- [Usage](#usage)
- [Future Implementations](#future-implementations)
- [License](#license)

---

##  Introduction

Welcome to the **AI-Powered Publishing Workflow**!  
This project demonstrates a sophisticated system designed to automate and enhance the initial stages of book publication. It intelligently fetches content from the web, leverages large language models (LLMs) to "spin" (rewrite) and review chapters, and integrates human feedback to continuously improve its AI agents.

The core idea is to create a seamless, iterative process where AI and human editors collaborate, with the system learning from each interaction to become more effective over time.

---

##  Key Features

### 🔍 Dynamic Web Scraping & Validation
- **Flexible Content Acquisition**: Scrapes chapter content and takes screenshots from Wikisource based on book title, number, and chapter.
- **Intelligent Validation**: Ensures chapter exists by checking content presence and filtering "Page not found" indicators.
- **Unique File Management**: Saves scraped data to uniquely named files (`scraped_content_BookX_ChapterY.txt`).

### ✍️ AI Content Generation (Spinning) & Review
- **AI Writer**: Uses Gemini LLM (`gemini-1.5-flash`) to rewrite content with improved engagement or clarity.
- **AI Reviewer**: Gemini LLM (`gemini-1.5-pro`) reviews the content like an experienced editor, suggesting improvements.
- **Asynchronous Operations**: All LLM interactions run asynchronously, enabling responsiveness and multi-chapter support.

### 👥 Human-in-the-Loop (HITL) Workflow
- **Interactive CLI**: Lets editors rate, revise, and finalize content.
- **Iterative Refinement**: Multiple review/edit/spin rounds until content is finalized.
- **Quantified Feedback**:
  - Human ratings (1–5 stars).
  - Levenshtein distance to measure edit effort.
  - Reward system based on feedback and performance.

### 🧬 Adaptive Prompt Learning (RL-Based Inference)
- **Reward Calculation**: Based on human feedback, edit effort, iteration count, and re-spin requests.
- **Prompt Scoring**: Maintains and updates scores for prompts, selecting top-performing ones over time.
- **AI Prompt Generator**: A Gemini model generates new prompts if existing ones fail, enriching the prompt pool dynamically.

### 🧠 Content Versioning & Semantic Search
- **ChromaDB Integration**: Stores all versions of content (original, spun, edited, finalized) with rich metadata.
- **Advanced Filtering**: Filter by version type, book/chapter, editor, etc.
- **RL for Scraping**: Tracks which source scrapes yield higher final rewards.

### 🔊 Voice Output
- **Text-to-Speech**: Uses `gTTS` + `python-vlc` for audio playback of AI content and reviews.

### 🧩 Modular & Asynchronous Architecture
- **Codebase**: Organized into logical modules (`scrape.py`, `review.py`, `intervention.py`, etc.).
- **Async Operations**: Ensures responsiveness using `asyncio` for API calls and scraping.

---

##  How It Works

1. **Start**: Load default or custom Wikisource chapter.
2. **AI Writer**: Generates rewritten chapter using adaptive prompt.
3. **AI Reviewer**: Adds feedback.
4. **Human Review**:
   - Rate output (1–5 stars).
   - Edit content directly.
   - Request re-spin (adaptive/custom/new prompt).
   - Listen to audio output.
   - Search content semantically.
5. **Learning & Reward**:
   - Reward calculated using ratings, edit effort, etc.
   - Prompt scores updated.
   - Poor prompts lead to new AI-generated ones.
6. **Versioning**: Every step/version is stored with full metadata in ChromaDB.
7. **Repeat** until chapter is finalized.

---

##  Setup & Installation

### 1. Clone the Repository
```bash
git clone https://github.com/YourUsername/AI-Powered-Publishing-Workflow.git
cd AI-Powered-Publishing-Workflow
```

### 2.Create a Virtual Environment(Recommended)
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 3.Install Dependencies
```bash
pip install -r requirements.txt
```

### 4.Install Playwright Browsers
```bash
playwright install
```

### 5.Install VLC Media Player

### 6.Set Your Gemini API Key
Get your key from Google AI Studio and set it as an environment variable:

Windows (Command Prompt):
```Cmd
set GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

PowerShell:
```Powershell
$env:GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

macOS/Linux:
```bash
export GEMINI_API_KEY="YOUR_API_KEY_HERE"
```

## Usage

Run the Main App

```bash
python intervention.py
```

## 2.Follow the Prompts:
The application will present a main menu:

### 1. Start/Continue Chapter Workflow (for initial chapter): 
This will load or scrape the default chapter (The Gates of Morning, Book 1, Chapter 1) and begin the review process.

### 2. Scrape a NEW Chapter and start its Workflow: 
This allows you to enter a custom book title, book number, and chapter number to scrape and initiate a new workflow.

### 3. Exit: Quits the application.

## 3.Interact with the Chapter Workflow:
Once a chapter workflow starts, you'll be prompted to:

- Enter your editor name.

- Rate the AI's spun content (1-5 stars).

- Choose an action:

- Edit the current content directly:
Opens a text editor (Notepad on Windows, Vim/Nano on Linux/macOS) for manual edits. Save and close the file, then press Enter in the terminal.

- Accept current content and finalize: Marks the chapter as complete and stores the final version.

- Request AI to re-spin the chapter: Offers options to use the adaptive prompt, provide a custom instruction, or generate a brand new prompt using AI.

- Perform a semantic search: Query the ChromaDB for relevant content across all stored chapter versions, with advanced filtering options.

- Listen to content: Play audio of the current AI-spun content or AI reviewer comments.

## Observe Learning:

- Keep an eye on the console output for messages from the Prompt Manager showing how prompt scores are updated.

- Check the prompt_scores.json file in your project directory to see the persistent changes in prompt effectiveness.

- Observe how the system's "adaptive prompt" choice changes over multiple iterations and feedback loops.

## Future Implementations
This project lays a strong foundation for an advanced AI-powered publishing system. Here are some exciting areas for future development:

- Graphical User Interface (GUI): Develop a web-based GUI ( using Streamlit, Flask, or React) to replace the command-line interface, providing a more intuitive and visually appealing user experience.

- Enhanced Error Resilience: Implement more sophisticated retry mechanisms with exponential backoff for all external API calls to gracefully handle transient network issues and API rate limits.

- Comprehensive Logging: Fully integrate Python's logging module across all project files for detailed, filterable, and persistent logs, aiding in debugging and performance monitoring.

- Granular Reviewer Feedback Integration: Implement a mechanism for humans to explicitly mark individual AI reviewer suggestions as "incorporated" or "ignored," providing more precise feedback for the AI Reviewer's learning.

- More Sophisticated RL Agents: Transition from heuristic-based adaptive prompting to formal Reinforcement Learning algorithms (Q-learning, Policy Gradients) to train dedicated agents that learn optimal strategies for content generation and review based on human preferences.

- User Authentication & Collaboration: For a multi-user environment, implement user authentication and features for collaborative editing and review.


License
This project is licensed under the MIT License - see the LICENSE file for details



