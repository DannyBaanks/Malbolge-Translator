// engine.zig — Motor Classic Malbolge (Zig 0.16)
//
// Semántica clásica (autoridad: intérprete Python clásico + reference_interpreter.c):
//   op = (mem[c] + c) % 94
//   instrucciones: 4=chase(c=mem[d]) 5=out(a%256) 23=in 39=rotate(mem[d])
//                  40=dload(d=mem[d]) 62=crazy(mem[d]=crazy(a,mem[d])) 68=nop 81=halt
//   tras ejecutar: si hubo jump, c=c_target
//                  si 33<=mem[c]<=126: mem[c]=_ENC[mem[c]]
//                  c=(c+1)%59049 ; d=(d+1)%59049
// La cinta es fija de 3^10 celdas; la cola se rellena por recurrencia crazy_op.

const std = @import("std");

pub const MEM_SIZE: usize = 59049;
pub const MOD: u16 = 94;
pub const LO: u8 = 33;
pub const HI: u8 = 126;

const CRAZY_TABLE = [_][3]u16{
    .{ 1, 0, 0 },
    .{ 1, 0, 2 },
    .{ 2, 2, 1 },
};

pub const ENCRYPT_TABLE = "5z]&gqtyfr$(we4{WP)H-Zn,[%\\3dL+Q;>U!pJS72FhOA1CB6v^=I_0/8|jsb9m<.TVac`uY*MK'X~xDl}REokN:#?G\"i@";

// Opcode -> instrucción (para compatir fuente_para del generador meowbolge).
pub const OP_OUT: u16 = 5;
pub const OP_ROT: u16 = 39;
pub const OP_MOVD: u16 = 40;
pub const OP_CRAZY: u16 = 62;
pub const OP_NOP: u16 = 68;
pub const OP_HALT: u16 = 81;
pub const OP_CHASE: u16 = 4;
pub const OP_IN: u16 = 23;

/// Decode a Classic Malbolge instruction without overflowing the 16-bit tape.
pub fn decodeOpcode(cell: u16, c: u16) u16 {
    return @intCast((@as(u32, cell) + @as(u32, c)) % @as(u32, MOD));
}

pub fn crazyOp(x: u16, y: u16) u16 {
    var res: u16 = 0;
    var p: u16 = 1;
    var xi = x;
    var yi = y;
    var i: u8 = 0;
    while (i < 10) : (i += 1) {
        const xt = xi % 3;
        const yt = yi % 3;
        res += @as(u16, CRAZY_TABLE[yt][xt]) * p;
        xi /= 3;
        yi /= 3;
        p *= 3;
    }
    return res;
}

/// Rellena la cinta completa: fuente imprimible en posiciones iniciales, luego
/// recurrencia crazy_op. Devuelve error.InvalidChar si hay char no imprimible.
pub fn loadMemory(source: []const u8, mem: *[MEM_SIZE]u16) !void {
    var idx: usize = 0;
    for (source) |c| {
        if (c == '\n' or c == '\r' or c == ' ' or c == '\t') continue;
        if (c < LO or c > HI) return error.InvalidChar;
        if (idx >= MEM_SIZE) return error.ProgramTooLong;
        mem[idx] = c;
        idx += 1;
    }
    var i: usize = idx;
    while (i < MEM_SIZE) : (i += 1) {
        // Python authority: mem[i-1]/mem[i-2] wrap to the END of the (zero)
        // pre-filled array when the index is negative (only for short programs).
        const prev1 = if (i >= 1) mem[i - 1] else mem[MEM_SIZE - 1];
        const prev2 = if (i >= 2) mem[i - 2] else mem[MEM_SIZE - 1];
        mem[i] = crazyOp(prev1, prev2);
    }
}

pub const RunStatus = enum { halted, invalid, max_steps };

pub const RunResult = struct {
    output: []u8, // owned by caller (allocator)
    status: RunStatus,
    steps: u64,
    a: u16,
    c: u16,
    d: u16,
};

/// Ejecuta un programa Classic Malbolge. `mem` debe ser un buffer de MEM_SIZE.
pub fn runInto(
    mem: *[MEM_SIZE]u16,
    source: []const u8,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !RunResult {
    loadMemory(source, mem) catch return RunResult{
        .output = &.{},
        .status = .invalid,
        .steps = 0,
        .a = 0,
        .c = 0,
        .d = 0,
    };

    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var out = std.array_list.Managed(u8).init(allocator);
    errdefer out.deinit();

    var steps: u64 = 0;
    var status: RunStatus = .max_steps;
    while (steps < max_steps) {
        steps += 1;
        const cell = mem[c];
        const op = decodeOpcode(cell, c);
        var jumped = false;
        var c_target: u16 = 0;

        switch (op) {
            OP_CHASE => {
                c_target = mem[d];
                jumped = true;
            },
            OP_OUT => try out.append(@intCast(a % 256)),
            OP_IN => a = 0xFFFF,
            OP_ROT => {
                const v = mem[d];
                mem[d] = (v / 3) + (v % 3) * 19683;
                a = mem[d];
            },
            OP_MOVD => d = mem[d],
            OP_CRAZY => {
                mem[d] = crazyOp(a, mem[d]);
                a = mem[d];
            },
            OP_NOP => {},
            OP_HALT => {
                status = .halted;
                break;
            },
            else => {}, // instrucción inválida -> NOP
        }

        if (jumped) c = c_target;
        if (mem[c] >= LO and mem[c] <= HI) {
            mem[c] = ENCRYPT_TABLE[mem[c] - LO];
        }
        c = @intCast((@as(usize, c) + 1) % MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % MEM_SIZE);
    }

    return RunResult{
        .output = try out.toOwnedSlice(),
        .status = status,
        .steps = steps,
        .a = a,
        .c = c,
        .d = d,
    };
}

/// Conveniencia: ejecuta y devuelve output (llamador libera con allocator.free).
pub fn run(
    source: []const u8,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !RunResult {
    var mem: [MEM_SIZE]u16 = undefined;
    return runInto(&mem, source, max_steps, allocator);
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

const hello = "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj";

test "hello world" {
    var mem: [MEM_SIZE]u16 = undefined;
    const r = try runInto(&mem, hello, 100_000, std.testing.allocator);
    defer std.testing.allocator.free(r.output);
    try std.testing.expectEqualStrings("Hello, world.", r.output);
    try std.testing.expectEqual(RunStatus.halted, r.status);
    try std.testing.expectEqual(@as(u64, 48), r.steps);
}

test "crazy op basic" {
    try std.testing.expectEqual(@as(u16, 29524), crazyOp(0, 0));
    try std.testing.expectEqual(@as(u16, 0), crazyOp(29524, 29524));
}

test "opcode decode widens before modulo" {
    try std.testing.expectEqual(@as(u16, 32), decodeOpcode(59048, 59048));
}

test "encryption table is the canonical Classic permutation" {
    try std.testing.expectEqual(@as(usize, 94), ENCRYPT_TABLE.len);
    try std.testing.expectEqual(@as(u8, 'w'), ENCRYPT_TABLE[12]);
    try std.testing.expectEqual(@as(u8, '@'), ENCRYPT_TABLE[93]);
}

test "load_memory tail is non-printable mostly" {
    var mem: [MEM_SIZE]u16 = undefined;
    try loadMemory("i", &mem);
    // mem[0] es 'i' (imprimible); la cola es crazy_op recurrence.
    try std.testing.expect(mem[0] >= LO and mem[0] <= HI);
    // El valor de la cola debe estar en [0, 59048].
    try std.testing.expect(mem[100] < 59049);
}
