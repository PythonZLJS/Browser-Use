# 🌐 Browser Agent Desktop

A comprehensive desktop GUI for [Browser Use](https://github.com/browser-use/browser-use). Automate web tasks, extract structured data, and run multi-step browser workflows using local AI models (via LM Studio) or cloud providers (OpenAI, Gemini). Everything is backed by a local SQLite database for persistent memory, flashcards, and custom datasets.

**Repo:** https://github.com/YOUR-USERNAME/YOUR-REPO-NAME

## 👋 Hey, welcome

I made this to put a powerful, persistent, and user-friendly interface on top of the awesome `browser-use` library. Instead of writing custom scripts for every browser automation task, you can just chat with your agent, save repeatable actions, and build local databases of information it collects.

A couple of honest heads-ups before you dive in:

* **Local vs. Cloud:** You can run this 100% locally using LM Studio, which is great for privacy. However, browser automation requires models with strong tool-calling capabilities. If your local model struggles, you can easily switch to OpenAI or Gemini in the app's connection settings.

* **Browser Profile:** By default, the app looks for a standard Brave installation on Windows and creates an isolated profile just for the agent. This prevents it from messing with your daily browsing sessions. If Brave isn't found, it falls back to the default Chromium instance.

* **API Keys:** If you use OpenAI or Gemini, your API keys are intentionally kept session-only. They are never written to disk or saved in the settings file.

* **Pre-compiled versions:** If you don't want to mess with Python or command lines, there are pre-compiled versions for Windows available now in the Releases section! You can choose between a **portable version** (just download and run, no installation required) or a standard **Windows installer**. *(Pre-compiled versions for macOS and Linux are coming soon!)*

If you enjoy this project or find it useful for your own workflows, please consider starring the repo!

## ✨ Features

* **Multi-Provider AI** — Switch seamlessly between LM Studio (local), OpenAI, and Gemini. The app automatically handles the endpoint routing and requirements for each.

* **Task Modes** — Adjust the agent's behavior on the fly: *Balanced* (normal speed/verification), *Research* (prioritizes citations and multiple sources), *Extract* (favor structured JSON outputs), or *Careful* (pauses before risky actions).

* **Exact-Answer Flashcards** — Save specific Q&A pairs. During quizzes or data entry, the agent can use a dedicated tool to look up and inject your exact stored text, verbatim.

* **Custom Collections** — Create your own local datasets (JSON records with custom fields). The agent can read, search, add, update, or delete records in these collections during its web research.

* **Reusable Actions & Multi-URL Workflows** — Save prompt templates for repeatable tasks. Feed the action a list of target URLs, and the agent will sequentially execute the workflow on every site, keeping results neatly separated.

* **Follow-up Queuing & Checkpoints** — Think of something else while the agent is working? Type it and hit send to queue it up. You can also tell the agent to call `wait_for_user` before submitting a form, and the UI will pop up a reply box so you can give it the green light.

* **Data Manager** — Import/export your history and datasets as JSON, prune old runs, and clear out temporary browser cache folders to save space.

* **Built-in GUI Packager** — Includes a cross-platform graphical build manager to easily compile your own standalone executables and native installers using PyInstaller.

## 🚀 How to use it

### Connecting to an AI Provider

1. Open the app and look at the **Connection & runtime** panel at the top.

2. Select your **AI provider** (LM Studio, OpenAI, or Gemini).

3. **For LM Studio:** Load a tool-calling capable model in LM Studio, start the local server (usually `http://localhost:1234/v1`), and click **Find models** in the app to populate the dropdown.

4. **For OpenAI/Gemini:** Enter your API key and type in your desired model string (e.g., `gpt-4o` or `gemini-2.5-flash`).

### Running Tasks

1. Go to the **Run & follow up** tab.

2. Describe your task in the message box (e.g., *"Go to example.com and extract the pricing table"*).

3. Hit **Send** (or `Ctrl+Enter`).

4. Watch the live browser activity log. If you need to stop the agent, hit **Stop**.

### Browser interaction and isolation

* The visible browser runs in a separate window while the desktop app remains responsive. Follow-ups can be queued while the browser or model starts.

* Ask the agent to use `wait_for_user` when you want it to stop and let you take over the page. For a screen handoff, include the stopping point and your action in the task (e.g., "Open the checkout page, then wait for me to choose the shipping option"). The agent pauses, the checkpoint panel tells you to use the open browser, and you click **Done — continue** when finished.

* The optional navigation guard blocks file URLs, localhost destinations, and direct IP-address URLs to restrict agent navigation.

### Periodic screen checks and keeping the browser open

* The agent runs in five-step batches. At each checkpoint it requests a fresh screen/page inspection, incorporates any changes you made, and continues the same task (capped at 100 agent steps).

* Select **Keep browser open after task finishes** before starting a task to leave its visible browser window open when the task completes. Use **Close kept browser** to shut it down.

### Managing Local Data

* **Flashcards Tab:** Add static Q&A data you want the agent to memorize.

* **Collections Tab:** Define data structures. Tell the agent to "Save the pricing data to the Competitor Pricing collection."

* **Data Manager Tab:** Keep your local SQLite database clean, export your workspaces, or restore from a backup.

## 🧠 How it works

Under the hood, the application seamlessly marries a synchronous GUI with asynchronous LLM browser interactions:

* **Local Memory Store:** The application relies on `MemoryStore`, a thread-safe local SQLite database wrapper (`agent_memory.sqlite3`). This database handles flashcards, chat history, custom collections, and saved actions using a fast WAL journal mode.

* **Threaded Execution:** The Tkinter GUI runs on the main thread, while the heavy `browser-use` AI loop runs in a dedicated background `threading.Thread`. They communicate via thread-safe queues (like `followup_queue`) and `root.after()` callbacks, keeping the UI liquid smooth even during heavy browser processing.

* **Agent Integration:** When a task starts, the app spins up a `browser_use.Agent` attached to an asynchronous `Browser` instance. Custom tools are injected into the agent using `@tools.action()`, allowing the LLM to directly trigger database calls (like `save_flashcard` or `search_collection`) and pause via the `wait_for_user` future checkpoint.

* **Build System (`build_gui.py`):** Uses PyInstaller to bundle the app into a portable package. It features an automated OS detection system that wraps the bundle in an Inno Setup `.exe` on Windows, a `.dmg` on macOS using `hdiutil`, or a `.tar.gz` on Linux.

## 🛠️ Getting started (running from source)

If you are using the pre-compiled Windows executables, you can skip this entirely. If you want to run the raw Python code, follow these steps:

### 1. Install Python

You need Python 3.11 or newer. Jump to [**Installing Python**](#-installing-python) at the very bottom of this page if you don't have it yet.

### 2. Get the code

```bash
git clone https://github.com/YOUR-USERNAME/YOUR-REPO-NAME.git
cd YOUR-REPO-NAME
```

### 3. Set up a virtual environment (Recommended)

```bash
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

*(Note: Because this relies on `browser-use`, you may also need to install Playwright's browsers by running `playwright install` in your terminal after the pip install).*

### 5. Run the app

```bash
python main.py
```

## 📦 Compiling a standalone executable

The project includes a graphical Build Manager (`build_gui.py`) so you can easily package the app for your current operating system into a single bundle or installer.

> **Note:** Native desktop packaging must be run on the operating system where the result will be used (e.g., build Windows on Windows, macOS on macOS).

1. Run the build manager:

   ```bash
   python build_gui.py
   ```

2. Click **Install all requirements** before the first build. This installs only the Python project dependencies and PyInstaller required to compile the app.

3. On Windows, click **Install Windows installer tools**. This automatically detects or installs Inno Setup via `winget` so the build manager can create a native `.exe` installer.

4. Choose your output folder and click **Build portable ZIP** or **Build installer**.

5. The builder uses a fast onedir build, Python bytecode optimization, and lean module exclusions. **Use UPX when available** can reduce size further.

Installed builds store editable data safely in `%LOCALAPPDATA%\BrowserAgent\data` (on Windows) or `~/.local/share/BrowserAgent/data` (on Unix), preventing SQLite read-only errors.

## 📁 Project structure

```text
browser-agent/
├── main.py                   # Core application engine and GUI
├── build_gui.py              # Cross-platform GUI builder for making executables
├── requirements.txt          # Python dependencies
└── data/                     # (Auto-generated) 100% local storage directory
    ├── agent_memory.sqlite3  # SQLite database for history, actions, and collections
    ├── app_settings.json     # Saved UI preferences and connection settings
    └── browser_profile/      # Isolated Brave/Chromium profile data (cookies, logins)
```

## 🐍 Installing Python

If you don't already have Python installed:

1. Go to https://www.python.org/downloads/

2. Download the latest Python 3 installer for your OS (3.11+ recommended).

3. **Windows:** during install, tick **"Add python.exe to PATH"** before clicking Install — this is the single most common setup mistake, and skipping it is why `python` or `pip` might say "not recognized" later.

4. **macOS:** the installer from python.org works fine, or use `brew install python` if you have Homebrew.

5. **Linux:** most distributions include Python already; if not, `sudo apt install python3 python3-pip python3-venv` (Debian/Ubuntu) or your distribution's equivalent package manager.

6. Confirm it worked:

   ```bash
   python --version      # Windows
   python3 --version     # Linux/macOS
   ```

## 📜 License

MIT — do whatever you like with it.