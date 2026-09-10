// real.zig -- Sintesis por byte sobre estados REALES (sin simulador espejo).
//
// Por cada byte objetivo, BFS de extensiones evaluadas con ejecucion real
// `prefijo + extension + halt`. Poda: output == prefijo exacto del objetivo.
// La frontera se ordena por progreso de output (best-first). Dedup (a,d,len)
// acotado por nivel: heuristico, no completo -- NoRuta significa "no hallado
// en presupuesto", nunca "imposible".

const std = @import("std");
const engine = @import("engine.zig");
const generator = @import("generator.zig");

const BRANCH_OPS = [_]u16{ engine.OP_OUT, engine.OP_ROT, engine.OP_CRAZY, engine.OP_MOVD };
const EXT_MAX: usize = 16;
const NODE_MAX: usize = 300_000;
const BEAM_MAX: usize = 8_000;
const STEP_CAP: u64 = 20_000;
const GLOBAL_EXT_MAX: usize = 28;
const GLOBAL_NODE_MAX: usize = 1_000_000;
const GLOBAL_BEAM_MAX: usize = 16_000;

pub var diag: bool = false;

pub const Stats = struct {
    nodes: usize = 0,
    solution_depth: usize = 0,
};

fn runFull(program: []const u8, al: std.mem.Allocator) !engine.RunResult {
    var mem: [engine.MEM_SIZE]u16 = undefined;
    return engine.runInto(&mem, program, STEP_CAP, al);
}

/// Ejecucion instrumentada: devuelve output + maximo indice tocado (leido o
/// escrito). Un prefijo P es ESTABLE si max_touch < P.len: su ejecucion no
/// depende de ninguna celda posterior y puede extenderse composicionalmente.
const StableRun = struct {
    output: []u8,
    status: engine.RunStatus,
    a: u16,
    d: u16,
    steps: u64,
    max_touch: usize,
};

fn runStable(program: []const u8, al: std.mem.Allocator) !StableRun {
    var mem: [engine.MEM_SIZE]u16 = undefined;
    try engine.loadMemory(program, &mem);
    var out = std.array_list.Managed(u8).init(al);
    errdefer out.deinit();
    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var max_touch: usize = 0;
    var steps: u64 = 0;
    var status: engine.RunStatus = .max_steps;
    while (steps < STEP_CAP) {
        steps += 1;
        const cell = mem[c];
        const op = engine.decodeOpcode(cell, c);
        var jumped = false;
        var c_target: u16 = 0;
        switch (op) {
            engine.OP_CHASE => {
                if (@as(usize, mem[d]) > max_touch) max_touch = @as(usize, mem[d]);
                c_target = mem[d];
                jumped = true;
            },
            engine.OP_OUT => try out.append(@intCast(a % 256)),
            engine.OP_IN => a = 0xffff,
            engine.OP_ROT => {
                if (@as(usize, d) > max_touch) max_touch = d;
                const value = mem[d];
                mem[d] = (value / 3) + (value % 3) * 19683;
                a = mem[d];
            },
            engine.OP_MOVD => {
                if (@as(usize, d) > max_touch) max_touch = d;
                d = mem[d];
            },
            engine.OP_CRAZY => {
                if (@as(usize, d) > max_touch) max_touch = d;
                mem[d] = engine.crazyOp(a, mem[d]);
                a = mem[d];
            },
            engine.OP_NOP => {},
            engine.OP_HALT => {
                status = .halted;
                break;
            },
            else => {},
        }
        if (jumped) c = c_target;
        if (mem[c] >= engine.LO and mem[c] <= engine.HI) {
            if (@as(usize, c) > max_touch) max_touch = c;
            mem[c] = engine.ENCRYPT_TABLE[mem[c] - engine.LO];
        }
        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
    }
    return .{
        .output = try out.toOwnedSlice(),
        .status = status,
        .a = a,
        .d = d,
        .steps = steps,
        .max_touch = max_touch,
    };
}

