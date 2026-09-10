// main.zig — CLI del core Zig de Malbolge-Translator.
// Subcomandos: run <program> [max_steps] | generate <target>
const std = @import("std");
const engine = @import("engine.zig");
const generator = @import("generator.zig");
const snapshot = @import("snapshot.zig");

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();

    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);

    if (args.items.len < 2) {
        std.debug.print("uso: malbolge-zig <run|generate|resume> ...\n", .{});
        return;
    }
    const cmd = args.items[1];
    if (std.mem.eql(u8, cmd, "run")) {
        if (args.items.len < 3) {
            std.debug.print("uso: malbolge-zig run <program> [max_steps]\n", .{});
            return;
        }
        const max_steps: u64 = if (args.items.len >= 4)
            std.fmt.parseInt(u64, args.items[3], 10) catch 100_000_000
        else
            100_000_000;
        var mem: [engine.MEM_SIZE]u16 = undefined;
        const r = try engine.runInto(&mem, args.items[2], max_steps, allocator);
        defer allocator.free(r.output);
        std.debug.print("status={s} steps={d}\n", .{ @tagName(r.status), r.steps });
        std.debug.print("output={s}\n", .{r.output});
    } else if (std.mem.eql(u8, cmd, "generate")) {
        try generator.main(init);
    } else if (std.mem.eql(u8, cmd, "resume")) {
        if (args.items.len < 4) {
            std.debug.print("uso: malbolge-zig resume <snapshot.mbs> <suffix-opcodes> [max_steps]\n", .{});
            return;
        }
        const max_steps: u64 = if (args.items.len >= 5)
            std.fmt.parseInt(u64, args.items[4], 10) catch 100_000_000
        else
            100_000_000;
        const result = try snapshot.runFile(init.io, args.items[2], args.items[3], max_steps, allocator);
        defer allocator.free(result.output);
        std.debug.print("status={s} steps={d}\n", .{ @tagName(result.status), result.steps });
        std.debug.print("output={s}\n", .{result.output});
    } else {
        std.debug.print("subcomando desconocido: {s}\n", .{cmd});
    }
}
