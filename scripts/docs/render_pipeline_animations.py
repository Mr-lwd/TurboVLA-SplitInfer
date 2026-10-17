"""Deterministic scheduling animations, separate from DDS-generated slide art.

Illustrative latency = two time units. One unit equals one idealized control
interval, not a measured duration. H=12, R=4, B=3; all modes bootstrap once.
Pillow draws new animation frames; it never edits photographs or slide images.
"""
from pathlib import Path
import json
import math
from PIL import Image, ImageDraw, ImageFont

OUT = Path(__file__).resolve().parents[2] / 'assets/diagrams/split-inference/animations'
OUT.mkdir(exist_ok=True)
from matplotlib import get_data_path
FONT_DIR = Path(get_data_path()) / 'fonts/ttf'
FONT = FONT_DIR / 'DejaVuSans.ttf'
BOLD = FONT_DIR / 'DejaVuSans-Bold.ttf'
W, H = 1600, 1110
X, CW, END = 260, 68, 18
C = dict(ink='#142333', muted='#536678', blue='#285EA8', pale='#EDF4FB',
         old='#DFEAF5', new='#B8D4EE', mix='#D7DDF6', wait='#ECEFF3',
         line='#CBD8E5', white='#FFFFFF', dark='#164979')

def font(size, bold=False):
    return ImageFont.truetype(str(BOLD if bold else FONT), size)

def text(d, xy, value, size=22, color='ink', bold=False, anchor=None):
    d.text(xy, str(value), font=font(size, bold), fill=C.get(color, color), anchor=anchor)

def simulate(mode):
    """Explicit fixed-latency event model used by all frames and QA assertions."""
    slots = []
    calls = [('A', 0, 2, 0, 0)]
    if mode == 'sync':
        calls += [('B', 14, 16, 12, 12)]
    else:
        calls += [(name, wall, wall + 2, wall - 2, wall)
                  for name, wall in [('B', 6), ('C', 10), ('D', 14)]]
    for wall in range(END):
        if wall < 2 or (mode == 'sync' and 14 <= wall < 16):
            slots.append(dict(label='Wait', kind='wait', step=0 if wall < 2 else 12))
            continue
        step = wall - 2 if mode != 'sync' or wall < 14 else wall - 4
        if mode == 'sync':
            label = f'A{step}' if step < 12 else f'B{step - 12}'
            slots.append(dict(label=label, kind='old' if step < 12 else 'new', step=step))
            continue
        active = [call for call in calls if call[2] <= wall][-1]
        name, start, finish, obs, apply = active
        label = f'{name}{step - obs}'
        kind = 'old' if name == 'A' else 'new'
        slot = dict(label=label, kind=kind, step=step)
        if mode == 'blend' and name != 'A' and step < apply + 3:
            k = step - apply
            previous = chr(ord(name) - 1)
            old_obs = 0 if previous == 'A' else obs - 4
            slot.update(kind='mix', alpha=(k + 1) / 3,
                        weight=['1/3', '2/3', '1'][k],
                        old=f'{previous}{step - old_obs}')
        slots.append(slot)
    return dict(mode=mode, calls=calls, slots=slots)

DATA = {mode: simulate(mode) for mode in ['async', 'blend', 'sync']}
# Semantic checks concern scheduling facts, not pixels or mirrored drawing code.
assert DATA['async']['slots'][8]['label'] == 'B2'
assert [s['weight'] for s in DATA['blend']['slots'][8:11]] == ['1/3', '2/3', '1']
assert [s['step'] for s in DATA['sync']['slots'][14:17]] == [12, 12, 12]
assert DATA['sync']['slots'][16]['label'] == 'B0'
assert DATA['async']['calls'][2][1:3] == (10, 12)

def box(d, bounds, fill, outline=None, width=1):
    d.rectangle(bounds, fill=C.get(fill, fill), outline=C.get(outline, outline), width=width)