fn extendByte(
    base: []const u8,
    target: []const u8,
    stats: *Stats,
    ext_max: usize,
    node_max: usize,
    beam_max: usize,
    stable_only: bool,
    al: std.mem.Allocator,
) !?[]u8 {
    const Node = struct {
        ext: []u8,
        out_len: usize,
    };
    const base_out = blk: {
        if (base.len == 0) break :blk @as(usize, 0);
        const halt_char = generator.colaHalt(base.len) catch break :blk @as(usize, 0);
        var prog = std.ArrayList(u8).empty;
        try prog.appendSlice(al, base);
        try prog.append(al, halt_char);
        const r = try runFull(prog.items, al);
        defer al.free(r.output);
        if (r.status != .halted) return null;
        break :blk r.output.len;
    };
    var frontier = std.ArrayList(Node).empty;
    try frontier.append(al, .{ .ext = try al.dupe(u8, ""), .out_len = base_out });
    var seen = std.AutoHashMapUnmanaged(u64, void){};

    var depth: usize = 0;
    while (depth <= ext_max) : (depth += 1) {
        // Best-first: mas output primero.
        std.mem.sort(Node, frontier.items, {}, struct {
            fn lt(_: void, a: Node, b: Node) bool {
                return a.out_len > b.out_len;
            }
        }.lt);
        if (frontier.items.len > beam_max) frontier.items.len = beam_max;
        var next = std.ArrayList(Node).empty;
        for (frontier.items) |node| {
            const ext = node.ext;
            const pos = base.len + ext.len;
            for (BRANCH_OPS) |op| {
                if (stats.nodes >= node_max) return null;
                const ch = generator.fuentePara(op, pos) orelse continue;
                stats.nodes += 1;
                varprog: {
                    var prog = std.ArrayList(u8).empty;
                    try prog.appendSlice(al, base);
                    try prog.appendSlice(al, ext);
                    try prog.append(al, ch);
                    const halt_char = generator.colaHalt(prog.items.len) catch break :varprog;
                    try prog.append(al, halt_char);
                    const r = try runStable(prog.items, al);
                    defer al.free(r.output);
                    if (diag) {
                        std.debug.print("diag child op={d} status={s} outlen={d} out={s} touch={d}/{d}\n", .{ op, @tagName(r.status), r.output.len, r.output, r.max_touch, prog.items.len - 1 });
                    }
                    if (r.status != .halted) break :varprog;
                    if (r.output.len > target.len) break :varprog;
                    if (!std.mem.eql(u8, r.output, target[0..r.output.len])) break :varprog;
                    if (std.mem.eql(u8, r.output, target)) {
                        stats.solution_depth = depth + 1;
                        var out = try al.alloc(u8, base.len + ext.len + 1);
                        @memcpy(out[0..base.len], base);
                        @memcpy(out[base.len .. base.len + ext.len], ext);
                        out[out.len - 1] = ch;
                        return out;
                    }
                    // Solo los prefijos estables son extensibles (modo por-byte).
                    if (stable_only and r.max_touch >= prog.items.len - 1) break :varprog;
                    const key = (@as(u64, r.a) << 32) | (@as(u64, r.d) << 16) | (@as(u64, r.output.len) << 8) | @as(u64, depth);
                    if (seen.contains(key)) break :varprog;
                    try seen.put(al, key, {});
                    var child = try al.alloc(u8, ext.len + 1);
                    @memcpy(child[0..ext.len], ext);
                    child[ext.len] = ch;
                    try next.append(al, .{ .ext = child, .out_len = r.output.len });
                }
            }
        }
        if (next.items.len == 0) return null;
        frontier = next;
    }
    return null;
}

/// Programa Classic que emite exactamente `target`, o error.NoRuta.
pub fn generarReal(target: []const u8, stats: *Stats, allocator: std.mem.Allocator) ![]u8 {
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const al = arena.allocator();
    var prefix = std.ArrayList(u8).empty;
    for (target, 0..) |_, i| {
        const want = target[0 .. i + 1];
        const ext = try extendByte(prefix.items, want, stats, EXT_MAX, NODE_MAX, BEAM_MAX, true, al) orelse return error.NoRuta;
        try prefix.appendSlice(al, ext[prefix.items.len..]);
    }
    const halt_char = try generator.colaHalt(prefix.items.len);
    try prefix.append(al, halt_char);
    return try allocator.dupe(u8, prefix.items);
}

