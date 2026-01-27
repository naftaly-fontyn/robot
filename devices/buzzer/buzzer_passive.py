"""
Buzzer module
"""
# pylint: disable=E0401,W0612,C0116,C0115
import ure
from machine import Pin, PWM
from utime import sleep_ms

_NOTES = {
    'c': 261.63, 'c#': 277.18, 'd': 293.66, 'd#': 311.13,
    'e': 329.63, 'f': 349.23, 'f#': 369.99, 'g': 392.00,
    'g#': 415.30, 'a': 440.00, 'a#': 466.16, 'b': 493.88,
    'p': 0  # pause
}

def note_to_freq(note):
    m = ure.search('([a-gp#]+)(\\.?)([0-9]*)',note.lower())
    n, o = m.group(1), int(m.group(3)) if m.group(3) else 4
    return 0 if n == 'p' else _NOTES[n] * (2 ** (o - 4))


def parse_rttl(rttl_str):
    """Parse RTTTL string into note sequence"""
    name, defaults, notes_str = rttl_str.split(':')
    params = {p.split('=')[0]: p.split('=')[1] for p in defaults.split(',')}
    # Defaults
    default_dur = int(params.get('d', 4))
    default_oct = int(params.get('o', 6))
    bpm = int(params.get('b', 63))

    whole_note = (60_000 / bpm) * 4  # duration of whole note in ms
    notes_str = ure.sub('\\|',',',notes_str) # make "|" separator convert to comma
    notes_str = ure.sub('[^a-gA-GpP#,\\.]','',notes_str)
    notes = notes_str.split(',')

    result = []
    for n in notes:
        n = n.strip().lower()
        if not n:
            continue
        # parse note <dur?><note><dot?><oct?>
        m = ure.search('([0-9]*)([a-gA-GpP#]*)(\\.?)([0-9]*)',n)
        note_def = dict(zip(['dur','note','dot','oct'],[m.group(i) for i in range(1,5)]))
        dur = int(note_def['dur']) if note_def['dur'] else default_dur
        note = note_def['note'] if note_def['note'] else 'p'
        dotted = True if note_def['dot'] else False
        octv = int(note_def['oct']) if note_def['oct'] else default_oct
        freq = 0 if note == 'p' else _NOTES[note] * (2 ** (octv - 4))
        # Duration in ms
        note_duration = int(whole_note * 1.5 // dur) if dotted else int(whole_note // dur)
        result.append((freq, note_duration))

    return result


class BuzzerPassive:
    def __init__(self, pin):
        self.pin = pin
        self.pwm = PWM(Pin(pin))

    def play_tone(self, note, duration_ms):
        self.play_freq(note_to_freq(note), duration_ms)

    def play_freq(self, freq, duration_ms):
        if not self.pwm:
            self.pwm = PWM(self.pin)
        if freq == 0:
            self.pwm.duty(0)
        else:
            self.pwm.freq(round(freq))
            self.pwm.duty(512)
        if duration_ms > 0:
            sleep_ms(duration_ms)
            self.pwm.duty(0)

        sleep_ms(duration_ms)
        self.pwm.duty(0)
        sleep_ms(20)  # Small gap between notes

    def play_rttl(self, rttl_str):
        self.silent()
        for freq, dur in parse_rttl(rttl_str):
    #         print(f'F={freq}, D={dur}')
            self.play_freq(freq, dur)

    def silent(self):
        if self.pwm:
            self.pwm.duty(0)

    def off(self):
        if self.pwm:
            self.pwm.deinit()
            self.pwm = None
