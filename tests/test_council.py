import contextlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import council as co  # noqa: E402

SEATS = co.read_seats()
BENCH_NAMES = [
    "Jane Austen",
    "Sun Tzu",
    "Agatha Christie",
    "Voltaire",
    "Oscar Wilde",
    "Arthur Conan Doyle",
]
CLEAN = (
    "<prompt>\nYou are a Python engineer on a small internal tool. Read config.yaml "
    "and report what it sets, outcome first. Ask one question if the path is missing. "
    "Done means the report names every key and its value.\n</prompt>\n"
    "<note>I cut nothing.</note>\n"
)
FIX = Path(__file__).resolve().parent / "fixtures"
EXPECTED_ROSTER_RESIDUE_TERMS = (
    "the road",
    "no country",
    "drown",
    "complications",
    "surgeon",
    "neurologist",
    "primate",
    "orthodoxy",
    "the trial",
    "the castle",
    "metamorphosis",
    "usher",
)
CORPUS_PHRASES = ("fork in the road",) + EXPECTED_ROSTER_RESIDUE_TERMS[1:]
FORBIDDEN_REPLACEMENTS = (
    "suttree",
    "no country for old men",
    "brief wondrous life",
    "brigham",
    "surgeon's notes",
    "uncle tungsten",
    "masai mara",
    "flambeau",
    "penal colony",
    "hunger artist",
    "odradek",
    "house of usher",
)


def draft(tmp, name, body):
    p = Path(tmp) / (co.slug(name) + ".md")
    p.write_text(body, encoding="utf-8")
    return p


def pick_case(tmp, prompt=CLEAN, roll_data=None):
    root = Path(tmp)
    drafts = root / "drafts"
    drafts.mkdir()
    selected = draft(drafts, "plain", prompt)
    roll = root / "roll.json"
    roll.write_text(json.dumps(co.roll(7) if roll_data is None else roll_data), encoding="utf-8")
    verdict = root / "verdict.md"
    verdict.write_text("WINNER: plain\n", encoding="utf-8")
    return drafts, selected, roll, verdict, root / "winner.md"


def contains_term(text, term):
    pattern = rf"(?i)(?<![\w-]){re.escape(term)}(?![\w-])"
    return re.search(pattern, text) is not None


class TestSeats(unittest.TestCase):
    def test_twenty_two_rows_with_regular_bench_and_wild_seats(self):
        self.assertEqual(len(SEATS), 22)
        self.assertEqual(sum(1 for r in SEATS if r["kind"] == "regular"), 15)
        self.assertEqual(sum(1 for r in SEATS if r["kind"] == "bench"), 6)
        self.assertEqual(sum(1 for r in SEATS if r["kind"] == "wild"), 1)
        self.assertEqual([r["name"] for r in SEATS if r["kind"] == "bench"], BENCH_NAMES)
        self.assertEqual(SEATS[-1]["name"], "Werner Herzog")

    def test_names_unique_and_fields_filled(self):
        names = [r["name"] for r in SEATS]
        self.assertEqual(len(names), len(set(names)))
        for r in SEATS:
            for k in ("name", "kind", "creed", "catch", "residue"):
                self.assertTrue(r[k].strip(), "%s: empty %s" % (r["name"], k))
            self.assertIn(r["kind"], ("regular", "bench", "wild"))


class TestRoll(unittest.TestCase):
    def test_an_explicit_empty_seat_list_is_refused(self):
        with self.assertRaisesRegex(ValueError, "--seats needs exactly 3 names"):
            co.roll(1, seats=[])

    def test_same_seed_same_seats(self):
        a, b = co.roll(4127), co.roll(4127)
        self.assertEqual(a, b)
        names = [s["name"] for s in a["seats"]]
        self.assertEqual(len(names), 4)
        self.assertEqual(len(set(names)), 4)
        self.assertEqual(a["seats"][-1]["kind"], "wild")
        self.assertTrue(all(s["kind"] == "regular" for s in a["seats"][:3]))

    def test_different_seeds_differ_somewhere(self):
        rolls = {tuple(s["name"] for s in co.roll(i)["seats"][:3]) for i in range(30)}
        self.assertGreater(len(rolls), 5)

    def test_seats_override_keeps_order(self):
        r = co.roll(1, seats=["Mark Twain", "franz-kafka", "Oliver Sacks"])
        self.assertEqual(
            [s["name"] for s in r["seats"][:3]], ["Mark Twain", "Franz Kafka", "Oliver Sacks"]
        )

    def test_default_roll_never_draws_from_the_bench(self):
        bench = set(BENCH_NAMES)
        for seed in range(100):
            names = {s["name"] for s in co.roll(seed)["seats"][:3]}
            self.assertTrue(bench.isdisjoint(names), (seed, names & bench))

    def test_seats_override_promotes_a_bench_writer_to_a_regular_chair(self):
        fixed = ["Jane Austen", "Mark Twain", "Oliver Sacks"]
        r = co.roll(1, seats=fixed)
        self.assertEqual([s["name"] for s in r["seats"][:3]], fixed)
        self.assertTrue(all(s["kind"] == "regular" for s in r["seats"][:3]))
        with self.assertRaises(ValueError):
            co.roll(1, seats=fixed, wild="Jane Austen")

    def test_seats_override_rejects_the_roster_wild_card(self):
        with self.assertRaises(ValueError):
            co.roll(1, seats=["Werner Herzog", "Mark Twain", "Oliver Sacks"])

    def test_unknown_seat_raises(self):
        with self.assertRaises(ValueError):
            co.roll(1, seats=["Mark Twain", "Nobody Here", "Oliver Sacks"])

    def test_no_wild(self):
        self.assertEqual(len(co.roll(1, no_wild=True)["seats"]), 3)

    def test_wild_override_by_name(self):
        r = co.roll(1, wild="Dorothy Parker")
        self.assertEqual(r["seats"][-1]["name"], "Dorothy Parker")
        self.assertEqual(r["seats"][-1]["kind"], "wild")

    def test_wild_override_promotes_a_bench_writer_to_the_wild_chair(self):
        r = co.roll(1, wild="Sun Tzu")
        source = next(s for s in SEATS if s["name"] == "Sun Tzu")
        self.assertEqual(r["seats"][-1]["name"], "Sun Tzu")
        self.assertEqual(r["seats"][-1]["kind"], "wild")
        self.assertEqual(r["seats"][-1]["creed"], source["creed"])
        self.assertEqual(r["seats"][-1]["residue"], source["residue"])

    def test_seats_override_rejects_the_same_seat_twice(self):
        with self.assertRaises(ValueError):
            co.roll(1, seats=["Mark Twain", "mark twain", "Oliver Sacks"])

    def test_wild_from_the_roster_flips_kind_and_cannot_duplicate_a_seat(self):
        fixed = ["Mark Twain", "Franz Kafka", "Oliver Sacks"]
        r = co.roll(1, seats=fixed, wild="Edgar Allan Poe")
        self.assertEqual(r["seats"][-1]["name"], "Edgar Allan Poe")
        self.assertEqual(r["seats"][-1]["kind"], "wild")
        with self.assertRaises(ValueError):
            co.roll(1, seats=fixed, wild="Mark Twain")

    def test_the_roll_records_which_model_and_frame_it_was_written_for(self):
        r = co.roll(1)
        self.assertEqual(r["target_model"], co.MODEL)
        self.assertEqual(r["frame"], co.FRAME)

    def test_a_seat_with_no_filename_safe_name_is_refused(self):
        # slug() keeps only [a-z0-9], so a name with no Latin letters slugs to "" and its
        # draft lands at drafts/.md, which the run's *.md glob never sees.
        self.assertEqual(co.slug("村上春樹"), "")
        with self.assertRaises(ValueError) as e:
            co.roll(1, wild="村上春樹")
        self.assertIn("Latin-letter", str(e.exception))

    def test_roll_json_shape_for_the_lint(self):
        r = co.roll(7)
        self.assertEqual([c["name"] for c in r["critics"]], [s["name"] for s in r["seats"]])
        for s in r["seats"]:
            for word in s["residue"].split("|"):
                self.assertIn(word, r["graft"]["residue"])


