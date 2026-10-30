from direct_encoder19 import assemble19, decode19

ops = [23, 5, 81]
program = assemble19(ops)
print(f"ops={ops}")
print(f"program={program!r}")
for c, (op, char) in enumerate(zip(ops, program)):
    decoded = decode19(char, c)
    print(f"c={c} desired={op} source={char!r} ascii={ord(char)} decoded={decoded}")
print(f"decoded_ops={[decode19(char, c) for c, char in enumerate(program)]}")
print("DIRECT_OPCODE_ENCODING=PASS")
