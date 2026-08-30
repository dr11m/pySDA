# Bundled browser extensions

`steam-browser` loads **Simple Proxy Switcher** from this folder for every account.

Target path:

```text
browser_launcher/bundled_extensions/simple-proxy-switcher/manifest.json
```

## One-time setup

1. Download the extension `.crx` file for  
   [Simple Proxy Switcher](https://chromewebstore.google.com/detail/simple-proxy-switcher/pcboajngloecgmaailkmphmpbacmbcfb)

2. Unpack it into the project:

```bash
uv run python scripts/unpack_browser_extension.py path/to/simple-proxy-switcher.crx
```

3. Start the browser launcher:

```bash
uv run python cli_browser.py
```

All account profiles will use the same unpacked extension.

## Manual unpack

If you already have an unpacked extension folder, copy its contents into:

```text
browser_launcher/bundled_extensions/simple-proxy-switcher/
```

The folder must contain `manifest.json` at the root.
