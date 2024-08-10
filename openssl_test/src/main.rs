fn main() {
    let body = reqwest::blocking::get("https://www.rust-lang.org")
        .unwrap()
        .text()
        .unwrap();
    println!("body = {body:?}");
}
