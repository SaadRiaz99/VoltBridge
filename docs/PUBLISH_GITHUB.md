# Working with VoltBridge on GitHub

Repository: https://github.com/SaadRiaz99/VoltBridge

## Clone and install (PowerShell)

```powershell
git clone https://github.com/SaadRiaz99/VoltBridge.git
cd VoltBridge
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m pytest -q
```

## Publish future changes

Create a feature branch, edit files, run the tests, then commit and push:

```powershell
git switch -c feature/my-change
git add .
git commit -m "Describe your change"
git push -u origin feature/my-change
```

Open a pull request on GitHub. Do not force-push over existing work. The ignore file excludes local databases, credentials, virtual environments and caches; review staged changes before committing.

The included GitHub Actions workflow tests Python 3.11, 3.12 and 3.13 when Actions is enabled. Local validation is documented separately in VALIDATION.md.
