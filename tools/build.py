"""
build.py - Builds the Umvoti LGE 2026 infographic pages from data.

Reads data/umvoti_lge_2026.json, calculates turnout, vote shares and seat
totals, checks that the numbers add up, then writes three poster pages
and a gallery page into site/.

Usage (from the project root):
    python tools/build.py
"""

import json
import math
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "umvoti_lge_2026.json"
SITE = ROOT / "site"

BAR_SCALE = 35  # a 35% vote share fills the whole bar


# ---------- calculations ----------

def load():
    return json.loads(DATA.read_text(encoding="utf-8"))


def summarise(d):
    """Work out the figures the posters show, and check they add up."""
    others = sum(p["ward_votes"] for p in d["other_parties"])
    party_votes = sum(p["ward_votes"] for p in d["parties"])
    if party_votes + others != d["ward_ballot_valid_votes"]:
        raise ValueError("Party votes do not add up to the valid vote total")

    for p in d["parties"]:
        p["seats"] = p["ward_seats"] + p["pr_seats"]
        p["pct"] = p["ward_votes"] / d["ward_ballot_valid_votes"] * 100
        listed = d["councillors"].get(p["short"], [])
        if len(listed) != p["seats"]:
            raise ValueError(f"{p['short']}: {len(listed)} names listed but {p['seats']} seats")

    s = {
        "turnout": d["votes_cast"] / d["registered_voters"] * 100,
        "ward_seats": sum(p["ward_seats"] for p in d["parties"]),
        "pr_seats": sum(p["pr_seats"] for p in d["parties"]),
        "others_votes": others,
        "others_pct": others / d["ward_ballot_valid_votes"] * 100,
    }
    s["total_seats"] = s["ward_seats"] + s["pr_seats"]
    return s


# ---------- small HTML helpers ----------

FONTS = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">\n'
    '  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&amp;family=Space+Grotesk:wght@500;600;700&amp;display=swap" rel="stylesheet">'
)
OTHERS_COLOR = "#B8C0CC"


def n(value):
    return f"{value:,}"


def page(title, body_class, body):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(title)}</title>
  {FONTS}
  <link rel="stylesheet" href="style.css">
</head>
<body>
<main class="poster {body_class}">
{body}
</main>
</body>
</html>
"""


def masthead(kicker_left, kicker_right, title, deck=""):
    deck_html = f'\n  <p class="deck">{deck}</p>' if deck else ""
    return f"""<header class="mast">
  <div class="kicker"><span>{escape(kicker_left)}</span><span>{escape(kicker_right)}</span></div>
  <h1>{escape(title)}</h1>{deck_html}
  <div class="ballot" aria-hidden="true"></div>
</header>"""


def section(no, title, note, inner):
    note_html = f'<span class="note">{note}</span>' if note else ""
    return f"""<section class="sec">
  <div class="sec-head"><span class="no">{no}</span><h2>{escape(title)}</h2>{note_html}</div>
{inner}
</section>"""


def footer(d, extra=""):
    extra_html = f"<br>{extra}" if extra else ""
    return f"""<footer class="foot">
  <div>Source: {escape(d['source'])}, data as at {d['data_as_at']}.{extra_html}</div>
  <div class="credit">Design <b>Ukhezo</b><br>Not an official IEC publication</div>
