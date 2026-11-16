"""Cross-platform graphical builder for Browser Agent.

Native desktop builds must be produced on the operating system where they will
run. This tool creates a portable onedir build and a platform installer/archive.
"""

from __future__ import annotations

import os
import platform
import queue
import shutil
import subprocess
import sys
import tarfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "releases"


class BuildManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Browser Agent Build Manager")
        root.geometry("860x650")
        root.minsize(720, 540)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Hint.TLabel", foreground="#5f6b7a")
        style.configure("Primary.TButton", padding=(14, 8))

        shell = ttk.Frame(root, padding=18)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Browser Agent Build Manager", style="Title.TLabel").pack(anchor="w")
        ttk.Label(
            shell,
            text="Create portable builds and native installers for the current operating system.",
            style="Hint.TLabel",
        ).pack(anchor="w", pady=(3, 14))

        settings = ttk.LabelFrame(shell, text="Build settings", padding=10)
        settings.pack(fill="x")
        self.project_dir = tk.StringVar(value=str(ROOT))
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.app_name = tk.StringVar(value="BrowserAgent")
        self.version = tk.StringVar(value="1.0.0")
        self.clean_build = tk.BooleanVar(value=True)
        self.include_readme = tk.BooleanVar(value=True)

        self._path_row(settings, 0, "Project folder", self.project_dir, self.choose_project)
        self._path_row(settings, 1, "Output folder", self.output_dir, self.choose_output)
        ttk.Label(settings, text="Application name").grid(row=2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(settings, textvariable=self.app_name).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Label(settings, text="Version").grid(row=2, column=2, sticky="w", padx=(12, 0), pady=(8, 0))
        ttk.Entry(settings, textvariable=self.version, width=14).grid(row=2, column=3, sticky="ew", padx=(8, 0), pady=(8, 0))
        ttk.Checkbutton(settings, text="Clean previous build", variable=self.clean_build).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(settings, text="Include README", variable=self.include_readme).grid(
            row=3, column=2, columnspan=2, sticky="w", pady=(8, 0)
        )
        settings.columnconfigure(1, weight=1)
        settings.columnconfigure(3, weight=1)

        actions = ttk.LabelFrame(shell, text="Package", padding=10)
        actions.pack(fill="x", pady=(12, 0))
        self.portable_button = ttk.Button(actions, text="Build portable ZIP", command=self.build_portable, style="Primary.TButton")
        self.portable_button.pack(side="left")
        self.installer_button = ttk.Button(actions, text="Build installer", command=self.build_installer)
        self.installer_button.pack(side="left", padx=(8, 0))
        self.both_button = ttk.Button(actions, text="Build both", command=self.build_both)
        self.both_button.pack(side="left", padx=(8, 0))
        ttk.Button(actions, text="Install PyInstaller", command=self.install_pyinstaller).pack(side="right")

        self.platform_label = ttk.Label(
            shell,
            text=f"Current platform: {platform.system()} ({platform.machine()})  •  Native builds must run on the target OS",
            style="Hint.TLabel",
        )
        self.platform_label.pack(anchor="w", pady=(10, 5))
        log_frame = ttk.LabelFrame(shell, text="Build log", padding=8)
        log_frame.pack(fill="both", expand=True)
        self.log = tk.Text(log_frame, state="disabled", wrap="word", font=("Consolas", 9), height=18)
        self.log.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log.yview)
        scrollbar.pack(side="right", fill="y")
        self.log.configure(yscrollcommand=scrollbar.set)
        self.write_log("Ready. Use 'Install PyInstaller' once if the build command is unavailable.")
        self.root.after(100, self.drain_events)

    def _path_row(
        self, parent: ttk.Widget, row: int, label: str, variable: tk.StringVar, command: object
    ) -> None:
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w")
        ttk.Entry(parent, textvariable=variable).grid(row=row, column=1, columnspan=3, sticky="ew", padx=(8, 0))
        ttk.Button(parent, text="Browse", command=command).grid(row=row, column=4, padx=(8, 0))
        parent.columnconfigure(1, weight=1)
        parent.columnconfigure(2, weight=1)
        parent.columnconfigure(3, weight=1)

    def choose_project(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.project_dir.get(), title="Choose project folder")
        if selected:
            self.project_dir.set(selected)

    def choose_output(self) -> None:
        selected = filedialog.askdirectory(initialdir=self.output_dir.get(), title="Choose output folder")
        if selected:
            self.output_dir.set(selected)

    def write_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text.rstrip() + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def drain_events(self) -> None:
        try:
            while True:
                kind, text = self.events.get_nowait()
                if kind == "log":
                    self.write_log(text)
                elif kind == "done":
                    self.running = False
                    self.set_buttons(True)
                    self.write_log(text)
                elif kind == "error":
                    self.running = False
                    self.set_buttons(True)
                    self.write_log("ERROR: " + text)
                    messagebox.showerror("Build failed", text)
        except queue.Empty:
            pass
        self.root.after(100, self.drain_events)

    def set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (self.portable_button, self.installer_button, self.both_button):
            button.configure(state=state)

    def run_background(self, action: str) -> None:
        if self.running:
            return
        self.running = True
        self.set_buttons(False)
        threading.Thread(target=self.build, args=(action,), daemon=True).start()

    def build_portable(self) -> None:
        self.run_background("portable")

    def build_installer(self) -> None:
        self.run_background("installer")

    def build_both(self) -> None:
        self.run_background("both")

    def install_pyinstaller(self) -> None:
        if self.running:
            return
        self.running = True
        self.set_buttons(False)
        threading.Thread(target=self.install_pyinstaller_worker, daemon=True).start()

    def install_pyinstaller_worker(self) -> None:
        try:
            self.run_command([sys.executable, "-m", "pip", "install", "pyinstaller"])
            self.events.put(("done", "PyInstaller installation completed."))
        except RuntimeError as exc:
            self.events.put(("error", str(exc)))

    def run_command(self, command: list[str], cwd: Path | None = None) -> None:
        self.events.put(("log", "$ " + " ".join(command)))
        process = subprocess.Popen(
            command, cwd=str(cwd or ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
        )
        assert process.stdout is not None
        for line in process.stdout:
            self.events.put(("log", line.rstrip()))
        if process.wait() != 0:
            raise RuntimeError(f"Command failed with exit code {process.returncode}: {' '.join(command)}")

    def build(self, action: str) -> None:
        try:
            project = Path(self.project_dir.get()).expanduser().resolve()
            output = Path(self.output_dir.get()).expanduser().resolve()
            entry = project / "main.py"
            if not entry.is_file():
                raise RuntimeError(f"Could not find application entry point: {entry}")
            output.mkdir(parents=True, exist_ok=True)
            dist = output / "dist"
            work = output / "build"
            name = self.app_name.get().strip() or "BrowserAgent"
            if self.clean_build.get():
                shutil.rmtree(dist, ignore_errors=True)
                shutil.rmtree(work, ignore_errors=True)

            self.events.put(("log", f"Building {name} for {platform.system()}..."))
            command = [
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
                "--name", name, "--distpath", str(dist), "--workpath", str(work),
                "--specpath", str(work), "--collect-all", "browser_use", str(entry),
            ]
            self.run_command(command, cwd=project)
            bundle = dist / name
            if not bundle.exists():
                raise RuntimeError(f"PyInstaller did not create the expected bundle: {bundle}")
            if self.include_readme.get() and (project / "README.md").is_file():
                shutil.copy2(project / "README.md", bundle / "README.md")
            self.write_release_notes(bundle, name)
            if action in ("portable", "both"):
                archive = self.make_portable_archive(bundle, output, name)
                self.events.put(("log", f"Portable package: {archive}"))
            if action in ("installer", "both"):
                artifact = self.make_installer(bundle, output, name)
                self.events.put(("log", f"Installer package: {artifact}"))
            self.events.put(("done", "Build completed successfully."))
        except (OSError, RuntimeError, ValueError) as exc:
            self.events.put(("error", str(exc)))

    def write_release_notes(self, bundle: Path, name: str) -> None:
        (bundle / "BUILD_INFO.txt").write_text(
            f"{name}\nPlatform: {platform.system()} {platform.machine()}\n"
            "This is a portable onedir build. Run the executable inside this folder.\n"
            "Browser engines may need to be installed by Browser Use on first run.\n",
            encoding="utf-8",
        )

    def make_portable_archive(self, bundle: Path, output: Path, name: str) -> Path:
        suffix = "windows" if os.name == "nt" else platform.system().lower()
        archive = output / f"{name}-{self.version.get().strip() or '1.0.0'}-{suffix}"
        if os.name == "nt":
            archive = archive.with_suffix(".zip")
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zipped:
                for path in bundle.rglob("*"):
                    if path.is_file():
                        zipped.write(path, path.relative_to(bundle.parent))
        else:
            archive = archive.with_suffix(".tar.gz")
            with tarfile.open(archive, "w:gz") as tar:
                tar.add(bundle, arcname=bundle.name)
        return archive

    def make_installer(self, bundle: Path, output: Path, name: str) -> Path:
        system = platform.system()
        if system == "Windows":
            return self.make_windows_installer(bundle, output, name)
        if system == "Darwin":
            return self.make_macos_installer(bundle, output, name)
        return self.make_linux_installer(bundle, output, name)

    def make_windows_installer(self, bundle: Path, output: Path, name: str) -> Path:
        iscc = shutil.which("iscc") or shutil.which("ISCC.exe")
        if not iscc:
            raise RuntimeError("Windows installer needs Inno Setup (ISCC.exe). Install it, add it to PATH, then retry.")
        script = output / f"{name}.iss"
        script.write_text(
            f'''[Setup]
AppName={name}
AppVersion={self.version.get().strip() or "1.0.0"}
DefaultDirName={{autopf}}\\{name}
OutputDir={output}
OutputBaseFilename={name}-installer
Compression=lzma
SolidCompression=yes
[Files]
Source: "{bundle}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{{autoprograms}}\\{name}"; Filename: "{{app}}\\{name}.exe"
Name: "{{commondesktop}}\\{name}"; Filename: "{{app}}\\{name}.exe"
''',
            encoding="utf-8",
        )
        self.run_command([iscc, str(script)], cwd=output)
        return output / f"{name}-installer.exe"

    def make_macos_installer(self, bundle: Path, output: Path, name: str) -> Path:
        hdiutil = shutil.which("hdiutil")
        if not hdiutil:
            raise RuntimeError("macOS installer needs hdiutil, which is included with macOS.")
        staging = output / f"{name}-dmg"
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir()
        shutil.copytree(bundle, staging / bundle.name)
        dmg = output / f"{name}-{self.version.get().strip() or '1.0.0'}.dmg"
        self.run_command([hdiutil, "create", "-volname", name, "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(dmg)])
        shutil.rmtree(staging, ignore_errors=True)
        return dmg

    def make_linux_installer(self, bundle: Path, output: Path, name: str) -> Path:
        installer_dir = output / f"{name}-installer"
        shutil.rmtree(installer_dir, ignore_errors=True)
        installer_dir.mkdir()
        shutil.copytree(bundle, installer_dir / bundle.name)
        (installer_dir / "install.sh").write_text(
            f'''#!/bin/sh
set -eu
TARGET="${{1:-$HOME/.local/opt/{name}}}"
mkdir -p "$TARGET"
cp -R "$(dirname "$0")/{name}/." "$TARGET/"
printf '%s\\n' "Installed {name} to $TARGET"
printf '%s\\n' "Run: $TARGET/{name}"
''',
            encoding="utf-8",
        )
        os.chmod(installer_dir / "install.sh", 0o755)
        archive = output / f"{name}-{self.version.get().strip() or '1.0.0'}-linux-installer.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(installer_dir, arcname=installer_dir.name)
        shutil.rmtree(installer_dir, ignore_errors=True)
        return archive


if __name__ == "__main__":
    root = tk.Tk()
    BuildManager(root)
    root.mainloop()
