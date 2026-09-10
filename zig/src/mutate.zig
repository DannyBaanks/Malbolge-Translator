// mutate.zig -- One-cell loop search around a verified Classic seed.
// A candidate is accepted only when the Zig Classic engine emits a long run of
// one byte and epoch.zig confirms a repeated post-OUT machine state.

const std = @import("std");
const engine = @import("engine.zig");
const epoch = @import("epoch.zig");

fn isOnly(output: []const u8, byte: u8) bool {
    for (output) |value| if (value != byte) return false;
    return true;
}

pub const SearchResult = struct {
    source: []u8,
    position: usize,
    replacement: u8,
    output_bytes: usize,
    steps: u64,
    evaluations: usize,
};

fn sourceFor(op: u16, position: usize) ?u8 {
    const value: i64 = 33 + @mod(@as(i64, op) - @as(i64, @intCast(position)) - 33, 94);
    if (value < engine.LO or value > engine.HI) return null;
    return @intCast(value);
}

pub fn search(
    seed: []const u8,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    var candidate = try allocator.dupe(u8, seed);
    defer allocator.free(candidate);
    var evaluations: usize = 0;

    for (candidate, 0..) |original, position| {
        if (original < engine.LO or original > engine.HI) continue;
        var replacement: u8 = engine.LO;
        while (replacement <= engine.HI) : (replacement += 1) {
            if (replacement == original) continue;
            candidate[position] = replacement;
            evaluations += 1;

            var mem: [engine.MEM_SIZE]u16 = undefined;
            const run = try engine.runInto(&mem, candidate, max_steps, allocator);
            const viable = run.status == .max_steps and run.output.len >= min_output and isOnly(run.output, byte);
            const output_bytes = run.output.len;
            const steps = run.steps;
            allocator.free(run.output);
            if (!viable) continue;

            const scan = try epoch.scan(candidate, max_steps, allocator);
            if (scan.repeated_epoch) {
                return .{
                    .source = try allocator.dupe(u8, candidate),
                    .position = position,
                    .replacement = replacement,
                    .output_bytes = output_bytes,
                    .steps = steps,
                    .evaluations = evaluations,
                };
            }
        }
        candidate[position] = original;
    }
    return null;
}

pub fn searchPair(
    seed: []const u8,
    first: usize,
    second: usize,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    var candidate = try allocator.dupe(u8, seed);
    defer allocator.free(candidate);
    if (first >= candidate.len or second >= candidate.len or first == second) return error.InvalidPositions;
    var evaluations: usize = 0;
    var left: u8 = engine.LO;
    while (left <= engine.HI) : (left += 1) {
        var right: u8 = engine.LO;
        while (right <= engine.HI) : (right += 1) {
            candidate[first] = left;
            candidate[second] = right;
            evaluations += 1;
            var mem: [engine.MEM_SIZE]u16 = undefined;
            const run = try engine.runInto(&mem, candidate, max_steps, allocator);
            const viable = run.status == .max_steps and run.output.len >= min_output and isOnly(run.output, byte);
            const output_bytes = run.output.len;
            const steps = run.steps;
            allocator.free(run.output);
            if (!viable) continue;
            const scan = try epoch.scan(candidate, max_steps, allocator);
            if (scan.repeated_epoch) {
                return .{
                    .source = try allocator.dupe(u8, candidate),
                    .position = first,
                    .replacement = left,
                    .output_bytes = output_bytes,
                    .steps = steps,
                    .evaluations = evaluations,
                };
            }
        }
    }
    return null;
}

pub fn searchControlPairs(
    seed: []const u8,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    return searchControlPairsInRange(seed, 0, seed.len, byte, min_output, max_steps, allocator);
}

pub fn searchControlPairsInRange(
    seed: []const u8,
    range_start: usize,
    range_end: usize,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    var candidate = try allocator.dupe(u8, seed);
    defer allocator.free(candidate);
    if (range_start >= range_end or range_end > candidate.len) return error.InvalidPositions;
    var evaluations: usize = 0;
    const control_ops = [_]u16{ engine.OP_CHASE, engine.OP_MOVD };

    for (candidate[range_start..range_end], range_start..) |first_original, first| {
        for (candidate[range_start..range_end], range_start..) |second_original, second| {
            if (first == second) continue;
            for (control_ops) |first_op| {
                const first_char = sourceFor(first_op, first) orelse continue;
                for (control_ops) |second_op| {
                    const second_char = sourceFor(second_op, second) orelse continue;
                    candidate[first] = first_char;
                    candidate[second] = second_char;
                    evaluations += 1;

                    var mem: [engine.MEM_SIZE]u16 = undefined;
                    const run = try engine.runInto(&mem, candidate, max_steps, allocator);
                    const viable = run.status == .max_steps and run.output.len >= min_output and isOnly(run.output, byte);
                    const output_bytes = run.output.len;
                    const steps = run.steps;
                    allocator.free(run.output);
                    if (viable) {
                        const scan = try epoch.scan(candidate, max_steps, allocator);
                        if (scan.repeated_epoch) {
                            return .{
                                .source = try allocator.dupe(u8, candidate),
                                .position = first,
                                .replacement = first_char,
                                .output_bytes = output_bytes,
                                .steps = steps,
                                .evaluations = evaluations,
                            };
                        }
                    }
                }
            }
            candidate[first] = first_original;
            candidate[second] = second_original;
        }
    }
    return null;
}

