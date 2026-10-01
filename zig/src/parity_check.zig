// parity_check.zig — Classic parity checker for malbolge-free corpus
// Runs the 6 corpus programs through engine.zig, outputs JSON for Python consumer
const std = @import("std");
const engine = @import("engine.zig");

const Program = struct {
    name: []const u8,
    source: []const u8,
};

const PROGRAMS = [_]Program{
    .{ .name = "echo.mal", .source = @embedFile("corpus/echo.mal") },
    .{ .name = "echo1.mal", .source = @embedFile("corpus/echo1.mal") },
    .{ .name = "echo2.mal", .source = @embedFile("corpus/echo2.mal") },
    .{ .name = "echo3.mal", .source = @embedFile("corpus/echo3.mal") },
    .{ .name = "hello.mal", .source = @embedFile("corpus/hello.mal") },
    .{ .name = "reproducer.mal", .source = @embedFile("corpus/reproducer.mal") },
};

pub fn main() !void {
    const allocator = std.heap.page_allocator;

    var out = std.array_list.Managed(u8).init(allocator);
    defer out.deinit();

    try out.appendSlice("[\n");

    for (PROGRAMS, 0..) |prog, i| {
        var mem: [engine.MEM_SIZE]u16 = undefined;
        const result = try engine.runInto(&mem, prog.source, 2_000_000, allocator);

        // Compute SHA256 of stdout
        var h = std.crypto.hash.sha2.Sha256.init(.{});
        h.update(result.output);
        var digest: [32]u8 = undefined;
        h.final(&digest);
        const hex = std.fmt.bytesToHex(digest, .lower);

        const status_str = if (result.status == .halted) "HALTED" else "MAX_STEPS";

        try out.appendSlice("  {\n");
        const prog_json = std.fmt.allocPrint(allocator, "    \"program\": \"{s}\",\n", .{prog.name}) catch "    \"program\": \"error\",\n";
        defer allocator.free(prog_json);
        try out.appendSlice(prog_json);

        const status_json = std.fmt.allocPrint(allocator, "    \"status\": \"{s}\",\n", .{status_str}) catch "    \"status\": \"error\",\n";
        defer allocator.free(status_json);
        try out.appendSlice(status_json);

        const steps_json = std.fmt.allocPrint(allocator, "    \"steps\": {d},\n", .{result.steps}) catch "    \"steps\": 0,\n";
        defer allocator.free(steps_json);
        try out.appendSlice(steps_json);

        const sha_json = std.fmt.allocPrint(allocator, "    \"stdout_sha256\": \"{s}\"\n", .{hex}) catch "    \"stdout_sha256\": \"error\"\n";
        defer allocator.free(sha_json);
        try out.appendSlice(sha_json);
        try out.appendSlice("  }");
        if (i != PROGRAMS.len - 1) try out.appendSlice(",");
        try out.appendSlice("\n");
    }

    try out.appendSlice("]\n");

    std.debug.print("{s}\n", .{out.items});
}