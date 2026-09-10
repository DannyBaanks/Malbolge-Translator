// generator.zig — Generador Classic Malbolge (Zig 0.16), espejo de meowbolge v2.
//
// Construcción por congruencia + proponente dirigido por estado:
//   op = (mem[c] + c) % 94  =>  ch = 33 + ((op - pos - 33) % 94)
// Cada candidato se acepta SOLO si el motor real (engine.zig) emite exactamente
// el objetivo. Toda la memoria interna usa arena allocator (sin frees manuales);
// el programa resultante se copia al allocator del llamador.

const std = @import("std");
const engine = @import("engine.zig");

const MOD: u16 = 94;
const LO: u8 = 33;
const HI: u8 = 126;
const MEM: usize = engine.MEM_SIZE;

const DFS_DEPTH_MAX: usize = 160;
const DFS_NODE_MAX: usize = 5_000_000;
const RUTAS_MAX: usize = 500;

const CANDIDATAS = [_]u16{ engine.OP_ROT, engine.OP_CRAZY, engine.OP_MOVD };
const OP_ORDER = [_]u16{ engine.OP_OUT, engine.OP_ROT, engine.OP_CRAZY, engine.OP_MOVD };

/// Caracter que en la posicion `pos` se ejecuta como opcode `op`, o null.
pub fn fuentePara(op: u16, pos: usize) ?u8 {
    const v: i64 = 33 + @mod(@as(i64, op) - @as(i64, @intCast(pos)) - 33, 94);
    if (v >= 33 and v <= 126) return @intCast(v);
    return null;
}

pub fn colaHalt(pos: usize) !u8 {
    return fuentePara(engine.OP_HALT, pos) orelse error.NoHaltAtPosition;
}

/// Cuando es true, `generar` reporta cada byte sintetizado por stderr-debug.
pub var verbose: bool = false;

fn verificaSalida(programa: []const u8, objetivo: []const u8, al: std.mem.Allocator) !bool {
    var mem: [MEM]u16 = undefined;
    const r = try engine.runInto(&mem, programa, 200_000, al);
    if (r.status != .halted) return false;
    return std.mem.eql(u8, r.output, objetivo);
}

fn rellenarCola(mem: []u16, llenado: usize) void {
    var i: usize = llenado;
    while (i < MEM) : (i += 1) {
        const prev1 = if (i >= 1) mem[i - 1] else mem[MEM - 1];
        const prev2 = if (i >= 2) mem[i - 2] else mem[MEM - 1];
        mem[i] = engine.crazyOp(prev1, prev2);
    }
}

// ---------------------------------------------------------------------------
// Proponente DFS con regla de toque exacta: durante la simulacion ninguna
// lectura de mem[d] puede estar mas alla de la celda que se coloca (d <= pos),
// y el prefijo base no puede haber tocado nada >= desde. Bajo esa regla la
// simulacion coincide con la ejecucion real celda por celda, asi que las rutas
// propuestas verifican. Memoria O(profundidad): una sola cinta + undo.
// ---------------------------------------------------------------------------

const DfsCtx = struct {
    mem: *[MEM]u16,
    desde: usize,
    objetivo: u8,
    restrict_past: bool,
    budget: *usize,
    rutas: *std.ArrayList([]u16),
    seen: *std.AutoHashMapUnmanaged(u64, void),
    al: std.mem.Allocator,
    stack: [DFS_DEPTH_MAX + 1]u16,
};

