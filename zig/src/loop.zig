// loop.zig -- Buscador aleatorio de loops RLE en Classic Malbolge.
//
// Genera programas frescos al azar (semilla fija => reproducible) y busca
// repetidores: rachas largas de un solo byte. Un candidato que pase el umbral
// se confirma con el auditor epochal (estado repetido = ciclo real).
// Veredicto honesto: FOUND con programa testigo, o NOT_FOUND con estadistica.

const std = @import("std");
const engine = @import("engine.zig");
const epoch = @import("epoch.zig");

pub const Run = struct {
    byte: u8,
    len: usize,
};

pub fn longestRun(output: []const u8) Run {
    var best: Run = .{ .byte = 0, .len = 0 };
    var i: usize = 0;
    while (i < output.len) {
        var j = i + 1;
        while (j < output.len and output[j] == output[i]) : (j += 1) {}
        if (j - i > best.len) best = .{ .byte = output[i], .len = j - i };
        i = j;
    }
    return best;
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();
    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);
    if (args.items.len < 6 or args.items.len > 7) {
        std.debug.print("uso: malbolge-loop <seed> <count> <prog_len> <max_steps> <min_run> [found.mal]\n", .{});
        return;
    }
    const seed = std.fmt.parseInt(u64, args.items[1], 10) catch 42;
    const count = std.fmt.parseInt(usize, args.items[2], 10) catch 100000;
    const prog_len = std.fmt.parseInt(usize, args.items[3], 10) catch 120;
    const max_steps = std.fmt.parseInt(u64, args.items[4], 10) catch 3000;
    const min_run = std.fmt.parseInt(usize, args.items[5], 10) catch 16;

    var prng = std.Random.DefaultPrng.init(seed);
    const rng = prng.random();
    const prog = try allocator.alloc(u8, prog_len);
    var best: Run = .{ .byte = 0, .len = 0 };
    var halted_count: usize = 0;

    var n: usize = 0;
    while (n < count) : (n += 1) {
        for (prog) |*cell| cell.* = engine.LO + rng.intRangeLessThan(u8, 0, 94);
        var mem: [engine.MEM_SIZE]u16 = undefined;
        const r = try engine.runInto(&mem, prog, max_steps, allocator);
        defer allocator.free(r.output);
        if (r.status == .halted) halted_count += 1;
        const run = longestRun(r.output);
        if (run.len > best.len) {
            best = run;
            std.debug.print("best run={d} byte=0x{x} n={d}\n", .{ best.len, best.byte, n });
        }
        if (run.len >= min_run) {
            const scan = try epoch.scan(prog, max_steps, allocator);
            if (scan.repeated_epoch) {
                std.debug.print("FOUND run={d} byte=0x{x} n={d} steps={d} status={s}\n", .{
                    run.len, run.byte, n, scan.steps, @tagName(scan.status),
                });
                if (args.items.len == 7) try std.Io.Dir.cwd().writeFile(init.io, .{
                    .sub_path = args.items[6],
                    .data = prog,
                });
                return;
            }
        }
        if ((n + 1) % 10000 == 0) {
            std.debug.print("progress n={d}/{d} best_run={d} halted={d}\n", .{ n + 1, count, best.len, halted_count });
        }
    }
    std.debug.print("NOT_FOUND n={d} best_run={d} best_byte=0x{x} halted={d}\n", .{ count, best.len, best.byte, halted_count });
}

test "longest run basic" {
    const got = longestRun("aaabbbba");
    try std.testing.expectEqual(@as(u8, 'b'), got.byte);
    try std.testing.expectEqual(@as(usize, 4), got.len);
    const empty = longestRun("");
    try std.testing.expectEqual(@as(usize, 0), empty.len);
}
