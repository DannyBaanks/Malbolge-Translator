// pca.zig — PURE_CONTINUATION_ANCHOR harness (Zig 0.16)
//
// Audita un programa Classic Malbolge para detectar fases de output
// (A, B, C, ...) dentro de UNA ejecución sin intervención del host, y
// captura el estado de memoria (S0/S1/S2) como candidato a anchor.
//
// Atribuye cada escritura a su vía: _ENC / crazy_op / rotate / write-through-d.
//
// Uso: malbolge-pca <program.mal> [max_steps] [stdin_hex]

const std = @import("std");
const engine = @import("engine.zig");

const WriteKind = enum { enc, crazy, rotate, dload, none };

const WriteEvent = struct {
    addr: usize,
    kind: WriteKind,
    before: u16,
    after: u16,
};

const Phase = struct {
    byte: u8,
    step: u64,
    a: u16,
    c: u16,
    d: u16,
    /// hash de la memoria completa en esta frontera (SHA-256 de mem como bytes)
    mem_hash: [32]u8,
};

const Trace = struct {
    steps: u64,
    status: engine.RunStatus,
    output: []u8,
    a: u16,
    c: u16,
    d: u16,
    phases: std.array_list.Managed(Phase),
    writes: std.array_list.Managed(WriteEvent),
    total_enc_writes: u64 = 0,
    total_crazy_writes: u64 = 0,
    total_rotate_writes: u64 = 0,
    total_dload_writes: u64 = 0,
    memory_loads: u64 = 0,
    vm_initializations: u64 = 0,
    snapshots: u64 = 0,
    host_injections: u64 = 0,
};

/// Hash de la memoria: SHA-256 sobre la cinta serializada como u16 LE.
/// La cinta completa son 59049*2 = 118098 bytes.
fn memHash(mem: *const [engine.MEM_SIZE]u16, out: *[32]u8) void {
    var buf: [engine.MEM_SIZE * 2]u8 = undefined;
    for (mem, 0..) |v, i| {
        buf[i * 2] = @intCast(v & 0xFF);
        buf[i * 2 + 1] = @intCast((v >> 8) & 0xFF);
    }
    std.crypto.hash.sha2.Sha256.hash(&buf, out, .{});
}

