"""Read electrical data from a saved board using KiCad's bundled Python.

This probe never saves or changes the board. Geometry is not evidence of a circuit.
"""
import json
import sys

import pcbnew


def snapshot(path):
    board = pcbnew.LoadBoard(path)
    footprints, pads = [], []
    for footprint in board.GetFootprints():
        ref = footprint.GetReference()
        footprints.append({'ref': ref, 'value': footprint.GetValue(), 'board_only': footprint.IsBoardOnly()})
        for pad in footprint.Pads():
            pads.append({'ref': ref, 'pin': pad.GetNumber(), 'net': pad.GetNetname(),
                         'electrical': pad.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH and bool(pad.GetNumber())})
    tracks = list(board.GetTracks())
    zones = list(board.Zones())
    board.BuildConnectivity()
    return {'footprints': sorted(footprints, key=lambda item: item['ref']),
            'pads': sorted(pads, key=lambda item: (item['ref'], item['pin'])),
            'tracks': sum(item.Type() != pcbnew.PCB_VIA_T for item in tracks),
            'vias': sum(item.Type() == pcbnew.PCB_VIA_T for item in tracks),
            'zones': len(zones), 'filled_zones': sum(zone.IsFilled() for zone in zones),
            'nets': sorted(net.GetNetname() for net in board.GetNetInfo().NetsByNetcode().values() if net.GetNetCode()),
            'unconnected': board.GetConnectivity().GetUnconnectedCount(False)}


if __name__ == '__main__':
    print(json.dumps(snapshot(sys.argv[1])))
