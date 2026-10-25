# Lunifier 2.x configuration

## Configuration (`config.json`)

Settings can be modified via the UI or by editing `config.json`:
- **Windows location**: `%APPDATA%\Lunifier\config.json`
- **Linux location**: `~/.config/lunifier/config.json`

Schema specification: [configuration schema](https://github.com/silviuk/Lunifier/blob/2.0/src/common/config.schema.json).

```json
{
  "host_name": "Host",
  "my_channel": 1,
  "target_channel": 2,
  "hold_delay_ms": 250,
  "cooldown_ms": 2500,
  "border_active_zone_pct": 50,
  "knock_enabled": false,
  "knock_timeout_ms": 1000,
  "monitor_configs": {
    "0": {
      "enabled": true,
      "edges": {
        "left": null,
        "right": 2,
        "top": null,
        "bottom": null
      }
    }
  },
  "switch_backend": "auto",
  "connection_support": "both",
  "log_level": "normal",
  "bt_p2p_enabled": false,
  "sync_cursor_position": true,
  "sync_clipboard": false
}
```

---
