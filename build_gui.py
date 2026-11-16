"""Cross-platform graphical builder for Browser Agent.

Native desktop builds must be produced on the operating system where they will
run. This tool creates a portable onedir build and a platform installer/archive.
"""

from __future__ import annotations

import os
import platform
import queue
import re
import shutil
import subprocess
import sys
import tarfile
import threading
import tkinter as tk
import zipfile
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
try:
    import winreg
except ImportError:
    winreg = None


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "releases"
LEAN_EXCLUDES = (
    "tkinter.test",
    "pytest",
    "IPython",
    "jupyter",
    "matplotlib",
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SAFE_VERSION = re.compile(r"^[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?$")
PYINSTALLER_VERSION = "6.22.3"


def find_inno_compiler() -> str | None:
    """Find Inno Setup even when its installer directory is not on PATH."""
    candidates = [
        shutil.which("iscc"),
        shutil.which("ISCC.exe"),
        os.environ.get("INNO_SETUP_PATH"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
        r"C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
        r"C:\Program Files\Inno Setup 5\ISCC.exe",
        str(Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"),
        str(Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 5" / "ISCC.exe"),
    ]
    if winreg is not None and os.name == "nt":
        for root, subkey in (
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        ):
            try:
                with winreg.OpenKey(root, subkey) as uninstall:
                    for index in range(winreg.QueryInfoKey(uninstall)[0]):
                        try:
                            child_name = winreg.EnumKey(uninstall, index)
                            with winreg.OpenKey(uninstall, child_name) as child:
                                display_name = str(winreg.QueryValueEx(child, "DisplayName")[0])
                                install_location = str(winreg.QueryValueEx(child, "InstallLocation")[0])
                            if "Inno Setup" in display_name and install_location:
                                candidates.append(str(Path(install_location) / "ISCC.exe"))
                        except (OSError, FileNotFoundError):
                            continue
            except OSError:
                continue
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate))
    return None


class BuildManager:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("Browser Agent Build Manager")
        root.geometry("860x650")
        root.minsize(720, 540)
        self.events: queue.Queue[tuple[str, str]] = queue.Queue()
        self.running = False
        self.build_settings: dict[str, object] = {}
        self.install_project_dir = str(ROOT)

        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 20, "bold"))
        style.configure("Status.TLabel", foreground="#2563eb", font=("Segoe UI", 10, "bold"))
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
        status_bar = ttk.Frame(shell)
        status_bar.pack(fill="x", pady=(0, 12))
        self.status = tk.StringVar(value="Ready to build")
        self.status_label = ttk.Label(status_bar, textvariable=self.status, style="Status.TLabel")
        self.status_label.pack(side="left")
        self.progress_value = tk.DoubleVar(value=0)
        self.progress = ttk.Progressbar(
            status_bar, variable=self.progress_value, maximum=100, mode="determinate", length=260
        )
        self.progress.pack(side="right", fill="x", expand=True, padx=(18, 0))

        settings = ttk.LabelFrame(shell, text="Build settings", padding=10)
        settings.pack(fill="x")
        self.project_dir = tk.StringVar(value=str(ROOT))
        self.output_dir = tk.StringVar(value=str(DEFAULT_OUTPUT))
        self.app_name = tk.StringVar(value="BrowserAgent")
        self.version = tk.StringVar(value="1.0.0")
        self.clean_build = tk.BooleanVar(value=True)
        self.include_readme = tk.BooleanVar(value=True)
        self.compact_build = tk.BooleanVar(value=True)
        self.use_upx = tk.BooleanVar(value=False)

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
        ttk.Checkbutton(settings, text="Compact build", variable=self.compact_build).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(8, 0)
        )
        ttk.Checkbutton(settings, text="Use UPX when available", variable=self.use_upx).grid(
            row=4, column=2, columnspan=2, sticky="w", pady=(8, 0)
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
        self.install_pyinstaller_button = ttk.Button(actions, text="Install PyInstaller", command=self.install_pyinstaller)
        self.install_pyinstaller_button.pack(side="right")
        self.install_all_button = ttk.Button(
            actions, text="Install all requirements", command=self.install_all_requirements, style="Primary.TButton"
        )
        self.install_all_button.pack(side="right", padx=(0, 8))
        self.install_installer_button = ttk.Button(
            actions, text="Install Windows installer tools", command=self.install_windows_tools
        )
        self.install_installer_button.pack(side="right", padx=(0, 8))

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
        self.write_log("Ready. Use 'Install all requirements' before the first build.")
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
                elif kind == "progress":
                    value, status = text.split("|", 1)
                    self.progress_value.set(float(value))
                    self.status.set(status)
                elif kind == "done":
                    self.running = False
                    self.set_buttons(True)
                    self.progress_value.set(100)
                    self.status.set("Build completed")
                    self.write_log(text)
                elif kind == "error":
                    self.running = False
                    self.set_buttons(True)
                    self.status.set("Build failed")
                    self.write_log("ERROR: " + text)
                    messagebox.showerror("Build failed", text)
        except (ValueError, tk.TclError) as exc:
            self.running = False
            self.set_buttons(True)
            self.status.set("Build manager error")
            self.write_log("ERROR: Could not update build status: " + str(exc))
        except queue.Empty:
            pass
        self.root.after(100, self.drain_events)

    def set_buttons(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for button in (
            self.portable_button, self.installer_button, self.both_button,
            self.install_pyinstaller_button, self.install_all_button,
            self.install_installer_button,
        ):
            button.configure(state=state)

    def run_background(self, action: str) -> None:
        if self.running:
            return
        self.running = True
        self.set_buttons(False)
        self.progress_value.set(0)
        self.status.set("Preparing build...")
        self.build_settings = {
            "project_dir": self.project_dir.get().strip(),
            "output_dir": self.output_dir.get().strip(),
            "app_name": self.app_name.get().strip() or "BrowserAgent",
            "version": self.version.get().strip() or "1.0.0",
            "clean_build": self.clean_build.get(),
            "include_readme": self.include_readme.get(),
            "compact_build": self.compact_build.get(),
            "use_upx": self.use_upx.get(),
        }
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

    def install_all_requirements(self) -> None:
        if self.running:
            return
        self.running = True
        self.set_buttons(False)
        self.progress_value.set(0)
        self.status.set("Preparing dependency setup...")
        self.install_project_dir = self.project_dir.get().strip()
        threading.Thread(target=self.install_all_worker, daemon=True).start()

    def install_windows_tools(self) -> None:
        if self.running:
            return
        if platform.system() != "Windows":
            messagebox.showinfo(
                "Not needed on this platform",
                "Windows installer tools are only required when building the Windows installer on Windows.",
            )
            return
        if find_inno_compiler():
            self.status.set("Windows installer tools are already installed")
            self.write_log("Inno Setup compiler found.")
            return
        if not shutil.which("winget"):
            messagebox.showerror(
                "Cannot install Windows installer tools",
                "Inno Setup was not found and winget is unavailable. Install Inno Setup from "
                "https://jrsoftware.org/isinfo.php, then run this tool again.",
            )
            return
        self.running = True
        self.set_buttons(False)
        self.progress_value.set(0)
        self.status.set("Installing Windows installer tools...")
        threading.Thread(target=self.install_windows_tools_worker, daemon=True).start()

    def install_windows_tools_worker(self) -> None:
        try:
            self.events.put(("progress", "15|Installing Inno Setup..."))
            self.run_command([
                "winget", "install", "--id", "JRSoftware.InnoSetup", "--exact",
                "--silent", "--accept-source-agreements", "--accept-package-agreements",
            ])
            if not find_inno_compiler():
                raise RuntimeError("Inno Setup installation finished, but ISCC.exe was not found. Restart this app and try again.")
            self.events.put(("done", "Windows installer tools installed successfully."))
        except (OSError, RuntimeError) as exc:
            self.events.put(("error", f"Windows installer setup stopped: {exc}"))

    def install_all_worker(self) -> None:
        try:
            project = Path(self.install_project_dir).expanduser().resolve()
            requirements = project / "requirements.txt"
            if not requirements.is_file():
                raise RuntimeError(f"Could not find dependency file: {requirements}")
            self.events.put(("progress", "5|Checking Python and project files..."))
            self.events.put(("progress", "25|Installing application dependencies..."))
            self.run_command([
                sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                "--requirement", str(requirements),
            ])
            self.events.put(("progress", "55|Installing PyInstaller..."))
            self.run_command([
                sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                f"pyinstaller=={PYINSTALLER_VERSION}",
            ])
            self.events.put(("progress", "78|Checking optional installer tools..."))
            if platform.system() == "Windows" and not find_inno_compiler():
                self.events.put(("log", "Inno Setup is not installed. Use 'Install Windows installer tools' before building an EXE installer."))
            self.events.put(("done", "All requirements installed successfully. You can build now."))
        except (OSError, RuntimeError) as exc:
            self.events.put(("error", f"Dependency setup stopped: {exc}"))

    def install_pyinstaller_worker(self) -> None:
        try:
            self.events.put(("progress", "10|Installing PyInstaller..."))
            self.run_command([
                sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                f"pyinstaller=={PYINSTALLER_VERSION}",
            ])
            self.events.put(("done", "PyInstaller installation completed."))
        except (OSError, RuntimeError) as exc:
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
            settings = self.build_settings
            project = Path(str(settings["project_dir"])).expanduser().resolve()
            output = Path(str(settings["output_dir"])).expanduser().resolve()
            entry = project / "main.py"
            if not entry.is_file():
                raise RuntimeError(f"Could not find application entry point: {entry}")
            output.mkdir(parents=True, exist_ok=True)
            dist = output / "dist"
            work = output / "build"
            name = str(settings["app_name"])
            version = str(settings["version"])
            if not SAFE_NAME.fullmatch(name):
                raise ValueError("Application name must use only letters, numbers, dots, hyphens, and underscores.")
            if not SAFE_VERSION.fullmatch(version):
                raise ValueError("Version must look like 1.0.0 and contain no script characters.")
            if bool(settings["clean_build"]):
                shutil.rmtree(dist, ignore_errors=True)
                shutil.rmtree(work, ignore_errors=True)

            self.events.put(("progress", "5|Checking project files..."))
            self.events.put(("log", f"Building {name} for {platform.system()}..."))
            command = [
                sys.executable, "-m", "PyInstaller", "--noconfirm", "--windowed",
                "--onedir", "--clean", "--optimize", "2",
                "--name", name, "--distpath", str(dist), "--workpath", str(work),
                "--specpath", str(work), "--collect-submodules", "browser_use",
                "--collect-data", "browser_use", str(entry),
            ]
            if bool(settings["compact_build"]):
                for module in LEAN_EXCLUDES:
                    command.extend(["--exclude-module", module])
            if bool(settings["use_upx"]):
                upx = shutil.which("upx")
                if upx:
                    command.extend(["--upx-dir", str(Path(upx).parent)])
                else:
                    self.events.put(("log", "UPX was selected but was not found; continuing without UPX compression."))
            self.events.put(("progress", "15|Packaging application with PyInstaller..."))
            self.run_command(command, cwd=project)
            bundle = dist / name
            if not bundle.exists():
                raise RuntimeError(f"PyInstaller did not create the expected bundle: {bundle}")
            if bool(settings["include_readme"]) and (project / "README.md").is_file():
                shutil.copy2(project / "README.md", bundle / "README.md")
            self.write_release_notes(bundle, name)
            self.events.put(("progress", "72|Portable application bundle created..."))
            if action in ("portable", "both"):
                self.events.put(("progress", "82|Creating portable archive..."))
                archive = self.make_portable_archive(bundle, output, name)
                self.events.put(("log", f"Portable package: {archive}"))
            if action in ("installer", "both"):
                self.events.put(("progress", "91|Creating platform installer..."))
                artifact = self.make_installer(bundle, output, name)
                self.events.put(("log", f"Installer package: {artifact}"))
            self.events.put(("progress", "99|Finalizing build outputs..."))
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

    def package_version(self) -> str:
        return str(self.build_settings.get("version") or self.version.get().strip() or "1.0.0")

    @staticmethod
    def inno_value(value: str) -> str:
        if "\r" in value or "\n" in value:
            raise ValueError("Installer values cannot contain newlines.")
        return value.replace('"', '""')

    def make_portable_archive(self, bundle: Path, output: Path, name: str) -> Path:
        suffix = "windows" if os.name == "nt" else platform.system().lower()
        archive = output / f"{name}-{self.package_version()}-{suffix}"
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
        iscc = find_inno_compiler()
        if not iscc:
            raise RuntimeError("Windows installer needs Inno Setup. Click 'Install Windows installer tools', restart this app, then retry.")
        if not SAFE_NAME.fullmatch(name):
            raise ValueError("Application name must use only letters, numbers, dots, hyphens, and underscores.")
        version = self.package_version()
        if not SAFE_VERSION.fullmatch(version):
            raise ValueError("Version must look like 1.0.0 and contain no script characters.")
        safe_name = self.inno_value(name)
        safe_version = self.inno_value(version)
        safe_bundle = self.inno_value(str(bundle))
        safe_output = self.inno_value(str(output))
        script = output / f"{name}.iss"
        script.write_text(
            f'''[Setup]
AppName={safe_name}
AppVersion={safe_version}
DefaultDirName={{localappdata}}\\Programs\\{safe_name}
PrivilegesRequired=lowest
Uninstallable=yes
UninstallDisplayName={safe_name}
OutputDir="{safe_output}"
OutputBaseFilename={safe_name}-installer
Compression=lzma
SolidCompression=yes
[Files]
Source: "{safe_bundle}\\*"; DestDir: "{{app}}"; Flags: recursesubdirs ignoreversion
[Icons]
Name: "{{userprograms}}\\{safe_name}"; Filename: "{{app}}\\{safe_name}.exe"
Name: "{{userdesktop}}\\{safe_name}"; Filename: "{{app}}\\{safe_name}.exe"
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
        dmg = output / f"{name}-{self.package_version()}.dmg"
        self.run_command([hdiutil, "create", "-volname", name, "-srcfolder", str(staging), "-ov", "-format", "UDZO", str(dmg)])
        shutil.rmtree(staging, ignore_errors=True)
        return dmg

    def make_linux_installer(self, bundle: Path, output: Path, name: str) -> Path:
        if not SAFE_NAME.fullmatch(name):
            raise ValueError("Application name must use only letters, numbers, dots, hyphens, and underscores.")
        safe_name = name
        installer_dir = output / f"{name}-installer"
        shutil.rmtree(installer_dir, ignore_errors=True)
        installer_dir.mkdir()
        shutil.copytree(bundle, installer_dir / bundle.name)
        (installer_dir / "install.sh").write_text(
            f'''#!/bin/sh
set -eu
TARGET="${{1:-$HOME/.local/opt/{safe_name}}}"
mkdir -p "$TARGET"
cp -R "$(dirname "$0")/{safe_name}/." "$TARGET/"
printf '%s\\n' "Installed {safe_name} to $TARGET"
printf '%s\\n' "Run: $TARGET/{safe_name}"
''',
            encoding="utf-8",
        )
        os.chmod(installer_dir / "install.sh", 0o755)
        archive = output / f"{name}-{self.package_version()}-linux-installer.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(installer_dir, arcname=installer_dir.name)
        shutil.rmtree(installer_dir, ignore_errors=True)
        return archive


if __name__ == "__main__":
    root = tk.Tk()
    BuildManager(root)
    root.mainloop()