pub fn searchControlCrossRanges(
    seed: []const u8,
    first_start: usize,
    first_end: usize,
    second_start: usize,
    second_end: usize,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    var candidate = try allocator.dupe(u8, seed);
    defer allocator.free(candidate);
    if (first_start >= first_end or second_start >= second_end or second_end > candidate.len) return error.InvalidPositions;
    var evaluations: usize = 0;
    const control_ops = [_]u16{ engine.OP_CHASE, engine.OP_MOVD };
    for (candidate[first_start..first_end], first_start..) |first_original, first| {
        for (candidate[second_start..second_end], second_start..) |second_original, second| {
            for (control_ops) |first_op| {
                const first_char = sourceFor(first_op, first) orelse continue;
                for (control_ops) |second_op| {
                    const second_char = sourceFor(second_op, second) orelse continue;
                    candidate[first] = first_char;
                    candidate[second] = second_char;
                    evaluations += 1;
                    var mem: [engine.MEM_SIZE]u16 = undefined;
                    const run = try engine.runInto(&mem, candidate, max_steps, allocator);
                    const viable = run.status == .max_steps and run.output.len >= min_output and isOnly(run.output, byte);
                    const output_bytes = run.output.len;
                    const steps = run.steps;
                    allocator.free(run.output);
                    if (viable) {
                        const scan = try epoch.scan(candidate, max_steps, allocator);
                        if (scan.repeated_epoch) return .{
                            .source = try allocator.dupe(u8, candidate),
                            .position = first,
                            .replacement = first_char,
                            .output_bytes = output_bytes,
                            .steps = steps,
                            .evaluations = evaluations,
                        };
                    }
                }
            }
            candidate[first] = first_original;
            candidate[second] = second_original;
        }
    }
    return null;
}