/// Ejecuta un programa y registra fases de output + escrituras.
pub fn traceRun(
    mem: *[engine.MEM_SIZE]u16,
    source: []const u8,
    stdin: []const u8,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !Trace {
    const memory_loads: u64 = 1;
    // This path owns one VM state and never snapshots or reloads it.
    try engine.loadMemory(source, mem);

    var trace = Trace{
        .steps = 0,
        .status = .max_steps,
        .output = &.{},
        .a = 0,
        .c = 0,
        .d = 0,
        .phases = std.array_list.Managed(Phase).init(allocator),
        .writes = std.array_list.Managed(WriteEvent).init(allocator),
        .memory_loads = memory_loads,
        .vm_initializations = 1,
    };
    errdefer {
        trace.phases.deinit();
        trace.writes.deinit();
    }

    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var inp_pos: usize = 0;
    var out = std.array_list.Managed(u8).init(allocator);
    errdefer out.deinit();

    var steps: u64 = 0;
    var status: engine.RunStatus = .max_steps;

    while (steps < max_steps) {
        steps += 1;
        const cell = mem[c];
        const op = engine.decodeOpcode(cell, c);
        var jumped = false;
        var c_target: u16 = 0;

        switch (op) {
            engine.OP_CHASE => {
                c_target = mem[d];
                jumped = true;
            },
            engine.OP_OUT => {
                const byte: u8 = @intCast(a % 256);
                try out.append(byte);
                // Frontera de fase: cada byte emitido es un candidato S_k
                var h: [32]u8 = undefined;
                memHash(mem, &h);
                try trace.phases.append(.{
                    .byte = byte,
                    .step = steps,
                    .a = a,
                    .c = c,
                    .d = d,
                    .mem_hash = h,
                });
            },
            engine.OP_IN => {
                if (inp_pos < stdin.len) {
                    a = stdin[inp_pos];
                    inp_pos += 1;
                    trace.host_injections += 1;
                } else {
                    a = 0xFFFF;
                }
            },
            engine.OP_ROT => {
                const v = mem[d];
                const nv = (v / 3) + (v % 3) * 19683;
                try trace.writes.append(.{ .addr = d, .kind = .rotate, .before = v, .after = nv });
                mem[d] = nv;
                a = nv;
            },
            engine.OP_MOVD => {
                d = mem[d];
            },
            engine.OP_CRAZY => {
                const v = mem[d];
                const nv = engine.crazyOp(a, v);
                try trace.writes.append(.{ .addr = d, .kind = .crazy, .before = v, .after = nv });
                mem[d] = nv;
                a = nv;
            },
            engine.OP_NOP => {},
            engine.OP_HALT => {
                status = .halted;
                break;
            },
            else => {}, // inválida -> NOP
        }

        if (jumped) c = c_target;

        // Post-ejecución: cifrado de la celda del contador si es imprimible
        const enc_before = mem[c];
        if (enc_before >= engine.LO and enc_before <= engine.HI) {
            const enc_after = engine.ENCRYPT_TABLE[enc_before - engine.LO];
            if (enc_after != enc_before) {
                try trace.writes.append(.{ .addr = c, .kind = .enc, .before = enc_before, .after = enc_after });
                mem[c] = enc_after;
            }
        }

        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
    }

    trace.steps = steps;
    trace.status = status;
    trace.a = a;
    trace.c = c;
    trace.d = d;
    trace.output = try out.toOwnedSlice();

    // Contar escrituras por vía
    for (trace.writes.items) |w| {
        switch (w.kind) {
            .enc => trace.total_enc_writes += 1,
            .crazy => trace.total_crazy_writes += 1,
            .rotate => trace.total_rotate_writes += 1,
            .dload => trace.total_dload_writes += 1,
            .none => {},
        }
    }

    return trace;
}

pub fn deinitTrace(trace: *Trace) void {
    trace.phases.deinit();
    trace.writes.deinit();
    // output lo libera el llamador
}

fn hexByte(b: u8) void {
    const hx = "0123456789abcdef";
    std.debug.print("{c}{c}", .{ hx[b >> 4], hx[b & 0xF] });
}

fn printHash(h: [32]u8) void {
    for (h) |b| hexByte(b);
}

const RunState = struct {
    a: u16,
    c: u16,
    d: u16,
    steps: u64,
    halted: bool,
};

/// Ejecuta desde el principio hasta `target_steps` (o HALT) y devuelve el
/// estado exacto de la maquina en ese punto: registros + memoria mutada en
/// `mem` (carga el fuente y aplica toda la ejecucion anterior).
fn runUntilSteps(
    mem: *[engine.MEM_SIZE]u16,
    source: []const u8,
    target_steps: u64,
    stdin: []const u8,
    allocator: std.mem.Allocator,
) !RunState {
    _ = allocator;
    try engine.loadMemory(source, mem);
    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var inp_pos: usize = 0;
    var steps: u64 = 0;
    var halted = false;
    while (steps < target_steps) {
        steps += 1;
        const cell = mem[c];
        const op = engine.decodeOpcode(cell, c);
        var jumped = false;
        var c_target: u16 = 0;
        switch (op) {
            engine.OP_CHASE => {
                c_target = mem[d];
                jumped = true;
            },
            engine.OP_OUT => {},
            engine.OP_IN => {
                if (inp_pos < stdin.len) {
                    a = stdin[inp_pos];
                    inp_pos += 1;
                } else {
                    a = 0xFFFF;
                }
            },
            engine.OP_ROT => {
                const v = mem[d];
                mem[d] = (v / 3) + (v % 3) * 19683;
                a = mem[d];
            },
            engine.OP_MOVD => d = mem[d],
            engine.OP_CRAZY => {
                mem[d] = engine.crazyOp(a, mem[d]);
                a = mem[d];
            },
            engine.OP_NOP => {},
            engine.OP_HALT => {
                halted = true;
                break;
            },
            else => {},
        }
        if (jumped) c = c_target;
        const enc_before = mem[c];
        if (enc_before >= engine.LO and enc_before <= engine.HI) {
            mem[c] = engine.ENCRYPT_TABLE[enc_before - engine.LO];
        }
        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
    }
    return .{ .a = a, .c = c, .d = d, .steps = steps, .halted = halted };
}

const ResumeResult = struct {
    output: []u8,
    steps: u64,
    a: u16,
    c: u16,
    d: u16,
    halted: bool,
};

/// Reanuda desde un estado dado (memoria ya mutada + registros). No recarga.
fn resumeFrom(
    mem: *[engine.MEM_SIZE]u16,
    start_a: u16,
    start_c: u16,
    start_d: u16,
    stdin: []const u8,
    max_steps: u64,
    allocator: std.mem.Allocator,
) !ResumeResult {
    var a = start_a;
    var c = start_c;
    var d = start_d;
    var inp_pos: usize = 0;
    var out = std.array_list.Managed(u8).init(allocator);
    errdefer out.deinit();
    var steps: u64 = 0;
    var halted = false;
    while (steps < max_steps) {
        steps += 1;
        const cell = mem[c];
        const op = engine.decodeOpcode(cell, c);
        var jumped = false;
        var c_target: u16 = 0;
        switch (op) {
            engine.OP_CHASE => {
                c_target = mem[d];
                jumped = true;
            },
            engine.OP_OUT => try out.append(@intCast(a % 256)),
            engine.OP_IN => {
                if (inp_pos < stdin.len) {
                    a = stdin[inp_pos];
                    inp_pos += 1;
                } else {
                    a = 0xFFFF;
                }
            },
            engine.OP_ROT => {
                const v = mem[d];
                mem[d] = (v / 3) + (v % 3) * 19683;
                a = mem[d];
            },
            engine.OP_MOVD => d = mem[d],
            engine.OP_CRAZY => {
                mem[d] = engine.crazyOp(a, mem[d]);
                a = mem[d];
            },
            engine.OP_NOP => {},
            engine.OP_HALT => {
                halted = true;
                break;
            },
            else => {},
        }
        if (jumped) c = c_target;
        const enc_before = mem[c];
        if (enc_before >= engine.LO and enc_before <= engine.HI) {
            mem[c] = engine.ENCRYPT_TABLE[enc_before - engine.LO];
        }
        c = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        d = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
    }
    return .{ .output = try out.toOwnedSlice(), .steps = steps, .a = a, .c = c, .d = d, .halted = halted };
}

fn opName(op: u16) []const u8 {
    return switch (op) {
        engine.OP_CHASE => "chase",
        engine.OP_OUT => "out",
        engine.OP_IN => "in",
        engine.OP_ROT => "rot",
        engine.OP_MOVD => "movd",
        engine.OP_CRAZY => "crazy",
        engine.OP_NOP => "nop",
        engine.OP_HALT => "halt",
        else => "invalid",
    };
}

fn printJsonOpt(value: ?u16) void {
    if (value) |v| {
        std.debug.print("{d}", .{v});
    } else {
        std.debug.print("null", .{});
    }
}

fn printJsonStep(
    step: u64,
    a_before: u16,
    c_before: u16,
    d_before: u16,
    op: u16,
    read_addr: ?u16,
    read_value: ?u16,
    write_addr: ?u16,
    write_before: ?u16,
    write_after: ?u16,
    enc_addr: ?u16,
    enc_before: ?u16,
    enc_after: ?u16,
    jump_target: ?u16,
    a_after: u16,
    c_after: u16,
    d_after: u16,
) void {
    std.debug.print("{{\"schema\":\"malbolge-step-v1\",\"step\":{d},\"a_before\":{d},\"c_before\":{d},\"d_before\":{d},\"opcode\":\"{s}\",\"read_addr\":", .{
        step, a_before, c_before, d_before, opName(op),
    });
    printJsonOpt(read_addr);
    std.debug.print(",\"read_value\":", .{});
    printJsonOpt(read_value);
    std.debug.print(",\"write_addr\":", .{});
    printJsonOpt(write_addr);
    std.debug.print(",\"write_before\":", .{});
    printJsonOpt(write_before);
    std.debug.print(",\"write_after\":", .{});
    printJsonOpt(write_after);
    std.debug.print(",\"enc_addr\":", .{});
    printJsonOpt(enc_addr);
    std.debug.print(",\"enc_before\":", .{});
    printJsonOpt(enc_before);
    std.debug.print(",\"enc_after\":", .{});
    printJsonOpt(enc_after);
    std.debug.print(",\"jump_target\":", .{});
    printJsonOpt(jump_target);
    std.debug.print(",\"a_after\":{d},\"c_after\":{d},\"d_after\":{d}}}\n", .{ a_after, c_after, d_after });
}

/// Dump posicional: por paso, registros antes/despues, direccion de
/// instruccion (c_before), operando (d_before), saltos (chase) y escrituras.
/// Confirma si una direccion es leida, escrita, saltada por un chase, o muerta.
fn traceSteps(
    mem: *[engine.MEM_SIZE]u16,
    source: []const u8,
    stdin: []const u8,
    max_steps: u64,
    allocator: std.mem.Allocator,
    jsonl: bool,
) !void {
    _ = allocator;
    try engine.loadMemory(source, mem);
    var a: u16 = 0;
    var c: u16 = 0;
    var d: u16 = 0;
    var inp_pos: usize = 0;
    var steps: u64 = 0;
    while (steps < max_steps) {
        steps += 1;
        const a_before = a;
        const c_before = c;
        const d_before = d;
        const cell = mem[c_before];
        const op = engine.decodeOpcode(cell, c_before);
        var jumped = false;
        var c_target: u16 = 0;
        var read_addr: ?u16 = null;
        var read_value: u16 = 0;
        var write_addr: ?u16 = null;
        var write_before: u16 = 0;
        var write_after: u16 = 0;
        switch (op) {
            engine.OP_CHASE => {
                read_addr = d_before;
                read_value = mem[d_before];
                c_target = read_value;
                jumped = true;
            },
            engine.OP_OUT => {},
            engine.OP_IN => {
                if (inp_pos < stdin.len) {
                    a = stdin[inp_pos];
                    inp_pos += 1;
                } else {
                    a = 0xFFFF;
                }
            },
            engine.OP_ROT => {
                read_addr = d_before;
                read_value = mem[d_before];
                write_addr = d_before;
                write_before = read_value;
                write_after = (read_value / 3) + (read_value % 3) * 19683;
                mem[d_before] = write_after;
                a = write_after;
            },
            engine.OP_MOVD => {
                read_addr = d_before;
                read_value = mem[d_before];
                d = read_value;
            },
            engine.OP_CRAZY => {
                read_addr = d_before;
                read_value = mem[d_before];
                write_addr = d_before;
                write_before = read_value;
                write_after = engine.crazyOp(a, read_value);
                mem[d_before] = write_after;
                a = write_after;
            },
            engine.OP_NOP => {},
            engine.OP_HALT => {
                if (jsonl) {
                    printJsonStep(steps, a_before, c_before, d_before, op, null, null, null, null, null, null, null, null, null, a, c, d);
                } else {
                    std.debug.print("step={d} op=halt c_before={d} d_before={d}\n", .{ steps, c_before, d_before });
                }
                return;
            },
            else => {},
        }
        if (jumped) c = c_target;
        const enc_addr_value = c;
        const enc_before = mem[enc_addr_value];
        var enc_addr: ?u16 = null;
        var enc_after: u16 = enc_before;
        if (enc_before >= engine.LO and enc_before <= engine.HI) {
            enc_after = engine.ENCRYPT_TABLE[enc_before - engine.LO];
            enc_addr = enc_addr_value;
            mem[enc_addr_value] = enc_after;
        }
        const c_after: u16 = @intCast((@as(usize, c) + 1) % engine.MEM_SIZE);
        const d_after: u16 = @intCast((@as(usize, d) + 1) % engine.MEM_SIZE);
        c = c_after;
        d = d_after;
        if (jsonl) {
            printJsonStep(
                steps, a_before, c_before, d_before, op,
                read_addr, if (read_addr != null) read_value else null,
                write_addr, if (write_addr != null) write_before else null,
                if (write_addr != null) write_after else null,
                enc_addr, if (enc_addr != null) enc_before else null,
                if (enc_addr != null) enc_after else null,
                if (jumped) c_target else null,
                a, c, d,
            );
            continue;
        }
        std.debug.print("step={d} op={s} c_before={d} d_before={d}", .{ steps, opName(op), c_before, d_before });
        if (read_addr) |ra| {
            std.debug.print(" read@{d}={d}", .{ ra, read_value });
        }
        if (write_addr) |wa| {
            std.debug.print(" write@{d}={d}->{d}", .{ wa, write_before, write_after });
        }
        if (enc_addr) |ea| {
            std.debug.print(" enc@{d}={d}->{d}", .{ ea, enc_before, enc_after });
        }
        if (jumped) std.debug.print(" J->{d}", .{c_target});
        std.debug.print(" c_after={d} d_after={d}\n", .{ c_after, d_after });
    }
}

pub fn main(init: std.process.Init) !void {
    const allocator = init.arena.allocator();

    var args_it = try std.process.Args.Iterator.initAllocator(init.minimal.args, allocator);
    defer args_it.deinit();
    var args = std.array_list.Managed([]const u8).init(allocator);
    while (args_it.next()) |arg| try args.append(arg);

    if (args.items.len < 2) {
        std.debug.print("uso:\n", .{});
        std.debug.print("  malbolge-pca <program.mal> [max_steps] [stdin]\n", .{});
        std.debug.print("  malbolge-pca perturb <program.mal> <phase_idx> <addr> <newval> [max_steps] [stdin]\n", .{});
        std.debug.print("  malbolge-pca trace <program.mal> [max_steps] [stdin]\n", .{});
        std.debug.print("  malbolge-pca trace-jsonl <program.mal> [max_steps] [stdin]\n", .{});
        return;
    }

    // Subcomandos de traza: formato humano o JSONL canónico.
    const is_trace = std.mem.eql(u8, args.items[1], "trace");
    const is_trace_jsonl = std.mem.eql(u8, args.items[1], "trace-jsonl");
    if (is_trace or is_trace_jsonl) {
        if (args.items.len < 3) {
            std.debug.print("uso: malbolge-pca trace[-jsonl] <program.mal> [max_steps] [stdin]\n", .{});
            return;
        }
        const src_path = args.items[2];
        const max_steps: u64 = if (args.items.len >= 4)
            std.fmt.parseInt(u64, args.items[3], 10) catch 2_000_000
        else
            2_000_000;
        const stdin_input: []const u8 = if (args.items.len >= 5) args.items[4] else "";
        const source = try std.Io.Dir.cwd().readFileAlloc(init.io, src_path, allocator, .unlimited);
        var mem: [engine.MEM_SIZE]u16 = undefined;
        try traceSteps(&mem, source, stdin_input, max_steps, allocator, is_trace_jsonl);
        return;
    }

    // Subcomando perturb: control causal de S_k. Reanuda desde el estado tras
    // emitir la fase `phase_idx`, sin perturbacion (control) y con la celda
    // `addr` forzada a `newval` (perturbacion); compara la cola de output.
    if (std.mem.eql(u8, args.items[1], "perturb")) {
        if (args.items.len < 6) {
            std.debug.print("uso: malbolge-pca perturb <program.mal> <phase_idx> <addr> <newval> [max_steps] [stdin]\n", .{});
            return;
        }
        const src_path = args.items[2];
        const phase_idx: usize = std.fmt.parseInt(usize, args.items[3], 10) catch {
            std.debug.print("phase_idx invalido\n", .{});
            return;
        };
        const perturb_addr: usize = std.fmt.parseInt(usize, args.items[4], 10) catch {
            std.debug.print("addr invalido\n", .{});
            return;
        };
        const perturb_val: u16 = std.fmt.parseInt(u16, args.items[5], 10) catch {
            std.debug.print("newval invalido\n", .{});
            return;
        };
        const max_steps: u64 = if (args.items.len >= 7)
            std.fmt.parseInt(u64, args.items[6], 10) catch 2_000_000
        else
            2_000_000;
        const stdin_input: []const u8 = if (args.items.len >= 8) args.items[7] else "";

        const source = try std.Io.Dir.cwd().readFileAlloc(init.io, src_path, allocator, .unlimited);

        // 1) Traza completa para conocer las fases.
        var mem0: [engine.MEM_SIZE]u16 = undefined;
        var trace = try traceRun(&mem0, source, stdin_input, max_steps, allocator);
        defer allocator.free(trace.output);
        defer deinitTrace(&trace);
        if (phase_idx >= trace.phases.items.len) {
            std.debug.print("phase_idx {d} fuera de rango (hay {d})\n", .{ phase_idx, trace.phases.items.len });
            return;
        }
        const target = trace.phases.items[phase_idx].step;

        // 2) Estado exacto S tras emitir la fase: registros + memoria mutada.
        var memS: [engine.MEM_SIZE]u16 = undefined;
        const st = try runUntilSteps(&memS, source, target, stdin_input, allocator);
        var hS: [32]u8 = undefined;
        memHash(&memS, &hS);
        std.debug.print("S_{d} step={d} a={d} c={d} d={d} hash=", .{ phase_idx, st.steps, st.a, st.c, st.d });
        printHash(hS);
        std.debug.print("\n", .{});

        // 3) Control: reanudar sin tocar nada.
        var memC = memS;
        const ctl = try resumeFrom(&memC, st.a, st.c, st.d, stdin_input, max_steps, allocator);
        defer allocator.free(ctl.output);
        std.debug.print("CONTROL  resume: status={s} steps={d} output={s}\n", .{ if (ctl.halted) "halted" else "max_steps", ctl.steps, ctl.output });

        // 4) Perturbacion: forzar la celda antes de reanudar.
        const before = memS[perturb_addr];
        memS[perturb_addr] = perturb_val;
        const per = try resumeFrom(&memS, st.a, st.c, st.d, stdin_input, max_steps, allocator);
        defer allocator.free(per.output);
        std.debug.print("PERTURB  addr={d} {d}->{d} resume: status={s} steps={d} output={s}\n", .{ perturb_addr, before, perturb_val, if (per.halted) "halted" else "max_steps", per.steps, per.output });

        const same = std.mem.eql(u8, ctl.output, per.output);
        std.debug.print("PERTURBATION_DIVERGENCE={s}\n", .{if (same) "FAIL" else "PASS"});
        return;
    }

    const src_path = args.items[1];
    const max_steps: u64 = if (args.items.len >= 3)
        std.fmt.parseInt(u64, args.items[2], 10) catch 2_000_000
    else
        2_000_000;
    const stdin_input: []const u8 = if (args.items.len >= 4) args.items[3] else "";

    const source = try std.Io.Dir.cwd().readFileAlloc(init.io, src_path, allocator, .unlimited);
    std.debug.print("source_len={d}\n", .{source.len});

    var mem: [engine.MEM_SIZE]u16 = undefined;
    var trace = try traceRun(&mem, source, stdin_input, max_steps, allocator);
    defer allocator.free(trace.output);
    defer deinitTrace(&trace);

    std.debug.print("status={s} steps={d}\n", .{ @tagName(trace.status), trace.steps });
    std.debug.print("output_len={d} output={s}\n", .{ trace.output.len, trace.output });
    std.debug.print("final a={d} c={d} d={d}\n", .{ trace.a, trace.c, trace.d });
    std.debug.print("writes: enc={d} crazy={d} rotate={d} dload={d}\n", .{
        trace.total_enc_writes,
        trace.total_crazy_writes,
        trace.total_rotate_writes,
        trace.total_dload_writes,
    });
    std.debug.print("audit: memory_loads={d} vm_initializations={d} snapshots={d} host_injections={d}\n", .{
        trace.memory_loads,
        trace.vm_initializations,
        trace.snapshots,
        trace.host_injections,
    });

    std.debug.print("phases={d}\n", .{trace.phases.items.len});
    for (trace.phases.items, 0..) |ph, i| {
        std.debug.print("  phase[{d}] byte=0x{x} step={d} a={d} c={d} d={d} hash=", .{ i, ph.byte, ph.step, ph.a, ph.c, ph.d });
        printHash(ph.mem_hash);
        std.debug.print("\n", .{});
    }

    // Muestreo de escrituras (primeras 50)
    const n_show = @min(@as(usize, 50), trace.writes.items.len);
    std.debug.print("writes_sample={d}\n", .{n_show});
    for (trace.writes.items[0..n_show], 0..) |w, i| {
        std.debug.print("  w[{d}] addr={d} kind={s} {d}->{d}\n", .{ i, w.addr, @tagName(w.kind), w.before, w.after });
    }
}