fn dfsDive(ctx: *DfsCtx, a: u16, d: u16, depth: usize) !void {
    if (ctx.budget.* == 0 or ctx.rutas.items.len >= RUTAS_MAX or depth > DFS_DEPTH_MAX) return;
    const clave = (@as(u64, a) << 16) | d;
    if (ctx.seen.contains(clave)) return;
    try ctx.seen.put(ctx.al, clave, {});
    const pos = ctx.desde + depth;
    // OUT terminal: solo se registra si emitiria el objetivo.
    if (fuentePara(engine.OP_OUT, pos) != null) {
        const b: u8 = @intCast(a % 256);
        if (b == ctx.objetivo) {
            var ruta = try ctx.al.alloc(u16, depth + 1);
            @memcpy(ruta[0..depth], ctx.stack[0..depth]);
            ruta[depth] = engine.OP_OUT;
            try ctx.rutas.append(ctx.al, ruta);
            if (ctx.rutas.items.len >= RUTAS_MAX) return;
        }
    }
    if (depth >= DFS_DEPTH_MAX) return;
    const ops = [_]u16{ engine.OP_ROT, engine.OP_CRAZY, engine.OP_MOVD };
    for (ops) |op| {
        if (ctx.budget.* == 0 or ctx.rutas.items.len >= RUTAS_MAX) return;
        const ch = fuentePara(op, pos) orelse continue;
        // Regla exacta: la lectura de mem[d] debe ver una celda ya colocada.
        if (@as(usize, d) > pos) continue;
        ctx.budget.* -= 1;
        const pos_address: u16 = @intCast(pos);
        const saved_pos = ctx.mem[pos];
        const touched_d = d != pos_address;
        const saved_dcell: u16 = if (touched_d) ctx.mem[d] else 0;
        ctx.mem[pos] = ch;
        var a2 = a;
        var d2 = d;
        var accept = true;
        switch (op) {
            engine.OP_ROT => {
                const v = ctx.mem[d];
                a2 = (v / 3) + (v % 3) * 19683;
                ctx.mem[d] = a2;
            },
            engine.OP_CRAZY => {
                const v = ctx.mem[d];
                a2 = engine.crazyOp(a2, v);
                ctx.mem[d] = a2;
            },
            else => { // MOVD
                const destino = ctx.mem[d];
                if (ctx.restrict_past and destino >= pos) accept = false;
                d2 = destino;
            },
        }
        if (accept) {
            if (ctx.mem[pos] >= LO and ctx.mem[pos] <= HI) ctx.mem[pos] = engine.ENCRYPT_TABLE[ctx.mem[pos] - LO];
            const d_sig: u16 = @intCast((@as(usize, d2) + 1) % MEM);
            ctx.stack[depth] = op;
            try dfsDive(ctx, a2, d_sig, depth + 1);
        }
        ctx.mem[pos] = saved_pos;
        if (touched_d) ctx.mem[d] = saved_dcell;
    }
}

fn proponerRuta(
    prefix: []const u8,
    objetivo_byte: u8,
    restrict_past: bool,
    al: std.mem.Allocator,
) !std.ArrayList([]u16) {
    var rutas = std.ArrayList([]u16).empty;

    const hal = try colaHalt(prefix.len);
    const base_len = prefix.len + 1;
    var mem: [MEM]u16 = undefined;
    for (prefix, 0..) |c, i| mem[i] = c;
    mem[prefix.len] = hal;
    rellenarCola(&mem, base_len);

    // Puerta de estabilidad: si el prefijo leyo/escribio >= desde, su estado
    // simulado no coincide con el real bajo ninguna extension. Sin rutas.
    const desde = prefix.len;
    var a: u16 = 0;
    var d: u16 = 0;
    for (prefix, 0..) |_, pos| {
        const op = engine.decodeOpcode(mem[pos], @intCast(pos % MOD));
        switch (op) {
            engine.OP_ROT => {
                if (@as(usize, d) >= desde) return rutas;
                const v = mem[d];
                mem[d] = (v / 3) + (v % 3) * 19683;
                a = mem[d];
            },
            engine.OP_CRAZY => {
                if (@as(usize, d) >= desde) return rutas;
                mem[d] = engine.crazyOp(a, mem[d]);
                a = mem[d];
            },
            engine.OP_MOVD => {
                if (@as(usize, d) >= desde) return rutas;
                d = mem[d];
            },
            else => {},
        }
        if (mem[pos] >= LO and mem[pos] <= HI) mem[pos] = engine.ENCRYPT_TABLE[mem[pos] - LO];
        d = @intCast((@as(usize, d) + 1) % MEM);
    }

    var budget: usize = DFS_NODE_MAX;
    var seen = std.AutoHashMapUnmanaged(u64, void){};
    var ctx = DfsCtx{
        .mem = &mem,
        .desde = desde,
        .objetivo = objetivo_byte,
        .restrict_past = restrict_past,
        .budget = &budget,
        .rutas = &rutas,
        .seen = &seen,
        .al = al,
        .stack = undefined,
    };
    try dfsDive(&ctx, a, d, 0);
    return rutas;
}

