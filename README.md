# Rust simple release

Extremely simple all-in-one release for small rust project.

**You don't need to worry about openssl deps, this action will solve it.** Just add `openssl = { version = "0", features = ["vendored"] }` to your `Cargo.toml`.

This CI is for small rust project, which doesn't need complex CI/CD. It supports rust workspace, but only allows one package with one binary to build and upload.

If you are using nightly or other toolchains, please add it to `rust-toolchain.toml`.

This action will automatically setup rust dev environment, and other tools like cargo-zigbuild and sccache. We don't use containers, so if you have other dependencies, just install them before running this action.

## Usage

Please set your Github token before using this action. The example below uses `GH_TOKEN` as the secret name, you can change it to your own secret name.

### Simple

assume that your project only has one package with one binary, with no features.

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
          targets: "aarch64-unknown-linux-gnu, aarch64-unknown-linux-musl, x86_64-pc-windows-msvc, x86_64-unknown-linux-musl, x86_64-unknown-linux-gnu, aarch64-apple-darwin, x86_64-apple-darwin"
          token: ${{ secrets.GH_TOKEN }}
```

### Full

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
          # targets to compile, seperated by comma
          targets: aarch64-unknown-linux-gnu, aarch64-unknown-linux-musl, x86_64-pc-windows-msvc, x86_64-unknown-linux-musl, x86_64-unknown-linux-gnu, aarch64-apple-darwin, x86_64-apple-darwin

          # choose one package to build
          package: openssl-test

          # choose one binary to build
          bin: my-action-test

          # features to build, seperated by comma
          features: test1, test2

          # files or folders to pack into release assets, relative path seperated by comma
          files_to_pack: README.md, LICENSE, assets

          # release create options, see https://cli.github.com/manual/gh_release_create
          release_options: --draft --latest --title 123

          # GITHUB TOKEN, REQUIRED
          token: ${{ secrets.GH_TOKEN }}
        env:
          # debug level, print more log
          debug: 1
```
