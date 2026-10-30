// bf_interpreter.zig — Brainfuck interpreter in Zig (for TC test)
const std = @import("std");

pub const TapeSize = 30_000;
pub const MaxSteps = 10_000_000;

pub fn run(source: []const u8, input: []const u8, allocator: std.mem.Allocator) ![]u8 {
    var tape: [TapeSize]u8 = undefined;
    @memset(tape[0..], 0);
    var ptr: usize = 0;
    var pc: usize = 0;
    var input_ptr: usize = 0;
    var output = std.array_list.Managed(u8).init(allocator);
    errdefer output.deinit();

    // Precompute bracket matching
    var bracket_map = std.AutoHashMap(usize, usize).init(allocator);
    errdefer bracket_map.deinit();

    var stack = std.array_list.Managed(usize).init(allocator);
    errdefer stack.deinit();

    for (source, 0..) |ch, i| {
        switch (ch) {
            '[' => try stack.append(i),
            ']' => {
                const match = stack.pop() orelse return error.UnmatchedBracket;
                try bracket_map.put(i, match);
                try bracket_map.put(match, i);
            },
            else => {},
        }
    }
    if (stack.items.len > 0) return error.UnmatchedBracket;

    var steps: u64 = 0;
    while (pc < source.len) {
        steps += 1;
        if (steps > MaxSteps) return error.MaxStepsExceeded;

        switch (source[pc]) {
            '>' => ptr += 1,
            '<' => ptr -= 1,
            '+' => tape[ptr] += 1,
            '-' => tape[ptr] -= 1,
            '.' => try output.append(tape[ptr]),
            ',' => {
                tape[ptr] = if (input_ptr < input.len) input[input_ptr] else 0;
                input_ptr += 1;
            },
            '[' => {
                if (tape[ptr] == 0) {
                    pc = bracket_map.get(pc).?;
                }
            },
            ']' => {
                if (tape[ptr] != 0) {
                    pc = bracket_map.get(pc).?;
                }
            },
            else => {}, // ignore comments
        }
        pc += 1;
    }

    return try output.toOwnedSlice();
}

pub const Error = error{
    UnmatchedBracket,
    MaxStepsExceeded,
};