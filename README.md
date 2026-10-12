# SimpleMemKitty

A lightweight memory cleaner for Windows. It ships with a small GUI (plus a system
tray icon) and can also run headless from the command line.

## Features

- **One-click clean** — trims the working set of running processes and purges the
  standby memory list. Fast and smooth.
- **Deep clean** — everything a one-click clean does, plus flushing the modified
  page list and purging the low-priority standby list.
- **Auto clean** — optionally runs the light clean automatically whenever memory
  usage stays above a configurable threshold.
- **System tray** — stays out of the way in the notification area.
- **Bilingual UI** — switch between Chinese and English at runtime.
- **Persistent settings** — stored as a small JSON file.
- **Testable core** — the cleaning logic is decoupled from the UI and from the
  Windows API, so it is covered by unit tests.

## Requirements

- Windows 10 or Windows 11 (64-bit)
- Python 3.8 or newer — only when running from source

Cleaning system-level memory lists requires administrator rights. When the app is
started without them it asks once and then keeps running in a degraded mode that
only trims regular process working sets.

## Getting started

### Prebuilt executable

Download `SimpleMemKitty.exe` from the release archive and double-click it.
The first launch takes a few seconds, because the single-file build unpacks itself
to a temporary folder before starting.

Headless deep clean (useful for Task Scheduler):

```
SimpleMemKitty.exe --deep-clean
```

### From source

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

`main.py` can also be double-clicked: if the current interpreter is missing the
dependencies, it re-launches itself with the `.venv` interpreter. The virtual
environment is looked up first in the project folder and then in the parent
folder, so a shared `.venv` in the parent directory works as well.

## Usage

Command line:

```bash
python main.py                # start the GUI
python main.py --deep-clean   # headless deep clean, no window
```

In the window:

- **One-Click Clean** — the everyday action; performs the light clean.
- **Deep Clean** — runs in a worker thread, so the window stays responsive.
- **Settings** — auto clean on/off, memory threshold, interval, language, and an
  optional notification after each clean (off by default).
- **Tray icon** — left-click shows or hides the window; right-click opens a menu
  with *Show Window*, *Settings* and *Exit*. Closing the window hides it to the
  tray, so use *Exit* to quit the app.

## Settings

Configuration is stored in `%USERPROFILE%\.simplememkitty\settings.json`, created
the first time the app saves it.

## Project structure

```
SimpleMemKitty/
├── main.py                    # entry point, double-clickable
├── simplememkitty/
│   ├── __init__.py
│   ├── __main__.py            # command line entry point (--deep-clean)
│   ├── core/                  # pure logic, no UI
│   │   ├── stats.py           # memory statistics
│   │   ├── settings.py        # settings persistence
│   │   ├── memory_api.py      # Windows API wrapper
│   │   └── cleaner.py         # cleaning orchestration
│   ├── auto/
│   │   └── auto_cleaner.py    # auto clean policy
│   └── ui/
│       ├── main_window.py     # main window + tray
│       └── settings_dialog.py
├── tests/                     # unit tests
├── build_exe.bat              # one-click packaging
├── build_exe.py               # packaging script
├── pyproject.toml
├── requirements.txt
├── conftest.py
├── .gitignore
└── LICENSE
```

## Development

Run the test suite:

```bash
pytest
```

The core tests do not need a GUI; the UI import test is skipped automatically when
PyQt5 is not installed.

### Architecture

- `simplememkitty.core` and `simplememkitty.auto` contain pure logic. `Cleaner` and
  `AutoCleaner` receive their collaborators (a `MemoryAPI` implementation, a
  settings object, a clock) through the constructor, which keeps them testable with
  fakes.
- Every Windows-specific call lives in `simplememkitty/core/memory_api.py`.
- Each cleaning step is wrapped in its own `try` block, so a single failing step is
  logged and never aborts the rest of the clean.
- Both cleaners measure available memory before and after a run and report the
  difference as the freed amount.

### Extending

- **New cleaning step** — add the method to `MemoryAPI` and `WindowsMemoryAPI`,
  then call it from `Cleaner`.
- **New option** — add it to `DEFAULTS` in `core/settings.py`; stored values are
  type-checked against the default when the file is loaded.

## Packaging

Build a single-file executable:

```bash
build_exe.bat
```

or

```bash
python build_exe.py
```

The executable is written to the project's parent folder. The script prepares its
own build environment under `%LOCALAPPDATA%\SimpleMemKittyBuild` and builds from a
temporary ASCII-only path, so the project itself can live anywhere.

Options:

```bash
python build_exe.py --outdir D:\out    # output directory
python build_exe.py --console          # keep a console window (debugging)
python build_exe.py --keep-temp        # keep intermediate files
python build_exe.py --clean-venv       # rebuild the build environment
```

Environment variables: `SMK_BUILD_ROOT` (build environment location) and
`SMK_PIP_INDEX` (pip index, defaults to `https://pypi.org/simple`).

## License

MIT — see [LICENSE](LICENSE).
