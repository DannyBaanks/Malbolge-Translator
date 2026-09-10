// reducer.zig -- Semantic delta reduction using the Classic Zig engine.
//
// Every tentative deletion is run from a fresh 3^10-cell tape. A deletion is
// retained only when the program halts and its bytes exactly equal the target.

const std = @import("std");
const engine = @import("engine.zig");

fn exact(source: []const u8, target: []const u8, allocator: std.mem.Allocator) !bool {
    var mem: [engine.MEM_SIZE]u16 = undefined;
    const result = try engine.runInto(&mem, source, 10_000_000, allocator);
    defer allocator.free(result.output);
    return result.status == .halted and std.mem.eql(u8, result.output, target);
}

pub const Reduction = struct {
    initial_len: usize,
    source: []u8,
    evaluations: usize,
};

pub fn reduce(source: []const u8, target: []const u8, allocator: std.mem.Allocator) !Reduction {
    var current = std.ArrayList(u8).empty;
    for (source) |byte| {
        if (byte != '\n' and byte != '\r' and byte != ' ' and byte != '\t') {
            try current.append(allocator, byte);
        }
    }
    errdefer current.deinit(allocator);
    const initial_len = current.items.len;

    if (!try exact(current.items, target, allocator)) return error.SeedDoesNotMatch;

    var evaluations: usize = 0;
    var span = current.items.len / 2;
    while (span > 0) {
        var changed = false;
        var offset: usize = 0;
        while (offset + span <= current.items.len) {
            const old_len = current.items.len;
            const removed = try allocator.dupe(u8, current.items[offset .. offset + span]);

            std.mem.copyForwards(u8, current.items[offset .. old_len - span], current.items[offset + span .. old_len]);
            current.items.len = old_len - span;
            evaluations += 1;

            if (try exact(current.items, target, allocator)) {
                changed = true;
                offset = 0;
            } else {
                current.items.len = old_len;
                std.mem.copyBackwards(u8, current.items[offset + span .. old_len], current.items[offset .. old_len - span]);
                @memcpy(current.items[offset .. offset + span], removed);
                offset += span;
            }
            allocator.free(removed);
        }
        if (!changed) span /= 2;
    }

    return .{
        .initial_len = initial_len,
        .source = try current.toOwnedSlice(allocator),
        .evaluations = evaluations,
    };
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();
    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);

    if (args.items.len != 3) {
        std.debug.print("uso: malbolge-reduce <source.mal> <target-ascii>\n", .{});
        return;
    }

    const source = try std.Io.Dir.cwd().readFileAlloc(init.io, args.items[1], allocator, .unlimited);
    const reduced = reduce(source, args.items[2], allocator) catch |err| {
        std.debug.print("reduction_error={s}\n", .{@errorName(err)});
        return;
    };
    const ratio = @as(f64, @floatFromInt(args.items[2].len)) / @as(f64, @floatFromInt(reduced.source.len));
    std.debug.print("seed_chars={d}\nreduced_chars={d}\nremoved_chars={d}\nevaluations={d}\noutput_over_source={d:.6}\n", .{
        reduced.initial_len,
        reduced.source.len,
        reduced.initial_len - reduced.source.len,
        reduced.evaluations,
        ratio,
    });
}

test "exact uses Classic semantics" {
    try std.testing.expect(!try exact("v", "A", std.testing.allocator));
}
