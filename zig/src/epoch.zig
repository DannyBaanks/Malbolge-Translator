// epoch.zig -- Detect repeated post-OUT states in Classic Malbolge.
// A repeated (a,c,d,tape) state with no input means deterministic periodic
// execution. This is the prerequisite signature for a real RLE loop.

const std = @import("std");
const engine = @import("engine.zig");

const Epoch = struct {
    a: u16,
    c: u16,
    d: u16,
    tape_hash: [32]u8,
};

const DeltaCell = struct {
    address: u16,
    before: u16,
    after: u16,
};

pub const Scan = struct {
    status: engine.RunStatus,
    steps: u64,
    output_bytes: usize,
    repeated_epoch: bool,
    min_epoch_tape_delta: ?usize,
    min_delta_cells: [8]DeltaCell,
    min_delta_cell_count: u8,
    min_before_a: u16,
    min_before_c: u16,
    min_before_d: u16,
    min_after_a: u16,
    min_after_c: u16,
    min_after_d: u16,
};

fn tapeHash(mem: *const [engine.MEM_SIZE]u16) [32]u8 {
    var hasher = std.crypto.hash.sha2.Sha256.init(.{});
    for (mem) |value| {
        const bytes = [_]u8{ @intCast(value & 0xff), @intCast(value >> 8) };
        hasher.update(&bytes);
    }
    var result: [32]u8 = undefined;
    hasher.final(&result);
    return result;
}

