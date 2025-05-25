fn main() {
    tonic_build::configure()
    .build_server(true)
    .out_dir("src/kos_proto") // 生成的代码放到 src/kos_proto 下
    .compile(&["proto/sound.proto"], &["proto"])
    .unwrap();
    }