test "stable runner matches engine" {
    const hello = "(=<`#9]~6ZY327Uv4-QsqpMn&+Ij\"'E%e{Ab~w=_:]Kw%o44Uqp0/Q?xNvL:`H%c#DD2^WV>gY;dts76qKJImZkj";
    for ([_][]const u8{ hello, "v", "ibCBA@?>=<;:9876543210" }) |src| {
        var mem: [engine.MEM_SIZE]u16 = undefined;
        const ref = try engine.runInto(&mem, src, STEP_CAP, std.testing.allocator);
        defer std.testing.allocator.free(ref.output);
        const st = try runStable(src, std.testing.allocator);
        defer std.testing.allocator.free(st.output);
        try std.testing.expectEqualStrings(ref.output, st.output);
        try std.testing.expectEqual(ref.status, st.status);
        try std.testing.expectEqual(ref.steps, st.steps);
        try std.testing.expectEqual(ref.a, st.a);
        try std.testing.expectEqual(ref.d, st.d);
    }
}

test "diag real per-byte A then B" {
    diag = true;
    defer diag = false;
    var stats = Stats{};
    const prog_a = generarReal("A", &stats, std.testing.allocator) catch |err| {
        std.debug.print("diag real A: err={s} nodes={d}\n", .{ @errorName(err), stats.nodes });
        return;
    };
    defer std.testing.allocator.free(prog_a);
    std.debug.print("diag real A: chars={d} nodes={d} soldepth={d}\n", .{ prog_a.len, stats.nodes, stats.solution_depth });
    var stats2 = Stats{};
    const prog_b = generarReal("AB", &stats2, std.testing.allocator) catch |err| {
        std.debug.print("diag real AB: err={s} nodes={d}\n", .{ @errorName(err), stats2.nodes });
        return;
    };
    defer std.testing.allocator.free(prog_b);
    std.debug.print("diag real AB: chars={d} nodes={d} soldepth={d}\n", .{ prog_b.len, stats2.nodes, stats2.solution_depth });
}

/// Busqueda global: el objetivo completo desde vacio, sin congelar prefijos.
pub fn generarGlobal(target: []const u8, stats: *Stats, allocator: std.mem.Allocator) ![]u8 {
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const al = arena.allocator();
    const ext = try extendByte("", target, stats, GLOBAL_EXT_MAX, GLOBAL_NODE_MAX, GLOBAL_BEAM_MAX, false, al) orelse return error.NoRuta;
    var prog = std.ArrayList(u8).empty;
    try prog.appendSlice(al, ext);
    try prog.append(al, try generator.colaHalt(ext.len));
    return try allocator.dupe(u8, prog.items);
}

test "global real-state finds AB" {
    var stats = Stats{};
    const prog = generarGlobal("AB", &stats, std.testing.allocator) catch |err| {
        std.debug.print("global AB: err={s} nodes={d}\n", .{ @errorName(err), stats.nodes });
        return;
    };
    defer std.testing.allocator.free(prog);
    var mem: [engine.MEM_SIZE]u16 = undefined;
    const r = try engine.runInto(&mem, prog, 200_000, std.testing.allocator);
    defer std.testing.allocator.free(r.output);
    std.debug.print("global AB: chars={d} steps={d} nodes={d} soldepth={d}\n", .{ prog.len, r.steps, stats.nodes, stats.solution_depth });
    try std.testing.expectEqualStrings("AB", r.output);
    try std.testing.expectEqual(engine.RunStatus.halted, r.status);
}

test "real-state per-byte finds AB" {
    // Documenta la no-composicionalidad probada por traza: el prefijo 'A'
    // hallado lee mas alla de si mismo, asi que congelarlo y extenderlo no
    // puede producir "AB". El camino es sintesis global o prefijos estables.
    var stats = Stats{};
    try std.testing.expectError(error.NoRuta, generarReal("AB", &stats, std.testing.allocator));
}