def draw_row(d, mode, y, now, compact=False):
    data = DATA[mode]
    name = {'async': 'ASYNC', 'blend': 'BLEND', 'sync': 'SYNC'}[mode]
    subtitle = {'async': 'Async replacement', 'blend': 'Async blending', 'sync': 'Blocking execution'}[mode]
    text(d, (42, y + 8), name, 29, bold=True)
    text(d, (42, y + 49), subtitle, 19, 'muted')
    if mode == 'async': text(d, (42, y + 79), 'CLI: replace', 17, 'muted')
    text(d, (X - 20, y + 27), 'Thor', 20, anchor='ra')
    text(d, (X - 20, y + 97), 'Orin', 20, anchor='ra')
    box(d, (X, y, X + CW * END, y + 47), 'pale')
    for name, start, finish, obs, apply in data['calls']:
        left, right = X + CW * start + 2, X + CW * finish - 2
        box(d, (left, y + 3, right, y + 44), 'blue')
        if start <= now < finish:
            d.rectangle((left, y + 3, right, y + 44), outline=C['ink'], width=3)
        text(d, ((left + right) / 2, y + 24), f'Infer {name}', 20, 'white', anchor='mm')
        # One continuous polyline, with only one destination arrowhead.
        xx = X + CW * finish
        d.line([(xx - 10, y + 46), (xx - 10, y + 60), (xx + 9, y + 60), (xx + 9, y + 70)], fill=C['blue'], width=2)
        d.polygon([(xx + 9, y + 73), (xx + 4, y + 65), (xx + 14, y + 65)], fill=C['blue'])
    for i, slot in enumerate(data['slots']):
        left = X + CW * i + 2
        box(d, (left, y + 75, left + CW - 4, y + 125), slot['kind'])
        if i <= now < i + 1:
            d.rectangle((left, y + 75, left + CW - 4, y + 125), outline=C['blue'], width=3)
        label = f"{slot['old']}/{slot['label']}" if 'old' in slot else slot['label']
        text(d, (left + (CW - 4) / 2, y + 101), label, 14 if 'old' in slot else 19, anchor='mm')
        if 'weight' in slot:
            text(d, (left + (CW - 4) / 2, y + 146), slot['weight'], 16, 'blue', anchor='mm')
    note = {'async': 's=4 → t=6: discard B0/B1; apply B2 onward. Replan every 4 steps.',
            'blend': 'Same trimming; new-action weights 1/3 → 2/3 → 1. Gripper switches discretely.',
            'sync': 'After A0...A11, request B. Control pauses at step 12, then resumes from B0.'}[mode]
    text(d, (X, y + 170), note, 20, 'muted')
    cursor = X + CW * min(now, END)
    d.line((cursor, y - 8, cursor, y + 126), fill=C['ink'], width=3)
    d.polygon([(cursor - 6, y - 11), (cursor + 6, y - 11), (cursor, y - 3)], fill=C['ink'])
    if now < END:
        slot = data['slots'][int(now)]
        if slot['kind'] == 'wait':
            action_text = 'Blocking wait'
        elif slot['kind'] == 'mix':
            action_text = f"Blend {slot['old']}/{slot['label']}"
        else:
            action_text = f"Execute {slot['label']}"
        state = f"Control step {slot['step']} · " + action_text
    else:
        state = 'Continue the loop'
    text(d, (42, y + 148), state.split(' · ')[0], 17, 'muted')
    if ' · ' in state:
        text(d, (42, y + 176), state.split(' · ')[1], 16, 'blue')

def render(now, only=None):
    height = H if not only else 600
    im = Image.new('RGB', (W, height), C['white'])
    d = ImageDraw.Draw(im)
    text(d, (42, 30), 'Three Collaborative Inference Modes' if not only else {'async':'ASYNC · Async replacement','blend':'BLEND · Async blending','sync':'SYNC · Blocking execution'}[only], 40, bold=True)
    text(d, (42, 91), 'Orin Nano 8GB: control execution · Thor 128GB: complete-model inference', 23, 'muted')
    text(d, (42, 133), 'H=12  /  R=4  /  B=3     Inference: 2 illustrative units, not measured latency', 20, 'muted')
    # Identical wall-time axis, unlike control-step alignment.
    for i in range(0, END + 1, 2):
        xx = X + CW * i
        text(d, (xx, 192), i, 17, 'muted', anchor='mm')
    text(d, (42, 183), 'Wall time →', 19, 'muted')
    modes = [only] if only else ['async', 'blend', 'sync']
    for idx, mode in enumerate(modes):
        draw_row(d, mode, 232 + idx * 236, now)
    bottom = 477 if only else 958
    labels = [('old', 'Old actions'), ('new', 'New actions'), ('mix', 'Blend window'), ('wait', 'Blocking wait')]
    for idx, (color, label) in enumerate(labels):
        xx = 42 + idx * 225
        box(d, (xx, bottom, xx + 28, bottom + 22), color)
        text(d, (xx + 40, bottom - 2), label, 20)
    text(d, (42, bottom + 43), 'All modes block for initialization. One request in flight; trim by executed steps, not elapsed time.', 20, 'muted')
    text(d, (42, bottom + 77), 'Empty buffer: zero arm increments, retain gripper (not triggered here). Control is capped at 20 Hz.', 19, 'muted')
    return im

def export(mode=None):
    basename = 'pipeline-comparison' if mode is None else f'pipeline-{mode}'
    frames = [render(i * END / 90, mode) for i in range(91)]
    # Shared adaptive palette keeps flat-color blocks stable between frames.
    palette = frames[0].quantize(colors=128)
    frames = [frame.quantize(palette=palette, dither=Image.Dither.NONE) for frame in frames]
    frames[0].save(OUT / f'{basename}.gif', save_all=True, append_images=frames[1:],
                   duration=[100] * 90 + [2000], loop=0, optimize=True, disposal=1)
    render(8.5, mode).save(OUT / f'{basename}-poster.png')
    print(f'Wrote {basename}.gif: {len(frames)} frames', flush=True)

if __name__ == '__main__':
    for mode in [None, 'async', 'blend', 'sync']:
        export(mode)
    (OUT / 'schedule.json').write_text(json.dumps({
        'description': 'Illustrative fixed-latency scheduling; not measured performance',
        'H':12, 'R':4, 'B':3, 'inference_time_units':2, 'modes':DATA
    }, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
