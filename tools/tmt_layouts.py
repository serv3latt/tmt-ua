"""Circle layouts for the Trail Making Test: generator and rule checker (T1.1).

The layout is fixed and the same for every participant and at retest
(decision 64). This tool proposes candidates; the author picks one per part.
Rules come from docs/11-technical-plan.md, section 3, in the research repo:
the correct path never crosses itself, circles keep a minimum distance, the
centre stays free for the start cross, and the path of part B is longer than
that of part A (Bowie & Harvey, 2006; Gaudino et al., 1995).

Units. Coordinates are in field units: the field is 160 x 100 units with the
origin in its centre, x to the right, y down. One unit is 1/100 of the field
height, so a layout does not depend on the field size in mm chosen later
(with a 240 x 150 mm field one unit is 1.5 mm). Practice layouts use the
central 96 x 60 units, which gives 8 circles the same density as 25 circles
have on the whole field.

check_layout() is independent of the generator: it only looks at a finished
layout, and app/tests/test_tmt_layouts.py runs it on the stored file.

Usage, from app/:
    python tools/tmt_layouts.py generate   # writes stimuli/tmt-layout-candidates.json
    python tools/tmt_layouts.py check      # checks the stored file, prints the metrics
"""

import json
import math
import random
import sys
from pathlib import Path

CANDIDATES_FILE = Path(__file__).resolve().parent.parent / "stimuli" / "tmt-layout-candidates.json"
VERSION = "candidates-1"
VARIANTS = 4

UKR_LETTERS = "АБВГҐДЕЄЖЗИІ"  # decision 121: the first 12 letters, none removed

FIELD = {"w": 160.0, "h": 100.0}
PRACTICE_FIELD = {"w": 96.0, "h": 60.0}

# All distances in field units. The largest circle the rules allow for is
# 8 units across (12 mm on a 150 mm high field).
RULES = {
    "circle_max": 8.0,
    # Circle centres stay this far from the field edge: the circle is inside
    # with room to spare.
    "edge_margin": 7.0,
    # Centre-to-centre distance: the gap between two circles is at least one
    # diameter of the largest circle (as in Recker & Poth, 2023).
    "min_distance": 16.0,
    # No circle centre this close to the start cross in the field centre.
    "centre_free_radius": 14.0,
    # A line of the correct path passes at least this far from the centre of
    # any circle it does not connect, so it never touches another circle.
    "line_clearance": 7.0,
    # The path does not fold back on itself: the angle between two
    # consecutive lines is at least this many degrees.
    "min_turn_angle": 25.0,
    # The first circle is neither under the cursor nor at the far edge.
    "first_distance": [18.0, 48.0],
    # Every quarter of the field holds at least this share of the circles.
    "min_quadrant_share": 0.16,
    # Mean length of one line of the correct path, by layout kind, and the
    # tolerance around it. Part B is 1.35 times part A: on a 240 x 150 mm
    # field its path is then about 43 cm longer, which is the 56.9 cm of the
    # paper test (Gaudino et al., 1995) scaled down to this field.
    "mean_step": {"a": 34.0, "b": 46.0, "practice_a": 24.0, "practice_b": 32.4},
    "mean_step_tolerance": 0.03,
    # No single line longer than this, so that the length is spread over the
    # path and not made by one jump across the field.
    "max_step": {"a": 60.0, "b": 85.0, "practice_a": 40.0, "practice_b": 52.0},
    # Room for the words "Початок" / "Кінець" above or below the first and
    # the last circle: a box this size, this far from the circle centre,
    # free of other circles, of path lines and of the other word.
    "label_box": {"w": 18.0, "h": 6.0, "offset": 5.5},
}

KINDS = {
    "a": {"n": 25, "field": FIELD},
    "b": {"n": 25, "field": FIELD},
    "practice_a": {"n": 8, "field": PRACTICE_FIELD},
    "practice_b": {"n": 8, "field": PRACTICE_FIELD},
}


