"""Checks of the TMT layouts (task T1.1): the stored candidates keep every
rule, the checker catches each kind of broken layout, and the generator is
reproducible. No browser needed.

Run from the app/ folder: ../.venv/bin/python -m unittest tests.test_tmt_layouts -v
"""

import copy
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import tmt_layouts as t  # noqa: E402


def load():
    return json.loads(t.CANDIDATES_FILE.read_text())


class StoredLayoutsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_file_was_made_with_the_current_rules(self):
        self.assertEqual(self.data["rules"], t.RULES)
        self.assertEqual(self.data["version"], t.VERSION)

    def test_every_layout_keeps_every_rule(self):
        self.assertEqual(t.check_file(self.data, t.RULES), [])

    def test_there_are_enough_variants_of_each_kind(self):
        for kind in t.KINDS:
            with self.subTest(kind=kind):
                layouts = self.data["layouts"][kind]
                self.assertEqual([l["variant"] for l in layouts], list(range(1, t.VARIANTS + 1)))
                self.assertEqual(len({json.dumps(l["points"]) for l in layouts}), t.VARIANTS)

    def test_labels(self):
        layouts = self.data["layouts"]
        self.assertEqual(layouts["a"][0]["labels"], [str(i) for i in range(1, 26)])
        self.assertEqual(
            layouts["b"][0]["labels"],
            "1 А 2 Б 3 В 4 Г 5 Ґ 6 Д 7 Е 8 Є 9 Ж 10 З 11 И 12 І 13".split(),
        )
        self.assertEqual(layouts["practice_a"][0]["labels"], "1 2 3 4 5 6 7 8".split())
        self.assertEqual(layouts["practice_b"][0]["labels"], "1 А 2 Б 3 В 4 Г".split())

    def test_part_b_path_is_longer_than_part_a(self):
        # Any A may be combined with any B: the ratio stays near 1.35.
        for a_kind, b_kind in (("a", "b"), ("practice_a", "practice_b")):
            for a in self.data["layouts"][a_kind]:
                for b in self.data["layouts"][b_kind]:
                    ratio = t.path_length(b["points"]) / t.path_length(a["points"])
                    self.assertGreater(ratio, 1.25, (a["id"], b["id"]))
                    self.assertLess(ratio, 1.45, (a["id"], b["id"]))

    def test_gap_is_at_least_a_diameter_in_the_offered_sizes(self):
        # Field heights and circle diameters offered in src/tmt/candidates.js;
        # only the largest circle on the smallest field may fall short.
        for field_h, circle in ((140, 10), (140, 11), (150, 10), (150, 11), (150, 12), (160, 10), (160, 11), (160, 12)):
            unit = field_h / 100
            for layouts in self.data["layouts"].values():
                for layout in layouts:
                    gap = layout["metrics"]["min_distance"] * unit - circle
                    self.assertGreaterEqual(gap, circle, (layout["id"], field_h, circle))

    def test_stored_metrics_match_the_points(self):
        for kind, layouts in self.data["layouts"].items():
            for layout in layouts:
                points = [tuple(p) for p in layout["points"]]
                self.assertEqual(layout["metrics"], t.metrics(points, t.KINDS[kind]["field"]), layout["id"])


