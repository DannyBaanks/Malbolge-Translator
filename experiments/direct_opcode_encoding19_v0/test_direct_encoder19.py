import random
import unittest

from direct_encoder19 import (
    END, OFFSETS, THIRD, VALID_OPCODES, assemble19, decode19,
    disassemble19, encode19, offset,
)


class DirectEncoder19Tests(unittest.TestCase):
    def test_exact_offsets(self):
        self.assertEqual(OFFSETS, (0, 117, 140))

    def test_required_minimum_program(self):
        ops = [23, 5, 81]
        program = assemble19(ops)
        self.assertEqual(program, "ubO")
        self.assertEqual(disassemble19(program), ops)

    def test_all_opcodes_at_region_boundaries(self):
        positions = (0, 1, 32, 33, 93, 94, THIRD - 1, THIRD,
                     THIRD + 1, 2 * THIRD - 1, 2 * THIRD, END - 1)
        for c in positions:
            for op in VALID_OPCODES:
                char = encode19(op, c)
                self.assertTrue(33 <= ord(char) <= 126)
                self.assertEqual(decode19(char, c), op)

    def test_seeded_position_sample(self):
        rng = random.Random(190094)
        for _ in range(10_000):
            c = rng.randrange(END)
            for op in VALID_OPCODES:
                char = encode19(op, c)
                self.assertTrue(33 <= ord(char) <= 126)
                self.assertEqual(decode19(char, c), op)

    def test_start_c(self):
        ops = [23, 5, 81]
        for start in (17, THIRD - 1, THIRD, 2 * THIRD, END - len(ops)):
            source = assemble19(ops, start)
            self.assertEqual(disassemble19(source, start), ops)

    def test_rejects_invalid_domains(self):
        with self.assertRaises(ValueError): encode19(0, 0)
        with self.assertRaises(ValueError): encode19(23, -1)
        with self.assertRaises(ValueError): encode19(23, END)
        with self.assertRaises(ValueError): decode19(" ", 0)
        with self.assertRaises(ValueError): assemble19([23, 5], END - 1)


if __name__ == "__main__":
    unittest.main()