def labels_for(kind):
    """Circle labels in the order of the correct path."""
    n = KINDS[kind]["n"]
    if kind.endswith("a"):
        return [str(i) for i in range(1, n + 1)]
    out = []
    for i in range(n):
        out.append(str(i // 2 + 1) if i % 2 == 0 else UKR_LETTERS[i // 2])
    return out


# --- geometry ---------------------------------------------------------------


def dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def point_segment_distance(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return dist(p, a)
    t = ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2
    t = max(0.0, min(1.0, t))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _orient(a, b, c):
    value = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    return 0 if abs(value) < 1e-9 else (1 if value > 0 else -1)


def _on_segment(a, b, c):
    """c is collinear with a-b; is it within the segment?"""
    return min(a[0], b[0]) - 1e-9 <= c[0] <= max(a[0], b[0]) + 1e-9 and \
        min(a[1], b[1]) - 1e-9 <= c[1] <= max(a[1], b[1]) + 1e-9


def segments_intersect(a, b, c, d):
    """Whether segments a-b and c-d share any point."""
    o1, o2, o3, o4 = _orient(a, b, c), _orient(a, b, d), _orient(c, d, a), _orient(c, d, b)
    if o1 != o2 and o3 != o4:
        return True
    return (o1 == 0 and _on_segment(a, b, c)) or (o2 == 0 and _on_segment(a, b, d)) or \
        (o3 == 0 and _on_segment(c, d, a)) or (o4 == 0 and _on_segment(c, d, b))


def turn_angle(a, b, c):
    """Angle at b between the lines b-a and b-c, in degrees (180 = straight on)."""
    v1 = (a[0] - b[0], a[1] - b[1])
    v2 = (c[0] - b[0], c[1] - b[1])
    cos = (v1[0] * v2[0] + v1[1] * v2[1]) / (math.hypot(*v1) * math.hypot(*v2))
    return math.degrees(math.acos(max(-1.0, min(1.0, cos))))


def path_length(points):
    return sum(dist(points[i], points[i + 1]) for i in range(len(points) - 1))


def crossings(points):
    """Pairs of path lines that cross or touch (neighbours share their end only)."""
    found = []
    n = len(points) - 1
    for i in range(n):
        for j in range(i + 2, n):
            if segments_intersect(points[i], points[i + 1], points[j], points[j + 1]):
                found.append((i, j))
    return found


def _segment_hits_box(a, b, box):
    x0, y0, x1, y1 = box
    inside = lambda p: x0 <= p[0] <= x1 and y0 <= p[1] <= y1
    if inside(a) or inside(b):
        return True
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return any(segments_intersect(a, b, corners[k], corners[(k + 1) % 4]) for k in range(4))


def _point_box_distance(p, box):
    x0, y0, x1, y1 = box
    return math.hypot(max(x0 - p[0], 0, p[0] - x1), max(y0 - p[1], 0, p[1] - y1))


def label_box(point, side, rules=RULES):
    """Box for the word next to a circle: side is 'above' or 'below'."""
    spec = rules["label_box"]
    x0 = point[0] - spec["w"] / 2
    if side == "above":
        y0 = point[1] - spec["offset"] - spec["h"]
    else:
        y0 = point[1] + spec["offset"]
    return (x0, y0, x0 + spec["w"], y0 + spec["h"])


def label_fits(points, index, side, field, rules=RULES):
    """Whether the word box on this side of circle `index` is inside the
    field and free of other circles and of path lines."""
    box = label_box(points[index], side, rules)
    if box[0] < -field["w"] / 2 or box[2] > field["w"] / 2:
        return False
    if box[1] < -field["h"] / 2 or box[3] > field["h"] / 2:
        return False
    if any(_point_box_distance(p, box) < rules["circle_max"] / 2 + 1
           for k, p in enumerate(points) if k != index):
        return False
    return not any(_segment_hits_box(points[k], points[k + 1], box) for k in range(len(points) - 1))


def _boxes_apart(a, b, gap=1.0):
    return a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1]


def labels_fit(points, sides, field, rules=RULES):
    """Whether both words fit: sides is { start, end }, each 'above' or 'below'.
    The two words must also keep clear of each other."""
    last = len(points) - 1
    if sides.get("start") not in ("above", "below") or sides.get("end") not in ("above", "below"):
        return False
    if not label_fits(points, 0, sides["start"], field, rules):
        return False
    if not label_fits(points, last, sides["end"], field, rules):
        return False
    return _boxes_apart(label_box(points[0], sides["start"], rules), label_box(points[last], sides["end"], rules))


def label_sides(points, field, rules=RULES):
    """Sides for the words at the first and the last circle, or None."""
    for start in ("above", "below"):
        for end in ("below", "above"):
            sides = {"start": start, "end": end}
            if labels_fit(points, sides, field, rules):
                return sides
    return None


# --- rules ------------------------------------------------------------------


def metrics(points, field):
    n = len(points)
    pair = min(dist(points[i], points[j]) for i in range(n) for j in range(i + 1, n))
    clearance = min(
        point_segment_distance(points[k], points[i], points[i + 1])
        for i in range(n - 1) for k in range(n) if k not in (i, i + 1)
    )
    angle = min(turn_angle(points[i - 1], points[i], points[i + 1]) for i in range(1, n - 1))
    steps = [dist(points[i], points[i + 1]) for i in range(n - 1)]
    quadrants = [0, 0, 0, 0]
    for x, y in points:
        quadrants[(1 if x > 0 else 0) + (2 if y > 0 else 0)] += 1
    return {
        "path_length": round(sum(steps), 1),
        "mean_step": round(sum(steps) / len(steps), 2),
        "min_step": round(min(steps), 1),
        "max_step": round(max(steps), 1),
        "min_distance": round(pair, 1),
        "min_line_clearance": round(clearance, 1),
        "min_turn_angle": round(angle, 1),
        "centre_distance_min": round(min(math.hypot(*p) for p in points), 1),
        "first_distance": round(math.hypot(*points[0]), 1),
        "quadrants": quadrants,
        "crossings": len(crossings(points)),
    }


def check_layout(layout, rules=RULES):
    """Returns the list of broken rules; empty when the layout is valid."""
    kind = layout["kind"]
    field = KINDS[kind]["field"]
    points = [tuple(p) for p in layout["points"]]
    n = len(points)
    problems = []
    if n != KINDS[kind]["n"]:
        problems.append(f"count: {n} circles, expected {KINDS[kind]['n']}")
        return problems
    if layout["labels"] != labels_for(kind):
        problems.append("labels: not the expected sequence")

    limit_x = field["w"] / 2 - rules["edge_margin"]
    limit_y = field["h"] / 2 - rules["edge_margin"]
    for i, (x, y) in enumerate(points):
        if abs(x) > limit_x + 1e-9 or abs(y) > limit_y + 1e-9:
            problems.append(f"edge: circle {i + 1} is too close to the field edge")
        if math.hypot(x, y) < rules["centre_free_radius"] - 1e-9:
            problems.append(f"centre: circle {i + 1} is in the start-cross zone")
    for i in range(n):
        for j in range(i + 1, n):
            if dist(points[i], points[j]) < rules["min_distance"] - 1e-9:
                problems.append(f"distance: circles {i + 1} and {j + 1} are too close")
    for i, j in crossings(points):
        problems.append(f"crossing: lines {i + 1}-{i + 2} and {j + 1}-{j + 2} cross")
    for i in range(n - 1):
        for k in range(n):
            if k in (i, i + 1):
                continue
            if point_segment_distance(points[k], points[i], points[i + 1]) < rules["line_clearance"] - 1e-9:
                problems.append(f"clearance: line {i + 1}-{i + 2} passes too close to circle {k + 1}")
    for i in range(1, n - 1):
        if turn_angle(points[i - 1], points[i], points[i + 1]) < rules["min_turn_angle"] - 1e-9:
            problems.append(f"angle: the path folds back at circle {i + 1}")
    low, high = rules["first_distance"]
    if not low - 1e-9 <= math.hypot(*points[0]) <= high + 1e-9:
        problems.append("first: the first circle is too close to or too far from the centre")
    quadrants = [0, 0, 0, 0]
    for x, y in points:
        quadrants[(1 if x > 0 else 0) + (2 if y > 0 else 0)] += 1
    if min(quadrants) < math.floor(rules["min_quadrant_share"] * n):
        problems.append(f"spread: quarters hold {quadrants} circles")
    target = rules["mean_step"][kind]
    mean = path_length(points) / (n - 1)
    if abs(mean - target) > rules["mean_step_tolerance"] * target + 1e-9:
        problems.append(f"length: mean line {mean:.1f}, expected {target} ± {rules['mean_step_tolerance']:.0%}")
    longest = max(dist(points[i], points[i + 1]) for i in range(n - 1))
    if longest > rules["max_step"][kind] + 1e-9:
        problems.append(f"step: the longest line is {longest:.1f}, allowed {rules['max_step'][kind]}")
    if not labels_fit(points, layout.get("label_sides") or {}, field, rules):
        problems.append("label: no room for the words at the first and the last circle")
    return problems


def check_file(data, rules=None):
    """Checks a whole candidates file: every layout, and B against A."""
    rules = rules or data["rules"]
    problems = []
    for kind, layouts in data["layouts"].items():
        for layout in layouts:
            problems += [f"{layout['id']}: {p}" for p in check_layout(layout, rules)]
    for pair in (("a", "b"), ("practice_a", "practice_b")):
        shortest_b = min(path_length(l["points"]) for l in data["layouts"][pair[1]])
        longest_a = max(path_length(l["points"]) for l in data["layouts"][pair[0]])
        if shortest_b < 1.25 * longest_a:
            problems.append(f"{pair[1]}: the path is not clearly longer than in {pair[0]}")
    return problems


# --- generator --------------------------------------------------------------


# The generator keeps this much spare room on every rule, so that rounding
# the coordinates to 0.1 cannot break one.
SLACK = 0.2


def _allowed(p, others, field, rules):
    margin = rules["edge_margin"] + SLACK
    if abs(p[0]) > field["w"] / 2 - margin or abs(p[1]) > field["h"] / 2 - margin:
        return False
    if math.hypot(*p) < rules["centre_free_radius"] + SLACK:
        return False
    return all(dist(p, q) >= rules["min_distance"] + SLACK for q in others)


def _quadrants_ok(points, rules):
    counts = [0, 0, 0, 0]
    for x, y in points:
        counts[(1 if x > 0 else 0) + (2 if y > 0 else 0)] += 1
    return min(counts) >= math.floor(rules["min_quadrant_share"] * len(points))


def _scatter(rng, n, field, rules):
    """Random points that keep the distance, edge and centre rules."""
    for _ in range(200):
        points = []
        for _ in range(4000):
            p = (rng.uniform(-field["w"] / 2, field["w"] / 2), rng.uniform(-field["h"] / 2, field["h"] / 2))
            if _allowed(p, points, field, rules):
                points.append(p)
                if len(points) == n:
                    break
        if len(points) == n and _quadrants_ok(points, rules):
            return points
    raise RuntimeError("could not scatter the circles")


def _cost(points, target, longest, field, rules):
    """0 for a path that keeps every path rule and has the target length."""
    n = len(points)
    cost = 60.0 * len(crossings(points))
    if label_sides(points, field, rules) is None:
        cost += 8.0
    for i in range(n - 1):
        cost += 2.0 * max(0.0, dist(points[i], points[i + 1]) - longest + 0.5)
    clear = rules["line_clearance"] + 0.4
    for i in range(n - 1):
        a, b = points[i], points[i + 1]
        for k in range(n):
            if k != i and k != i + 1:
                d = point_segment_distance(points[k], a, b)
                if d < clear:
                    cost += 6.0 * (clear - d)
    for i in range(1, n - 1):
        angle = turn_angle(points[i - 1], points[i], points[i + 1])
        if angle < rules["min_turn_angle"] + 2:
            cost += 0.6 * (rules["min_turn_angle"] + 2 - angle)
    low, high = rules["first_distance"]
    first = math.hypot(*points[0])
    cost += 2.0 * max(0.0, low + 0.5 - first, first - high + 0.5)
    mean = path_length(points) / (n - 1)
    off = abs(mean - target) / target
    cost += 400.0 * max(0.0, off - 0.4 * rules["mean_step_tolerance"])
    return cost


def _anneal(rng, points, kind, rules, iterations):
    field = KINDS[kind]["field"]
    target = rules["mean_step"][kind]
    current = list(points)
    longest = rules["max_step"][kind]
    cost = _cost(current, target, longest, field, rules)
    n = len(current)
    for step in range(iterations):
        if cost == 0:
            break
        temperature = 8.0 * (0.002 / 8.0) ** (step / iterations)
        candidate = list(current)
        move = rng.random()
        if move < 0.35:  # reverse a stretch of the path
            i, j = sorted(rng.sample(range(n), 2))
            candidate[i:j + 1] = reversed(candidate[i:j + 1])
        elif move < 0.55:  # move one circle elsewhere in the order
            p = candidate.pop(rng.randrange(n))
            candidate.insert(rng.randrange(n), p)
        elif move < 0.65:  # swap two circles in the order
            i, j = rng.sample(range(n), 2)
            candidate[i], candidate[j] = candidate[j], candidate[i]
        else:  # shift one circle on the field
            i = rng.randrange(n)
            p = (candidate[i][0] + rng.gauss(0, 5), candidate[i][1] + rng.gauss(0, 5))
            if not _allowed(p, candidate[:i] + candidate[i + 1:], field, rules):
                continue
            candidate[i] = p
            if not _quadrants_ok(candidate, rules):
                continue
        new_cost = _cost(candidate, target, longest, field, rules)
        if new_cost <= cost or rng.random() < math.exp((cost - new_cost) / temperature):
            current, cost = candidate, new_cost
    return current, cost


def make_layout(kind, variant, rules=RULES, iterations=None):
    """One valid layout; the same kind and variant always give the same one."""
    field = KINDS[kind]["field"]
    n = KINDS[kind]["n"]
    iterations = iterations or (9000 if n > 10 else 3000)
    for attempt in range(1, 400):
        rng = random.Random(f"tmt-ua/{VERSION}/{kind}/{variant}/{attempt}")
        points, cost = _anneal(rng, _scatter(rng, n, field, rules), kind, rules, iterations)
        if cost > 0:
            continue
        points = [(round(x, 1), round(y, 1)) for x, y in points]
        sides = label_sides(points, field, rules)
        layout = {
            "id": f"{kind}-{variant}",
            "kind": kind,
            "variant": variant,
            "attempt": attempt,
            "labels": labels_for(kind),
            "points": [list(p) for p in points],
            "label_sides": sides,
        }
        if check_layout(layout, rules):
            continue  # rounding or the label room broke a rule: try again
        layout["metrics"] = metrics(points, field)
        return layout
    raise RuntimeError(f"no valid layout for {kind} {variant}")


def generate(variants=VARIANTS, log=print):
    data = {
        "version": VERSION,
        "units": "field units: field height = 100, origin in the field centre, x right, y down",
        "fields": {kind: spec["field"] for kind, spec in KINDS.items()},
        "rules": RULES,
        "layouts": {},
    }
    for kind in KINDS:
        data["layouts"][kind] = []
        for variant in range(1, variants + 1):
            layout = make_layout(kind, variant)
            data["layouts"][kind].append(layout)
            log(f"{layout['id']}: attempt {layout['attempt']}, {layout['metrics']}")
    return data


def main(argv):
    command = argv[1] if len(argv) > 1 else "check"
    if command == "generate":
        data = generate()
        problems = check_file(data)
        if problems:
            sys.exit("\n".join(problems))
        CANDIDATES_FILE.parent.mkdir(exist_ok=True)
        CANDIDATES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
        print(f"written: {CANDIDATES_FILE}")
    elif command == "check":
        data = json.loads(CANDIDATES_FILE.read_text())
        for layouts in data["layouts"].values():
            for layout in layouts:
                print(layout["id"], metrics([tuple(p) for p in layout["points"]], KINDS[layout["kind"]]["field"]))
        problems = check_file(data)
        print("\n".join(problems) if problems else "all rules hold")
        sys.exit(1 if problems else 0)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