</footer>"""


def waffle(pct):
    filled = round(pct)
    cells = "".join('<i class="on"></i>' if i < filled else "<i></i>" for i in range(100))
    return f'<div class="waffle" role="img" aria-label="{filled} of 100 squares filled">{cells}</div>'


def vote_bars(d, s, include_others=True, with_seats=False):
    rows = [(p["short"], p["pct"], p["ward_votes"], p["color"], p["seats"]) for p in d["parties"]]
    if include_others:
        rows.append(("Others", s["others_pct"], s["others_votes"], OTHERS_COLOR, 0))
    html = ""
    if with_seats:
        html += '\n  <div class="bar head"><div>Party</div><div>Share of the vote</div><div style="text-align:right">Seats</div></div>'
    for short, pct, votes, color, seats in rows:
        width = min(78, pct / BAR_SCALE * 78)
        seat_html = f'<div class="seat">{seats}</div>' if with_seats else ""
        html += (
            f'\n  <div class="bar"><div class="p">{short}</div><div class="track">'
            f'<div class="fill" style="width:{width:.1f}%;background:{color}"></div>'
            f'<div class="v">{pct:.1f}%<span>{n(votes)} votes</span></div></div>{seat_html}</div>'
        )
    return f'<div class="bars">{html}\n</div>'


def hemicycle(parties, width=560):
    """A parliament-style arc: one dot per seat, coloured by party, left to right."""
    total = sum(p["seats"] for p in parties)
    radii = [1.0, 0.78, 0.56]
    weights = [r / sum(radii) for r in radii]
    counts = [round(total * w) for w in weights]
    counts[0] += total - sum(counts)

    outer, dot = width / 2 - 22, 20
    cx, cy = width / 2, outer + dot + 2
    seats = []
    for r, count in zip(radii, counts):
        for i in range(count):
            angle = math.pi - (i * math.pi / (count - 1) if count > 1 else math.pi / 2)
            seats.append((angle, r))
    seats.sort(key=lambda a: (-round(a[0], 6), a[1]))

    colours = [p["color"] for p in parties for _ in range(p["seats"])]
    circles = ""
    for (angle, r), colour in zip(seats, colours):
        x = cx + outer * r * math.cos(angle)
        y = cy - outer * r * math.sin(angle)
        circles += f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{dot}" fill="{colour}"/>'
    height = cy + dot + 2
    return (
        f'<svg viewBox="0 0 {width} {height:.0f}" role="img" '
        f'aria-label="{total} council seats by party">{circles}</svg>'
    )


# ---------- the three designs ----------

def results_page(d, s):
    did_not_vote = d["registered_voters"] - d["votes_cast"]
    turnout = f"""<div class="turnout">
  <div>{waffle(s['turnout'])}<div class="legend-sq"><i></i> 1 square = 1% of voters</div></div>
  <div><div class="big">{s['turnout']:.1f}<small>%</small></div><p class="big-cap">of registered voters<br>cast a ballot</p></div>
  <div class="figs">
    <div class="fig"><div class="n">{n(d['registered_voters'])}</div><div class="l">Registered voters</div></div>
    <div class="fig"><div class="n">{n(d['votes_cast'])}</div><div class="l">Voted</div></div>
    <div class="fig"><div class="n">{n(did_not_vote)}</div><div class="l">Did not vote</div></div>
  </div>
</div>"""

    rows = "".join(
        f"<tr><td><span class=\"key\" style=\"background:{p['color']}\"></span>{p['short']}</td>"
        f"<td>{p['ward_seats']}</td><td>{p['pr_seats']}</td><td class=\"t\">{p['seats']}</td></tr>"
        for p in d["parties"]
    )
    seats = f"""<div class="seats">
  <div class="arc">{hemicycle(d['parties'], 440)}<div class="centre"><b style="font-size:72px">{s['total_seats']}</b><span>seats</span></div></div>
  <div>
    <table class="tbl">
      <tr><th>Party</th><th>Ward</th><th>PR</th><th>Seats</th></tr>
      {rows}
      <tr class="sum"><td>Total</td><td>{s['ward_seats']}</td><td>{s['pr_seats']}</td><td class="t">{s['total_seats']}</td></tr>
    </table>
    <div class="hung"><b>Hung council</b><span>No party reached the {d['seats_needed_for_majority']} seats needed for a majority.</span></div>
  </div>