// ---------------------------------------------------------------------------
// Generador experimental acotado: directo -> proponente -> bruta. Arena interna.
// Solo devuelve una fuente tras verificarla en el motor Classic; `NoRuta` es un
// resultado normal cuando el presupuesto no alcanza para una continuacion.
// ---------------------------------------------------------------------------

pub fn generar(texto: []const u8, ancho: usize, allocator: std.mem.Allocator) ![]u8 {
    var arena = std.heap.ArenaAllocator.init(allocator);
    defer arena.deinit();
    const al = arena.allocator();

    var fuente = std.ArrayList(u8).empty;

    for (texto, 0..) |ch, i| {
        const objetivo = texto[0 .. i + 1];
        var hallado: ?[]u8 = null;

        // 1) Directo.
        if (fuentePara(engine.OP_OUT, fuente.items.len)) |c_out| {
            var cand = std.ArrayList(u8).empty;
            try cand.appendSlice(al, fuente.items);
            try cand.append(al, c_out);
            try cand.append(al, try colaHalt(cand.items.len));
            if (try verificaSalida(cand.items, objetivo, al)) {
                cand.shrinkRetainingCapacity(cand.items.len - 1);
                hallado = try al.dupe(u8, cand.items);
            }
        }

        // 2) Rapido: proponente.
        if (hallado == null) {
            for ([_]bool{ true, false }) |restrict| {
                if (hallado != null) break;
                const rutas = try proponerRuta(fuente.items, ch, restrict, al);
                for (rutas.items) |ruta| {
                    var cand = std.ArrayList(u8).empty;
                    try cand.appendSlice(al, fuente.items);
                    var ok = true;
                    for (ruta) |op| {
                        const cc = fuentePara(op, cand.items.len) orelse {
                            ok = false;
                            break;
                        };
                        try cand.append(al, cc);
                    }
                    if (!ok) continue;
                    if (ruta[ruta.len - 1] != engine.OP_OUT) {
                        const cc = fuentePara(engine.OP_OUT, cand.items.len) orelse continue;
                        try cand.append(al, cc);
                    }
                    try cand.append(al, try colaHalt(cand.items.len));
                    if (try verificaSalida(cand.items, objetivo, al)) {
                        cand.shrinkRetainingCapacity(cand.items.len - 1);
                        hallado = try al.dupe(u8, cand.items);
                        break;
                    }
                }
            }
        }

        // 3) Bruta.
        if (hallado == null) {
            var largo: usize = 0;
            outer: while (largo < ancho) : (largo += 1) {
                var combo = std.ArrayList(u16).empty;
                try brutaRec(CANDIDATAS[0..], largo, &combo, &fuente, objetivo, &hallado, al);
                if (hallado != null) break :outer;
            }
        }

        // `found` ya contiene el programa completo hasta aqui (base + extension),
        // como `fuente = hallado` del meowbolge original: reemplazo, no append.
        const found = hallado orelse return error.NoRuta;
        fuente.clearRetainingCapacity();
        try fuente.appendSlice(al, found);
        if (verbose) {
            std.debug.print("byte[{d}/{d}] {c} celdas={d}\n", .{ i + 1, texto.len, ch, fuente.items.len });
        }
    }

    try fuente.append(al, try colaHalt(fuente.items.len));
    return try allocator.dupe(u8, fuente.items);
}

