#[cfg(windows)]
fn main() {
    use std::env;
    use std::path::PathBuf;

    let manifest_directory = PathBuf::from(
        env::var("CARGO_MANIFEST_DIR").expect("Cargo should provide CARGO_MANIFEST_DIR"),
    );
    let icon_path = manifest_directory.join("assets").join("n2-vocabulary.ico");

    println!("cargo:rerun-if-changed=build.rs");
    println!("cargo:rerun-if-changed={}", icon_path.display());

    let mut resource = winresource::WindowsResource::new();
    resource.set_icon(
        icon_path
            .to_str()
            .expect("the Windows icon path should be valid UTF-8"),
    );
    resource
        .compile()
        .expect("compile the N2 Vocabulary Windows icon resource");
}

#[cfg(not(windows))]
fn main() {}
