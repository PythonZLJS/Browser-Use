# Browser Agent for LM Studio

A Windows desktop GUI for [Browser Use](https://github.com/browser-use/browser-use) with an OpenAI-compatible model served by LM Studio. The app launches Brave when it finds the Brave executable; otherwise it falls back to Browser Use Chromium. The model can run on this computer or another machine.

## Start LM Studio

1. Load a model that supports tool/function calling.
2. Start the server from LM Studio's Developer tab. The usual local address is `http://localhost:1234`.
3. For a model server on another computer, enable **Serve on Local Network** and use its address, such as `http://192.168.1.20:1234/v1`.
4. In the GUI, click **Find models** and select a model ID. Enter an API key only if authentication is enabled.

The app checks LM Studio's OpenAI-compatible `/v1/models` endpoint, then falls back to its native `/api/v1/models` endpoint. [LM Studio model endpoint](https://lmstudio.ai/docs/developer/openai-compat/models)

## Install and run

Install Python 3.11 or newer. In PowerShell, from this folder:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## Brave profile

When Brave is installed in a standard Windows location, the app launches Brave with its own profile under `data/browser_profile`. This keeps your everyday Brave profile separate and avoids profile-lock conflicts. Sign in from the agent's Brave window to keep that session between runs. Turn off **Remember browser logins** to use a temporary profile.

## Saved information and actions

The app creates `data/agent_memory.sqlite3` for flashcards, task history, reusable actions, and custom collections. Flashcards preserve question/answer text. You can edit cards and collection names, descriptions, fields, and records in the GUI. The agent uses the same store and can inspect/search data, add and update records, and make requested deletions or metadata changes. It can also search, update, and remove flashcards and saved actions when asked.

The Run tab is a chat: the same message box starts tasks, queues follow-ups while it works, and starts a contextual follow-up after a task finishes. Use **Ctrl+Enter** to send. For questions that need web information, the agent can search using the browser even when you do not provide a URL. The activity feed shows browser steps and current status; it does not expose private model reasoning.

The Run tab accepts normal instructions with multiple HTTP(S) links embedded anywhere in the prompt. For multi-site research it visits the links in order, continues past pages that fail, saves source-by-source findings to a suitable local collection, then uses those saved findings to answer. The Actions tab also supports reusable workflows: select an action, enter one or more target URLs (one per line; semicolons also work), add optional run-specific details, and choose **Run action**. The workflow is expanded for each URL and runs sequentially, with results kept separate by site. You can ask the agent to save an action template during a task too.

The app sets Browser Use's conversation limit to 24,000 characters; its built-in compaction summarizes older steps once the conversation passes about 75% of that limit. Recent steps remain available, and the summary checkpoint carries into follow-up runs in the same session. The **Data manager** tab reviews saved item counts, deletes old or individual task history, removes empty collections, clears temporary browser cache while keeping login cookies, and compacts the shared SQLite database to reclaim unused file space.

To pause at a manual checkpoint, include an instruction like: "Before submitting, call `wait_for_user` with a summary and wait for my reply. Continue only after I say so." The Run tab then displays a reply box. A message sent there is used as the checkpoint reply; other messages are queued for after the current task finishes.

## Backup and restore

**Create backup** exports flashcards, custom collections and records, saved actions, and task history/chat as JSON. **Restore backup** replaces the sections present after confirmation; sections missing from an older backup are kept from the current database. The app keeps the existing SQLite database and adds new tables without deleting older data. It also accepts early version-1 backups and older `cards`/`runs` list names. Backups do not include browser cookies or login profiles.

## Safety and reliability

- Local models differ in tool-calling reliability. Use a model that supports tools/function calling.
- Keep a remote LM Studio endpoint on a trusted network, enable authentication, and do not expose unauthenticated HTTP to the public internet.
- Browser automation can submit forms and change accounts. Supervise actions with external effects.
- The app data folder is excluded from version control. It may contain personal information and browser login state; keep it private.
