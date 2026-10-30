// snapshot.zig - Hybrid Python -> Zig continuation contract.
//
// MBS1 binary layout, little-endian:
//   magic "MBS1"; u32 tape_len; u32 a; u32 c; u32 d; u8 halted;
//   tape_len * u16 tape cells.
// Python owns search and snapshot production. Zig validates this bounded state,
// appends normalized suffix opcodes at tape_len, and canonically executes it.

const std = @import("std");
const engine = @import("engine.zig");

const MAGIC = "MBS1";
const HEADER_LEN = 4 + 4 + 4 + 4 + 4 + 1;

pub const Status = enum { halted, program_end, max_steps };

pub const Result = struct {
    output: []u8,
    status: Status,
    steps: u64,
    a: u16,
    c: u16,
    d: u16,
};

const Snapshot = struct {
    tape: []const u16,
    a: u16,
    c: u16,
    d: u16,
};

fn readU32(data: []const u8, pos: *usize) !u32 {
    if (pos.* + 4 > data.len) return error.TruncatedSnapshot;
    const value = std.mem.readInt(u32, data[pos.*..][0..4], .little);
    pos.* += 4;
    return value;
}

fn readU16(data: []const u8, pos: *usize) !u16 {
    if (pos.* + 2 > data.len) return error.TruncatedSnapshot;
    const value = std.mem.readInt(u16, data[pos.*..][0..2], .little);
    pos.* += 2;
    return value;
}

fn decode(data: []const u8, allocator: std.mem.Allocator) !Snapshot {
    if (data.len < HEADER_LEN or !std.mem.eql(u8, data[0..4], MAGIC)) return error.InvalidSnapshot;
    var pos: usize = 4;
    const tape_len: usize = @intCast(try readU32(data, &pos));
    const a_raw = try readU32(data, &pos);
    const c_raw = try readU32(data, &pos);
    const d_raw = try readU32(data, &pos);
    if (pos >= data.len) return error.TruncatedSnapshot;
    _ = data[pos]; // Python records halted; resume intentionally clears it.
    pos += 1;

    if (tape_len == 0 or tape_len > engine.MEM_SIZE or
        a_raw >= engine.MEM_SIZE or c_raw >= engine.MEM_SIZE or d_raw >= engine.MEM_SIZE)
    {
        return error.InvalidSnapshot;
    }
    if (data.len != pos + tape_len * 2) return error.InvalidSnapshot;

    const tape = try allocator.alloc(u16, tape_len);
    for (tape) |*cell| {
        cell.* = try readU16(data, &pos);
        if (cell.* >= engine.MEM_SIZE) return error.InvalidSnapshot;
    }
    return .{ .tape = tape, .a = @intCast(a_raw), .c = @intCast(c_raw), .d = @intCast(d_raw) };
}

fn opcodeValue(opcode: u8) !u16 {
    return switch (opcode) {
        'i' => engine.OP_CHASE,
        '<' => engine.OP_OUT,
        '/' => engine.OP_IN,
        '*' => engine.OP_ROT,
        'j' => engine.OP_MOVD,
        'p' => engine.OP_CRAZY,
        'o' => engine.OP_NOP,
        'v' => engine.OP_HALT,
        else => error.InvalidOpcode,
    };
}

fn sourceForOpcode(opcode: u8, position: usize) !u16 {
    const value = try opcodeValue(opcode);
    return @intCast(33 + @mod(@as(i64, value) - @as(i64, @intCast(position)) - 33, 94));
}

fn ensureFilled(mem: *[engine.MEM_SIZE]u16, filled_until: *usize, address: usize) !void {
    if (address >= engine.MEM_SIZE) return error.MemoryLimit;
    while (filled_until.* <= address) : (filled_until.* += 1) {
        if (filled_until.* < 2) return error.InvalidSnapshot;
        mem[filled_until.*] = engine.crazyOp(mem[filled_until.* - 1], mem[filled_until.* - 2]);
    }
}

