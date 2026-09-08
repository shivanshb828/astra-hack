# Blender integration for the shared floating widget

Run `addon.py` inside the canonical open MissionPCB Blender scene using its Python console:

```python
import runpy; widget_adapter = runpy.run_path('/Users/dhruvavutukury/Documents/ChatGPT/astra/missionpcb_blender_demo/blender_widget/addon.py', run_name='__main__')
```

The adapter is session-scoped; reopening Blender requires running it again. It does not save or replace the scene. The floating widget's Blender selector prefixes commands with `blender:` and uses the existing authenticated localhost bridge on port 8768.

Supported: Inspect, Full check, Focus sensor/regulator/radio/MCU/charger/battery connector. Full check runs the embedded constraint engine and creates red attention rings for failed subjects in Blender. Focus selects and frames the component in the real viewport. Target file is checked before every command; unrelated scenes are rejected. Unknown commands cannot run Python.

Verified: native Swift build, Python syntax, background check on six components, unknown-action rejection, live full check (26 PASS, 0 FAIL, 2 SKIP), and HTTP bridge focus sensor.

Scope: geometry/policy checks only. No electrical DRC/ERC, physical thermal solve, patient safety certification, live Astra, or arbitrary CAD auto-assembly. No drag/drop import added in this pass. Existing KiCad commands remain separate.

## Isolated adapter tests

Run `python3 -m unittest discover -s missionpcb_blender_demo/blender_widget -p 'test_*.py' -v` from the repository root. The 16 tests use a temporary IPC directory and a stub Blender module; they do not send commands to the running scene. They cover disconnected adapters, scene targeting, engine presence, unsupported commands, pending-command preservation, stale-result suppression, acknowledgement snapshot ordering, malformed messages, invalid IDs, and expired/invalid timestamps.

These tests check command handling, not actual Blender rendering or component geometry. Live viewport and engine verification remain separate. Commands are allowlisted; the widget does not execute arbitrary Python provided as chat text.
