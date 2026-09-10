const std = @import("std");

pub fn build(b: *std.Build) void {
    const target = b.standardTargetOptions(.{});
    const optimize = b.standardOptimizeOption(.{});

    const exe = b.addExecutable(.{
        .name = "malbolge-zig",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/main.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(exe);

    const pca = b.addExecutable(.{
        .name = "malbolge-pca",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/pca.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(pca);

    const gen = b.addExecutable(.{
        .name = "malbolge-gen",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/generator.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(gen);

    const reducer = b.addExecutable(.{
        .name = "malbolge-reduce",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/reducer.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(reducer);

    const epoch = b.addExecutable(.{
        .name = "malbolge-epoch",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/epoch.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(epoch);

    const loop = b.addExecutable(.{
        .name = "malbolge-loop",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/loop.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(loop);

    const mutate = b.addExecutable(.{
        .name = "malbolge-mutate",
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/mutate.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    b.installArtifact(mutate);

    const run_cmd = b.addRunArtifact(exe);
    run_cmd.step.dependOn(b.getInstallStep());
    if (b.args) |args| run_cmd.addArgs(args);
    const run_step = b.step("run", "Run the engine");
    run_step.dependOn(&run_cmd.step);

    const unit_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/engine.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_unit_tests = b.addRunArtifact(unit_tests);
    const generator_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/generator.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_generator_tests = b.addRunArtifact(generator_tests);
    const reducer_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/reducer.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_reducer_tests = b.addRunArtifact(reducer_tests);
    const epoch_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/epoch.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_epoch_tests = b.addRunArtifact(epoch_tests);
    const loop_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/loop.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_loop_tests = b.addRunArtifact(loop_tests);
    const mutate_tests = b.addTest(.{
        .root_module = b.createModule(.{
            .root_source_file = b.path("src/mutate.zig"),
            .target = target,
            .optimize = optimize,
        }),
    });
    const run_mutate_tests = b.addRunArtifact(mutate_tests);
    const test_step = b.step("test", "Run unit tests");
    test_step.dependOn(&run_unit_tests.step);
    test_step.dependOn(&run_generator_tests.step);
    test_step.dependOn(&run_reducer_tests.step);
    test_step.dependOn(&run_epoch_tests.step);
    test_step.dependOn(&run_loop_tests.step);
    test_step.dependOn(&run_mutate_tests.step);
}
