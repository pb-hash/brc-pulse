"""Writes giveaway configs for the "prize paid" state of the giveaway page tests.
Usage: python3 tests/paid_fixture.py <giveaway-drawn.json> <giveaway-fixture.json> <out-dir>
giveaway-paid.json pays the fixture's drawn winner; giveaway-paid-wrong.json records a payout to another address."""
import json, os, sys
drawn, fx, out = json.load(open(sys.argv[1])), json.load(open(sys.argv[2])), sys.argv[3]
os.makedirs(out, exist_ok=True)
win = fx['expected']['winner']
other = next(a for a in fx['entries']['addresses'] if a != win)
for name, to in (('paid', win), ('paid-wrong', other)):
    c = dict(drawn, payout={'to': to, 'amount': '49.99999', 'block': 92700})
    json.dump(c, open(os.path.join(out, f'giveaway-{name}.json'), 'w'), indent=1)
