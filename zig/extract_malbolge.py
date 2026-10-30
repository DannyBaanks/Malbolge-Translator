#!/usr/bin/env python3
"""Extract clean Malbolge program for Hello World!"""
import sys
sys.path.insert(0, 'C:/Development/ISyCo Git/Malbolge-Translator/zig')

# Use the generator module via subprocess
import subprocess
result = subprocess.run(
    ['zig', 'run', 'src/t_turing.zig'],
    cwd='C:/Development/ISyCo Git/Malbolge-Translator/zig',
    capture_output=True, text=True, timeout=60
)

# Parse output to extract raw program
output = result.stderr
lines = output.split('\n')
capturing = False
program_lines = []
for line in lines:
    if 'Malbolge program' in line:
        capturing = True
        # Extract after the colon
        parts = line.split(': ', 1)
        if len(parts) > 1:
            program_lines.append(parts[1])
        continue
    if capturing:
        if 'Running generated Malbolge' in line:
            break
        program_lines.append(line)

program = ''.join(program_lines).strip()
print(f"Extracted {len(program)} chars")

# Write clean file
with open('C:/Development/ISyCo Git/malbolge-free/tests/turing_malbolge_hello.mal', 'w') as f:
    f.write(program)
print(f"Written {len(program)} bytes")