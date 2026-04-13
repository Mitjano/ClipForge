# ClipForge

Automated psychedelic & fractal video production pipeline for YouTube.

## Pipeline

```
Preset (YAML) → Render Engine → Frames → FFmpeg + Audio → YouTube
                 ├─ Mandelbulber (3D fractals)
                 └─ Blender (tunnels, mandalas, particles)
```

## Quick Start

```bash
# Render a fractal flight
python pipeline/render.py presets/mandelbulber/mandelbulb_flight.yaml

# Compile to video with music
python pipeline/compile.py renders/latest/ --music music/ambient_01.mp3

# Full pipeline: render + music + compile
python pipeline/forge.py presets/mandelbulber/mandelbulb_flight.yaml
```

## Structure

- `pipeline/` — core scripts (render, compile, upload)
- `presets/` — scene configurations (Mandelbulber .fract, Blender .py)
- `renders/` — output frames and videos
- `music/` — generated audio tracks
- `config/` — global settings
