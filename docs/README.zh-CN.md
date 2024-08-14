# Rust simple release

[English](../README.md) | 简体中文

**极其简单**的构建 rust 项目到 Github release 的 action！

此 CI 适用于不需要复杂 CI/CD 的中小型 rust 项目。它支持 rust workspace，但一次只允许从一个 package 构建和上传。（如果您想构建更多 package，请开 issue 进行 feature request）它还支持声明 features，bins 和 lib 的任意组合。

**您无需担心 openssl 造成的问题，此 action 已帮您解决。** 只需启用 `vendored` feature（将 `openssl = { version = "0", features = ["vendored"] }` 添加到您的 `Cargo.toml`）即可。

如果您使用 nightly 或其他 channels，请将其添加到 `rust-toolchain.toml` 中。

此操作将自动设置 rust 开发环境和其他工具，如 `cargo-zigbuild`。**它不使用容器**，所以如果您有其他依赖项，只需在运行此操作前安装和配置即可。

## 使用

请在使用此操作前设置 Github token。下面的示例使用 `GH_TOKEN` 作为 secret name，您可以使用任意 secret name。

### 简单

假设您的项目只有一个 package，没有任何 features。如果您的软件包有 bins，则构建 bins；如果您的软件包是 lib，则构建 lib。

```yaml
name: rust release action
on:
  push:
    tags:
      - "v*"
jobs:
  release:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - name: test build rust project
        uses: lxl66566/rust-simple-release@main
        with:
          targets: aarch64-unknown-linux-gnu, aarch64-unknown-linux-musl, x86_64-pc-windows-msvc, x86_64-unknown-linux-musl, x86_64-unknown-linux-gnu, aarch64-apple-darwin, x86_64-apple-darwin
          token: ${{ secrets.GH_TOKEN }}
```

### 所有配置

```yaml
name: test rust release action
on:
  push:
    tags:
      - "v*"
jobs:
  basic_test:
    runs-on: ${{ matrix.os }}
    strategy:
      matrix:
        os: [ubuntu-latest, windows-latest, macos-latest]
    steps:
      - uses: actions/checkout@v4
      - name: test build rust project
        uses: lxl66566/rust-simple-release@main
        with:
          # 要编译的目标，用逗号隔开（允许空格）
          # 支持 Linux, Windows, Darwin(macos)
          targets: aarch64-unknown-linux-gnu, aarch64-unknown-linux-musl, x86_64-pc-windows-msvc, x86_64-unknown-linux-musl, x86_64-unknown-linux-gnu, aarch64-apple-darwin, x86_64-apple-darwin

          # 选择要构建的 package。如果未设置，它将构建 workspace 中的第一个 package。
          package: openssl-test

          # 是否在包中构建 lib。如果包同时有 lib 和 bin 目标，则需要设置该选项来构建 lib，否则 lib 将被忽略，仅构建 bins。
          # 如果包有 lib 目标而没有 bin 目标，则默认构建 lib。
          # 如果包没有 lib 目标，将此选项设置为 true 会导致错误。
          lib: true

          # 选择要构建的 bins，以逗号分隔。如果未设置，它将构建包中的所有 bin。这个 `bins` 选项应该是 `Cargo.toml` 中声明的 bin 的子集。
          bins: my-action-test, my-action-test2

          # 要启用的 features，以逗号分隔（允许空格）
          features: test1, test2

          # 要打包到 release assets 中的文件或文件夹，相对路径，以逗号分隔。
          # 文件和文件夹将被添加到压缩包的根目录中。
          # build 的输出（bins 和 lib）将自动添加到压缩包中，无需手动再添加。
          files_to_pack: README.md, LICENSE, assets

          # release 创建选项, 查看 https://cli.github.com/manual/gh_release_create
          release_options: --draft --title 123

          # GITHUB TOKEN, **必填**
          token: ${{ secrets.GH_TOKEN }}

        env:
          # debug 等级，设置此项以打印更详细的日志
          debug: 1
```

## 提示

- 不要设置 `sccache`，因为在 macos 上使用 `cargo-zigbuild` 时可能会失败。
- 目前无法选择打包格式： 在 windows 上是 `zip`，在其他系统上是 `tar.gz`。(如果希望更改打包格式，请提 issue)

## License

MIT
