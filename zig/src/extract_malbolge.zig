// Extract just the raw Malbolge program for "Hello World!"
const std = @import("std");
const generator = @import("generator.zig");

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    const io = std.Io.Threaded.global_single_threaded;
    const target = "Hello World!";
    generator.verbose = false;
    const malbolge_src = try generator.generar(target, 20, allocator);
    defer allocator.free(malbolge_src);

    // Write raw program to file
    const dir = std.Io.Dir.cwd();
    try std.Io.Dir.writeFile(dir, io, .{
        .sub_path = "turing_malbolge_hello.mal",
        .flags = .{ .write = true, .create = true, .truncate = true },
        .data = malbolge_src,
    });

    std.debug.print("Written {d} bytes to turing_malbolge_hello.mal\n", .{malbolge_src.len});
}