class CheckerTest(unittest.TestCase):
    """Each broken layout must be reported, and for the right reason."""

    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def layout(self, kind="a"):
        return copy.deepcopy(self.data["layouts"][kind][0])

    def reasons(self, layout):
        return {problem.split(":")[0] for problem in t.check_layout(layout)}

    def test_untouched_layout_is_valid(self):
        for kind in t.KINDS:
            self.assertEqual(t.check_layout(self.layout(kind)), [])

    def test_crossing_lines(self):
        layout = self.layout()
        points = layout["points"]
        points[5], points[15] = points[15], points[5]
        self.assertIn("crossing", self.reasons(layout))

    def test_circles_too_close(self):
        layout = self.layout()
        x, y = layout["points"][3]
        layout["points"][10] = [x + 9, y + 9]
        self.assertIn("distance", self.reasons(layout))

    def test_circle_in_the_start_cross_zone(self):
        layout = self.layout()
        layout["points"][7] = [3, -4]
        self.assertIn("centre", self.reasons(layout))

    def test_circle_at_the_field_edge(self):
        layout = self.layout()
        layout["points"][7] = [78, 0]
        self.assertIn("edge", self.reasons(layout))

    def test_practice_circle_outside_the_practice_area(self):
        layout = self.layout("practice_a")
        layout["points"][2] = [60, 0]  # inside the full field, outside 96 x 60
        self.assertIn("edge", self.reasons(layout))

    def test_line_through_another_circle(self):
        layout = self.layout()
        (x0, y0), (x1, y1) = layout["points"][0], layout["points"][1]
        layout["points"][20] = [(x0 + x1) / 2 + 2, (y0 + y1) / 2 + 2]
        self.assertIn("clearance", self.reasons(layout))

    def test_path_folding_back(self):
        layout = self.layout("practice_a")
        layout["points"][:3] = [[-30, 0], [10, 0], [-28, 6]]
        self.assertIn("angle", self.reasons(layout))

    def test_path_too_short_for_part_b(self):
        layout = self.layout("b")
        layout["points"] = self.layout("a")["points"]
        self.assertIn("length", self.reasons(layout))

    def test_one_long_jump(self):
        layout = self.layout()
        layout["points"][24] = [-layout["points"][23][0], -layout["points"][23][1]]
        layout["points"][23] = [70 if layout["points"][24][0] < 0 else -70, 40 if layout["points"][24][1] < 0 else -40]
        self.assertTrue({"step", "length"} & self.reasons(layout))

    def test_first_circle_far_from_the_centre(self):
        layout = self.layout()
        layout["points"][0] = [72, 42]
        self.assertIn("first", self.reasons(layout))

    def test_empty_quarter(self):
        layout = self.layout("practice_a")
        layout["points"] = [[abs(x) if abs(x) > 1 else 5, y] for x, y in layout["points"]]
        self.assertIn("spread", self.reasons(layout))

    def test_wrong_labels_and_count(self):
        layout = self.layout("b")
        layout["labels"][9] = "Д"  # Ґ skipped
        self.assertIn("labels", self.reasons(layout))
        layout = self.layout()
        layout["points"].pop()
        self.assertIn("count", self.reasons(layout))

    def test_no_room_for_the_word(self):
        layout = self.layout()
        layout["label_sides"]["start"] = "above" if layout["label_sides"]["start"] == "below" else "below"
        x, y = layout["points"][0]
        box = t.label_box((x, y), layout["label_sides"]["start"])
        # Put a far-away circle into the box of the other side: one side is
        # always chosen by the generator, so only the stored side is checked.
        layout["points"][12] = [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2]
        self.assertIn("label", self.reasons(layout))

    def test_crossing_helper(self):
        self.assertTrue(t.segments_intersect((0, 0), (10, 10), (0, 10), (10, 0)))
        self.assertTrue(t.segments_intersect((0, 0), (10, 0), (5, 0), (5, 9)))  # touching counts
        self.assertFalse(t.segments_intersect((0, 0), (10, 0), (0, 1), (10, 1)))
        self.assertFalse(t.segments_intersect((0, 0), (4, 4), (5, 5), (9, 9)))  # same line, apart


class GeneratorTest(unittest.TestCase):
    def test_same_variant_gives_the_same_layout(self):
        stored = load()["layouts"]["practice_a"][0]
        again = t.make_layout("practice_a", 1)
        self.assertEqual(again["points"], stored["points"])
        self.assertEqual(again["label_sides"], stored["label_sides"])


class LabelRoomTest(unittest.TestCase):
    """The words "Початок" and "Кінець" next to the first and the last circle."""

    FIELD = t.PRACTICE_FIELD

    def test_words_must_not_overlap_each_other(self):
        # First circle above the last one, 20 units apart: the word under the
        # first and the word over the last would share the same place.
        points = [(0.0, -10.0), (-30.0, -15.0), (-30.0, 15.0), (0.0, 10.0)]
        self.assertTrue(t.label_fits(points, 0, "below", self.FIELD))
        self.assertTrue(t.label_fits(points, 3, "above", self.FIELD))
        self.assertFalse(t.labels_fit(points, {"start": "below", "end": "above"}, self.FIELD))
        self.assertEqual(t.label_sides(points, self.FIELD), {"start": "above", "end": "below"})

    def test_word_keeps_clear_of_circles_lines_and_the_edge(self):
        points = [(0.0, -22.0), (-40.0, -22.0), (0.0, 10.0)]
        self.assertFalse(t.label_fits(points, 0, "above", self.FIELD))  # outside the practice area
        self.assertTrue(t.label_fits(points, 0, "below", self.FIELD))
        self.assertFalse(t.label_fits([(0.0, -22.0), (-40.0, -22.0), (0.0, -11.0)], 0, "below", self.FIELD))  # a circle there
        self.assertFalse(t.label_fits([(0.0, -22.0), (0.0, 10.0), (-40.0, -22.0)], 0, "below", self.FIELD))  # its own line
        self.assertFalse(t.labels_fit(points, {"start": "below"}, self.FIELD))  # a side is missing


if __name__ == "__main__":
    unittest.main()
