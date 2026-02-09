# Kiyomi Self-Update System

The self-update system allows Kiyomi to update herself from GitHub Releases automatically or on demand. No git dependency required.

## How It Works

### User-Triggered Updates
Users can trigger updates via the `/update` command in Telegram, or by saying:
- "update"
- "update yourself"
- "check for updates"
- "upgrade"
- "get latest version"
- "please update"
- "upgrade to latest"

The system **will NOT** trigger on:
- "update my calendar"
- "update the spreadsheet"
- "update my profile"
- etc. (must be about Kiyomi herself)

## Update Process

When an update is triggered:
1. **Check**: Query GitHub Releases API for the latest release tag
2. **Compare**: Parse semantic version from `engine/VERSION` vs release tag
3. **Download**: Download the release zip asset from GitHub
4. **Backup**: Copy current `~/.kiyomi/app/` to `~/.kiyomi/app.backup/`
5. **Extract**: Replace app files with the new release
6. **Dependencies**: If `requirements.txt` changed, run `pip install -r requirements.txt`
7. **Restart**: Replace the current process with `os.execv`

## Configuration

Auto-update can be enabled in `~/.kiyomi/config.json`:
```json
{
  "auto_update": true
}
```

## Files

- `engine/updater.py` — Core update functionality (GitHub Releases-based)
- `engine/VERSION` — Current version string (source of truth)

## Testing

```bash
cd engine/
python3 updater.py
```

## Requirements

- Internet access to reach `api.github.com`
- No git installation needed
- No repository clone needed

## Error Handling

- Network issues: Returns error message, does not crash
- Download failures: Restores from backup automatically
- Version parse errors: Defaults to (0, 0, 0), triggering update

## Security

- Only downloads from the configured GitHub repo (RichardEchols/kiyomi)
- Uses `os.execv` for secure process replacement
- Backup is created before any files are replaced
