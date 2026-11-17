# 🌐 Browser Agent Desktop

A comprehensive Windows desktop GUI for [Browser Use](https://github.com/browser-use/browser-use). Automate web tasks, extract structured data, and run multi-step browser workflows using local AI models (via LM Studio) or cloud providers (OpenAI, Gemini). Everything is backed by a local SQLite database for persistent memory, flashcards, and custom datasets.

## 👋 Hey, welcome

I made this to put a powerful, persistent, and user-friendly interface on top of the awesome `browser-use` library. Instead of writing custom scripts for every browser automation task, you can just chat with your agent, save repeatable actions, and build local databases of information it collects.

**📦 Pre-compiled versions:**
If you don't want to mess with Python or command lines, **there is a pre-compiled version for Windows available now in the Releases section.** Just download and run it—no installation required! 
*(Pre-compiled versions for **macOS** and **Linux** are coming soon!)*

A couple of honest heads-ups if you are running it from source:

* **Local vs. Cloud:** You can run this 100% locally using LM Studio, which is great for privacy. However, browser automation requires models with strong tool-calling capabilities. If your local model struggles, you can easily switch to OpenAI or Gemini in the app's connection settings.
* **Browser Profile:** By default, the app looks for a standard Brave installation on Windows and creates an isolated profile just for the agent under `data/browser_profile`. This prevents it from messing with your daily browsing sessions. If Brave isn't found, it falls back to the default Chromium instance.
* **API Keys:** If you use OpenAI or Gemini, your API keys are intentionally kept session-only. They are never written to disk or saved in the settings file.

If you enjoy this project or find it useful for your own workflows, please consider starring the repo!

## ✨ What it does

* **Multi-Provider AI** — Switch seamlessly between LM Studio (local), OpenAI, and Gemini. The app automatically handles the endpoint routing and requirements for each.
* **Task Modes** — Adjust the agent's behavior on the fly: *Balanced* (normal speed/verification), *Research* (prioritizes citations and multiple sources), *Extract* (favor structured JSON outputs), or *Careful* (pauses before risky actions).
* **Exact-Answer Flashcards** — Save specific Q&A pairs. During quizzes or data entry, the agent can use a dedicated tool to look up and inject your exact stored text, verbatim.
* **Custom Collections** — Create your own local datasets (JSON records with custom fields). The agent can read, search, add, update, or delete records in these collections during its web research.
* **Reusable Actions & Multi-URL Workflows** — Save prompt templates for repeatable tasks. Feed the action a list of target URLs, and the agent will sequentially execute the workflow on every site, keeping results neatly separated.
* **Follow-up Queuing & Checkpoints** — Think of something else while the agent is working? Type it and hit send to queue it up. You can also tell the agent to call `wait_for_user` before submitting a form, and the UI will pop up a reply box so you can give it the green light.
* **Data Manager** — Import/export your history and datasets as JSON, prune old runs, and clear out temporary browser cache folders to save space.
* **Built-in GUI Packager** — Includes a cross-platform graphical build manager to easily compile your own standalone executables and native installers using PyInstaller.

## 🚀 Setup instructions (Running from source)

If you are using the pre-compiled Windows `.exe`, you can skip this entirely. If you want to run the raw Python code, follow these steps:

### 1. Install Python
You need Python 3.11 or newer. Grab it from [python.org](https://www.python.org/downloads/) (make sure to tick "Add python.exe to PATH" during installation on Windows).

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

## 📦 Building your own executables

The project now includes a graphical Build Manager (`build_gui.py`) so you can easily package the app for your current operating system. 

1. Run the build manager:
   ```bash
   python build_gui.py
   ```
2. Click **Install all requirements** before the first build. This installs only the Python project dependencies and PyInstaller required to compile the app. Browser engines are runtime downloads, not compiler inputs, so they are not downloaded during packaging setup.
3. On Windows, click **Install Windows installer tools**. This installs Inno Setup through `winget` when available and lets the build manager create the `.exe` installer. It now **automatically detects Inno Setup via the Windows Registry** or local AppData folders, so you don't even need to add it to your system PATH!
4. Choose your output folder and click **Build portable ZIP** or **Build installer**. The builder uses a fast onedir build by default, Python bytecode optimization, lean module exclusions, and only the Browser Use code/data it needs. **Use UPX when available** can reduce size further, but may trade a little startup speed for compression. 
   * *Native desktop packaging must be run on the operating system where the result will be used (e.g., build Windows on Windows, macOS on macOS).*
   * The Windows installer includes a standard uninstaller. Use **Windows Settings → Apps → Installed apps → BrowserAgent → Uninstall**, or run `unins000.exe` from the installation folder. Portable ZIP builds do not include an uninstaller; delete the extracted folder manually.

Installed builds store editable data in `%LOCALAPPDATA%\BrowserAgent\data`, so protected install folders will not cause SQLite read-only errors.

## 🖱️ How to use it

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

### Managing Local Data
* **Flashcards Tab:** Add static Q&A data you want the agent to memorize.
* **Collections Tab:** Define data structures (e.g., a "Competitor Pricing" collection). Tell the agent to "Save the pricing data to the Competitor Pricing collection."
* **Data Manager Tab:** Keep your local SQLite database clean, export your workspaces, or restore from a backup.

## 📁 Where your data goes

Once you run the application for the first time, it automatically generates a local data directory to keep everything safely on your machine:

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

## 📜 License

MIT — do whatever you like with it.
## Browser interaction and isolation

The visible browser runs in a separate window while the desktop app remains responsive. Follow-ups can be queued while the browser or model starts. Ask the agent to use `wait_for_user` when you want it to stop and let you take over the page; otherwise it may continue interacting with the same tab.

For a screen handoff, include the stopping point and your action in the task, for example: "Open the checkout page, then wait for me to choose the shipping option. Continue after I click Done." The agent pauses at that point, the checkpoint panel tells you to use the open browser, and **Done — continue** resumes the task after you finish.

The agent uses its own browser profile, or a temporary profile when saved logins are disabled. The optional navigation guard blocks file URLs, localhost destinations, and direct IP-address URLs. This is a navigation restriction, not a complete operating-system sandbox: page subrequests and the connection to the configured AI provider are outside the guard.

Frozen builds collect Browser Use's modules and runtime assets. Their editable data is stored beside the executable when writable, with the normal per-user data folder as a fallback.

## Periodic screen checks and keeping the browser open

The agent runs in five-step batches. At each checkpoint it requests a fresh screen/page inspection, incorporates any changes you made, and continues the same task. The task is capped at 100 agent steps.

Select **Keep browser open after task finishes** before starting a task to leave its visible browser window open when the task completes. Use **Close kept browser** to shut it down; starting another task also closes the previous kept window first.
