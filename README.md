# Circuit Shelf — electronics inventory

Offline desktop archive for lab components, inspired by ECE Basics Companion. Runs on Windows with Python 3.10+; no pip installs or account required.

## Start

Double-click `start_windows.bat` on Windows, or run `python app.py` from this folder. Your database is created at `%LOCALAPPDATA%\ElectronicsInventory\inventory.db` (on other systems, under your home folder). The app does not need a network connection.

## Use

- **New → Save** creates a component. Record name, category, part number, value, package, quantity, reorder minimum, physical location, datasheet reference, and notes.
- Search across names, categories, part numbers, values, locations, and notes. Filter by category or low stock. Amber rows have quantity at or below the minimum.
- Select a record to edit it. **Adjust stock** records additions and use with a reason and timestamp. Editing quantity directly also records the difference.
- **Export CSV** makes a spreadsheet-friendly inventory. **Import CSV** appends rows, including duplicates; review the confirmation count first. CSV needs `name` and `quantity` headers. Use **Backup** to save a full SQLite copy including stock history. To restore, close the app and replace `inventory.db` with the backup.
- The datasheet field stores a URL or file path as text. Place or bin identifiers such as `Cabinet A / Drawer 2 / Box 4` in Location.

The archive starts empty so only your actual lab stock is represented. Avoid opening the same database in two app instances while making edits. Deleting a record also deletes its history.
