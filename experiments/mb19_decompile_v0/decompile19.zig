// decompile19.zig — static-plane decoder for 3^19 images (Win32 direct, as bolge19).
const std = @import("std");
const END: u64 = 1162261467;
const THIRD: u64 = 387420489;

const win = struct {
    pub const INVALID_HANDLE: ?*anyopaque = @ptrFromInt(@as(usize, @bitCast(@as(isize, -1))));
    pub const GENERIC_READ: u32 = 0x8000_0000;
    pub const FILE_SHARE_READ: u32 = 1;
    pub const OPEN_EXISTING: u32 = 3;
    pub extern "kernel32" fn GetCommandLineW() callconv(.c) [*:0]u16;
    pub extern "shell32" fn CommandLineToArgvW(cmd: [*:0]const u16, n: ?*i32) callconv(.c) ?[*][*:0]u16;
    pub extern "kernel32" fn CreateFileW(name: [*:0]const u16, access: u32, share: u32, sec: ?*anyopaque, disp: u32, flags: u32, tmpl: ?*anyopaque) callconv(.c) ?*anyopaque;
    pub extern "kernel32" fn ReadFile(h: ?*anyopaque, buf: [*]u8, n: u32, got: ?*u32, ov: ?*anyopaque) callconv(.c) i32;
    pub extern "kernel32" fn CloseHandle(h: ?*anyopaque) callconv(.c) i32;
    pub extern "kernel32" fn GetFileSizeEx(h: ?*anyopaque, size: *i64) callconv(.c) i32;
};

pub fn main() void {
    var argc: i32 = 0;
    const argv = win.CommandLineToArgvW(win.GetCommandLineW(), &argc) orelse return;
    if (argc < 2) { std.debug.print("uso: decompile19 <imagen.mb>\n", .{}); return; }
    const hf = win.CreateFileW(argv[1], win.GENERIC_READ, win.FILE_SHARE_READ, null, win.OPEN_EXISTING, 0, null);
    if (hf == null or hf == win.INVALID_HANDLE) { std.debug.print("no pude abrir\n", .{}); return; }
    defer _ = win.CloseHandle(hf);
    var fsize: i64 = 0;
    _ = win.GetFileSizeEx(hf, &fsize);
    const size: usize = @intCast(fsize);
    const alloc = std.heap.page_allocator;
    const data = alloc.alloc(u8, size) catch return;
    defer alloc.free(data);
    var done: usize = 0;
    while (done < size) {
        var got: u32 = 0;
        const chunk: u32 = @intCast(@min(size - done, 1 << 30));
        if (win.ReadFile(hf, data.ptr + done, chunk, &got, null) == 0 or got == 0) break;
        done += got;
    }
    const a1: u64 = 94 - ((END - 1) / 6 - 29524) % 94;
    const a2: u64 = 94 - ((END - 1) / 3 - 59048) % 94;
    const off0: u64 = 0;
    const off1: u64 = (a1 - THIRD % 94 + 94) % 94 + 94;
    const off2: u64 = a2 - (2 * THIRD) % 94 + 94;
    var hist = [_]u32{0} ** 94;
    var valid_total: u64 = 0;
    var run_len: u64 = 0;
    var run_start: u64 = 0;
    var best_start: u64 = 0;
    var best_len: u64 = 0;
    var runs_over_1000: u64 = 0;
    var second_start: u64 = 0;
    var second_len: u64 = 0;
    for (data, 0..) |b, i| {
        const c: u64 = i;
        const o: u64 = if (c < THIRD) off0 else if (c < 2 * THIRD) off1 else off2;
        const idx: usize = @intCast((c + b + o) % 94);
        hist[idx] += 1;
        const valid = idx == 4 or idx == 5 or idx == 23 or idx == 39 or idx == 40 or idx == 62 or idx == 68 or idx == 81;
        if (valid) valid_total += 1;
        if (valid) {
            if (run_len == 0) run_start = c;
            run_len += 1;
            if (run_len > best_len) { best_len = run_len; best_start = run_start; }
        } else {
            if (run_len > 1000) runs_over_1000 += 1;
            if (run_len > second_len) { second_len = run_len; second_start = run_start; }
            run_len = 0;
        }
    }
    if (run_len > 1000) runs_over_1000 += 1;
    std.debug.print("imagen={d} offs=({d},{d},{d})\n", .{ size, off0, off1, off2 });
    std.debug.print("validas={d} invalidas={d}\n", .{ valid_total, size - valid_total });
    std.debug.print("hist jmp={d} out={d} in={d} rot={d} movd={d} opr={d} nop={d} end={d}\n", .{ hist[4], hist[5], hist[23], hist[39], hist[40], hist[62], hist[68], hist[81] });
    std.debug.print("longest_valid_run start={d} len={d}\nsecond_run start={d} len={d}\nruns_gt1000={d}\n", .{ best_start, best_len, second_start, second_len, runs_over_1000 });
}