pub fn scan(source: []const u8, max_steps: u64, allocator: std.mem.Allocator) !Scan {
    var mem: [engine.MEM_SIZE]u16 = undefined;
    engine.loadMemory(source, &mem) catch return .{
        .status = .invalid,
        .steps = 0,
        .output_bytes = 0,
        .repeated_epoch = false,
        .min_epoch_tape_delta = null,
        .min_delta_cells = undefined,
        .min_delta_cell_count = 0,
        .min_before_a = 0,
        .min_before_c = 0,
        .min_before_d = 0,
        .min_after_a = 0,
        .min_after_c = 0,
        .min_after_d = 0,
    };

    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var output_bytes: usize = 0;
    var last_output_tape: [engine.MEM_SIZE]u16 = undefined;
    var have_last_output_tape = false;
    var min_epoch_tape_delta: ?usize = null;
    var min_delta_cells: [8]DeltaCell = undefined;
    var min_delta_cell_count: u8 = 0;
    var last_output_a: u16 = 0;
    var last_output_c: u16 = 0;
    var last_output_d: u16 = 0;
    var min_before_a: u16 = 0;
    var min_before_c: u16 = 0;
    var min_before_d: u16 = 0;
    var min_after_a: u16 = 0;
    var min_after_c: u16 = 0;
    var min_after_d: u16 = 0;
    var seen = std.AutoHashMap(Epoch, void).init(allocator);
    defer seen.deinit();

    var steps: u64 = 0;
    while (steps < max_steps) {
        steps += 1;
        const op = engine.decodeOpcode(mem[c], c);
        var emitted = false;
        var jumped = false;
        var c_target: u16 = 0;

        switch (op) {
            engine.OP_CHASE => {
                c_target = mem[d];
                jumped = true;
            },
            engine.OP_OUT => {
                emitted = true;
                output_bytes += 1;
            },
            engine.OP_IN => a = 0xffff,
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
                .status = .halted,
                .steps = steps,
                .output_bytes = output_bytes,
                .repeated_epoch = false,
                .min_epoch_tape_delta = min_epoch_tape_delta,
                .min_delta_cells = min_delta_cells,
                .min_delta_cell_count = min_delta_cell_count,
                .min_before_a = min_before_a,
                .min_before_c = min_before_c,
                .min_before_d = min_before_d,
                .min_after_a = min_after_a,
                .min_after_c = min_after_c,
                .min_after_d = min_after_d,
            },
            else => {},
        }

        if (jumped) c = c_target;
        if (mem[c] >= engine.LO and mem[c] <= engine.HI) mem[c] = engine.ENCRYPT_TABLE[mem[c] - engine.LO];
        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);

        if (emitted) {
            if (have_last_output_tape) {
                var delta: usize = 0;
                for (mem, 0..) |value, index| {
                    if (value != last_output_tape[index]) delta += 1;
                }
                if (min_epoch_tape_delta == null or delta < min_epoch_tape_delta.?) {
                    min_epoch_tape_delta = delta;
                    min_before_a = last_output_a;
                    min_before_c = last_output_c;
                    min_before_d = last_output_d;
                    min_after_a = a;
                    min_after_c = c;
                    min_after_d = d;
                    min_delta_cell_count = 0;
                    for (mem, 0..) |value, index| {
                        if (value != last_output_tape[index] and min_delta_cell_count < min_delta_cells.len) {
                            min_delta_cells[min_delta_cell_count] = .{
                                .address = @intCast(index),
                                .before = last_output_tape[index],
                                .after = value,
                            };
                            min_delta_cell_count += 1;
                        }
                    }
                }
            }
            last_output_tape = mem;
            have_last_output_tape = true;
            last_output_a = a;
            last_output_c = c;
            last_output_d = d;
            const epoch = Epoch{ .a = a, .c = c, .d = d, .tape_hash = tapeHash(&mem) };
            if (seen.contains(epoch)) return .{
                .status = .max_steps,
                .steps = steps,
                .output_bytes = output_bytes,
                .repeated_epoch = true,
                .min_epoch_tape_delta = min_epoch_tape_delta,
                .min_delta_cells = min_delta_cells,
                .min_delta_cell_count = min_delta_cell_count,
                .min_before_a = min_before_a,
                .min_before_c = min_before_c,
                .min_before_d = min_before_d,
                .min_after_a = min_after_a,
                .min_after_c = min_after_c,
                .min_after_d = min_after_d,
            };
            try seen.put(epoch, {});
        }
    }
    return .{
        .status = .max_steps,
        .steps = steps,
        .output_bytes = output_bytes,
        .repeated_epoch = false,
        .min_epoch_tape_delta = min_epoch_tape_delta,
        .min_delta_cells = min_delta_cells,
        .min_delta_cell_count = min_delta_cell_count,
        .min_before_a = min_before_a,
        .min_before_c = min_before_c,
        .min_before_d = min_before_d,
        .min_after_a = min_after_a,
        .min_after_c = min_after_c,
        .min_after_d = min_after_d,
    };
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();
    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);
    if (args.items.len < 2 or args.items.len > 3) {
        std.debug.print("uso: malbolge-epoch <source.mal> [max_steps]\n", .{});
        return;
    }
    const limit: u64 = if (args.items.len == 3) std.fmt.parseInt(u64, args.items[2], 10) catch 10_000_000 else 10_000_000;
    const source = try std.Io.Dir.cwd().readFileAlloc(init.io, args.items[1], allocator, .unlimited);
    const result = try scan(source, limit, allocator);
    std.debug.print("status={s}\nsteps={d}\noutput_bytes={d}\nrepeated_epoch={any}\nmin_epoch_tape_delta={any}\n", .{
        @tagName(result.status), result.steps, result.output_bytes, result.repeated_epoch, result.min_epoch_tape_delta,
    });
    for (result.min_delta_cells[0..result.min_delta_cell_count]) |cell| {
        std.debug.print("delta_cell addr={d} {d}->{d}\n", .{ cell.address, cell.before, cell.after });
    }
    if (result.min_epoch_tape_delta != null) {
        std.debug.print("epoch_before a={d} c={d} d={d}\n", .{ result.min_before_a, result.min_before_c, result.min_before_d });
        std.debug.print("epoch_after a={d} c={d} d={d}\n", .{ result.min_after_a, result.min_after_c, result.min_after_d });
    }
}

test "hello world has no repeated output epoch" {
    const hello = "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj";
    const result = try scan(hello, 100_000, std.testing.allocator);
    try std.testing.expectEqual(engine.RunStatus.halted, result.status);
    try std.testing.expect(!result.repeated_epoch);
}