fn resumeSnapshot(snapshot: Snapshot, suffix: []const u8, max_steps: u64, allocator: std.mem.Allocator) !Result {
    const program_len = snapshot.tape.len + suffix.len;
    if (program_len > engine.MEM_SIZE or max_steps == 0) return error.InvalidArgument;

    var mem: [engine.MEM_SIZE]u16 = undefined;
    @memcpy(mem[0..snapshot.tape.len], snapshot.tape);
    for (suffix, 0..) |opcode, i| {
        mem[snapshot.tape.len + i] = try sourceForOpcode(opcode, snapshot.tape.len + i);
    }

    var output = std.ArrayList(u8).empty;
    errdefer output.deinit(allocator);
    var a = snapshot.a;
    var c = snapshot.c;
    var d = snapshot.d;
    var filled_until = program_len;
    var steps: u64 = 0;

    while (steps < max_steps) {
        if (c >= program_len) return .{
            .output = try output.toOwnedSlice(allocator),
            .status = .program_end,
            .steps = steps,
            .a = a,
            .c = c,
            .d = d,
        };
        try ensureFilled(&mem, &filled_until, c);
        try ensureFilled(&mem, &filled_until, d);
        steps += 1;

        const op = engine.decodeOpcode(mem[c], c);
        switch (op) {
            engine.OP_CHASE => c = mem[d],
            engine.OP_OUT => try output.append(allocator, @intCast(a % 256)),
            engine.OP_IN => return error.InputUnsupported,
            engine.OP_ROT => {
                const value = mem[d];
                mem[d] = (value / 3) + (value % 3) * 19683;
                a = mem[d];
            },
            engine.OP_MOVD => d = mem[d],
            engine.OP_CRAZY => {
                mem[d] = engine.crazyOp(a, mem[d]);
                a = mem[d];
            },
            engine.OP_HALT => return .{
                .output = try output.toOwnedSlice(allocator),
                .status = .halted,
                .steps = steps,
                .a = a,
                .c = c,
                .d = d,
            },
            else => {},
        }
        if (mem[c] >= engine.LO and mem[c] <= engine.HI) mem[c] = engine.ENCRYPT_TABLE[mem[c] - engine.LO];
        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
    }
    return .{ .output = try output.toOwnedSlice(allocator), .status = .max_steps, .steps = steps, .a = a, .c = c, .d = d };
}

pub fn runFile(io: std.Io, path: []const u8, suffix: []const u8, max_steps: u64, allocator: std.mem.Allocator) !Result {
    const data = try std.Io.Dir.cwd().readFileAlloc(io, path, allocator, .unlimited);
    defer allocator.free(data);
    const snapshot = try decode(data, allocator);
    return resumeSnapshot(snapshot, suffix, max_steps, allocator);
}

test "source opcode encoding is position-correct" {
    const cell = try sourceForOpcode('v', 0);
    try std.testing.expectEqual(engine.OP_HALT, engine.decodeOpcode(cell, 0));
}

test "decode rejects unknown magic" {
    const data = "XXXX";
    try std.testing.expectError(error.InvalidSnapshot, decode(data, std.testing.allocator));
}

test "decode rejects truncated header" {
    const data = "MBS1";
    try std.testing.expectError(error.InvalidSnapshot, decode(data, std.testing.allocator));
}

test "decode rejects too-short tape payload" {
    const data = [_]u8{ 'M', 'B', 'S', '1', 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0 };
    try std.testing.expectError(error.InvalidSnapshot, decode(&data, std.testing.allocator));
}

test "snapshot resume of abc fixture emits ABC" {
    const mbs = @embedFile("testdata/abc.mbs");
    const suffix = @embedFile("testdata/abc.suffix");
    const snap = try decode(mbs, std.testing.allocator);
    defer std.testing.allocator.free(snap.tape);

    var output = std.ArrayList(u8).empty;
    defer output.deinit(std.testing.allocator);
    const result = try resumeSnapshot(snap, suffix, 1_000_000, std.testing.allocator);
    defer std.testing.allocator.free(result.output);

    try std.testing.expectEqual(Status.halted, result.status);
    try std.testing.expectEqualStrings("ABC", result.output);
}

test "snapshot resume of hello fixture emits Hello" {
    const mbs = @embedFile("testdata/hello.mbs");
    const suffix = @embedFile("testdata/hello.suffix");
    const snap = try decode(mbs, std.testing.allocator);
    defer std.testing.allocator.free(snap.tape);

    const result = try resumeSnapshot(snap, suffix, 1_000_000, std.testing.allocator);
    defer std.testing.allocator.free(result.output);

    try std.testing.expectEqual(Status.halted, result.status);
    try std.testing.expectEqualStrings("Hello", result.output);
}