class TestExtraChecks(unittest.TestCase):
    def test_reasoning_reproduction(self):
        rules = [f["rule"] for f in co.extra_checks("Show your reasoning first, then answer.")]
        self.assertIn("C1", rules)
        rules = [f["rule"] for f in co.extra_checks("Put your work in <thinking> tags.")]
        self.assertIn("C1", rules)

    def test_fossils(self):
        for text in (
            "Hold all findings for the final response.",
            "Never use bullets or headers.",
            "Do not narrate while you work.",
        ):
            self.assertIn("C2", [f["rule"] for f in co.extra_checks(text)], text)

    def test_the_reasoning_scaffold_is_C1_now_that_the_floor_owns_it(self):
        text = "Read the file and think step by step, then answer."
        self.assertIn("C1", [f["rule"] for f in co.extra_checks(text)])
        # The council assigns this reasoning shape to C1 and intentionally has no L2 rule.
        self.assertNotIn("L2", [f["rule"] for f in co.lint_prompt(text)])
        self.assertIn("C1", [f["rule"] for f in co.extra_checks("Let's think about the shape.")])

    def test_word_caps_warn_then_fail(self):
        self.assertEqual([f for f in co.extra_checks("A short prompt.") if f["rule"] == "C3"], [])
        warn = [f for f in co.extra_checks("word " * (co.SOFT_WORDS + 5)) if f["rule"] == "C3"]
        self.assertEqual([f["severity"] for f in warn], ["warn"])
        fail = [f for f in co.extra_checks("word " * (co.HARD_WORDS + 5)) if f["rule"] == "C3"]
        self.assertEqual([f["severity"] for f in fail], ["fail"])

    def test_an_empty_prompt_fails_instead_of_satisfying_every_rule(self):
        # A truncated Reviser or Drafter leaves nothing between the tags; without C3 the
        # floor calls that clean and pick ships an empty winner.md.
        for text in ("", "   \n\t "):
            with self.subTest(text=repr(text)):
                findings = co.extra_checks(text)
                self.assertEqual([f["rule"] for f in findings], ["C3"])
                self.assertEqual(findings[0]["severity"], "fail")

    def test_clean_text_has_no_extra_findings(self):
        self.assertEqual(co.extra_checks("Read the file, then report the outcome first."), [])


