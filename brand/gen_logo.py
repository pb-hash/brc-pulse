# Geometry for the polished flat BRC Pulse mark.
# viewBox 307.6 90 1316 1316 (same as BRC Vault). Pulse ribbon is 124 wide; its upper/left half is a
# lighter tone (a flat fold, from the user's reference). The line end is cut concave by a gap around the
# dot, and in the "breakthrough" variant the spike pierces the frame through a matching gap.
import json, math

VB = "307.6 90 1316 1316"
FRAME = ("M965.6 143.9H1371A198.7 198.7 0 0 1 1569.7 342.6V1153.4A198.7 198.7 0 0 1 1371 1352.1"
         "H560.2A198.7 198.7 0 0 1 361.5 1153.4V342.6A198.7 198.7 0 0 1 560.2 143.9Z")
FW, W, GAP, DOT = 107.8, 124, 34, (1272.4, 800, 114)

PTS = {
    'contained':    [(544.8, 800), (720, 800), (830, 470), (985, 1025), (1095, 800), (1215, 800)],
    'breakthrough': [(544.8, 800), (720, 800), (830, 470), (980, 1135), (1100, 800), (1215, 800)],
}

def offset(P, d):
    """Polyline offset by d to the left of travel (screen coords), mitred."""
    n = []
    for (x0, y0), (x1, y1) in zip(P, P[1:]):
        L = math.hypot(x1 - x0, y1 - y0); n.append(((y1 - y0) / L, -(x1 - x0) / L))
    out = [(P[0][0] + d * n[0][0], P[0][1] + d * n[0][1])]
    for k in range(1, len(P) - 1):
        a, b = n[k - 1], n[k]; s = 1 + a[0] * b[0] + a[1] * b[1]
        out.append((P[k][0] + d * (a[0] + b[0]) / s, P[k][1] + d * (a[1] + b[1]) / s))
    out.append((P[-1][0] + d * n[-1][0], P[-1][1] + d * n[-1][1]))
    return out

def d_of(P):
    return 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in P)

def geo(v):
    P = PTS[v]
    g = dict(lo=d_of(P), hi=d_of(offset(P, W / 4)), cut=d_of(P[2:5]) if v == 'breakthrough' else None)
    return g

def mark(v='breakthrough', uid='m', frame='#5956FD', hi='#3a3a3a', lo='#111114', dot='#5956FD',
         track=None, pct=None, bg=None, extra=''):
    """Full standalone SVG. track/pct: frame drawn as timer (track colour + frame colour progress)."""
    g = geo(v); cx, cy, r = DOT
    defs = (f'<mask id="{uid}d" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="2000">'
            f'<rect width="2000" height="2000" fill="#fff"/><circle cx="{cx}" cy="{cy}" r="{r + GAP}" fill="#000"/></mask>')
    if g['cut']:
        defs += (f'<mask id="{uid}f" maskUnits="userSpaceOnUse" x="0" y="0" width="2000" height="2000">'
                 f'<rect width="2000" height="2000" fill="#fff"/><path d="{g["cut"]}" fill="none" stroke="#000" '
                 f'stroke-width="{W + 2 * GAP}" stroke-miterlimit="6"/></mask>')
    fm = f' mask="url(#{uid}f)"' if g['cut'] else ''
    if frame is None:
        fr = ''
    elif track is None:
        fr = f'<path d="{FRAME}" fill="none" stroke="{frame}" stroke-width="{FW}"/>'
    else:
        fr = (f'<path d="{FRAME}" fill="none" stroke="{track}" stroke-width="{FW}"/>'
              f'<path d="{FRAME}" pathLength="100" stroke-dasharray="100" stroke-dashoffset="{100 - pct}" fill="none" stroke="{frame}" stroke-width="{FW}"/>')
    b = f'<rect x="307.6" y="90" width="1316" height="1316" rx="252.6" fill="{bg}"/>' if bg else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{VB}"><defs>{defs}</defs>{b}<g{fm}>{fr}</g>'
            f'<g mask="url(#{uid}d)" fill="none" stroke-miterlimit="6">'
            f'<path d="{g["lo"]}" stroke="{lo}" stroke-width="{W}"/><path d="{g["hi"]}" stroke="{hi}" stroke-width="{W / 2}"/></g>'
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{dot}"/>{extra}</svg>')

if __name__ == '__main__':
    json.dump({'FRAME': FRAME, 'contained': geo('contained'), 'breakthrough': geo('breakthrough')},
              open('geo.json', 'w'), indent=1)
    print(json.dumps(geo('breakthrough'), indent=1))
