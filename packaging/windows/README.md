# GuitarTA Windows Package

This folder keeps Windows packaging separate from the main app code.

GitHub Actions runs `build.ps1` on a Windows runner and uploads:

```text
packaging/windows/dist/GuitarTA-windows.zip
```

The application data is still stored by the app itself. Packaging files in this
folder do not change the existing local database location.
