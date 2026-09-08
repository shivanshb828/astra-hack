#!/bin/zsh
set -e
DEMO_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
# Both entry points open the same canonical scene through the running app.
open -a Blender "$DEMO_DIR/component_pass/missionpcb_three_cad_components.blend"
