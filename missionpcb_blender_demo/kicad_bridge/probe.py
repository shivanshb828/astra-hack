"""Read-only IPC connection check. Never changes or saves the open board."""
import json
import sys
from kipy import KiCad


def main():
    try:
        client=KiCad(client_name='MissionPCB read-only probe',timeout_ms=2000)
        version=client.get_version()
        board=client.get_board()
        footprints=board.get_footprints()
        print(json.dumps({'connected':True,'kicad_version':str(version),'footprints':len(footprints),'read_only':True},indent=2))
        return 0
    except Exception as error:
        print(json.dumps({'connected':False,'error':str(error),'next_step':'Keep PCB Editor open. Preferences > Plugins > Enable API server > OK.'},indent=2))
        return 1

if __name__=='__main__':sys.exit(main())