pub fn searchControlTriplesInRange(
    seed: []const u8,
    range_start: usize,
    range_end: usize,
    first_end: usize,
    byte: u8,
    min_output: usize,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !?SearchResult {
    var candidate = try allocator.dupe(u8, seed);
    defer allocator.free(candidate);
    if (range_start >= first_end or first_end > range_end or range_end > candidate.len) return error.InvalidPositions;
    var evaluations: usize = 0;
    const control_ops = [_]u16{ engine.OP_CHASE, engine.OP_MOVD };
    for (candidate[range_start..first_end], range_start..) |first_original, first| {
        for (candidate[range_start..range_end], range_start..) |second_original, second| {
            if (second == first) continue;
            for (candidate[range_start..range_end], range_start..) |third_original, third| {
                if (third == first or third == second) continue;
                for (control_ops) |first_op| {
                    const first_char = sourceFor(first_op, first) orelse continue;
                    for (control_ops) |second_op| {
                        const second_char = sourceFor(second_op, second) orelse continue;
                        for (control_ops) |third_op| {
                            const third_char = sourceFor(third_op, third) orelse continue;
                            candidate[first] = first_char;
                            candidate[second] = second_char;
                            candidate[third] = third_char;
                            evaluations += 1;
                            var mem: [engine.MEM_SIZE]u16 = undefined;
                            const run = try engine.runInto(&mem, candidate, max_steps, allocator);
                            const viable = run.status == .max_steps and run.output.len >= min_output and isOnly(run.output, byte);
                            const output_bytes = run.output.len;
                            const steps = run.steps;
                            allocator.free(run.output);
                            if (viable) {
                                const scan = try epoch.scan(candidate, max_steps, allocator);
                                if (scan.repeated_epoch) return .{
                                    .source = try allocator.dupe(u8, candidate),
                                    .position = first,
                                    .replacement = first_char,
                                    .output_bytes = output_bytes,
                                    .steps = steps,
                                    .evaluations = evaluations,
                                };
                            }
                        }
                    }
                }
                candidate[second] = second_original;
                candidate[third] = third_original;
            }
        }
        candidate[first] = first_original;
    }
    return null;
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();
    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);
    if (args.items.len < 3 or args.items.len > 11 or args.items[2].len != 1) {
        std.debug.print("uso: malbolge-mutate <source.mal> <byte> [min_output] [max_steps] [found.mal] | --pair <p1> <p2> | --controls | --controls-range <start> <end> | --controls-cross <a> <b> <c> <d> | --controls-triple <start> <end> [first_end]\n", .{});
        return;
    }
    const min_output: usize = if (args.items.len >= 4) std.fmt.parseInt(usize, args.items[3], 10) catch 256 else 256;
    const max_steps: u64 = if (args.items.len >= 5) std.fmt.parseInt(u64, args.items[4], 10) catch 10_000 else 10_000;
    const source = try std.Io.Dir.cwd().readFileAlloc(init.io, args.items[1], allocator, .unlimited);
    const pair_mode = args.items.len == 9 and std.mem.eql(u8, args.items[6], "--pair");
    const control_mode = args.items.len == 7 and std.mem.eql(u8, args.items[6], "--controls");
    const control_range_mode = args.items.len == 9 and std.mem.eql(u8, args.items[6], "--controls-range");
    const cross_mode = args.items.len == 11 and std.mem.eql(u8, args.items[6], "--controls-cross");
    const triple_mode = (args.items.len == 9 or args.items.len == 10) and std.mem.eql(u8, args.items[6], "--controls-triple");
    const result = if (triple_mode)
        try searchControlTriplesInRange(source, try std.fmt.parseInt(usize, args.items[7], 10), try std.fmt.parseInt(usize, args.items[8], 10), if (args.items.len == 10) try std.fmt.parseInt(usize, args.items[9], 10) else try std.fmt.parseInt(usize, args.items[8], 10), args.items[2][0], min_output, max_steps, allocator)
    else if (cross_mode)
        try searchControlCrossRanges(source, try std.fmt.parseInt(usize, args.items[7], 10), try std.fmt.parseInt(usize, args.items[8], 10), try std.fmt.parseInt(usize, args.items[9], 10), try std.fmt.parseInt(usize, args.items[10], 10), args.items[2][0], min_output, max_steps, allocator)
    else if (control_range_mode)
        try searchControlPairsInRange(source, try std.fmt.parseInt(usize, args.items[7], 10), try std.fmt.parseInt(usize, args.items[8], 10), args.items[2][0], min_output, max_steps, allocator)
    else if (control_mode)
        try searchControlPairs(source, args.items[2][0], min_output, max_steps, allocator)
    else if (pair_mode)
        try searchPair(source, try std.fmt.parseInt(usize, args.items[7], 10), try std.fmt.parseInt(usize, args.items[8], 10), args.items[2][0], min_output, max_steps, allocator)
    else
        try search(source, args.items[2][0], min_output, max_steps, allocator);
    if (result) |found| {
        std.debug.print("FOUND position={d} replacement={c} output_bytes={d} steps={d} evaluations={d}\n", .{
            found.position, found.replacement, found.output_bytes, found.steps, found.evaluations,
        });
        if (args.items.len == 6) try std.Io.Dir.cwd().writeFile(init.io, .{
            .sub_path = args.items[5],
            .data = found.source,
        });
    } else {
        const evaluations = if (triple_mode) blk: {
            const s = try std.fmt.parseInt(usize, args.items[7], 10);
            const e = try std.fmt.parseInt(usize, args.items[8], 10);
            const f = if (args.items.len == 10) try std.fmt.parseInt(usize, args.items[9], 10) else e;
            break :blk (f - s) * (e - s - 1) * (e - s - 2) * 8;
        } else if (cross_mode) (try std.fmt.parseInt(usize, args.items[8], 10) - try std.fmt.parseInt(usize, args.items[7], 10)) * (try std.fmt.parseInt(usize, args.items[10], 10) - try std.fmt.parseInt(usize, args.items[9], 10)) * 4 else if (control_range_mode) (try std.fmt.parseInt(usize, args.items[8], 10) - try std.fmt.parseInt(usize, args.items[7], 10)) * ((try std.fmt.parseInt(usize, args.items[8], 10) - try std.fmt.parseInt(usize, args.items[7], 10)) - 1) * 4 else if (control_mode) source.len * (source.len - 1) * 4 else if (pair_mode) 93 * 93 else source.len * 93;
        std.debug.print("NOT_FOUND evaluations={d}\n", .{evaluations});
    }
}

test "single cell search rejects a halting source" {
    const found = try search("v", 'A', 2, 100, std.testing.allocator);
    try std.testing.expect(found == null);
}

test "pair search rejects a halting source" {
    try std.testing.expectError(error.InvalidPositions, searchPair("v", 0, 1, 'A', 2, 100, std.testing.allocator));
}

test "triple search rejects an empty range" {
    try std.testing.expectError(error.InvalidPositions, searchControlTriplesInRange("vvv", 1, 3, 1, 'A', 2, 100, std.testing.allocator));
}
