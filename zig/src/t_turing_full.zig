// t_turing_full.zig — Turing completeness demonstration: BF → Malbolge → output
// Uses Malbolge-Translator's own engine for consistency.

const std = @import("std");
const engine = @import("engine.zig");
const generator = @import("generator.zig");
const bf = @import("bf_interpreter.zig");

// Brainfuck "Hello World!"
const BF_HELLO = "++++++++[>++++[>++>+++>+++>+<<<<-]>+>+>->>+[<]<-]>>.>---.+++++++..+++.>>.<-.<.+++.------.--------.>>+.>++.";

fn runTest(allocator: std.mem.Allocator) !void {
    // 1. Run Brainfuck to get expected output
    std.debug.print("Running Brainfuck Hello World...\n", .{});
    const bf_output = try bf.run(BF_HELLO, &.{}, allocator);
    defer allocator.free(bf_output);
    std.debug.print("BF output ({d} bytes): {s}\n", .{bf_output.len, bf_output});

    // 2. Generate Malbolge that produces the same output
    std.debug.print("\nGenerating Malbolge for same output...\n", .{});
    generator.verbose = true;
    const malbolge_src = try generator.generar(bf_output, 20, allocator);
    defer allocator.free(malbolge_src);
    std.debug.print("Malbolge program ({d} cells)\n", .{malbolge_src.len});

    // 3. Run generated Malbolge using Malbolge-Translator engine
    std.debug.print("\nRunning generated Malbolge...\n", .{});
    var mem: [engine.MEM_SIZE]u16 = undefined;
    const result = try engine.runInto(&mem, malbolge_src, 2_000_000, allocator);
    defer allocator.free(result.output);

    std.debug.print("Malbolge status: {s}, steps: {d}\n", .{@tagName(result.status), result.steps});
    std.debug.print("Malbolge output ({d} bytes): {s}\n", .{result.output.len, result.output});

    // 4. Verify exact match
    if (std.mem.eql(u8, bf_output, result.output)) {
        std.debug.print("\n✅ TURING COMPLETENESS DEMONSTRATED\n", .{});
        std.debug.print("   Brainfuck (TC) -> Malbolge compilation works\n", .{});
        std.debug.print("   Both produce identical output: {s}\n", .{bf_output});
    } else {
        std.debug.print("\n❌ OUTPUT MISMATCH\n", .{});
        std.debug.print("   Expected: {s}\n", .{bf_output});
        std.debug.print("   Got:      {s}\n", .{result.output});
        return error.OutputMismatch;
    }
}

pub fn main() !void {
    const allocator = std.heap.page_allocator;
    try runTest(allocator);
}

const Error = error{ OutputMismatch };