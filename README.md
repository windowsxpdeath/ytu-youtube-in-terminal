# ytu 2.0

A compact, terminal picker for YouTube. `ytu` searches with
`yt-dlp`, shows a numbered TUI list, and streams the selected result through
`mpv`. It does not download the whole video first.

## Requirements

- Python 3.9+
- `yt-dlp`
- `mpv`

### Install

```bash
python -m pip install .
ytu --check
```

For an isolated installation, use `pipx install .` instead.

NixOS example:

```bash
nix-shell -p python3Packages.pipx yt-dlp mpv ffmpeg
pipx install .
ytu --check
```

## Commands

```bash
ytu "search words"                 # best available quality
ytu -q 480 "search words"          # up to 480p
ytu -q 1080 "search words"         # up to 1080p
ytu -low "search words"            # lowest playable video/audio streams
ytu -high "search words"           # maximum available quality
ytu -q audio "song or podcast"     # audio only
ytu -n 20 "search words"           # show 20 results
ytu --check                         # verify runtime tools
ytu --no-color "search words"      # retain frames, disable ANSI colour
ytu --help
```

Both requested short forms and conventional long forms work:
`-low`/`--low`, `-high`/`--high`, and `-q`/`--quality`.

Available explicit quality values are `144`, `240`, `360`, `480`, `720`,
`1080`, `1440`, `2160`, and `audio`. A numeric value is a maximum: if that
exact resolution is unavailable, `yt-dlp` chooses the best compatible stream
under the limit. `-low` prefers the smallest video and audio streams and is
intended for weak connections. For music with no picture, `-q audio` uses less
traffic than carrying even a low-resolution video stream.

Colours are enabled automatically only in an interactive terminal. The
standard `NO_COLOR` environment variable is respected; `--color` forces colour
and `--no-color` disables it.