</div>"""

    body = "\n".join([
        masthead(d["election"], f"{d['code']} · KwaZulu-Natal", "Umvoti",
                 f"How <b>{escape(d['municipality'])}</b> voted: turnout, share of the vote and the new council."),
        section("01", "Turnout", "", turnout),
        section("02", "Share of the vote", f"Ward ballot · {n(d['ward_ballot_valid_votes'])} valid votes", vote_bars(d, s)),
        section("03", "The new council", f"{s['ward_seats']} ward + {s['pr_seats']} PR councillors", seats),
        footer(d, f"Turnout = votes cast ÷ registered voters (IEC reports {d['iec_reported_turnout_pct']}%). "
                  f"Others = {len(d['other_parties'])} parties under 1% each."),
    ])
    return page(f"{d['municipality']} – {d['election']} results", "", body)


def councillors_page(d, s):
    blocks = ""
    for p in d["parties"]:
        people = ""
        for entry in d["councillors"][p["short"]]:
            name, seat = entry[0], entry[1]
            kind = "w" if seat.startswith("Ward") else "pr"
            label = seat.replace("Ward ", "W") if kind == "w" else seat.replace(" ", "")
            note = f"<em>{escape(entry[2])}</em>" if len(entry) > 2 else ""
            people += f'\n    <div class="person"><span class="tag {kind}">{label}</span><span>{escape(name)}{note}</span></div>'
        blocks += f"""
  <div class="party">
    <div class="party-top"><span class="sw" style="background:{p['color']}"></span><h3>{p['short']}</h3><span class="full">{escape(p['name'])}</span><span class="cnt">{p['seats']}</span></div>
    <div class="party-sub">{p['ward_seats']} ward · {p['pr_seats']} PR</div>{people}
  </div>"""

    explain = f"""<section class="sec">
  <div class="sec-head"><span class="no">?</span><h2>Ward and PR councillors</h2></div>
  <div class="parties" style="margin-top:0">
    <p style="margin:0;font-size:18px;line-height:1.5"><b class="tag w">W</b> <b>Ward councillors ({s['ward_seats']})</b> are elected directly by voters in each of Umvoti's {s['ward_seats']} wards.</p>
    <p style="margin:0;font-size:18px;line-height:1.5"><b class="tag pr">PR</b> <b>PR councillors ({s['pr_seats']})</b> come from party lists, so each party's total seats reflect its share of the vote.</p>
  </div>
</section>"""

    body = "\n".join([
        masthead(d["election"] + " · Part 2", f"{d['code']} · KwaZulu-Natal", "Council",
                 f"The <b>{s['total_seats']} councillors</b> elected to {escape(d['municipality'])}, by party."),
        f'<div class="parties">{blocks}\n</div>',
        explain,
        footer(d, escape(d["councillors_note"])),
    ])
    return page("Umvoti councillors by party", "", body)


def square_page(d, s):
    body = f"""{masthead('LGE 2026 results', d['code'], 'Umvoti')}
<div class="sq-body">
  <div>
    <div class="big">{s['turnout']:.1f}<small>%</small></div>
    <p class="big-cap" style="font-size:20px">turnout · {n(d['votes_cast'])} of {n(d['registered_voters'])} registered voters</p>
  </div>
  <div class="arc">{hemicycle(d['parties'], 500)}<div class="centre"><b style="font-size:72px">{s['total_seats']}</b><span>seats · hung council</span></div></div>
</div>
<section class="sec sq-rows" style="margin-top:28px">
  <div class="sec-head" style="margin-bottom:12px"><h2 style="font-size:28px">Share of the vote and seats won</h2><span class="note">Ward ballot vote share</span></div>
{vote_bars(d, s, include_others=False, with_seats=True)}
</section>
<footer class="foot"><div>Source: IEC results via ESP.info, {d['data_as_at']}. Not an official IEC publication.</div><div class="credit">Design <b>Ukhezo</b></div></footer>"""
    return page("Umvoti 2026 results – square post", "square", body)


def gallery_page(d):
    items = [
        ("results.html", "designs/01-results.png", "Poster 1 – Results (A3)"),
        ("councillors.html", "designs/02-councillors.png", "Poster 2 – Council (A3)"),
        ("square.html", "designs/03-square.png", "Instagram square"),
    ]
    thumbs = "\n".join(
        f'    <a href="{href}"><img src="../{img}" alt="{label}"><span>{label}</span></a>'
        for href, img, label in items
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(d['municipality'])} – {escape(d['election'])}</title>
  {FONTS}
  <link rel="stylesheet" href="style.css">
</head>
<body>
<div class="gallery">
  <h1>Umvoti Votes 2026</h1>
  <p>An editorial infographic series on the {escape(d['election'])} in {escape(d['municipality'])}. Click a design to open it full size.</p>
  <div class="thumbs">
{thumbs}
  </div>
</div>
</body>
</html>
"""


def main():
    d = load()
    s = summarise(d)
    outputs = {
        "results.html": results_page(d, s),
        "councillors.html": councillors_page(d, s),
        "square.html": square_page(d, s),
        "index.html": gallery_page(d),
    }
    for name, html in outputs.items():
        (SITE / name).write_text(html, encoding="utf-8")
        print(f"Built site/{name}")
    print(f"Turnout {s['turnout']:.1f}% · {s['total_seats']} seats ({s['ward_seats']} ward, {s['pr_seats']} PR)")


if __name__ == "__main__":
    main()