class TestFixtures(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.residue_terms = [
            term for seat in SEATS for term in seat["residue"].split("|") if term
        ]
        self.roster_terms = [seat["name"] for seat in SEATS] + self.residue_terms
        roll = {
            "seed": 0,
            "seats": SEATS,
            "critics": [{"name": seat["name"]} for seat in SEATS],
            "graft": {"residue": "|".join(self.residue_terms)},
        }
        self.roll_path = Path(self.tmp.name) / "all-roster-roll.json"
        self.roll_path.write_text(json.dumps(roll), encoding="utf-8")

    def test_prompt_fixtures_match_expected_failures(self):
        expected = json.loads((FIX / "expected.json").read_text(encoding="utf-8"))
        self.assertEqual(list(expected), ["bad_prompt", "clean_prompt"])
        for fixture, expected_rules in expected.items():
            with self.subTest(fixture=fixture):
                result = co.floor(FIX / (fixture + ".md"), self.roll_path)
                actual_rules = [
                    finding["rule"]
                    for finding in result["findings"]
                    if finding["severity"] == "fail"
                ]
                self.assertEqual(actual_rules, expected_rules)

    def test_corpus_has_only_expected_roster_residue(self):
        text = (FIX / "corpus.txt").read_text(encoding="utf-8")
        lines = text.splitlines()
        self.assertGreaterEqual(len(lines), 12)
        self.assertLessEqual(len(lines), 20)
        for line in lines:
            with self.subTest(line=line):
                self.assertEqual(sum(line.count(mark) for mark in ".!?"), 1)

        for phrase in CORPUS_PHRASES:
            with self.subTest(required_phrase=phrase):
                pattern = rf"(?i)(?<![\w-]){re.escape(phrase)}(?![\w-])"
                self.assertEqual(len(re.findall(pattern, text)), 1)
        for phrase in FORBIDDEN_REPLACEMENTS:
            with self.subTest(forbidden_replacement=phrase):
                self.assertFalse(contains_term(text, phrase))

        expected_matches = set(self.residue_terms).intersection(EXPECTED_ROSTER_RESIDUE_TERMS)
        actual_matches = {term for term in self.roster_terms if contains_term(text, term)}
        self.assertEqual(actual_matches, expected_matches)

        result = co.floor(FIX / "corpus.txt", self.roll_path)
        failures = [f for f in result["findings"] if f["severity"] == "fail"]
        self.assertEqual([f["rule"] for f in failures], ["L6"] * len(expected_matches))
        for term in expected_matches:
            self.assertTrue(any(repr(term) in finding["detail"] for finding in failures))


class TestFloor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.roll_path = Path(self.tmp) / "roll.json"
        self.roll = co.roll(1)
        self.roll_path.write_text(json.dumps(self.roll), encoding="utf-8")

    def test_clean_draft_passes(self):
        p = draft(self.tmp, "plain", CLEAN)
        r = co.floor(p, self.roll_path)
        self.assertTrue(r["ok"], r["findings"])

    def test_residue_of_a_seated_author_fails(self):
        word = self.roll["seats"][0]["residue"].split("|")[0]
        p = draft(self.tmp, "x", CLEAN.replace("small internal tool", "tool about %s" % word))
        r = co.floor(p, self.roll_path)
        self.assertFalse(r["ok"])
        self.assertIn("L6", [f["rule"] for f in r["findings"] if f["severity"] == "fail"])

    def test_step_by_step_fails(self):
        p = draft(self.tmp, "x", CLEAN.replace("outcome first", "and think step by step"))
        self.assertFalse(co.floor(p, self.roll_path)["ok"])

    def test_fossil_fails_through_floor(self):
        p = draft(
            self.tmp, "x", CLEAN.replace("outcome first", "and hold all findings for the end")
        )
        r = co.floor(p, self.roll_path)
        self.assertIn("C2", [f["rule"] for f in r["findings"]])
        self.assertFalse(r["ok"])

    def test_an_empty_draft_does_not_pass_the_floor(self):
        for body in ("", "<prompt>\n</prompt>\n<note>n</note>\n"):
            with self.subTest(body=repr(body)):
                p = draft(self.tmp, "x", body)
                r = co.floor(p, self.roll_path)
                self.assertFalse(r["ok"], r["findings"])
                self.assertIn("C3", [f["rule"] for f in r["findings"] if f["severity"] == "fail"])

    def test_a_placeholder_does_not_fail_the_floor(self):
        p = draft(self.tmp, "x", CLEAN.replace("config.yaml", "{$CONFIG_PATH}"))
        self.assertTrue(co.floor(p, self.roll_path)["ok"])

    def test_draft_without_prompt_tag_is_linted_whole(self):
        p = draft(self.tmp, "x", "Read config.yaml and report what it sets, outcome first.")
        self.assertTrue(co.floor(p, self.roll_path)["ok"])


class TestLintPrompt(unittest.TestCase):
    def rules(self, text, roll=None):
        return [f["rule"] for f in co.lint_prompt(text, roll) if f["severity"] == "fail"]

    def test_each_carried_rule_has_a_failing_case(self):
        cases = {
            "L1": "Read the file.\nAssistant: I will start with the failing test.",
            "L3": "Read the file." + "<example>x</example>" * 6,
            "L4": "If in doubt, choose the smallest change.",
            "L5": ("Do not edit unrelated files. Never skip the test. Avoid new "
                   "dependencies. No refactors are allowed. Read the report. Run the "
                   "suite. Name the cause. Report the outcome first."),
            "L7": "Use a robust check for the repaired branch.",
        }
        for rule, text in cases.items():
            with self.subTest(rule=rule):
                self.assertIn(rule, self.rules(text))

    def test_residue_needs_a_roll_and_warns_without_one(self):
        roll = {"critics": [{"name": "Mark Twain"}], "graft": {"residue": "tom sawyer"}}
        self.assertIn("L6", self.rules("A tool about tom sawyer.", roll))
        self.assertIn("L6", self.rules("Mark Twain reads it.", roll))
        self.assertEqual(self.rules("A tool about config files.", roll), [])
        warns = [f for f in co.lint_prompt("A tool about tom sawyer.") if f["rule"] == "L6"]
        self.assertEqual([f["severity"] for f in warns], ["warn"])

    def test_a_fork_in_the_road_survives_a_mccarthy_seat(self):
        roll = co.roll(1, seats=["Cormac McCarthy", "Mark Twain", "Oliver Sacks"])
        text = "When the config offers a fork in the road, ask the user which branch to take."
        self.assertEqual(self.rules(text, roll), [])

    def test_a_residue_word_the_idea_itself_uses_is_waived(self):
        roll = {"critics": [], "graft": {"residue": "serengeti"}}
        text = "Write a parser for the serengeti telemetry format."
        self.assertEqual(self.rules(text, roll), ["L6"])
        waived = [f for f in co.lint_prompt(text, roll, idea="index the serengeti telemetry")
                  if f["rule"] == "L6"]
        self.assertEqual([f["severity"] for f in waived], ["warn"])
        self.assertIn("waived", waived[0]["detail"])

    def test_clean_prompt_fixture_has_no_findings(self):
        text = (FIX / "clean_prompt.md").read_text(encoding="utf-8")
        self.assertEqual(self.rules(co.block(text, "prompt")), [])


class TestObjections(unittest.TestCase):
    def test_synthetic_fixture_parses_as_twelve_valid_objections(self):
        r = co.objections(FIX / "objections.md")
        self.assertEqual(r["received"], 12)
        self.assertEqual(len(r["valid"]), 12)
        self.assertEqual(r["dropped"], [])

    OBJ = (
        '<objection axis="%s" critic="%s" candidate="%s">'
        "<claim>the rival never names the config file</claim>"
        "<falsifying_input>a config.yaml holding a null timeout value</falsifying_input>"
        "<expected_divergence>rival guesses; mine asks</expected_divergence></objection>"
    )

    def test_the_filename_and_the_roll_say_who_filed_an_objection(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "roll.json").write_text(json.dumps(roll), encoding="utf-8")
            # The examiner stamped a rival's name on its own objection.
            (t / "junot-diaz.md").write_text(
                self.OBJ % ("cormac-mccarthy", "Cormac McCarthy", "cormac-mccarthy"),
                encoding="utf-8",
            )
            r = co.objections(t, t / "roll.json")
        self.assertEqual(r["received"], 1)
        self.assertEqual(len(r["valid"]), 1)
        self.assertEqual(r["valid"][0]["axis"], "junot-diaz")
        self.assertEqual(r["valid"][0]["critic"], "Junot Díaz")
        self.assertEqual(r["valid"][0]["candidate"], "cormac-mccarthy")

    def test_a_seated_single_file_is_restamped_from_filename_and_roll(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            roll_path = t / "roll.json"
            roll_path.write_text(json.dumps(roll), encoding="utf-8")
            objection_path = t / "junot-diaz.md"
            objection_path.write_text(
                self.OBJ % ("cormac-mccarthy", "Cormac McCarthy", "cormac-mccarthy"),
                encoding="utf-8",
            )
            r = co.objections(objection_path, roll_path)
        self.assertEqual(r["received"], 1)
        self.assertEqual(len(r["valid"]), 1)
        self.assertEqual(r["valid"][0]["axis"], "junot-diaz")
        self.assertEqual(r["valid"][0]["critic"], "Junot Díaz")
        self.assertEqual(r["valid"][0]["candidate"], "cormac-mccarthy")

    def test_an_objection_against_its_own_seat_or_a_stranger_is_dropped(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "roll.json").write_text(json.dumps(roll), encoding="utf-8")
            (t / "junot-diaz.md").write_text(
                self.OBJ % ("junot-diaz", "Junot Díaz", "junot-diaz")
                + self.OBJ % ("junot-diaz", "Junot Díaz", "jorge-luis-borges")
                + self.OBJ % ("junot-diaz", "Junot Díaz", "plain"),
                encoding="utf-8",
            )
            r = co.objections(t, t / "roll.json")
        self.assertEqual(r["received"], 3)
        self.assertEqual([o["candidate"] for o in r["valid"]], ["plain"])
        self.assertEqual([d["reason"] for d in r["dropped"]],
                         ["candidate 'junot-diaz' is the objection's own seat",
                          "candidate 'jorge-luis-borges' was never seated"])

    def test_an_unseated_objection_file_is_received_but_dropped(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "roll.json").write_text(json.dumps(roll), encoding="utf-8")
            (t / "stranger.md").write_text(
                self.OBJ % ("junot-diaz", "Junot Díaz", "cormac-mccarthy"),
                encoding="utf-8",
            )
            r = co.objections(t, t / "roll.json")
        self.assertEqual(r["received"], 1)
        self.assertEqual(r["valid"], [])
        self.assertEqual(
            r["dropped"],
            [{
                "index": 0,
                "reason": "objection file 'stranger.md' does not belong to a seated writer",
            }],
        )

    def test_an_unseated_single_file_is_received_but_dropped(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            roll_path = t / "roll.json"
            roll_path.write_text(json.dumps(roll), encoding="utf-8")
            objection_path = t / "stranger.md"
            objection_path.write_text(
                self.OBJ % ("junot-diaz", "Junot Díaz", "cormac-mccarthy"),
                encoding="utf-8",
            )
            r = co.objections(objection_path, roll_path)
        self.assertEqual(r["received"], 1)
        self.assertEqual(r["valid"], [])
        self.assertEqual(
            r["dropped"],
            [{
                "index": 0,
                "reason": "objection file 'stranger.md' does not belong to a seated writer",
            }],
        )

    def test_without_a_roll_file_and_directory_inputs_preserve_declared_provenance(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            objection_path = t / "stranger.md"
            objection_path.write_text(
                self.OBJ % ("declared-axis", "Declared Critic", "unseated-candidate"),
                encoding="utf-8",
            )
            from_file = co.objections(objection_path)
            from_directory = co.objections(t)
        self.assertEqual(from_file, from_directory)
        self.assertEqual(from_file["received"], 1)
        self.assertEqual(from_file["dropped"], [])
        self.assertEqual(len(from_file["valid"]), 1)
        self.assertEqual(from_file["valid"][0]["axis"], "declared-axis")
        self.assertEqual(from_file["valid"][0]["critic"], "Declared Critic")
        self.assertEqual(from_file["valid"][0]["candidate"], "unseated-candidate")

    def test_an_empty_objections_directory_returns_nothing_received(self):
        with tempfile.TemporaryDirectory() as t:
            r = co.objections(t)
        self.assertEqual(r, {"received": 0, "valid": [], "dropped": []})

    def test_a_short_falsifying_input_is_dropped(self):
        text = (
            '<objection axis="a" critic="A" candidate="b">'
            "<claim>c</claim><falsifying_input>too short</falsifying_input>"
            "<expected_divergence>d</expected_divergence></objection>"
        )
        with tempfile.TemporaryDirectory() as t:
            f = Path(t) / "a.md"
            f.write_text(text, encoding="utf-8")
            r = co.objections(f)
        self.assertEqual(r["received"], 1)
        self.assertEqual(r["valid"], [])
        self.assertEqual(r["dropped"][0]["reason"], "falsifying_input under 20 chars")


class TestPick(unittest.TestCase):
    def test_pick_copies_the_winner_prompt_and_never_overwrites(self):
        with tempfile.TemporaryDirectory() as t:
            drafts = Path(t) / "drafts"
            drafts.mkdir()
            draft(drafts, "Mark Twain", "<prompt>kill the adjective</prompt><note>n</note>")
            draft(drafts, "plain", "<prompt>plain one</prompt>")
            verdict = Path(t) / "verdict.md"
            verdict.write_text("WINNER: Mark Twain\nThe line that decided it.\n", encoding="utf-8")
            out = Path(t) / "winner.md"
            r = co.pick(verdict, drafts, out)
            self.assertEqual(r["winner"], "Mark Twain")
            self.assertEqual(out.read_text(encoding="utf-8"), "kill the adjective")
            before = out.read_bytes()
            with self.assertRaises(FileExistsError):
                co.pick(verdict, drafts, out)
            self.assertEqual(out.read_bytes(), before)

            raced = Path(t) / "raced-winner.md"
            path_open = Path.open

            def create_before_open(path, *args, **kwargs):
                if path == raced:
                    with path_open(path, "w", encoding="utf-8") as other:
                        other.write("another process won")
                return path_open(path, *args, **kwargs)

            with mock.patch.object(Path, "open", new=create_before_open):
                with self.assertRaises(FileExistsError):
                    co.pick(verdict, drafts, raced)
            self.assertEqual(raced.read_text(encoding="utf-8"), "another process won")

    def test_pick_refuses_an_empty_selected_prompt(self):
        for body in ("", "<prompt>\n</prompt>\n<note>n</note>\n"):
            with self.subTest(body=repr(body)), tempfile.TemporaryDirectory() as t:
                t = Path(t)
                drafts, _, roll, verdict, out = pick_case(t, body)

                result = co.pick(verdict, drafts, out, roll)

                self.assertFalse(result["ok"])
                self.assertIn("C3", [f["rule"] for f in result["findings"]])
                self.assertFalse(out.exists())

    def test_pick_resolves_an_accented_name_written_either_way(self):
        roll = co.roll(1, seats=["Junot Díaz", "Mark Twain", "Oliver Sacks"])
        for written in ("Junot Díaz", "Junot Diaz", "junot-diaz", "JUNOT DÍAZ"):
            with self.subTest(written=written), tempfile.TemporaryDirectory() as t:
                t = Path(t)
                (t / "drafts").mkdir()
                draft(t / "drafts", "Junot Díaz", "<prompt>the winning prompt</prompt>")
                (t / "roll.json").write_text(json.dumps(roll), encoding="utf-8")
                (t / "verdict.md").write_text("WINNER: %s\n" % written, encoding="utf-8")
                r = co.pick(t / "verdict.md", t / "drafts", t / "winner.md", t / "roll.json")
                self.assertEqual(r["slug"], "junot-diaz")
                self.assertEqual((t / "winner.md").read_text(encoding="utf-8"), "the winning prompt")

    def test_pick_rejects_a_name_nobody_on_the_roll_answers_to(self):
        roll = co.roll(1, seats=["Junot Díaz", "Mark Twain", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "drafts").mkdir()
            (t / "roll.json").write_text(json.dumps(roll), encoding="utf-8")
            (t / "verdict.md").write_text("WINNER: Jorge Luis Borges\n", encoding="utf-8")
            with self.assertRaises(ValueError) as e:
                co.pick(t / "verdict.md", t / "drafts", t / "winner.md", t / "roll.json")
        self.assertIn("Junot Díaz", str(e.exception))
        self.assertIn("plain", str(e.exception))

    def test_pick_draft_override_ships_a_different_file(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            (t / "drafts").mkdir()
            draft(t / "drafts", "Mark Twain", "<prompt>the original</prompt>")
            (t / "revision.md").write_text("<prompt>the revision</prompt>", encoding="utf-8")
            (t / "verdict.md").write_text("WINNER: Mark Twain\n", encoding="utf-8")
            r = co.pick(
                t / "verdict.md", t / "drafts", t / "winner.md", draft=t / "revision.md"
            )
            self.assertEqual(r["source"], str(t / "revision.md"))
            self.assertEqual((t / "winner.md").read_text(encoding="utf-8"), "the revision")

    def test_pick_rechecks_a_draft_override_instead_of_the_original(self):
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            drafts, _, roll, verdict, out = pick_case(t)
            revision = t / "revision.md"
            revision.write_text("<prompt>Work step by step.</prompt>", encoding="utf-8")

            result = co.pick(verdict, drafts, out, roll, draft=revision)

            self.assertFalse(result["ok"])
            self.assertEqual(result["file"], str(revision))
            self.assertIn("C1", [f["rule"] for f in result["findings"]])
            self.assertFalse(out.exists())

    def test_pick_ships_the_exact_prompt_that_passed_the_floor(self):
        with tempfile.TemporaryDirectory() as t:
            drafts, selected, roll, verdict, out = pick_case(t)
            read_text = Path.read_text
            source_reads = iter((CLEAN, "<prompt>Work step by step.</prompt>"))

            def changing_source(path, *args, **kwargs):
                if path == selected:
                    return next(source_reads)
                return read_text(path, *args, **kwargs)

            with mock.patch.object(Path, "read_text", new=changing_source):
                result = co.pick(verdict, drafts, out, roll)

            self.assertEqual(result["winner"], "plain")
            self.assertEqual(out.read_text(encoding="utf-8"), co.prompt_of(CLEAN))

    def test_pick_with_no_winner_line_raises(self):
        with tempfile.TemporaryDirectory() as t:
            drafts = Path(t) / "drafts"
            drafts.mkdir()
            verdict = Path(t) / "verdict.md"
            verdict.write_text("The judge rambled and named nobody.\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                co.pick(verdict, drafts, Path(t) / "winner.md")


class TestRunPointer(unittest.TestCase):
    POINTER_NAME = r"^current_run\.[0-9a-f]{64}$"

    def test_formerly_colliding_paths_have_distinct_filename_safe_pointers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            left, right = root / "a_b" / "c", root / "a" / "b_c"
            left.mkdir(parents=True)
            right.mkdir(parents=True)
            pointers = [co.run_pointer(root / "home", path) for path in (left, right)]

        self.assertNotEqual(*pointers)
        for pointer in pointers:
            self.assertRegex(pointer.name, self.POINTER_NAME)

    def test_pointer_identity_is_stable_for_the_same_physical_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            physical = root / "physical"
            physical.mkdir()
            first = co.run_pointer(root / "home", physical)
            repeated = co.run_pointer(root / "home", physical)
            other_home = co.run_pointer(root / "other-home", physical)

        self.assertEqual(first, repeated)
        self.assertEqual(first.name, other_home.name)
        self.assertRegex(first.name, self.POINTER_NAME)

    def test_symlink_and_physical_paths_have_the_same_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            physical, link = root / "physical", root / "link"
            physical.mkdir()
            link.symlink_to(physical, target_is_directory=True)
            physical_pointer = co.run_pointer(root / "home", physical)
            link_pointer = co.run_pointer(root / "home", link)

        self.assertEqual(physical_pointer, link_pointer)
        self.assertRegex(physical_pointer.name, self.POINTER_NAME)

    def test_newline_and_unusual_paths_stay_distinct_and_filename_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = [root / "odd", root / "odd\n", root / " spaces '$`[]\n"]
            for path in paths:
                path.mkdir()
            pointers = [co.run_pointer(root / "home", path) for path in paths]

        self.assertEqual(len(set(pointers)), len(paths))
        for pointer in pointers:
            self.assertRegex(pointer.name, self.POINTER_NAME)
            self.assertNotIn("\n", pointer.name)

    def test_pointer_cli_returns_python_identity_for_an_unusual_cwd(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cwd = root / " spaces '$`[]\n"
            cwd.mkdir()
            env = dict(os.environ, HOME=str(root / "home"))
            result = subprocess.run(
                [sys.executable, "-B", str(co.HERE / "council.py"), "pointer"],
                cwd=cwd, env=env, capture_output=True, text=True, check=False,
            )
            expected = co.run_pointer(Path(env["HOME"]) / ".council", cwd)

        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(json.loads(result.stdout), {"pointer": str(expected)})
        self.assertEqual(result.stderr, "")


class TestInit(unittest.TestCase):
    STAMP = "20260903-120000"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "council"

    def go(self, raw):
        return co.init(raw, home=self.home, stamp=self.STAMP, cwd="/tmp/somewhere")

    def test_every_flag_comes_out_of_the_one_argument(self):
        r = self.go(
            '--seed 4127 --seats "Mark Twain,Franz Kafka,Oliver Sacks" --no-wild '
            "--revise build a weekly scout report"
        )
        self.assertEqual(r["seed"], 4127)
        self.assertEqual(
            [s["name"] for s in r["seats"]], ["Mark Twain", "Franz Kafka", "Oliver Sacks"]
        )
        self.assertTrue(r["revise"])
        run = Path(r["run"])
        self.assertEqual(run.name, "build-a-weekly-scout-report-" + self.STAMP)
        for d in ("drafts", "lint", "objections"):
            self.assertTrue((run / d).is_dir(), d)
        self.assertEqual((run / "idea.md").read_text(encoding="utf-8").strip(),
                         "build a weekly scout report")
        self.assertEqual(json.loads((run / "roll.json").read_text(encoding="utf-8"))["seed"], 4127)
        self.assertEqual(Path(r["pointer"]).read_text(encoding="utf-8").strip(), str(run))

    def test_wild_seats_the_named_writer_and_revise_defaults_off(self):
        r = self.go('--wild "Oscar Wilde" write a release note')
        self.assertEqual(r["seats"][-1]["name"], "Oscar Wilde")
        self.assertEqual(r["seats"][-1]["kind"], "wild")
        self.assertFalse(r["revise"])

    def test_an_argument_naming_a_file_is_read_as_the_idea(self):
        f = Path(self.tmp.name) / "idea.txt"
        f.write_text("rewrite the onboarding email\n", encoding="utf-8")
        r = self.go(str(f))
        self.assertEqual(
            (Path(r["run"]) / "idea.md").read_text(encoding="utf-8").strip(),
            "rewrite the onboarding email",
        )

    def idea_of(self, r):
        return (Path(r["run"]) / "idea.md").read_text(encoding="utf-8").strip()

    def test_an_idea_with_an_apostrophe_starts_a_run(self):
        # shlex.split reads a bare apostrophe as an open quote and refuses the whole run.
        idea = "rewrite the onboarding email in a person's voice"
        self.assertEqual(self.idea_of(self.go(idea)), idea)

    def test_the_idea_reaches_idea_md_with_its_own_punctuation(self):
        idea = 'a prompt that says "yes" or "no", never maybe'
        self.assertEqual(self.idea_of(self.go(idea)), idea)

    def test_a_word_that_is_not_a_flag_stays_part_of_the_idea(self):
        self.assertEqual(self.idea_of(self.go("--nope do the thing")), "--nope do the thing")

    def test_double_dash_leaves_a_wild_flag_like_idea_alone(self):
        idea = "--wild behavior in parsers"
        parsed = self.go(idea)
        self.assertEqual(parsed["seats"][-1]["name"], "behavior")
        self.assertEqual(self.idea_of(parsed), "in parsers")
        self.assertEqual(self.idea_of(self.go("-- " + idea)), idea)

    def test_double_dash_leaves_a_seats_flag_like_idea_alone(self):
        idea = "--seats of power in the ancient world"
        with self.assertRaisesRegex(ValueError, "--seats needs exactly 3 names"):
            self.go(idea)
        self.assertEqual(self.idea_of(self.go("-- " + idea)), idea)

    def test_an_empty_wild_value_is_refused(self):
        with self.assertRaisesRegex(ValueError, "--wild needs a value"):
            self.go('--wild "" write the prompt')

    def test_an_empty_seats_value_is_refused(self):
        with self.assertRaisesRegex(ValueError, "--seats needs a value"):
            self.go('--seats "" write the prompt')

    def test_a_quoted_flag_value_must_close_at_a_token_boundary(self):
        with self.assertRaisesRegex(ValueError, "--wild quoted value does not close cleanly"):
            self.go('--wild "A \\"Quoted\\" Name" write the prompt')

    def test_a_seed_that_is_not_a_number_is_refused(self):
        with self.assertRaises(ValueError):
            self.go("--seed abc do the thing")

    def test_missing_or_blank_flag_values_are_refused(self):
        for flag in ("seed", "seats", "wild"):
            for suffix in ("", "=", "= write the prompt", ' "" write the prompt',
                           " '' write the prompt", ' " \t " write the prompt'):
                with self.subTest(flag=flag, suffix=suffix):
                    with self.assertRaisesRegex(ValueError, "--%s needs a value" % flag):
                        co.split_argument("--" + flag + suffix)

    def test_a_missing_value_does_not_consume_the_next_known_flag(self):
        for flag in ("seed", "seats", "wild"):
            for following in ("--seed 4", '--seats "Mark Twain,Franz Kafka,Oliver Sacks"',
                              '--wild "Oscar Wilde"', "--no-wild", "--revise", "--fast",
                              "--", "--\t"):
                with self.subTest(flag=flag, following=following):
                    with self.assertRaisesRegex(ValueError, "--%s needs a value" % flag):
                        co.split_argument("--%s %s write the prompt" % (flag, following))

    def test_bare_flags_reject_values(self):
        for flag in ("no-wild", "revise", "fast"):
            for value in ("", "false", '""'):
                with self.subTest(flag=flag, value=value):
                    with self.assertRaisesRegex(ValueError, "does not take a value"):
                        co.split_argument("--%s=%s write the prompt" % (flag, value))

    def test_later_valid_flags_do_not_hide_invalid_values(self):
        for raw in ('--seed nope --seed 7 idea',
                    '--seats " , " --seats "Mark Twain,Franz Kafka,Oliver Sacks" idea'):
            with self.subTest(raw=raw):
                with self.assertRaises(ValueError):
                    co.split_argument(raw)
        flags, idea = co.split_argument('--seed 1 --seed 7 --wild First --wild Second idea')
        self.assertEqual((flags["seed"], flags["wild"], idea), (7, "Second", "idea"))

    def test_valid_values_and_idea_characters_are_preserved(self):
        idea = 'a doctor\'s note: say "yes"\n\tthen  --wild stays in the idea'
        cases = (
            ('--seed=-7 ', "seed", -7),
            ('--wild "--revise" ', "wild", "--revise"),
            ('--wild=--no-wild ', "wild", "--no-wild"),
            ('--wild "  Oscar Wilde  " ', "wild", "  Oscar Wilde  "),
            ('--seats " Mark Twain, Franz Kafka ,Oliver Sacks " ', "seats",
             " Mark Twain, Franz Kafka ,Oliver Sacks "),
        )
        for prefix, key, value in cases:
            with self.subTest(prefix=prefix):
                flags, parsed = co.split_argument(prefix + idea)
                self.assertEqual(flags[key], value)
                self.assertEqual(parsed, idea)
        for prefix in ("--unknown ", "--wild-card ", "--seats-extra ", "--revise-later ",
                       "--help "):
            with self.subTest(prefix=prefix):
                self.assertEqual(co.split_argument(prefix + idea)[1], prefix + idea)
        self.assertEqual(co.split_argument("--seed 7 -- --wild " + idea)[1], "--wild " + idea)

    def test_malformed_init_is_write_safe_and_clears_only_the_pointer(self):
        first = self.go("a weekly scout report")
        ptr = Path(first["pointer"])
        before = {p.relative_to(self.home): p.read_bytes()
                  for p in self.home.rglob("*") if p.is_file() and p != ptr}
        for raw in ('--wild --no-wild write the prompt', '--wild= write the prompt',
                    '--seats " , \t, " write the prompt', '--seats ",,," write the prompt',
                    '--wild "" write the prompt', '--seed nope write the prompt'):
            with self.subTest(raw=raw):
                ptr.write_text(first["run"] + "\n", encoding="utf-8")
                with self.assertRaises(ValueError):
                    self.go(raw)
                self.assertFalse(ptr.exists())
                after = {p.relative_to(self.home): p.read_bytes()
                         for p in self.home.rglob("*") if p.is_file()}
                self.assertEqual(after, before)

    def test_a_refused_init_leaves_no_pointer_to_the_run_before_it(self):
        first = self.go("a weekly scout report")
        ptr = Path(first["pointer"])
        self.assertEqual(ptr.read_text(encoding="utf-8").strip(), first["run"])
        with self.assertRaises(ValueError):
            self.go("--seed 3")
        self.assertFalse(ptr.exists(), "a refused run left the previous run bookmarked")
        self.assertTrue(Path(first["run"], "idea.md").is_file(), "the earlier run was harmed")

    def test_two_runs_in_the_same_second_never_share_a_directory(self):
        first = self.go("a weekly scout report")
        second = self.go("a weekly scout report")
        self.assertNotEqual(first["run"], second["run"])
        self.assertEqual(Path(second["run"]).name, Path(first["run"]).name + "-2")

    def test_an_empty_idea_is_refused(self):
        with self.assertRaises(ValueError):
            self.go("--seed 3")

    def test_a_secret_is_refused_and_never_echoed(self):
        synthetic_api_key = "sk-" + "a1B2c3D4" * 3
        with self.assertRaises(ValueError) as e:
            self.go("write a client that calls the API with " + synthetic_api_key)
        self.assertNotIn(synthetic_api_key, str(e.exception))
        self.assertIn("API key", str(e.exception))
        self.assertFalse((self.home / "runs").exists(), "a refused run wrote to disk")

    def test_every_secret_shape_is_refused(self):
        # ~/.council/runs is append-only, so a pattern that stops firing writes a pasted
        # credential to disk permanently and nothing else notices.
        named_secret_value = "".join(("api", "_key=", "synthetic-", "fixture-value"))
        synthetic_secrets = {
            "an API key": "sk-" + "a1B2c3D4" * 3,
            "a GitHub token": "ghp_" + "A" * 20,
            "an AWS access key id": "AKIA" + "ABCDEFGHIJKLMNOP",
            # split literal: a placeholder, and the repo's own secret scanner reads
            # this file too.
            "a private key": "-----BEGIN RSA " + "PRIVATE KEY-----",
            "a named secret": named_secret_value,
        }
        for what, value in synthetic_secrets.items():
            with self.subTest(secret=what):
                found = co.find_secret("write a client that sends " + value)
                self.assertIsNotNone(found, value)
                self.assertEqual(found[0], what)
                self.assertNotIn(value, found[1])
        self.assertIsNone(co.find_secret("read config.yaml and report every key it sets"))

    def test_the_cli_exits_three_on_a_bad_argument(self):
        init = co.init
        for raw in ("", "--seed", '--wild "" idea', '--seats " , " idea',
                    "--wild --no-wild idea"):
            with self.subTest(raw=raw):
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(co, "init", side_effect=lambda value: init(
                        value, home=self.home, stamp=self.STAMP, cwd="/tmp/somewhere")), \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(co.main(["init", raw]), 3)
                self.assertEqual(set(json.loads(out.getvalue())), {"error"})
                self.assertEqual(err.getvalue(), "")

    def test_init_requires_one_raw_argument_and_clears_a_stale_pointer(self):
        init = co.init
        first = self.go("a weekly scout report")
        ptr = Path(first["pointer"])
        for rest in (["--wild", "", "write a prompt"], ["--wild", "Oscar Wilde", "idea"]):
            with self.subTest(rest=rest):
                ptr.write_text(first["run"] + "\n", encoding="utf-8")
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(co, "init", side_effect=lambda value: init(
                        value, home=self.home, stamp=self.STAMP, cwd="/tmp/somewhere")), \
                        mock.patch.object(co, "run_pointer", return_value=ptr), \
                        contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(co.main(["init"] + rest), 3)
                self.assertIn("one", json.loads(out.getvalue())["error"])
                self.assertEqual(err.getvalue(), "")
                self.assertFalse(ptr.exists())
                self.assertEqual(list((self.home / "runs").iterdir()), [Path(first["run"])])


class TestSkillMd(unittest.TestCase):
    TEXT = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text(encoding="utf-8")
    BASH = re.findall(r"(?s)```bash\n(.*?)```", TEXT)

    def test_public_entry_points_use_the_english_class_identity(self):
        root = Path(__file__).resolve().parents[1]
        texts = {
            name: (root / name).read_text(encoding="utf-8")
            for name in ("README.md", "SKILL.md", "SPEC.md", "council.py", co.FRAME)
        }
        former_names = tuple("a" + "p" + suffix for suffix in (" english", "-english", "_english"))
        for name, text in texts.items():
            for former_name in former_names:
                with self.subTest(file=name, former_name=former_name):
                    self.assertIsNone(re.search(re.escape(former_name), text, re.I))

        self.assertTrue(texts["README.md"].startswith("# English Class Prompt Council\n"))
        self.assertIn("https://github.com/chadmarkey/english-class", texts["README.md"])
        self.assertRegex(texts["SKILL.md"], r"(?m)^name: english-class$")
        self.assertTrue(texts["SPEC.md"].startswith("# English Class Prompt Council — design spec\n"))
        self.assertIn("Command: `/english-class`.", texts["SPEC.md"])
        self.assertIn("## English Class project policy", texts[co.FRAME])
        for name in ("README.md", "SKILL.md", "council.py"):
            with self.subTest(file=name):
                self.assertIn("/english-class", texts[name])

    def test_the_run_has_shell_blocks_to_check(self):
        self.assertGreaterEqual(len(self.BASH), 4)

    def test_commands_are_functions_not_variables(self):
        # zsh does not word-split an unquoted variable, so CO="python3 council.py"
        # followed by `$CO roll` runs a file named "python3 council.py" and fails.
        for blk in self.BASH:
            for line in blk.splitlines():
                self.assertIsNone(re.search(r"\$[A-Z][A-Z_]*\s+[A-Za-z-]", line), line)

    def test_no_conditional_expansion_hides_a_word_split(self):
        # ${SEED:+--seed $SEED} is one word in zsh and two in bash.
        self.assertEqual(re.findall(r"\$\{[A-Za-z_]+:\+[^}]*\s[^}]*\}", self.TEXT), [])

    def test_every_template_that_writes_a_prompt_states_the_word_caps(self):
        writers = ("Drafter", "Plain drafter", "Fast drafter", "Reviser")
        blocks = dict(re.findall(r"(?ms)^### ([^\n]+)\n\n```\n(.*?)\n```", self.TEXT))
        for name in writers:
            with self.subTest(template=name):
                self.assertIn("under %d words" % co.HARD_WORDS, blocks[name])
                self.assertIn("warns above %d" % co.SOFT_WORDS, blocks[name])
        self.assertEqual(len(re.findall(r"under %d words" % co.HARD_WORDS, self.TEXT)), len(writers))

    def test_python_owns_pointer_derivation_for_the_shell(self):
        preamble = self.BASH[0]
        self.assertIn("co pointer", preamble)
        for duplicate in ("pwd -P", "tr / _", "shasum", "sha256sum", "hashlib", "hexdigest"):
            with self.subTest(duplicate=duplicate):
                self.assertNotIn(duplicate, preamble)

        repo = str(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as t:
            t = Path(t)
            cwd = t / " spaces '$`[]\n"
            cwd.mkdir()
            env = dict(os.environ, HOME=str(t / "home"))
            installed = Path(env["HOME"]) / ".claude" / "skills"
            installed.mkdir(parents=True)
            (installed / "english-class").symlink_to(repo, target_is_directory=True)
            py = subprocess.run(
                [sys.executable, "-B", str(Path(repo) / "council.py"), "pointer"],
                cwd=str(cwd), env=env, capture_output=True, text=True,
            )
            self.assertEqual(py.returncode, 0, py.stderr)
            expected = json.loads(py.stdout)["pointer"]
            for shell in ("bash", "zsh"):
                with self.subTest(shell=shell):
                    sh = subprocess.run(
                        [shell, "-c", preamble + '\nprintf %s "$RUNPTR"\n'],
                        cwd=str(cwd), env=env, capture_output=True, text=True,
                    )
                    self.assertEqual(sh.returncode, 0, sh.stderr)
                    self.assertEqual(sh.stdout, expected)

    def test_step_zero_uses_the_pointer_returned_by_a_successful_init(self):
        step = re.search(r"(?s)## 0\..*?\n## 1\.", self.TEXT)
        self.assertIsNotNone(step, "no step 0")
        step = step.group(0)
        self.assertIn('INIT=$(co init "$ARGUMENTS")', step)
        self.assertIn("INIT_STATUS=$?", step)
        self.assertIn('exit "$INIT_STATUS"', step)
        self.assertRegex(step, r"RUNPTR=.*\$INIT")
        self.assertLess(step.index('co init "$ARGUMENTS"'), step.index("RUNPTR="))

    def test_the_revision_round_is_gated_on_the_flag(self):
        step = re.search(r"(?s)## 4b\..*?\n## 5\.", self.TEXT)
        self.assertIsNotNone(step, "no 4b step")
        step = step.group(0)
        self.assertIn('"revise": true', step)
        self.assertIn("revision.md", step)
        self.assertIn("--draft", step)
        self.assertIn("co floor", step)

    def test_the_frame_and_the_templates_name_one_model(self):
        # The frame is model-specific by design; a rename that misses a template would send
        # drafters a frame for one model while telling them to write for another.
        frame = Path(__file__).resolve().parents[1] / co.FRAME
        self.assertTrue(frame.is_file(), co.FRAME)
        self.assertIn(co.MODEL, frame.read_text(encoding="utf-8"))
        self.assertEqual(set(re.findall(r"frame[-\w.]*\.md", self.TEXT)), {co.FRAME})
        # Drafter, Plain drafter and Judge each tell the reader who the prompt is for.
        blocks = dict(re.findall(r"(?ms)^### ([^\n]+)\n\n```\n(.*?)\n```", self.TEXT))
        for name in ("Drafter", "Plain drafter", "Judge"):
            self.assertIn(co.MODEL, blocks[name], name)

    def test_the_run_passes_every_flag_the_script_needs(self):
        # objections only restamps and enforces seated candidates when it is given --roll,
        # and floor only waives the idea's own words with --idea. Both are the run's job.
        needs = {"floor": ("--roll", "--idea"), "objections": ("--roll",), "pick": ("--roll",)}
        calls = [
            ln for blk in self.BASH for ln in blk.splitlines()
            if re.search(r"\bco (floor|objections|pick)\b", ln)
        ]
        self.assertEqual(len(calls), 4, calls)
        for ln in calls:
            sub = re.search(r"\bco (floor|objections|pick)\b", ln).group(1)
            for flag in needs[sub]:
                with self.subTest(call=sub, flag=flag):
                    self.assertIn(flag, ln)

    def test_every_subcommand_the_run_calls_exists(self):
        used = {m for blk in self.BASH for m in re.findall(r"(?m)\bco ([a-z]+)\b", blk)}
        self.assertTrue(used)
        self.assertEqual(used - set(co.SUBCOMMANDS), set())

    def test_named_templates_use_only_the_supplied_editorial_lens(self):
        blocks = dict(re.findall(r"(?ms)^### ([^\n]+)\n\n```\n(.*?)\n```", self.TEXT))
        for name in ("Drafter", "Examiner", "Reviser"):
            with self.subTest(template=name):
                self.assertIn(
                    "Apply the {{NAME}} editorial lens using only the supplied lens text.",
                    blocks[name],
                )
                self.assertIn(
                    "The name labels the seat; do not imitate, quote, or infer beliefs from it.",
                    blocks[name],
                )
                self.assertIn("{{CREED}}", blocks[name])
                self.assertIn("{{CATCH}}", blocks[name])

    def test_custom_wildcard_uses_a_fixed_neutral_lens(self):
        self.assertIn(
            'fixed neutral fallback creed: "Challenge the draft from a neutral outsider '
            'perspective. Expose unstated assumptions, high-stakes failure modes, and unclear '
            'success criteria."',
            self.TEXT,
        )
        self.assertIn(
            'fixed fallback catch: "A claim that depends on hidden context or a failure mode '
            'the prompt never makes testable."',
            self.TEXT,
        )
        self.assertIn(
            "The custom name is only a seat label and supplies no beliefs, style, or quotations",
            self.TEXT,
        )

    def test_public_docs_describe_normalized_idea_storage(self):
        root = Path(__file__).resolve().parents[1]
        docs = {
            name: (root / name).read_text(encoding="utf-8")
            for name in ("README.md", "SKILL.md", "SPEC.md")
        }
        for name, text in docs.items():
            with self.subTest(document=name):
                self.assertNotIn("character-for-character", text)
                self.assertIn("surrounding whitespace", text)
                self.assertIn("trailing newline", text)


class TestReadme(unittest.TestCase):
    TEXT = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    BLOCK_RE = re.compile(
        r"(?m)^### ([^\n]+)\n\n- \*\*Creed\.\*\* ([^\n]+)\n"
        r"- \*\*Catches\.\*\* ([^\n]+)\n- \*\*Bans\.\*\* ([^\n]+)"
    )

    def test_readme_roster_matches_seats_tsv(self):
        # The roster is stated in three files. This one keeps the profiles honest, so a
        # banned word cannot be swapped in seats.tsv and left standing in the README.
        blocks = self.BLOCK_RE.findall(self.TEXT)
        rows = [r for r in SEATS if r["kind"] != "bench"]
        self.assertEqual([b[0].replace(", the wild card", "") for b in blocks],
                         [r["name"] for r in rows])
        for (name, creed, catch, bans), row in zip(blocks, rows):
            with self.subTest(seat=row["name"]):
                self.assertEqual(creed, row["creed"])
                self.assertEqual(catch, row["catch"])
                self.assertEqual(bans, ", ".join(row["residue"].split("|")))

    LINE_RE = re.compile(
        r"(?m)^### ([^\n]+)\n\n- \*\*Creed\.\*\* [^\n]+\n- \*\*Catches\.\*\* [^\n]+\n"
        r"- \*\*Bans\.\*\* [^\n]+\n- \*\*Line\.\*\* ([^\n]+)"
    )

    def test_every_seat_carries_a_sourced_line(self):
        # The quotation table was folded into the profiles. Every rolled seat's block ends
        # with a Line bullet, and the bench table lists the six bench seats in roster order,
        # so the complete roster still carries a sourced line.
        rolled = self.LINE_RE.findall(self.TEXT)
        self.assertEqual([b[0].replace(", the wild card", "") for b in rolled],
                         [r["name"] for r in SEATS if r["kind"] != "bench"])
        for name, line in rolled:
            with self.subTest(seat=name):
                self.assertIn("](http", line)
        self.assertNotIn("## Lines behind the lenses", self.TEXT)
        bench = self.TEXT.split("### The bench", 1)[1].split("\n## ", 1)[0]
        names = [
            line.split("|")[1].strip()
            for line in bench.splitlines()
            if line.startswith("| ") and not line.startswith("| Seat ")
        ]
        self.assertEqual(names, [r["name"] for r in SEATS if r["kind"] == "bench"])
        for row, line in zip(names, [ln for ln in bench.splitlines() if ln.startswith("| ") and not ln.startswith("| Seat ")]):
            with self.subTest(seat=row):
                self.assertIn("](http", line)

    def test_local_platform_claim_is_limited_to_the_validation_suite(self):
        self.assertIn("The validation suite has been tested locally", self.TEXT)
        self.assertNotIn("The project has been tested locally", self.TEXT)


class TestSpec(unittest.TestCase):
    def test_spec_roster_matches_seats_tsv(self):
        # Keep the ordered public table's operational fields equal to the roster of record.
        spec = (Path(__file__).resolve().parents[1] / "SPEC.md").read_text(encoding="utf-8")
        rows = re.findall(
            r"(?m)^\| ([^|]+?) \| (regular|bench|wild(?: card)?) \| "
            r"([^|]+?) \| ([^|]+?) \|$",
            spec,
        )
        actual = [
            (name, "wild" if kind == "wild card" else kind, creed, catch)
            for name, kind, creed, catch in rows
        ]
        expected = [(r["name"], r["kind"], r["creed"], r["catch"]) for r in SEATS]
        self.assertEqual(actual, expected)

    def test_spec_records_the_standalone_objection_fixture_result(self):
        spec = (Path(__file__).resolve().parents[1] / "SPEC.md").read_text(encoding="utf-8")
        self.assertIn("12 received, 12 valid, and 0 dropped", spec)


class TestCli(unittest.TestCase):
    def assert_json_error(self, argv):
        result = subprocess.run(
            [sys.executable, "-B", str(co.HERE / "council.py")] + argv,
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 3, result.stderr or result.stdout)
        out = json.loads(result.stdout)  # Extra JSON or prose also fails this assertion.
        self.assertIsInstance(out, dict)
        self.assertTrue(out["error"])
        self.assertEqual(result.stderr, "")

    def test_direct_parse_errors_are_one_json_object(self):
        cases = (
            ["nope"], ["--unknown"],
            ["pointer", "extra"], ["pointer", "--unknown"],
            ["roll", "--unknown"], ["roll", "--no-w"],
            ["roll", "--seed", "nope"], ["roll", "--no-wild=false"],
            ["roll", "--seats", "Nobody,Mark Twain,Oliver Sacks"],
            ["floor"], ["floor", "draft.md"], ["floor", "--unknown"],
            ["floor", "--roll", "roll.json"],
            ["objections"], ["objections", "--unknown"],
            ["pick"], ["pick", "verdict.md", "drafts"],
            ["pick", "verdict.md", "--out", "winner.md"],
            ["pick", "--unknown"],
        )
        for argv in cases:
            with self.subTest(argv=argv):
                self.assert_json_error(argv)

    def test_direct_value_flags_reject_missing_empty_and_next_flag_values(self):
        cases = (
            (["roll"], "--seed"), (["roll"], "--seats"), (["roll"], "--wild"),
            (["floor", "draft.md"], "--roll"),
            (["floor", "draft.md", "--roll", "roll.json"], "--idea"),
            (["objections", "objections"], "--roll"),
            (["pick", "verdict.md", "drafts"], "--out"),
            (["pick", "verdict.md", "drafts", "--out", "winner.md"], "--roll"),
            (["pick", "verdict.md", "drafts", "--out", "winner.md"], "--draft"),
            (["pick", "verdict.md", "drafts", "--out", "winner.md"], "--idea"),
        )
        for prefix, flag in cases:
            for suffix in ([], [""], [" \t "], ["--unknown"], ["--roll"], ["--"]):
                with self.subTest(prefix=prefix, flag=flag, suffix=suffix):
                    self.assert_json_error(prefix + [flag] + suffix)
            with self.subTest(prefix=prefix, flag=flag, value="attached empty"):
                self.assert_json_error(prefix + [flag + "="])
        for value in (",,,", " , \t, "):
            with self.subTest(seats=value):
                self.assert_json_error(["roll", "--seats", value])

    def test_help_is_successful(self):
        for argv in ([], ["--help"], ["-h"], ["pointer", "--help"], ["roll", "--help"],
                     ["floor", "--help"], ["objections", "--help"], ["pick", "--help"]):
            with self.subTest(argv=argv):
                result = subprocess.run(
                    [sys.executable, "-B", str(co.HERE / "council.py")] + argv,
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn("usage:", result.stdout.lower())
                self.assertEqual(result.stderr, "")

    def test_empty_paths_cannot_bypass_checks_or_write_a_winner(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = draft(root, "plain", CLEAN)
            roll = root / "roll.json"
            roll.write_text(json.dumps(co.roll(7)), encoding="utf-8")
            verdict = root / "verdict.md"
            verdict.write_text("WINNER: plain\n", encoding="utf-8")
            out = root / "winner.md"
            floor = ["floor", str(prompt), "--roll", str(roll)]
            pick = ["pick", str(verdict), tmp, "--out", str(out)]
            for empty in ("", " \t "):
                cases = (
                    ["floor", empty, "--roll", str(roll)],
                    ["floor", str(prompt), "--roll", empty],
                    floor + ["--idea", empty],
                    ["objections", empty], ["objections", tmp, "--roll", empty],
                    ["pick", str(verdict), empty, "--out", str(out), "--draft", str(prompt)],
                    pick + ["--roll", empty], pick + ["--draft", empty],
                )
                for argv in cases:
                    with self.subTest(argv=argv):
                        self.assert_json_error(argv)
                        self.assertFalse(out.exists())

    def test_pick_floor_failure_matches_floor_cli_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            drafts, selected, roll, verdict, out = pick_case(
                tmp, "<prompt>Work step by step.</prompt>"
            )
            command = [sys.executable, "-B", str(co.HERE / "council.py")]

            floor_result = subprocess.run(
                command + ["floor", str(selected), "--roll", str(roll)],
                capture_output=True, text=True, check=False,
            )
            pick_result = subprocess.run(
                command + ["pick", str(verdict), str(drafts), "--roll", str(roll),
                           "--out", str(out)],
                capture_output=True, text=True, check=False,
            )

            self.assertEqual(floor_result.returncode, 2)
            self.assertEqual(pick_result.returncode, 2)
            self.assertEqual(json.loads(pick_result.stdout), json.loads(floor_result.stdout))
            self.assertEqual(floor_result.stderr, "")
            self.assertEqual(pick_result.stderr, "")
            self.assertFalse(out.exists())

    def test_pick_idea_controls_the_final_floor(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prompt = CLEAN.replace("config.yaml", "serengeti.yaml")
            drafts, _, roll, verdict, out = pick_case(
                root,
                prompt,
                {"seats": [], "critics": [], "graft": {"residue": "serengeti"}},
            )
            idea = root / "idea.md"
            idea.write_text("Read the serengeti telemetry configuration.\n", encoding="utf-8")
            command = [sys.executable, "-B", str(co.HERE / "council.py"), "pick",
                       str(verdict), str(drafts), "--roll", str(roll)]

            self.assert_json_error(
                command[3:] + ["--idea", str(root / "missing.md"), "--out", str(out)]
            )
            self.assertFalse(out.exists())

            blocked = subprocess.run(
                command + ["--out", str(out)],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(blocked.returncode, 2)
            self.assertIn("L6", [f["rule"] for f in json.loads(blocked.stdout)["findings"]])
            self.assertFalse(out.exists())

            result = subprocess.run(
                command + ["--idea", str(idea), "--out", str(out)],
                capture_output=True, text=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertEqual(json.loads(result.stdout)["winner"], "plain")
            self.assertEqual(out.read_text(encoding="utf-8"), co.prompt_of(prompt))
            self.assertEqual(result.stderr, "")

    def test_direct_values_preserve_supported_forms(self):
        for argv, wild in ((["--wild=--revise"], "--revise"),
                           (["--wild", "Oscar Wilde"], "Oscar Wilde")):
            with self.subTest(argv=argv):
                with contextlib.redirect_stdout(io.StringIO()) as buf:
                    self.assertEqual(co.main(["roll", "--seed", "-7"] + argv), 0)
                result = json.loads(buf.getvalue())
                self.assertEqual(result["seed"], -7)
                self.assertEqual(result["seats"][-1]["name"], wild)

    def test_direct_paths_preserve_characters_and_bare_separator(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            name = '-draft\'s "name".md'
            (root / name).write_text(CLEAN, encoding="utf-8")
            (root / "-roll.json").write_text(json.dumps(co.roll(7)), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, "-B", str(co.HERE / "council.py"), "floor",
                 "--roll=-roll.json", "--", name],
                cwd=tmp, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertTrue(json.loads(result.stdout)["ok"])
            self.assertEqual(json.loads(result.stdout)["file"], name)
            self.assertEqual(result.stderr, "")

    def test_objections_cli_drops_an_unseated_single_file(self):
        roll = co.roll(1, seats=["Junot Díaz", "Cormac McCarthy", "Oliver Sacks"])
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            roll_path = root / "roll.json"
            roll_path.write_text(json.dumps(roll), encoding="utf-8")
            objection_path = root / "stranger.md"
            objection_path.write_text(
                TestObjections.OBJ % ("junot-diaz", "Junot Díaz", "cormac-mccarthy"),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, "-B", str(co.HERE / "council.py"), "objections",
                 str(objection_path), "--roll", str(roll_path)],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertEqual(result.stderr, "")
        out = json.loads(result.stdout)
        self.assertEqual(out["received"], 1)
        self.assertEqual(out["valid"], [])
        self.assertEqual(
            out["dropped"],
            [{
                "index": 0,
                "reason": "objection file 'stranger.md' does not belong to a seated writer",
            }],
        )

    def test_roll_cli_prints_json(self):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = co.main(["roll", "--seed", "4127"])
        self.assertEqual(code, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["seed"], 4127)
        self.assertEqual(len(out["seats"]), 4)

    def test_unknown_subcommand_exits_three(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(co.main(["nope"]), 3)

    def test_slug(self):
        self.assertEqual(co.slug("David Foster Wallace"), "david-foster-wallace")
        self.assertEqual(co.slug("G.K. Chesterton"), "g-k-chesterton")

    def test_slug_folds_accents_so_a_name_has_one_filename(self):
        self.assertEqual(co.slug("Junot Díaz"), "junot-diaz")
        self.assertEqual(co.slug("Junot Diaz"), co.slug("Junot Díaz"))
        self.assertEqual(co.slug("Cunégonde"), "cunegonde")


if __name__ == "__main__":
    unittest.main()


class TestFastRun(unittest.TestCase):
    STAMP = "20260101-000000"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name) / "council"

    def go(self, raw):
        return co.init(raw, home=self.home, stamp=self.STAMP, cwd="/tmp/somewhere")

    def test_fast_seats_two_regulars_and_the_wild_chair(self):
        r = self.go("--fast --seed 11 tighten the support bot prompt")
        self.assertTrue(r["fast"])
        self.assertEqual([s["kind"] for s in r["seats"]], ["regular", "regular", "wild"])
        self.assertEqual(r["seats"][-1]["name"], "Werner Herzog")
        roll = json.loads((Path(r["run"]) / "roll.json").read_text(encoding="utf-8"))
        self.assertTrue(roll["fast"])
        self.assertEqual(len(roll["seats"]), 3)
        # The same seed rolls the same two seats: a fast run is as replayable as a full one.
        self.assertEqual(co.roll(11, fast=True)["seats"], roll["seats"])

    def test_full_runs_default_to_three_regulars_and_report_fast_off(self):
        r = self.go("--seed 11 tighten the support bot prompt")
        self.assertFalse(r["fast"])
        self.assertEqual([s["kind"] for s in r["seats"]], ["regular"] * 3 + ["wild"])
        self.assertFalse(co.roll(11)["fast"])

    def test_fast_seats_take_two_names(self):
        r = self.go('--fast --seats "Mark Twain,Franz Kafka" write a release note')
        self.assertEqual([s["name"] for s in r["seats"]],
                         ["Mark Twain", "Franz Kafka", "Werner Herzog"])
        with self.assertRaisesRegex(ValueError, "--seats needs exactly 2 names"):
            self.go('--fast --seats "Mark Twain,Franz Kafka,Oliver Sacks" write a release note')
        with self.assertRaisesRegex(ValueError, "--seats needs exactly 3 names"):
            self.go('--seats "Mark Twain,Franz Kafka" write a release note')

    def test_fast_refuses_revise_and_creates_no_run(self):
        for raw in ("--fast --revise write a release note", "--revise --fast write a release note"):
            with self.subTest(raw=raw):
                with self.assertRaisesRegex(ValueError, "--revise needs the objections"):
                    self.go(raw)
        self.assertFalse((self.home / "runs").exists())

    def test_roll_subcommand_takes_fast(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            code = co.main(["roll", "--seed", "11", "--fast"])
        self.assertEqual(code, 0)
        r = json.loads(out.getvalue())
        self.assertTrue(r["fast"])
        self.assertEqual(len(r["seats"]), 3)

    def test_the_skill_describes_the_fast_run(self):
        root = Path(__file__).resolve().parents[1]
        skill = (root / "SKILL.md").read_text(encoding="utf-8")
        blocks = dict(re.findall(r"(?ms)^### ([^\n]+)\n\n```\n(.*?)\n```", skill))
        fast = blocks["Fast drafter"]
        self.assertIn("do not imitate, quote, or infer beliefs from it", fast)
        for slot in ("{{IDEA}}", "{{FRAME}}", "{{NAME}}", "{{CREED}}", "{{CATCH}}", "{{OUT}}"):
            self.assertIn(slot, fast)
        self.assertIn(co.MODEL, fast)
        step1 = re.search(r"(?s)## 1\..*?\n## 2\.", skill).group(0)
        self.assertIn('"fast": true', step1)
        self.assertIn("Fast drafter", step1)
        step3 = re.search(r"(?s)## 3\..*?\n## 4\.", skill).group(0)
        self.assertIn('"fast": true', step3)
        for name in ("README.md", "SKILL.md", "SPEC.md"):
            with self.subTest(document=name):
                self.assertIn("--fast", (root / name).read_text(encoding="utf-8"))