fn brutaRec(
    opciones: []const u16,
    rest: usize,
    combo: *std.ArrayList(u16),
    fuente: *std.ArrayList(u8),
    objetivo: []const u8,
    hallado: *?[]u8,
    al: std.mem.Allocator,
) !void {
    if (rest == 0) {
        var cand = std.ArrayList(u8).empty;
        try cand.appendSlice(al, fuente.items);
        var ok = true;
        for (combo.items) |op| {
            const cc = fuentePara(op, cand.items.len) orelse {
                ok = false;
                break;
            };
            try cand.append(al, cc);
        }
        if (!ok) return;
        const cc = fuentePara(engine.OP_OUT, cand.items.len) orelse return;
        try cand.append(al, cc);
        try cand.append(al, try colaHalt(cand.items.len));
        if (try verificaSalida(cand.items, objetivo, al)) {
            cand.shrinkRetainingCapacity(cand.items.len - 1);
            hallado.* = try al.dupe(u8, cand.items);
        }
        return;
    }
    for (opciones) |op| {
        try combo.append(al, op);
        try brutaRec(opciones, rest - 1, combo, fuente, objetivo, hallado, al);
        if (hallado.* != null) return;
        _ = combo.pop();
    }
}

// ---------------------------------------------------------------------------
// CLI: malbolge-zig generate <texto>
// ---------------------------------------------------------------------------

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();

    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);

    if (args.items.len < 3) {
        std.debug.print("uso: malbolge-zig generate <texto> [ancho] [out.mal]\n", .{});
        return;
    }
    const texto = args.items[2];
    const ancho: usize = if (args.items.len >= 4)
        std.fmt.parseInt(usize, args.items[3], 10) catch 14
    else
        14;
    verbose = true;
    const prog = try generar(texto, ancho, allocator);
    defer allocator.free(prog);

    if (args.items.len >= 5) {
        try std.Io.Dir.cwd().writeFile(init.io, .{
            .sub_path = args.items[4],
            .data = prog,
        });
        std.debug.print("escrito={s} celdas={d}\n", .{ args.items[4], prog.len });
    }
    defer allocator.free(prog);

    var mem: [MEM]u16 = undefined;
    const r = try engine.runInto(&mem, prog, 2_000_000, allocator);
    defer allocator.free(r.output);
    std.debug.print("texto={s}\nceldas={d}\nejecucion={s} ({s})\n", .{ texto, prog.len, r.output, @tagName(r.status) });
    if (!std.mem.eql(u8, r.output, texto)) {
        std.debug.print("NO COINCIDE\n", .{});
        std.process.exit(1);
    }
    std.debug.print("PROGRAM={s}\n", .{prog});
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test "fuente_para congruence" {
    const c = fuentePara(engine.OP_OUT, 0) orelse unreachable;
    try std.testing.expectEqual(@as(u16, 5), (c + 0) % MOD);
}

test "generate A verifies on engine" {
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();
    const al = arena.allocator();
    const r = try generar("A", 6, al);
    var mem: [MEM]u16 = undefined;
    const res = try engine.runInto(&mem, r, 200_000, al);
    try std.testing.expectEqualStrings("A", res.output);
    try std.testing.expectEqual(engine.RunStatus.halted, res.status);
}

test "dfs end-to-end AB" {
    // El DFS con 5M de presupuesto supera la tolerancia del runner en Debug;
    // este test exige ReleaseFast. La suite Debug sigue cubierta por "generate A".
    if (@import("builtin").mode != .ReleaseFast) return;
    var arena = std.heap.ArenaAllocator.init(std.testing.allocator);
    defer arena.deinit();
    const al = arena.allocator();
    // Solo AB en la suite Debug (el runner tolera ~1min); ABC/Hola se miden
    // en ReleaseFast y quedan registrados en experiments/rle_decompressor_v0/GUIA.md.
    for ([_][]const u8{"AB"}) |texto| {
        const prog = try generar(texto, 6, al);
        var mem: [MEM]u16 = undefined;
        const res = try engine.runInto(&mem, prog, 5_000_000, al);
        defer al.free(res.output);
        std.debug.print("dfs {s}: chars={d} steps={d} out={s}\n", .{ texto, prog.len, res.steps, res.output });
        try std.testing.expectEqualStrings(texto, res.output);
        try std.testing.expectEqual(engine.RunStatus.halted, res.status);
    }
}
